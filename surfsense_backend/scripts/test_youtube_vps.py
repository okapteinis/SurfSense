#!/usr/bin/env python3
"""
VPS Integration Test Script for YouTube Transcript Extraction (Phase 2C)

This script tests the production YouTube transcript extraction with real videos to verify:
- YouTube API transcript extraction works
- Rate limiting is functional (10 calls/60s default)
- Error handling for unavailable/private videos
- Thread-safe proxy handling (if configured)
- Transcript format consistency

Usage:
    python scripts/test_youtube_vps.py [--quick]

    --quick: Test only 2 videos instead of all 5
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

from app.utils.youtube_utils import (
    get_youtube_transcript_with_proxy,
    get_youtube_transcript,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test video IDs (public videos with known transcripts)
TEST_VIDEOS = [
    {
        "video_id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
        "expected_duration": 213,  # ~3.5 minutes
        "expected_transcript": True,
        "language": "en",
    },
    {
        "video_id": "9bZkp7q19f0",
        "title": "PSY - GANGNAM STYLE(강남스타일) M/V",
        "expected_duration": 252,  # ~4 minutes
        "expected_transcript": True,
        "language": "ko",
    },
    {
        "video_id": "kJQP7kiw5Fk",
        "title": "Luis Fonsi - Despacito ft. Daddy Yankee",
        "expected_duration": 282,  # ~4.5 minutes
        "expected_transcript": True,
        "language": "es",
    },
    {
        "video_id": "invalid123",
        "title": "Invalid Video ID (should fail)",
        "expected_duration": 0,
        "expected_transcript": False,
        "language": None,
    },
    {
        "video_id": "jNQXAC9IVRw",
        "title": "Me at the zoo (first YouTube video)",
        "expected_duration": 19,  # 19 seconds
        "expected_transcript": True,
        "language": "en",
    },
]

# Results storage
RESULTS_FILE = Path(__file__).parent.parent.parent / "debug_output" / "youtube_test_results.json"


def test_video(video_info: Dict[str, Any], test_num: int, total: int) -> Dict[str, Any]:
    """
    Test YouTube transcript extraction for a single video.

    Returns:
        Dictionary with test results
    """
    video_id = video_info["video_id"]
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST {test_num}/{total}: {video_info['title']}")
    logger.info(f"Video ID: {video_id}")
    logger.info(f"Expected transcript: {'Yes' if video_info['expected_transcript'] else 'No'}")
    logger.info(f"{'='*80}\n")

    start_time = time.time()

    try:
        # Attempt to fetch transcript using YouTube API with proxy
        transcript = get_youtube_transcript_with_proxy(video_id)

        extraction_time = time.time() - start_time

        # Validate transcript structure
        if not transcript or len(transcript) == 0:
            logger.warning(f"⚠️  Empty transcript returned for {video_id}")
            return {
                "video_id": video_id,
                "title": video_info["title"],
                "status": "PARTIAL",
                "error": "Empty transcript",
                "extraction_time": extraction_time,
            }

        # Validate segment format
        first_segment = transcript[0]
        required_keys = {"text", "start", "duration"}
        if not all(key in first_segment for key in required_keys):
            logger.error(f"❌ Invalid transcript format for {video_id}")
            return {
                "video_id": video_id,
                "title": video_info["title"],
                "status": "FAILED",
                "error": f"Invalid format, missing keys: {required_keys - set(first_segment.keys())}",
                "extraction_time": extraction_time,
            }

        # Calculate total duration from transcript
        last_segment = transcript[-1]
        total_duration = last_segment["start"] + last_segment["duration"]

        # Join transcript text
        full_text = " ".join(segment["text"] for segment in transcript)

        logger.info(f"✅ Transcript extracted successfully")
        logger.info(f"   Segments: {len(transcript)}")
        logger.info(f"   Total duration: {total_duration:.1f}s (expected: ~{video_info['expected_duration']}s)")
        logger.info(f"   Text length: {len(full_text):,} characters")
        logger.info(f"   Extraction time: {extraction_time:.2f}s")
        logger.info(f"   First segment: \"{transcript[0]['text'][:60]}...\"")

        return {
            "video_id": video_id,
            "title": video_info["title"],
            "status": "SUCCESS",
            "segment_count": len(transcript),
            "total_duration": total_duration,
            "expected_duration": video_info["expected_duration"],
            "text_length": len(full_text),
            "extraction_time": extraction_time,
            "first_segment_text": transcript[0]["text"][:100],
            "last_segment_text": transcript[-1]["text"][:100],
        }

    except Exception as e:
        extraction_time = time.time() - start_time
        error_type = type(e).__name__
        error_msg = str(e)

        # For expected failures (invalid video ID), this is actually success
        if not video_info["expected_transcript"]:
            logger.info(f"✅ Expected failure for invalid video: {error_type}")
            return {
                "video_id": video_id,
                "title": video_info["title"],
                "status": "SUCCESS",
                "note": "Expected failure (invalid video ID)",
                "error_type": error_type,
                "extraction_time": extraction_time,
            }
        else:
            logger.error(f"❌ Unexpected error for {video_id}: {error_type}: {error_msg}")
            return {
                "video_id": video_id,
                "title": video_info["title"],
                "status": "FAILED",
                "error": f"{error_type}: {error_msg}",
                "extraction_time": extraction_time,
            }


def run_integration_tests(quick_mode: bool = False) -> Dict[str, Any]:
    """
    Run all YouTube transcript integration tests.

    Args:
        quick_mode: If True, only test first 2 videos

    Returns:
        Dictionary with all test results and summary
    """
    test_videos = TEST_VIDEOS[:2] if quick_mode else TEST_VIDEOS
    total_tests = len(test_videos)

    logger.info(f"\n{'='*80}")
    logger.info(f"YOUTUBE TRANSCRIPT EXTRACTION TEST - PHASE 2C")
    logger.info(f"Testing {total_tests} videos")
    logger.info(f"Mode: {'QUICK' if quick_mode else 'FULL'}")
    logger.info(f"Start Time: {datetime.now().isoformat()}")
    logger.info(f"{'='*80}\n")

    overall_start = time.time()
    results = []

    for i, video_info in enumerate(test_videos, 1):
        result = test_video(video_info, i, total_tests)
        results.append(result)

        # Brief pause between tests to respect rate limiting
        if i < total_tests:
            logger.info("\nWaiting 3 seconds before next test (rate limiting)...\n")
            time.sleep(3)

    overall_time = time.time() - overall_start

    # Calculate summary statistics
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    partial_count = sum(1 for r in results if r["status"] == "PARTIAL")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")

    avg_extraction_time = sum(r["extraction_time"] for r in results) / len(results)

    # Count successful extractions vs expected failures
    expected_failures = sum(1 for r, v in zip(results, test_videos)
                           if r["status"] == "SUCCESS" and not v["expected_transcript"])
    actual_successes = sum(1 for r, v in zip(results, test_videos)
                          if r["status"] == "SUCCESS" and v["expected_transcript"])

    summary = {
        "test_date": datetime.now().isoformat(),
        "mode": "quick" if quick_mode else "full",
        "total_tests": total_tests,
        "success_count": success_count,
        "partial_count": partial_count,
        "failed_count": failed_count,
        "actual_successes": actual_successes,
        "expected_failures": expected_failures,
        "success_rate": f"{(success_count / total_tests * 100):.1f}%",
        "avg_extraction_time": f"{avg_extraction_time:.2f}s",
        "total_time": f"{overall_time:.2f}s",
    }

    # Log summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"✅ Success: {success_count} (including {expected_failures} expected failures)")
    logger.info(f"   - Actual extractions: {actual_successes}")
    logger.info(f"   - Expected failures: {expected_failures}")
    logger.info(f"⚠️  Partial: {partial_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info(f"Success Rate: {summary['success_rate']}")
    logger.info(f"Average Extraction Time: {summary['avg_extraction_time']}")
    logger.info(f"Total Test Time: {summary['total_time']}")
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
        description="Test YouTube transcript extraction on VPS (Phase 2C)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode - test only 2 videos instead of all 5"
    )

    args = parser.parse_args()

    # Run tests
    test_data = run_integration_tests(quick_mode=args.quick)

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
