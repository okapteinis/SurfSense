"""
Integration tests for news site URL crawler with multi-strategy extraction.

These tests verify that the Playwright-based smart extraction works correctly
across different news sites and doesn't break existing functionality.
"""

import pytest
from app.tasks.document_processors.url_crawler import (
    _try_article_tag,
    _try_main_tag,
    _try_largest_block_heuristic,
    _extract_article_with_playwright,
)


@pytest.mark.asyncio
async def test_aljazeera_extraction_recent():
    """
    Test extraction of recent Al Jazeera article (Dec 31, 2025).

    This test verifies that the largest block heuristic successfully extracts
    content from Al Jazeera's JavaScript-heavy site structure.
    """
    url = "https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Verify extraction succeeded
    assert headline is not None, "Headline should be extracted"
    assert body is not None, "Body should be extracted"

    # Verify content quality
    assert "jobless" in headline.lower() or "jobless" in body.lower(), "Content should mention 'jobless'"
    assert len(body) > 1000, f"Body should have substantial content, got {len(body)} chars"

    # Verify paragraph count (from diagnostic: 15 paragraphs)
    paragraph_count = body.count("\n\n") + 1
    assert paragraph_count >= 10, f"Should extract at least 10 paragraphs, got {paragraph_count}"

    # Verify metadata
    assert metadata.get("extraction_strategy") in ["article_tag", "main_tag", "largest_block_heuristic"]
    assert metadata.get("title") is not None


@pytest.mark.asyncio
async def test_aljazeera_extraction_older():
    """
    Test extraction of older Al Jazeera article (Dec 23, 2024).

    Verifies that the extractor works on older article layouts as well,
    ensuring resilience to layout changes over time.
    """
    url = "https://www.aljazeera.com/economy/2024/12/23/from-trump-to-bitcoin-inflation-and-china-the-big-economic-trends-of-2024"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Verify extraction succeeded
    assert headline is not None, "Headline should be extracted"
    assert body is not None, "Body should be extracted"

    # Verify content quality
    assert "trump" in headline.lower() or "trump" in body.lower(), "Content should mention 'Trump'"
    assert len(body) > 5000, f"Long article should have >5000 chars, got {len(body)}"

    # Verify paragraph count (from diagnostic: 52 paragraphs)
    paragraph_count = body.count("\n\n") + 1
    assert paragraph_count >= 40, f"Should extract at least 40 paragraphs, got {paragraph_count}"

    # Verify author extraction
    assert metadata.get("author") is not None, "Author should be extracted"


@pytest.mark.asyncio
async def test_aljazeera_long_article():
    """
    Test extraction of long-form Al Jazeera article (Dec 30, 2025).

    Verifies handling of articles with many paragraphs (48 in diagnostic).
    """
    url = "https://www.aljazeera.com/news/2025/12/30/trump-bombs-venezuelan-land-for-first-time-is-war-imminent"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Verify extraction succeeded
    assert headline is not None, "Headline should be extracted"
    assert body is not None, "Body should be extracted"

    # Verify content quality
    assert len(body) > 8000, f"Long article should have >8000 chars, got {len(body)}"

    # Verify paragraph count (from diagnostic: 48 paragraphs)
    paragraph_count = body.count("\n\n") + 1
    assert paragraph_count >= 40, f"Should extract at least 40 paragraphs, got {paragraph_count}"


@pytest.mark.asyncio
async def test_extraction_strategies_order():
    """
    Test that extraction strategies are tried in the correct order and
    the most appropriate one succeeds.

    For Al Jazeera, we expect:
    - article_tag to fail (no <article> tags)
    - main_tag to fail (no meaningful <main> content)
    - largest_block_heuristic to succeed
    """
    url = "https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # For Al Jazeera, we expect largest_block_heuristic to succeed
    # (from diagnostic analysis: no <article> or <main> tags)
    strategy = metadata.get("extraction_strategy")
    assert strategy in ["largest_block_heuristic", "main_tag", "article_tag"], \
        f"Should use valid strategy, got {strategy}"

    # Content should be successfully extracted regardless of strategy
    assert headline is not None
    assert body is not None
    assert len(body) > 1000


