"""
URL crawler document processor.
"""

import logging
from urllib.parse import quote, unquote, urlparse, urlunparse

import validators
from firecrawl import AsyncFirecrawlApp
from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_core.documents import Document as LangchainDocument
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
    md,
)

logger = logging.getLogger(__name__)


async def _try_article_tag(page: Page) -> tuple[str | None, str | None]:
    """
    Strategy 1: Extract content from semantic <article> tag.

    Args:
        page: Playwright page object

    Returns:
        Tuple of (headline, body_text) or (None, None) if not found
    """
    try:
        article = await page.query_selector("article")
        if not article:
            logger.debug("No <article> tag found")
            return None, None

        # Try to find headline within article
        headline_elem = await article.query_selector("h1")
        if not headline_elem:
            # Try page-level h1 if not in article
            headline_elem = await page.query_selector("h1")

        headline = await headline_elem.inner_text() if headline_elem else None

        # Extract all paragraphs within article
        paragraphs = await article.query_selector_all("p")
        if not paragraphs:
            logger.debug("No paragraphs found in <article> tag")
            return None, None

        body_parts = []
        for p in paragraphs:
            text = await p.inner_text()
            if text and text.strip():
                body_parts.append(text.strip())

        body = "\n\n".join(body_parts) if body_parts else None

        if body and len(body) > 100:  # Minimum content threshold
            logger.info(f"✅ Article tag extraction: {len(paragraphs)} paragraphs, {len(body)} chars")
            return headline, body

        return None, None
    except Exception as e:
        logger.debug(f"Article tag extraction failed: {e}")
        return None, None


async def _try_main_tag(page: Page) -> tuple[str | None, str | None]:
    """
    Strategy 2: Extract content from semantic <main> tag.

    Args:
        page: Playwright page object

    Returns:
        Tuple of (headline, body_text) or (None, None) if not found
    """
    try:
        main = await page.query_selector("main")
        if not main:
            logger.debug("No <main> tag found")
            return None, None

        # Try to find headline
        headline_elem = await main.query_selector("h1")
        if not headline_elem:
            headline_elem = await page.query_selector("h1")

        headline = await headline_elem.inner_text() if headline_elem else None

        # Extract all paragraphs within main
        paragraphs = await main.query_selector_all("p")
        if not paragraphs:
            logger.debug("No paragraphs found in <main> tag")
            return None, None

        body_parts = []
        for p in paragraphs:
            text = await p.inner_text()
            if text and text.strip():
                body_parts.append(text.strip())

        body = "\n\n".join(body_parts) if body_parts else None

        if body and len(body) > 100:  # Minimum content threshold
            logger.info(f"✅ Main tag extraction: {len(paragraphs)} paragraphs, {len(body)} chars")
            return headline, body

        return None, None
    except Exception as e:
        logger.debug(f"Main tag extraction failed: {e}")
        return None, None


async def _try_largest_block_heuristic(page: Page, min_paragraphs: int = 5) -> tuple[str | None, str | None]:
    """
    Strategy 3: Find the div with the most paragraph tags (heuristic for main content).

    This content-agnostic approach works across different site layouts and is resilient
    to HTML structure changes. It identifies the main article by finding the container
    with the highest paragraph density.

    Args:
        page: Playwright page object
        min_paragraphs: Minimum number of paragraphs required to consider a block valid

    Returns:
        Tuple of (headline, body_text) or (None, None) if not found
    """
    try:
        # Get all divs on the page
        divs = await page.query_selector_all("div")
        if not divs:
            logger.debug("No divs found on page")
            return None, None

        max_paragraphs = 0
        best_div = None

        # Find the div with the most paragraphs
        for div in divs:
            paragraphs = await div.query_selector_all("p")
            paragraph_count = len(paragraphs)

            if paragraph_count > max_paragraphs:
                max_paragraphs = paragraph_count
                best_div = div

        # Check if we found a valid content block
        if not best_div or max_paragraphs < min_paragraphs:
            logger.debug(f"No suitable content block found (max paragraphs: {max_paragraphs}, required: {min_paragraphs})")
            return None, None

        # Extract headline (try to find h1 anywhere on the page)
        headline_elem = await page.query_selector("h1")
        headline = await headline_elem.inner_text() if headline_elem else None

        # Extract body text from the best div
        paragraphs = await best_div.query_selector_all("p")
        body_parts = []
        for p in paragraphs:
            text = await p.inner_text()
            if text and text.strip():
                body_parts.append(text.strip())

        body = "\n\n".join(body_parts) if body_parts else None

        if body:
            logger.info(f"✅ Largest block heuristic: {max_paragraphs} paragraphs, {len(body)} chars")
            return headline, body

        return None, None
    except Exception as e:
        logger.debug(f"Largest block heuristic failed: {e}")
        return None, None


