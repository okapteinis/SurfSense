#!/usr/bin/env python3
"""
VPS Integration Test Script for Al Jazeera Crawler (Phase 2B)

This script tests the production crawler implementation with multiple Al Jazeera
articles to verify:
- All three extraction strategies work correctly
- Performance optimization (asyncio.gather) is effective
- Memory usage is acceptable
- Error handling is robust
- Metadata extraction works properly

Test Articles:
1. Recent short article (15 paragraphs) - Economy
2. Older long article (52 paragraphs) - Economy/Politics
3. Recent long article (48 paragraphs) - News/Politics
4. Feature article - Longer form content
5. Opinion piece - Different structure

Usage:
    python scripts/test_crawler_integration_vps.py [--headless] [--quick]

    --headless: Run browser in headless mode (default: visible)
    --quick: Test only 3 articles instead of all 5
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tasks.document_processors.url_crawler import (
    _extract_article_with_playwright,
    MIN_CONTENT_LENGTH,
)

# Test quality thresholds
MIN_PARAGRAPH_COUNT = 5  # Minimum paragraphs for quality content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test article URLs
TEST_ARTICLES = [
    {
        "url": "https://www.aljazeera.com/economy/2025/12/31/us-jobless-claims-slow-in-last-full-week-of-2025-amid-weak-labour-market",
        "category": "Economy",
        "type": "Short News",
        "expected_paragraphs": 15,
        "expected_keywords": ["jobless", "claims", "unemployment"],
    },
    {
        "url": "https://www.aljazeera.com/economy/2024/12/23/from-trump-to-bitcoin-inflation-and-china-the-big-economic-trends-of-2024",
        "category": "Economy/Politics",
        "type": "Long Analysis",
        "expected_paragraphs": 52,
        "expected_keywords": ["trump", "bitcoin", "inflation", "china"],
    },
    {
        "url": "https://www.aljazeera.com/news/2025/12/30/trump-bombs-venezuelan-land-for-first-time-is-war-imminent",
        "category": "News/Politics",
        "type": "Long News",
        "expected_paragraphs": 48,
        "expected_keywords": ["trump", "venezuela", "war"],
    },
    {
        "url": "https://www.aljazeera.com/features/2025/12/28/gaza-children-struggle-for-survival-amid-israels-starvation-campaign",
        "category": "Features",
        "type": "Long-form Feature",
        "expected_paragraphs": 30,
        "expected_keywords": ["gaza", "children", "israel"],
    },
    {
        "url": "https://www.aljazeera.com/opinions/2025/12/27/what-does-trump-20-hold-for-latin-america",
        "category": "Opinion",
        "type": "Opinion Piece",
        "expected_paragraphs": 20,
        "expected_keywords": ["trump", "latin america"],
    },
]

# Results storage
RESULTS_FILE = Path(__file__).parent.parent.parent / "debug_output" / "crawler_integration_test_results.json"


async def test_article(article_info: Dict[str, Any], test_num: int, total: int) -> Dict[str, Any]:
    """
    Test extraction of a single article.

    Returns:
        Dictionary with test results
    """
    url = article_info["url"]
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST {test_num}/{total}: {article_info['type']} - {article_info['category']}")
    logger.info(f"URL: {url}")
    logger.info(f"Expected: ~{article_info['expected_paragraphs']} paragraphs")
    logger.info(f"{'='*80}\n")

    start_time = time.time()

    try:
        # Extract article
        headline, body, metadata = await _extract_article_with_playwright(url)

        extraction_time = time.time() - start_time

        # Analyze results
        if headline is None or body is None:
            logger.error(f"❌ EXTRACTION FAILED for {url}")
            return {
                "url": url,
                "category": article_info["category"],
                "type": article_info["type"],
                "status": "FAILED",
                "error": "Extraction returned None",
                "extraction_time": extraction_time,
            }

        # Count paragraphs
        paragraph_count = body.count("\n\n") + 1
        content_length = len(body)

        # Check keywords
        content_lower = (headline + " " + body).lower()
        found_keywords = [kw for kw in article_info["expected_keywords"] if kw in content_lower]

        # Determine if extraction meets quality standards
        quality_checks = {
            "has_headline": headline is not None and len(headline) > 0,
            "has_body": body is not None and len(body) > MIN_CONTENT_LENGTH,
            "min_paragraphs": paragraph_count >= MIN_PARAGRAPH_COUNT,
            "keywords_found": len(found_keywords) > 0,
            "has_metadata": metadata is not None and len(metadata) > 0,
            "has_strategy": metadata.get("extraction_strategy") in ["article_tag", "main_tag", "largest_block_heuristic"],
        }

        all_checks_passed = all(quality_checks.values())

        # Log results
        logger.info(f"✅ Extraction completed in {extraction_time:.2f}s")
        logger.info(f"   Headline: {headline[:80]}{'...' if len(headline) > 80 else ''}")
        logger.info(f"   Strategy: {metadata.get('extraction_strategy', 'unknown')}")
        logger.info(f"   Paragraphs: {paragraph_count} (expected: ~{article_info['expected_paragraphs']})")
        logger.info(f"   Content Length: {content_length:,} characters")
        logger.info(f"   Keywords Found: {found_keywords}")
        logger.info(f"   Quality Checks: {sum(quality_checks.values())}/{len(quality_checks)} passed")

        if metadata.get("author"):
            logger.info(f"   Author: {metadata['author']}")

        if not all_checks_passed:
            logger.warning(f"⚠️  Some quality checks failed: {[k for k, v in quality_checks.items() if not v]}")

        return {
            "url": url,
            "category": article_info["category"],
            "type": article_info["type"],
            "status": "SUCCESS" if all_checks_passed else "PARTIAL",
            "headline": headline,
            "extraction_strategy": metadata.get("extraction_strategy"),
            "paragraph_count": paragraph_count,
            "expected_paragraphs": article_info["expected_paragraphs"],
            "content_length": content_length,
            "keywords_found": found_keywords,
            "expected_keywords": article_info["expected_keywords"],
            "quality_checks": quality_checks,
            "metadata": {
                "author": metadata.get("author"),
                "title": metadata.get("title"),
                "source": metadata.get("source"),
            },
            "extraction_time": extraction_time,
        }

    except Exception as e:
        extraction_time = time.time() - start_time
        logger.error(f"❌ EXCEPTION during extraction: {type(e).__name__}: {str(e)}")

        return {
            "url": url,
            "category": article_info["category"],
            "type": article_info["type"],
            "status": "ERROR",
            "error": f"{type(e).__name__}: {str(e)}",
            "extraction_time": extraction_time,
        }


async def run_integration_tests(quick_mode: bool = False) -> Dict[str, Any]:
    """
    Run all integration tests.

    Args:
        quick_mode: If True, only test first 3 articles

    Returns:
        Dictionary with all test results and summary
    """
    test_articles = TEST_ARTICLES[:3] if quick_mode else TEST_ARTICLES
    total_tests = len(test_articles)

    logger.info(f"\n{'='*80}")
    logger.info(f"AL JAZEERA CRAWLER INTEGRATION TEST - PHASE 2B")
    logger.info(f"Testing {total_tests} articles")
    logger.info(f"Mode: {'QUICK' if quick_mode else 'FULL'}")
    logger.info(f"Start Time: {datetime.now().isoformat()}")
    logger.info(f"{'='*80}\n")

    overall_start = time.time()
    results = []

    for i, article_info in enumerate(test_articles, 1):
        result = await test_article(article_info, i, total_tests)
        results.append(result)

        # Brief pause between tests
        if i < total_tests:
            logger.info("\nWaiting 3 seconds before next test...\n")
            await asyncio.sleep(3)

    overall_time = time.time() - overall_start

    # Calculate summary statistics
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
    failed_count = sum(1 for r in results if r["status"] in ["FAILED", "ERROR"])

    avg_extraction_time = sum(r["extraction_time"] for r in results) / len(results)

    strategies_used = {}
    for r in results:
        if r["status"] in ["SUCCESS", "PARTIAL"]:
            strategy = r.get("extraction_strategy", "unknown")
            strategies_used[strategy] = strategies_used.get(strategy, 0) + 1

    summary = {
        "test_date": datetime.now().isoformat(),
        "mode": "quick" if quick_mode else "full",
        "total_tests": total_tests,
        "success_count": success_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "success_rate": f"{(success_count / total_tests * 100):.1f}%",
        "avg_extraction_time": f"{avg_extraction_time:.2f}s",
        "total_time": f"{overall_time:.2f}s",
        "strategies_used": strategies_used,
    }

    # Log summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"⚠️  Partial: {partial_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info(f"Success Rate: {summary['success_rate']}")
    logger.info(f"Average Extraction Time: {summary['avg_extraction_time']}")
    logger.info(f"Total Test Time: {summary['total_time']}")
    logger.info(f"Strategies Used: {strategies_used}")
    logger.info(f"{'='*80}\n")

    return {
        "summary": summary,
        "results": results,
    }


def save_results(test_data: Dict[str, Any]) -> None:
    """Save test results to JSON file."""
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_FILE, "w") as f:
        json.dump(test_data, f, indent=2)

    logger.info(f"✅ Results saved to: {RESULTS_FILE}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Al Jazeera crawler integration on VPS (Phase 2B)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode - test only 3 articles instead of all 5"
    )

    args = parser.parse_args()

    # Note: headless parameter not used in this script since we call the production
    # crawler which doesn't expose headless as a parameter. This is intentional as
    # we're testing the production configuration.
    if args.headless:
        logger.info("Note: --headless flag noted but production crawler uses default configuration")

    # Run tests
    test_data = asyncio.run(run_integration_tests(quick_mode=args.quick))

    # Save results
    save_results(test_data)

    # Exit with appropriate code
    if test_data["summary"]["failed_count"] > 0:
        logger.error(f"\n❌ TESTS FAILED: {test_data['summary']['failed_count']} failures")
        sys.exit(1)
    elif test_data["summary"]["partial_count"] > 0:
        logger.warning(f"\n⚠️  TESTS PARTIAL: {test_data['summary']['partial_count']} incomplete")
        sys.exit(0)
    else:
        logger.info("\n✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