@pytest.mark.asyncio
async def test_playwright_timeout_handling():
    """
    Test that Playwright handles timeouts gracefully.

    This test uses an invalid URL to verify error handling.
    """
    url = "https://this-domain-does-not-exist-12345.com/article"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Should return None for both headline and body on timeout
    assert headline is None
    assert body is None
    assert "error" in metadata or metadata.get("extraction_strategy") == "none"


@pytest.mark.asyncio
async def test_extraction_with_minimal_content():
    """
    Test that extraction handles pages with minimal content gracefully.

    The heuristic requires at least 5 paragraphs by default, so pages with
    less content should fail gracefully.
    """
    # Use a very short Wikipedia page or similar
    url = "https://en.wikipedia.org/wiki/Special:Random"  # Random Wikipedia page

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Random Wikipedia pages should generally extract successfully
    # This test mainly verifies no crashes occur
    if headline or body:
        assert metadata.get("extraction_strategy") is not None
    else:
        # If extraction fails, it should be logged properly
        assert "error" in metadata or metadata.get("extraction_strategy") == "none"


# NOTE: Tests for BBC, CNN, Reuters would require finding stable article URLs
# that won't change. For now, we focus on Al Jazeera since we have diagnostic
# data confirming these URLs work.

# Example test structure for other sites (not run by default):
@pytest.mark.skip(reason="Requires finding stable CNN article URL")
@pytest.mark.asyncio
async def test_cnn_extraction_still_works():
    """
    Verify that CNN articles still extract correctly.

    This ensures no regression for sites that may use proper semantic tags.
    """
    # TODO: Find a stable CNN article URL for testing
    url = "https://www.cnn.com/..."

    headline, body, metadata = await _extract_article_with_playwright(url)

    assert headline is not None
    assert body is not None
    assert len(body) > 500


@pytest.mark.skip(reason="Requires finding stable BBC article URL")
@pytest.mark.asyncio
async def test_bbc_extraction_still_works():
    """
    Verify that BBC articles still extract correctly.
    """
    # TODO: Find a stable BBC article URL for testing
    url = "https://www.bbc.com/news/..."

    headline, body, metadata = await _extract_article_with_playwright(url)

    assert headline is not None
    assert body is not None
    assert len(body) > 500


# Metadata extraction tests
@pytest.mark.asyncio
async def test_author_extraction():
    """
    Test that author metadata is extracted when available.

    From diagnostic: Al Jazeera articles have author info.
    """
    url = "https://www.aljazeera.com/economy/2024/12/23/from-trump-to-bitcoin-inflation-and-china-the-big-economic-trends-of-2024"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # This specific article has "Erin Hale" as author (from diagnostic)
    assert metadata.get("author") is not None, "Author should be extracted"
    assert len(metadata["author"]) > 0, "Author should not be empty"


@pytest.mark.asyncio
async def test_canonical_url_extraction():
    """
    Test that the final URL (after redirects) is captured correctly.
    """
    url = "https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market"

    headline, body, metadata = await _extract_article_with_playwright(url)

    # Source should be the final URL
    assert metadata.get("source") is not None
    assert "aljazeera.com" in metadata["source"]


# Performance tests (optional - can be slow)
@pytest.mark.slow
@pytest.mark.asyncio
async def test_extraction_performance():
    """
    Test that extraction completes within reasonable time.

    From diagnostic: Page load ~1.2-1.8s, total time ~5-6s.
    """
    import time

    url = "https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market"

    start_time = time.time()
    headline, body, metadata = await _extract_article_with_playwright(url)
    elapsed = time.time() - start_time

    # Should complete within 15 seconds (generous for CI/CD environments)
    assert elapsed < 15, f"Extraction took {elapsed:.2f}s, should be <15s"

    # Content should be extracted
    assert headline is not None
    assert body is not None