async def _extract_article_with_playwright(url: str) -> tuple[str | None, str | None, dict]:
    """
    Extract article content using Playwright with multi-strategy fallback chain.

    This function implements a robust extraction approach that tries multiple strategies
    in order, falling back to a content-agnostic heuristic that works across different
    site layouts. This is particularly effective for JavaScript-heavy sites like Al Jazeera.

    Strategies tried in order:
    1. Semantic <article> tag (for sites using proper HTML5 structure)
    2. Semantic <main> tag (fallback for sites without article tags)
    3. Largest text block heuristic (content-agnostic, works on any layout)

    Args:
        url: URL to extract content from

    Returns:
        Tuple of (headline, body_text, metadata_dict)
    """
    async with async_playwright() as p:
        try:
            logger.info(f"Starting Playwright extraction for: {url}")

            # Launch browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate with proper wait for JavaScript-heavy sites
            logger.debug(f"Navigating to: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Additional wait for JavaScript execution and content rendering
            await page.wait_for_timeout(500)

            # Wait for content to be visible
            try:
                await page.wait_for_selector("div p", timeout=5000, state="visible")
            except PlaywrightTimeoutError:
                logger.warning("Timeout waiting for content paragraphs, proceeding anyway")

            logger.debug(f"Page loaded: {await page.title()}")
            logger.debug(f"Final URL after redirects: {page.url}")

            # Try extraction strategies in order
            headline, body = None, None

            # Strategy 1: <article> tag
            logger.debug("Trying Strategy 1: <article> tag")
            headline, body = await _try_article_tag(page)
            if headline or body:
                logger.info("SUCCESS: article tag strategy")
                strategy = "article_tag"
            else:
                # Strategy 2: <main> tag
                logger.debug("Trying Strategy 2: <main> tag")
                headline, body = await _try_main_tag(page)
                if headline or body:
                    logger.info("SUCCESS: main tag strategy")
                    strategy = "main_tag"
                else:
                    # Strategy 3: Largest block heuristic (ALWAYS TRIED)
                    logger.debug("Trying Strategy 3: largest block heuristic")
                    headline, body = await _try_largest_block_heuristic(page)
                    if headline or body:
                        logger.info("SUCCESS: largest block heuristic")
                        strategy = "largest_block_heuristic"
                    else:
                        logger.error("FAILED: All extraction strategies failed")
                        strategy = "none"

            # Extract metadata
            title = await page.title()
            final_url = page.url

            metadata = {
                "title": headline or title,
                "source": final_url,
                "extraction_strategy": strategy,
            }

            # Try to extract author if available
            try:
                author_elem = await page.query_selector('[rel="author"], .author, .byline, [class*="author"]')
                if author_elem:
                    author_text = await author_elem.inner_text()
                    if author_text:
                        metadata["author"] = author_text.strip()
            except Exception:
                pass  # Author extraction is optional

            await browser.close()

            if headline or body:
                logger.info(f"✅ Extraction successful using {strategy}")
                logger.info(f"   Headline: {headline[:100] if headline else 'None'}...")
                logger.info(f"   Body length: {len(body) if body else 0} characters")
                return headline, body, metadata
            else:
                logger.error(f"❌ All extraction strategies failed for {url}")
                return None, None, metadata

        except PlaywrightTimeoutError as e:
            logger.error(f"Playwright timeout for {url}: {e}")
            return None, None, {"error": f"Timeout: {e!s}"}
        except Exception as e:
            logger.error(f"Playwright extraction error for {url}: {e}", exc_info=True)
            return None, None, {"error": f"Extraction error: {e!s}"}


async def add_crawled_url_document(
    session: AsyncSession, url: str, search_space_id: int, user_id: str
) -> Document | None:
    """
    Process and store a document from a crawled URL.

    Args:
        session: Database session
        url: URL to crawl
        search_space_id: ID of the search space
        user_id: ID of the user

    Returns:
        Document object if successful, None if failed
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="crawl_url_document",
        source="background_task",
        message=f"Starting URL crawling process for: {url}",
        metadata={"url": url, "user_id": str(user_id)},
    )

    try:
        # Normalize URL - handle percent-encoded UTF-8 characters (e.g., Latvian, other special chars)
        # Decode percent-encoded characters and re-encode properly
        try:
            # First decode any percent-encoding
            decoded_url = unquote(url)
            # Re-encode only the path/query parts to ensure consistency
            # This handles URLs like https://lv.wikipedia.org/wiki/Vaira_Vīķe-Freiberga properly
            parsed = urlparse(decoded_url)
            # Re-encode the path component to handle special characters
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                quote(parsed.path, safe='/'),
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
        except Exception as e:
            # If normalization fails, use original URL
            logger.warning(f"URL normalization failed, using original URL: {e}")
            normalized_url = url

        # URL validation step
        await task_logger.log_task_progress(
            log_entry, f"Validating URL: {normalized_url}", {"stage": "validation", "original_url": url}
        )

        if not validators.url(normalized_url):
            raise ValueError(f"Url {normalized_url} is not a valid URL address")

        # Set up crawler
        await task_logger.log_task_progress(
            log_entry,
            f"Setting up crawler for URL: {normalized_url}",
            {
                "stage": "crawler_setup",
                "firecrawl_available": bool(config.FIRECRAWL_API_KEY),
            },
        )

        use_firecrawl = bool(config.FIRECRAWL_API_KEY)

        # Perform crawling
        await task_logger.log_task_progress(
            log_entry,
            f"Crawling URL content: {normalized_url}",
            {
                "stage": "crawling",
                "crawler_type": "AsyncFirecrawlApp"
                if use_firecrawl
                else "PlaywrightSmartExtractor",
            },
        )

        if use_firecrawl:
            # Use async Firecrawl SDK with v1 API - properly awaited
            firecrawl_app = AsyncFirecrawlApp(api_key=config.FIRECRAWL_API_KEY)
            scrape_result = await firecrawl_app.scrape_url(
                url=normalized_url, formats=["markdown"]
            )

            # scrape_result is a Pydantic ScrapeResponse object
            # Access attributes directly
            if scrape_result and scrape_result.success:
                # Extract markdown content
                markdown_content = scrape_result.markdown or ""

                # Extract metadata - this is a DICT
                metadata = scrape_result.metadata if scrape_result.metadata else {}

                # Convert to LangChain Document format
                url_crawled = [
                    LangchainDocument(
                        page_content=markdown_content,
                        metadata={
                            "source": url,
                            "title": metadata.get("title", url),
                            "description": metadata.get("description", ""),
                            "language": metadata.get("language", ""),
                            "sourceURL": metadata.get("sourceURL", url),
                            **metadata,  # Include all other metadata fields
                        },
                    )
                ]
                content_in_markdown = url_crawled[0].page_content
            else:
                error_msg = (
                    scrape_result.error
                    if scrape_result and hasattr(scrape_result, "error")
                    else "Unknown error"
                )
                raise ValueError(f"Firecrawl failed to scrape URL: {error_msg}")
        else:
            # Use Playwright with smart multi-strategy extraction
            # This implements robust content extraction with fallback strategies
            # See diagnostic analysis: docs/crawler_analysis_aljazeera.md
            logger.info(f"Using Playwright smart extraction for: {normalized_url}")

            headline, body, extraction_metadata = await _extract_article_with_playwright(normalized_url)

            if not headline and not body:
                raise ValueError(
                    f"Failed to extract content from {normalized_url}. "
                    f"All extraction strategies failed. "
                    f"See logs for details."
                )

            # Format extracted content as markdown
            markdown_parts = []
            if headline:
                markdown_parts.append(f"# {headline}\n")
            if extraction_metadata.get("author"):
                markdown_parts.append(f"**Author:** {extraction_metadata['author']}\n")
            if body:
                markdown_parts.append(f"\n{body}")

            content_in_markdown = "\n".join(markdown_parts)

            # Create LangChain Document format for compatibility
            url_crawled = [
                LangchainDocument(
                    page_content=content_in_markdown,
                    metadata={
                        "source": extraction_metadata.get("source", normalized_url),
                        "title": headline or extraction_metadata.get("title", url),
                        "extraction_strategy": extraction_metadata.get("extraction_strategy", "unknown"),
                        "author": extraction_metadata.get("author", ""),
                    },
                )
            ]

            logger.info(f"✅ Playwright extraction complete: {len(content_in_markdown)} chars")
            logger.debug(f"Extraction strategy used: {extraction_metadata.get('extraction_strategy')}")

        # Format document
        await task_logger.log_task_progress(
            log_entry,
            f"Processing crawled content from: {url}",
            {"stage": "content_processing", "content_length": len(content_in_markdown)},
        )

        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"{key.upper()}: {value}"
                    for key, value in url_crawled[0].metadata.items()
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: markdown", "TEXT_START", content_in_markdown, "TEXT_END"],
            ),
        ]

        # Build the document string more efficiently
        document_parts = []
        document_parts.append("<DOCUMENT>")

        for section_title, section_content in metadata_sections:
            document_parts.append(f"<{section_title}>")
            document_parts.extend(section_content)
            document_parts.append(f"</{section_title}>")

        document_parts.append("</DOCUMENT>")
        combined_document_string = "\n".join(document_parts)

        # Generate unique identifier hash for this URL
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.CRAWLED_URL, url, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check if document with this unique identifier already exists
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for existing URL: {url}",
            {"stage": "duplicate_check", "url": url},
        )

        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                await task_logger.log_task_success(
                    log_entry,
                    f"URL document unchanged: {url}",
                    {
                        "duplicate_detected": True,
                        "existing_document_id": existing_document.id,
                    },
                )
                logging.info(f"Document for URL {url} unchanged. Skipping.")
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(f"Content changed for URL {url}. Updating document.")
                await task_logger.log_task_progress(
                    log_entry,
                    f"Updating URL document: {url}",
                    {"stage": "document_update", "url": url},
                )

        # Get LLM for summary generation (needed for both create and update)
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {url}",
            {"stage": "llm_setup"},
        )

        # Get user's long context LLM
        user_llm = await get_user_long_context_llm(session, user_id, search_space_id)
        if not user_llm:
            raise RuntimeError(
                f"No long context LLM configured for user {user_id} in search space {search_space_id}"
            )

        # Generate summary
        await task_logger.log_task_progress(
            log_entry,
            f"Generating summary for URL content: {url}",
            {"stage": "summary_generation"},
        )

        # Generate summary with metadata
        document_metadata = {
            "url": url,
            "title": url_crawled[0].metadata.get("title", url),
            "document_type": "Crawled URL Document",
            "crawler_type": "FirecrawlApp" if use_firecrawl else "AsyncChromiumLoader",
        }
        summary_content, summary_embedding = await generate_document_summary(
            combined_document_string, user_llm, document_metadata
        )

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for URL: {url}",
            {"stage": "chunk_processing"},
        )

        chunks = await create_document_chunks(content_in_markdown)

        # Update or create document
        if existing_document:
            # Update existing document
            await task_logger.log_task_progress(
                log_entry,
                f"Updating document in database for URL: {url}",
                {"stage": "document_update", "chunks_count": len(chunks)},
            )

            existing_document.title = url_crawled[0].metadata.get(
                "title", url_crawled[0].metadata.get("source", url)
            )
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = url_crawled[0].metadata
            existing_document.chunks = chunks

            document = existing_document
        else:
            # Create new document
            await task_logger.log_task_progress(
                log_entry,
                f"Creating document in database for URL: {url}",
                {"stage": "document_creation", "chunks_count": len(chunks)},
            )

            document = Document(
                search_space_id=search_space_id,
                title=url_crawled[0].metadata.get(
                    "title", url_crawled[0].metadata.get("source", url)
                ),
                document_type=DocumentType.CRAWLED_URL,
                document_metadata=url_crawled[0].metadata,
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

            session.add(document)
        await session.commit()
        await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully crawled and processed URL: {url}",
            {
                "document_id": document.id,
                "title": document.title,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
            },
        )

        return document

    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error while processing URL: {url}",
            str(db_error),
            {"error_type": "SQLAlchemyError"},
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to crawl URL: {url}",
            str(e),
            {"error_type": type(e).__name__},
        )
        raise RuntimeError(f"Failed to crawl URL: {e!s}") from e
