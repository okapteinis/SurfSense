"""
YouTube transcript extraction utilities with proxy support and Whisper ASR fallback.

This module provides robust YouTube transcript extraction with:
1. Proxy-enabled youtube-transcript-api with rate limiting and retry logic
2. Whisper ASR fallback for when API is blocked or transcripts unavailable
3. Unified interface that automatically falls back between strategies

See docs/youtube_transcript_issue.md for architecture details.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ratelimit import limits, sleep_and_retry

# Whisper and yt-dlp imports
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    yt_dlp = None

logger = logging.getLogger(__name__)


# Global Whisper model cache to avoid reloading on every request
_whisper_model = None


def _get_whisper_model():
    """
    Load and cache Whisper model globally.

    Returns:
        whisper.Whisper: Loaded Whisper model

    Raises:
        ImportError: If Whisper is not installed
    """
    global _whisper_model

    if not WHISPER_AVAILABLE:
        raise ImportError("Whisper is not installed. Run: pip install openai-whisper")

    if _whisper_model is None:
        model_name = os.getenv("WHISPER_MODEL", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        logger.info(f"Loading Whisper model '{model_name}' on device '{device}'...")
        _whisper_model = whisper.load_model(model_name, device=device)
        logger.info("Whisper model loaded successfully")

    return _whisper_model


@sleep_and_retry
@limits(calls=int(os.getenv("YOUTUBE_RATE_LIMIT", "10")), period=60)
@retry(
    retry=retry_if_exception_type((CouldNotRetrieveTranscript, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def get_youtube_transcript_with_proxy(video_id: str) -> list[dict]:
    """
    Fetch YouTube transcript using youtube-transcript-api with proxy and rate limiting.

    This function includes:
    - Rate limiting (configurable via YOUTUBE_RATE_LIMIT env var)
    - Exponential backoff retry (3 attempts with 2-10s delays)
    - Optional proxy support (via YOUTUBE_PROXY_URL env var)

    Args:
        video_id: YouTube video ID (e.g., "dQw4w9WgXcQ")

    Returns:
        List of transcript segments with format:
        [
            {'text': 'Hello world', 'start': 0.0, 'duration': 2.5},
            {'text': 'Next segment', 'start': 2.5, 'duration': 3.0},
            ...
        ]

    Raises:
        TranscriptsDisabled: Transcripts are disabled for this video
        NoTranscriptFound: No transcript available in any language
        VideoUnavailable: Video does not exist or is private
        CouldNotRetrieveTranscript: Generic retrieval failure (may be blocking)
    """
    logger.info(f"Attempting to fetch YouTube transcript for video {video_id}")

    # Check if proxy is enabled
    proxy_enabled = os.getenv("YOUTUBE_PROXY_ENABLED", "false").lower() == "true"
    proxy_url = os.getenv("YOUTUBE_PROXY_URL")

    try:
        if proxy_enabled and proxy_url:
            logger.debug(f"Using proxy: {proxy_url}")
            # youtube-transcript-api uses requests internally, so we set up proxies dict
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

            # Note: youtube-transcript-api doesn't directly expose proxy parameter
            # We need to monkey-patch the session or use environment variables
            # For now, we'll use the standard API and let OS environment handle proxy
            import os
            original_http_proxy = os.environ.get("HTTP_PROXY")
            original_https_proxy = os.environ.get("HTTPS_PROXY")

            try:
                os.environ["HTTP_PROXY"] = proxy_url
                os.environ["HTTPS_PROXY"] = proxy_url

                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            finally:
                # Restore original proxy settings
                if original_http_proxy:
                    os.environ["HTTP_PROXY"] = original_http_proxy
                else:
                    os.environ.pop("HTTP_PROXY", None)

                if original_https_proxy:
                    os.environ["HTTPS_PROXY"] = original_https_proxy
                else:
                    os.environ.pop("HTTPS_PROXY", None)
        else:
            # No proxy, direct connection
            logger.debug("Fetching transcript without proxy")
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        logger.info(f"Successfully fetched {len(transcript_list)} transcript segments via YouTube API")
        return transcript_list

    except TranscriptsDisabled as e:
        logger.warning(f"Transcripts are disabled for video {video_id}: {e}")
        raise

    except NoTranscriptFound as e:
        logger.warning(f"No transcript found for video {video_id}: {e}")
        raise

    except VideoUnavailable as e:
        logger.error(f"Video {video_id} is unavailable: {e}")
        raise

    except CouldNotRetrieveTranscript as e:
        logger.warning(f"Could not retrieve transcript for video {video_id}: {e}")
        logger.debug("This may indicate IP blocking or rate limiting by YouTube")
        raise

    except Exception as e:
        logger.error(f"Unexpected error fetching transcript for video {video_id}: {e}", exc_info=True)
        raise CouldNotRetrieveTranscript(video_id) from e


def get_youtube_transcript_with_whisper(video_url: str, video_id: str) -> list[dict]:
    """
    Transcribe YouTube video locally using Whisper ASR.

    This is the fallback method when youtube-transcript-api fails (blocked, unavailable, etc.).
    Process:
    1. Download audio-only using yt-dlp (~1-5 MB per minute)
    2. Load Whisper model (cached globally)
    3. Transcribe audio
    4. Format output to match YouTube API format
    5. Clean up temporary files

    Args:
        video_url: Full YouTube URL (e.g., "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        video_id: YouTube video ID (for logging)

    Returns:
        List of transcript segments with format matching YouTube API:
        [
            {'text': 'Hello world', 'start': 0.0, 'duration': 2.5},
            ...
        ]

    Raises:
        ImportError: If Whisper or yt-dlp not installed
        RuntimeError: If audio download or transcription fails
    """
    if not WHISPER_AVAILABLE:
        raise ImportError("Whisper is not installed. Run: pip install openai-whisper")

    if not YTDLP_AVAILABLE:
        raise ImportError("yt-dlp is not installed. Run: pip install yt-dlp")

    logger.info(f"Starting Whisper transcription for video {video_id}")

    audio_file = None
    try:
        # Step 1: Download audio using yt-dlp
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp_audio:
            audio_file = tmp_audio.name

        logger.debug(f"Downloading audio to {audio_file}")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': audio_file,
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'm4a',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Check if file exists and has content
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise RuntimeError(f"Audio file was not created: {audio_file}")

        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        logger.debug(f"Audio downloaded: {file_size_mb:.2f} MB")

        # Step 2: Load Whisper model
        model = _get_whisper_model()

        # Step 3: Transcribe audio
        logger.debug("Transcribing audio with Whisper...")
        result = model.transcribe(audio_file, verbose=False)

        # Step 4: Format output to match YouTube API format
        segments = []
        for segment in result["segments"]:
            segments.append({
                "text": segment["text"].strip(),
                "start": segment["start"],
                "duration": segment["end"] - segment["start"],
            })

        logger.info(f"Whisper transcription complete: {len(segments)} segments, "
                   f"total duration {result['segments'][-1]['end']:.1f}s")

        return segments

    except Exception as e:
        logger.error(f"Whisper transcription failed for video {video_id}: {e}", exc_info=True)
        raise RuntimeError(f"Whisper transcription failed: {e}") from e

    finally:
        # Step 5: Clean up temporary audio file
        if audio_file:
            try:
                audio_path = Path(audio_file)
                if audio_path.exists():
                    audio_path.unlink()
                    logger.debug(f"Cleaned up temporary audio file: {audio_file}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up audio file {audio_file}: {cleanup_error}")


def get_youtube_transcript(video_url: str, video_id: str) -> tuple[list[dict], str]:
    """
    Unified YouTube transcript fetcher with automatic fallback.

    Tries strategies in order:
    1. YouTube Transcript API (with proxy and retry)
    2. Whisper ASR local transcription (fallback)

    Args:
        video_url: Full YouTube URL
        video_id: YouTube video ID

    Returns:
        Tuple of (transcript_segments, method):
        - transcript_segments: List of dicts with 'text', 'start', 'duration'
        - method: String indicating which method succeeded ('youtube_api' or 'whisper')

    Raises:
        RuntimeError: If all methods fail
    """
    logger.info(f"Fetching transcript for YouTube video {video_id}")

    # Tier 1: Try YouTube Transcript API
    whisper_enabled = os.getenv("WHISPER_ENABLED", "true").lower() == "true"

    try:
        segments = get_youtube_transcript_with_proxy(video_id)
        logger.info(f"Successfully fetched transcript via YouTube API for {video_id}")
        return segments, "youtube_api"

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        # These are definitive failures - transcript truly unavailable
        logger.warning(f"YouTube API definitively failed for {video_id}: {type(e).__name__}: {e}")

        if not whisper_enabled:
            logger.error("Whisper fallback is disabled, cannot proceed")
            raise RuntimeError(f"YouTube transcript unavailable and Whisper disabled: {e}") from e

        logger.info("Transcripts unavailable via API, falling back to Whisper ASR")

    except (CouldNotRetrieveTranscript, ConnectionError, Exception) as e:
        # These may indicate blocking or temporary issues
        logger.warning(f"YouTube API blocked or failed for {video_id}: {type(e).__name__}: {e}")

        if not whisper_enabled:
            logger.error("Whisper fallback is disabled, cannot proceed")
            raise RuntimeError(f"YouTube API blocked and Whisper disabled: {e}") from e

        logger.info("YouTube API appears blocked, falling back to Whisper ASR")

    # Tier 2: Whisper ASR fallback
    try:
        segments = get_youtube_transcript_with_whisper(video_url, video_id)
        logger.info(f"Successfully transcribed via Whisper ASR for {video_id}")
        return segments, "whisper"

    except Exception as whisper_error:
        logger.error(f"All transcript methods failed for {video_id}. "
                    f"YouTube API failed, Whisper ASR failed: {whisper_error}")
        raise RuntimeError(
            f"Failed to fetch transcript via YouTube API or Whisper ASR: {whisper_error}"
        ) from whisper_error
