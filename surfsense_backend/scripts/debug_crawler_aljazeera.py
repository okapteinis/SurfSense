#!/usr/bin/env python3
"""
Al Jazeera Web Crawler Diagnostic Script

This script uses Playwright to diagnose crawling issues with Al Jazeera news articles.
It provides detailed logging, network monitoring, bot detection checks, and multiple
content extraction strategies.

Usage:
    python debug_crawler_aljazeera.py <URL> [--headless]

Example:
    python debug_crawler_aljazeera.py \
        "https://www.aljazeera.com/news/2025/12/10/thailand-cambodia-border-clashes" \
        --headless
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Configure logging with timestamps
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('surfsense_backend/debug_output/crawler_debug.log')
    ]
)

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Page, Request, Response, TimeoutError as PlaywrightTimeoutError
except ImportError:
    logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


class AlJazeeraCrawlerDiagnostic:
    """Diagnostic tool for Al Jazeera web crawler issues."""

    def __init__(self, url: str, headless: bool = True):
        """
        Initialize diagnostic tool.

        Args:
            url: Al Jazeera article URL to test
            headless: Run browser in headless mode
        """
        self.url = url
        self.headless = headless
        self.output_dir = Path("surfsense_backend/debug_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.results = {
            "success": False,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "status_code": None,
            "redirect_chain": [],
            "bot_detection": {
                "cloudflare_challenge": False,
                "turnstile_widget": False,
                "captcha_iframe": False,
                "rate_limit_429": False,
                "detected_services": []
            },
            "network_activity": {
                "total_requests": 0,
                "total_responses": 0,
                "failed_requests": 0,
                "request_types": {},
                "api_calls": []
            },
            "content_extraction": {
                "strategies_tried": [],
                "successful_strategy": None,
                "headline": None,
                "author": None,
                "date": None,
                "paragraph_count": 0,
                "total_text_length": 0,
                "body_preview": None
            },
            "performance": {
                "page_load_time": None,
                "content_ready_time": None,
                "total_time": None
            },
            "errors": []
        }

        # Network monitoring lists
        self.requests = []
        self.responses = []

    async def _handle_request(self, request: Request) -> None:
        """Log all outgoing HTTP requests."""
        try:
            logger.debug(f"REQUEST: {request.method} {request.url}")
            self.requests.append({
                "method": request.method,
                "url": request.url,
                "resource_type": request.resource_type,
                "timestamp": datetime.now().isoformat()
            })
            self.results["network_activity"]["total_requests"] += 1

            # Track resource types
            resource_type = request.resource_type
            self.results["network_activity"]["request_types"][resource_type] = \
                self.results["network_activity"]["request_types"].get(resource_type, 0) + 1

            # Detect API calls (JSON/AJAX requests)
            if request.resource_type in ["xhr", "fetch"]:
                self.results["network_activity"]["api_calls"].append({
                    "url": request.url,
                    "method": request.method,
                    "timestamp": datetime.now().isoformat()
                })
                logger.info(f"API CALL DETECTED: {request.method} {request.url}")

        except Exception as e:
            logger.error(f"Error handling request: {e}")

    async def _handle_response(self, response: Response) -> None:
        """Log all incoming HTTP responses."""
        try:
            logger.debug(f"RESPONSE: {response.status} {response.url}")
            self.responses.append({
                "status": response.status,
                "url": response.url,
                "content_type": response.headers.get("content-type", ""),
                "timestamp": datetime.now().isoformat()
            })
            self.results["network_activity"]["total_responses"] += 1

            # Check for rate limiting
            if response.status == 429:
                logger.warning("⚠️ RATE LIMIT 429 detected!")
                self.results["bot_detection"]["rate_limit_429"] = True

            # Check for redirects
            if response.status in [301, 302, 303, 307, 308]:
                redirect_location = response.headers.get("location", "")
                logger.info(f"REDIRECT: {response.status} → {redirect_location}")
                self.results["redirect_chain"].append({
                    "from": response.url,
                    "to": redirect_location,
                    "status": response.status
                })

            # Check for bot detection services in headers
            headers_lower = {k.lower(): v for k, v in response.headers.items()}
            if "cf-ray" in headers_lower:
                logger.warning("⚠️ Cloudflare detected (cf-ray header)")
                if "Cloudflare" not in self.results["bot_detection"]["detected_services"]:
                    self.results["bot_detection"]["detected_services"].append("Cloudflare")

            if "x-datadome" in headers_lower:
                logger.warning("⚠️ DataDome detected")
                if "DataDome" not in self.results["bot_detection"]["detected_services"]:
                    self.results["bot_detection"]["detected_services"].append("DataDome")

        except Exception as e:
            logger.error(f"Error handling response: {e}")

    async def _check_bot_detection(self, page: Page) -> None:
        """Check for various bot detection mechanisms."""
        logger.info("Checking for bot detection indicators...")

        # Check for Cloudflare challenge
        cloudflare_challenge = await page.query_selector("#challenge-form")
        if cloudflare_challenge:
            logger.warning("⚠️ CLOUDFLARE CHALLENGE DETECTED!")
            self.results["bot_detection"]["cloudflare_challenge"] = True
            self.results["errors"].append("Cloudflare challenge page detected")

        # Check for Turnstile widget
        turnstile = await page.query_selector("[class*='turnstile']")
        if turnstile:
            logger.warning("⚠️ TURNSTILE WIDGET DETECTED!")
            self.results["bot_detection"]["turnstile_widget"] = True
            self.results["errors"].append("Cloudflare Turnstile widget detected")

        # Check for CAPTCHA iframes
        captcha_iframe = await page.query_selector("iframe[src*='captcha'], iframe[src*='recaptcha']")
        if captcha_iframe:
            logger.warning("⚠️ CAPTCHA IFRAME DETECTED!")
            self.results["bot_detection"]["captcha_iframe"] = True
            self.results["errors"].append("CAPTCHA iframe detected")

        # Check for rate limit messages in page text
        page_text = await page.text_content("body")
        if page_text and any(phrase in page_text.lower() for phrase in ["rate limit", "too many requests", "please wait"]):
            logger.warning("⚠️ RATE LIMIT MESSAGE in page content!")
            self.results["errors"].append("Rate limit message found in page text")

    async def _extract_content_strategy_article_tag(self, page: Page) -> dict | None:
        """Strategy 1: Extract content from <article> tag."""
        logger.info("Trying extraction strategy: <article> tag")
        self.results["content_extraction"]["strategies_tried"].append("article_tag")

        try:
            article = await page.query_selector("article, article[role='article']")
            if not article:
                logger.debug("No <article> tag found")
                return None

            # Extract headline (h1 within article)
            headline_elem = await article.query_selector("h1")
            headline = await headline_elem.inner_text() if headline_elem else None

            # Extract paragraphs
            paragraphs_elems = await article.query_selector_all("p")
            paragraphs = []
            for p in paragraphs_elems:
                text = await p.inner_text()
                if text and len(text.strip()) > 20:  # Filter out short/empty paragraphs
                    paragraphs.append(text.strip())

            if headline and paragraphs:
                logger.info(f"✅ Successfully extracted via <article> tag: {len(paragraphs)} paragraphs")
                return {
                    "headline": headline,
                    "paragraphs": paragraphs,
                    "paragraph_count": len(paragraphs)
                }

        except Exception as e:
            logger.error(f"Error in article_tag strategy: {e}")

        return None

    async def _extract_content_strategy_main_tag(self, page: Page) -> dict | None:
        """Strategy 2: Extract content from <main> tag."""
        logger.info("Trying extraction strategy: <main> tag")
        self.results["content_extraction"]["strategies_tried"].append("main_tag")

        try:
            main = await page.query_selector("main, [role='main']")
            if not main:
                logger.debug("No <main> tag found")
                return None

            # Look for article-like containers
            article_containers = await main.query_selector_all(
                "[class*='article'], [class*='content'], [class*='post'], [class*='entry']"
            )

            if not article_containers:
                # Fallback: use main directly
                article_containers = [main]

            for container in article_containers:
                # Extract headline
                headline_elem = await container.query_selector("h1")
                headline = await headline_elem.inner_text() if headline_elem else None

                # Extract paragraphs
                paragraphs_elems = await container.query_selector_all("p")
                paragraphs = []
                for p in paragraphs_elems:
                    text = await p.inner_text()
                    if text and len(text.strip()) > 20:
                        paragraphs.append(text.strip())

                if headline and len(paragraphs) >= 3:  # Require at least 3 substantial paragraphs
                    logger.info(f"✅ Successfully extracted via <main> tag: {len(paragraphs)} paragraphs")
                    return {
                        "headline": headline,
                        "paragraphs": paragraphs,
                        "paragraph_count": len(paragraphs)
                    }

        except Exception as e:
            logger.error(f"Error in main_tag strategy: {e}")

        return None

    async def _extract_content_strategy_largest_block(self, page: Page) -> dict | None:
        """Strategy 3: Find div with largest paragraph count (heuristic)."""
        logger.info("Trying extraction strategy: largest text block heuristic")
        self.results["content_extraction"]["strategies_tried"].append("largest_block_heuristic")

        try:
            # Find all divs with class containing common article keywords
            candidates = await page.query_selector_all(
                "div[class*='article'], div[class*='content'], div[class*='post'], div[class*='entry'], div[class*='body']"
            )

            if not candidates:
                logger.debug("No candidate divs found with article-like classes")
                return None

            best_candidate = None
            max_paragraphs = 0

            for candidate in candidates:
                paragraphs_elems = await candidate.query_selector_all("p")
                paragraph_count = len([p for p in paragraphs_elems if await p.inner_text()])

                if paragraph_count > max_paragraphs:
                    max_paragraphs = paragraph_count
                    best_candidate = candidate

            if best_candidate and max_paragraphs >= 3:
                # Extract headline (look for h1 anywhere on page)
                headline_elem = await page.query_selector("h1")
                headline = await headline_elem.inner_text() if headline_elem else None

                # Extract paragraphs from best candidate
                paragraphs_elems = await best_candidate.query_selector_all("p")
                paragraphs = []
                for p in paragraphs_elems:
                    text = await p.inner_text()
                    if text and len(text.strip()) > 20:
                        paragraphs.append(text.strip())

                if paragraphs:
                    logger.info(f"✅ Successfully extracted via largest block: {len(paragraphs)} paragraphs")
                    return {
                        "headline": headline,
                        "paragraphs": paragraphs,
                        "paragraph_count": len(paragraphs)
                    }

        except Exception as e:
            logger.error(f"Error in largest_block strategy: {e}")

        return None

    async def _extract_metadata(self, page: Page) -> dict:
        """Extract article metadata (author, date, canonical URL)."""
        metadata = {}

        try:
            # Canonical URL
            canonical = await page.query_selector("link[rel='canonical']")
            if canonical:
                metadata["canonical_url"] = await canonical.get_attribute("href")
                logger.info(f"Canonical URL: {metadata['canonical_url']}")

            # Meta tags
            meta_author = await page.query_selector("meta[name='author'], meta[property='article:author']")
            if meta_author:
                metadata["author"] = await meta_author.get_attribute("content")

            meta_date = await page.query_selector("meta[property='article:published_time'], meta[name='publish-date']")
            if meta_date:
                metadata["published_date"] = await meta_date.get_attribute("content")

            # Try to find author in page content
            if not metadata.get("author"):
                author_elem = await page.query_selector("[class*='author'], [class*='byline']")
                if author_elem:
                    metadata["author"] = await author_elem.inner_text()

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")

        return metadata

    async def run_diagnostic(self) -> dict:
        """Run complete diagnostic on Al Jazeera article."""
        start_time = datetime.now()
        logger.info(f"Starting diagnostic for URL: {self.url}")
        logger.info(f"Headless mode: {self.headless}")

        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=self.headless)
                logger.info("✅ Browser launched successfully")

                # Create context with realistic user agent
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )

                page = await context.new_page()

                # Set up network monitoring
                page.on("request", lambda req: asyncio.create_task(self._handle_request(req)))
                page.on("response", lambda res: asyncio.create_task(self._handle_response(res)))

                # Capture console messages and errors
                page.on("console", lambda msg: logger.debug(f"CONSOLE: {msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: logger.error(f"PAGE ERROR: {err}"))

                # STEP 1: Navigate to URL
                logger.info("Navigating to URL...")
                screenshot_counter = 1

                try:
                    response = await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
                    page_load_time = (datetime.now() - start_time).total_seconds()
                    self.results["performance"]["page_load_time"] = page_load_time
                    logger.info(f"✅ Page loaded in {page_load_time:.2f}s")

                    if response:
                        self.results["status_code"] = response.status
                        logger.info(f"HTTP Status: {response.status}")

                    # Screenshot after page load
                    await page.screenshot(path=self.output_dir / f"step{screenshot_counter}_page_load.png")
                    logger.info(f"Screenshot saved: step{screenshot_counter}_page_load.png")
                    screenshot_counter += 1

                except PlaywrightTimeoutError:
                    logger.error("⏱️ Page load timeout (30s exceeded)")
                    self.results["errors"].append("Page load timeout after 30 seconds")
                    await page.screenshot(path=self.output_dir / "error_timeout.png")
                    return self.results

                # STEP 2: Check for bot detection
                await self._check_bot_detection(page)

                # Screenshot after bot detection check
                await page.screenshot(path=self.output_dir / f"step{screenshot_counter}_bot_check.png")
                screenshot_counter += 1

                # STEP 3: Wait for main content to be ready
                logger.info("Waiting for main content...")
                content_ready_start = datetime.now()

                try:
                    # Try multiple selectors for article content
                    await page.wait_for_selector(
                        "article, main, [role='main'], [class*='article']",
                        timeout=10000
                    )
                    content_ready_time = (datetime.now() - content_ready_start).total_seconds()
                    self.results["performance"]["content_ready_time"] = content_ready_time
                    logger.info(f"✅ Content ready in {content_ready_time:.2f}s")
                except PlaywrightTimeoutError:
                    logger.warning("⏱️ Content selector timeout, proceeding anyway...")

                # Also wait for network idle as fallback
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                    logger.info("✅ Network idle reached")
                except PlaywrightTimeoutError:
                    logger.warning("⏱️ Network idle timeout, proceeding anyway...")

                # Screenshot after waiting for content
                await page.screenshot(path=self.output_dir / f"step{screenshot_counter}_content_wait.png")
                screenshot_counter += 1

                # STEP 4: Extract content using multiple strategies
                logger.info("Attempting content extraction...")
                extracted_data = None

                # Try strategies in order
                strategies = [
                    self._extract_content_strategy_article_tag,
                    self._extract_content_strategy_main_tag,
                    self._extract_content_strategy_largest_block
                ]

                for strategy in strategies:
                    extracted_data = await strategy(page)
                    if extracted_data:
                        self.results["content_extraction"]["successful_strategy"] = extracted_data.get("strategy", "unknown")
                        break

                if extracted_data:
                    self.results["content_extraction"]["headline"] = extracted_data.get("headline")
                    self.results["content_extraction"]["paragraph_count"] = extracted_data.get("paragraph_count", 0)
                    paragraphs = extracted_data.get("paragraphs", [])
                    total_text = "\n\n".join(paragraphs)
                    self.results["content_extraction"]["total_text_length"] = len(total_text)
                    self.results["content_extraction"]["body_preview"] = total_text[:500] + "..." if total_text else None
                    self.results["success"] = True
                    logger.info("✅ Content extraction SUCCESSFUL")
                else:
                    logger.error("❌ All extraction strategies FAILED")
                    self.results["errors"].append("All content extraction strategies failed")

                # STEP 5: Extract metadata
                metadata = await self._extract_metadata(page)
                self.results["content_extraction"]["author"] = metadata.get("author")
                self.results["content_extraction"]["date"] = metadata.get("published_date")

                # Screenshot after content extraction
                await page.screenshot(path=self.output_dir / f"step{screenshot_counter}_extraction_done.png")
                screenshot_counter += 1

                # STEP 6: Save full HTML
                html_content = await page.content()
                html_file = self.output_dir / "aljazeera_dump.html"
                html_file.write_text(html_content, encoding="utf-8")
                logger.info(f"✅ HTML saved to: {html_file}")

                # Get current URL (after any redirects)
                current_url = page.url
                logger.info(f"Final URL: {current_url}")

                await browser.close()

        except Exception as e:
            logger.error(f"❌ Diagnostic failed with exception: {e}", exc_info=True)
            self.results["errors"].append(f"Diagnostic exception: {str(e)}")

        # Calculate total time
        total_time = (datetime.now() - start_time).total_seconds()
        self.results["performance"]["total_time"] = total_time
        logger.info(f"Total diagnostic time: {total_time:.2f}s")

        return self.results

    def save_results(self) -> None:
        """Save results to JSON file."""
        output_file = self.output_dir / "aljazeera_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Results saved to: {output_file}")

    def print_summary(self) -> None:
        """Print summary of diagnostic results."""
        print("\n" + "=" * 80)
        print("DIAGNOSTIC SUMMARY")
        print("=" * 80)
        print(f"URL: {self.url}")
        print(f"Status: {'✅ SUCCESS' if self.results['success'] else '❌ FAILED'}")
        print(f"HTTP Status Code: {self.results['status_code']}")
        print(f"\nBot Detection:")
        print(f"  - Cloudflare Challenge: {self.results['bot_detection']['cloudflare_challenge']}")
        print(f"  - Turnstile Widget: {self.results['bot_detection']['turnstile_widget']}")
        print(f"  - CAPTCHA: {self.results['bot_detection']['captcha_iframe']}")
        print(f"  - Rate Limit 429: {self.results['bot_detection']['rate_limit_429']}")
        print(f"  - Detected Services: {', '.join(self.results['bot_detection']['detected_services']) or 'None'}")
        print(f"\nContent Extraction:")
        print(f"  - Strategies Tried: {', '.join(self.results['content_extraction']['strategies_tried'])}")
        print(f"  - Successful Strategy: {self.results['content_extraction']['successful_strategy']}")
        print(f"  - Headline: {self.results['content_extraction']['headline']}")
        print(f"  - Paragraph Count: {self.results['content_extraction']['paragraph_count']}")
        print(f"  - Total Text Length: {self.results['content_extraction']['total_text_length']} chars")
        print(f"\nPerformance:")
        print(f"  - Page Load: {self.results['performance']['page_load_time']:.2f}s" if self.results['performance']['page_load_time'] else "  - Page Load: N/A")
        print(f"  - Content Ready: {self.results['performance']['content_ready_time']:.2f}s" if self.results['performance']['content_ready_time'] else "  - Content Ready: N/A")
        print(f"  - Total Time: {self.results['performance']['total_time']:.2f}s")
        print(f"\nNetwork Activity:")
        print(f"  - Total Requests: {self.results['network_activity']['total_requests']}")
        print(f"  - Total Responses: {self.results['network_activity']['total_responses']}")
        print(f"  - API Calls: {len(self.results['network_activity']['api_calls'])}")
        if self.results["errors"]:
            print(f"\nErrors:")
            for error in self.results["errors"]:
                print(f"  - {error}")
        print("=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Diagnose Al Jazeera web crawler issues")
    parser.add_argument("url", help="Al Jazeera article URL to test")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    diagnostic = AlJazeeraCrawlerDiagnostic(args.url, headless=args.headless)
    results = await diagnostic.run_diagnostic()
    diagnostic.save_results()
    diagnostic.print_summary()

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
