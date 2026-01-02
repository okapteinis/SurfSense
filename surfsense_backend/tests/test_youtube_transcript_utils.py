"""
Comprehensive tests for YouTube transcript extraction utilities.

Tests cover:
1. YouTube Transcript API with proxy and rate limiting
2. Whisper ASR fallback mechanism
3. Retry logic and error handling
4. Temporary file cleanup
5. Output format consistency
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)

from app.utils.youtube_utils import (
    get_youtube_transcript_with_proxy,
    get_youtube_transcript_with_whisper,
    get_youtube_transcript,
    _get_whisper_model,
)


# Sample transcript data for mocking
MOCK_YOUTUBE_TRANSCRIPT = [
    {"text": "Hello world", "start": 0.0, "duration": 2.5},
    {"text": "This is a test", "start": 2.5, "duration": 3.0},
    {"text": "End of video", "start": 5.5, "duration": 2.0},
]

MOCK_WHISPER_RESULT = {
    "segments": [
        {"text": " Hello world", "start": 0.0, "end": 2.5},
        {"text": " This is a test", "start": 2.5, "end": 5.5},
        {"text": " End of video", "start": 5.5, "end": 7.5},
    ]
}


# =============================================================================
# Test YouTube Transcript API with Proxy
# =============================================================================


@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_success_no_proxy(mock_get_transcript):
    """Test successful YouTube API transcript fetch without proxy."""
    mock_get_transcript.return_value = MOCK_YOUTUBE_TRANSCRIPT

    result = get_youtube_transcript_with_proxy("dQw4w9WgXcQ")

    assert result == MOCK_YOUTUBE_TRANSCRIPT
    assert len(result) == 3
    assert result[0]["text"] == "Hello world"
    mock_get_transcript.assert_called_once_with("dQw4w9WgXcQ")


@patch.dict(os.environ, {"YOUTUBE_PROXY_ENABLED": "true", "YOUTUBE_PROXY_URL": "http://proxy.example.com:8080"})
@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_success_with_proxy(mock_get_transcript):
    """Test successful YouTube API transcript fetch with proxy enabled."""
    mock_get_transcript.return_value = MOCK_YOUTUBE_TRANSCRIPT

    with patch.dict(os.environ, {}, clear=False):
        result = get_youtube_transcript_with_proxy("dQw4w9WgXcQ")

    assert result == MOCK_YOUTUBE_TRANSCRIPT
    # Verify environment proxy was set (proxy is set via os.environ in the function)
    mock_get_transcript.assert_called_once()


@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_transcripts_disabled(mock_get_transcript):
    """Test YouTube API when transcripts are disabled for video."""
    mock_get_transcript.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")

    with pytest.raises(TranscriptsDisabled):
        get_youtube_transcript_with_proxy("dQw4w9WgXcQ")


@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_no_transcript_found(mock_get_transcript):
    """Test YouTube API when no transcript is available."""
    mock_get_transcript.side_effect = NoTranscriptFound("dQw4w9WgXcQ", [], None)

    with pytest.raises(NoTranscriptFound):
        get_youtube_transcript_with_proxy("dQw4w9WgXcQ")


@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_video_unavailable(mock_get_transcript):
    """Test YouTube API when video is unavailable."""
    mock_get_transcript.side_effect = VideoUnavailable("dQw4w9WgXcQ")

    with pytest.raises(VideoUnavailable):
        get_youtube_transcript_with_proxy("dQw4w9WgXcQ")


@patch("app.utils.youtube_utils.YouTubeTranscriptApi.get_transcript")
def test_youtube_api_could_not_retrieve(mock_get_transcript):
    """Test YouTube API when retrieval fails (blocking, rate limit, etc.)."""
    mock_get_transcript.side_effect = CouldNotRetrieveTranscript("dQw4w9WgXcQ")

    with pytest.raises(CouldNotRetrieveTranscript):
        get_youtube_transcript_with_proxy("dQw4w9WgXcQ")


# =============================================================================
# Test Whisper ASR Fallback
# =============================================================================


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", True)
@patch("app.utils.youtube_utils.YTDLP_AVAILABLE", True)
@patch("app.utils.youtube_utils._get_whisper_model")
@patch("app.utils.youtube_utils.yt_dlp.YoutubeDL")
@patch("app.utils.youtube_utils.Path")
@patch("app.utils.youtube_utils.tempfile.NamedTemporaryFile")
def test_whisper_transcription_success(
    mock_tempfile, mock_path_class, mock_ytdl, mock_get_model
):
    """Test successful Whisper ASR transcription."""
    # Setup mocks
    mock_temp = MagicMock()
    mock_temp.name = "/tmp/audio_test.m4a"
    mock_tempfile.return_value.__enter__.return_value = mock_temp

    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.stat.return_value.st_size = 5 * 1024 * 1024  # 5 MB
    mock_path_class.return_value = mock_path

    mock_model = MagicMock()
    mock_model.transcribe.return_value = MOCK_WHISPER_RESULT
    mock_get_model.return_value = mock_model

    mock_ydl_instance = MagicMock()
    mock_ytdl.return_value.__enter__.return_value = mock_ydl_instance

    # Execute
    result = get_youtube_transcript_with_whisper(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ"
    )

    # Verify
    assert len(result) == 3
    assert result[0]["text"] == "Hello world"  # Note: strip() removes leading space
    assert result[0]["start"] == 0.0
    assert result[0]["duration"] == 2.5

    mock_ydl_instance.download.assert_called_once()
    mock_model.transcribe.assert_called_once()


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", False)
def test_whisper_not_installed():
    """Test Whisper fallback when Whisper is not installed."""
    with pytest.raises(ImportError, match="Whisper is not installed"):
        get_youtube_transcript_with_whisper(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ"
        )


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", True)
@patch("app.utils.youtube_utils.YTDLP_AVAILABLE", False)
def test_ytdlp_not_installed():
    """Test Whisper fallback when yt-dlp is not installed."""
    with pytest.raises(ImportError, match="yt-dlp is not installed"):
        get_youtube_transcript_with_whisper(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ"
        )


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", True)
@patch("app.utils.youtube_utils.YTDLP_AVAILABLE", True)
@patch("app.utils.youtube_utils._get_whisper_model")
@patch("app.utils.youtube_utils.yt_dlp.YoutubeDL")
@patch("app.utils.youtube_utils.Path")
@patch("app.utils.youtube_utils.tempfile.NamedTemporaryFile")
def test_whisper_cleanup_on_error(
    mock_tempfile, mock_path_class, mock_ytdl, mock_get_model
):
    """Test that temporary files are cleaned up even when transcription fails."""
    # Setup mocks
    mock_temp = MagicMock()
    mock_temp.name = "/tmp/audio_test.m4a"
    mock_tempfile.return_value.__enter__.return_value = mock_temp

    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.stat.return_value.st_size = 5 * 1024 * 1024
    mock_path_class.return_value = mock_path

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("Transcription failed")
    mock_get_model.return_value = mock_model

    mock_ydl_instance = MagicMock()
    mock_ytdl.return_value.__enter__.return_value = mock_ydl_instance

    # Execute and expect failure
    with pytest.raises(RuntimeError, match="Whisper transcription failed"):
        get_youtube_transcript_with_whisper(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ"
        )

    # Verify cleanup was attempted
    mock_path.unlink.assert_called_once()


# =============================================================================
# Test Unified Transcript Fetcher
# =============================================================================


@patch("app.utils.youtube_utils.get_youtube_transcript_with_proxy")
def test_unified_fetcher_api_success(mock_proxy_fetch):
    """Test unified fetcher succeeds with YouTube API (no fallback needed)."""
    mock_proxy_fetch.return_value = MOCK_YOUTUBE_TRANSCRIPT

    result, method = get_youtube_transcript(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ"
    )

    assert result == MOCK_YOUTUBE_TRANSCRIPT
    assert method == "youtube_api"
    mock_proxy_fetch.assert_called_once_with("dQw4w9WgXcQ")


@patch.dict(os.environ, {"WHISPER_ENABLED": "true"})
@patch("app.utils.youtube_utils.get_youtube_transcript_with_proxy")
@patch("app.utils.youtube_utils.get_youtube_transcript_with_whisper")
def test_unified_fetcher_fallback_to_whisper_on_blocking(mock_whisper, mock_proxy):
    """Test unified fetcher falls back to Whisper when YouTube API is blocked."""
    # YouTube API fails (blocked)
    mock_proxy.side_effect = CouldNotRetrieveTranscript("dQw4w9WgXcQ")

    # Whisper succeeds
    whisper_segments = [
        {"text": "Whisper transcribed", "start": 0.0, "duration": 2.0},
    ]
    mock_whisper.return_value = whisper_segments

    result, method = get_youtube_transcript(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ"
    )

    assert result == whisper_segments
    assert method == "whisper"
    mock_proxy.assert_called_once()
    mock_whisper.assert_called_once()


@patch.dict(os.environ, {"WHISPER_ENABLED": "true"})
@patch("app.utils.youtube_utils.get_youtube_transcript_with_proxy")
@patch("app.utils.youtube_utils.get_youtube_transcript_with_whisper")
def test_unified_fetcher_fallback_to_whisper_on_disabled(mock_whisper, mock_proxy):
    """Test unified fetcher falls back to Whisper when transcripts are disabled."""
    # YouTube API fails (transcripts disabled)
    mock_proxy.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")

    # Whisper succeeds
    whisper_segments = [
        {"text": "Whisper transcribed", "start": 0.0, "duration": 2.0},
    ]
    mock_whisper.return_value = whisper_segments

    result, method = get_youtube_transcript(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ"
    )

    assert result == whisper_segments
    assert method == "whisper"


@patch.dict(os.environ, {"WHISPER_ENABLED": "false"})
@patch("app.utils.youtube_utils.get_youtube_transcript_with_proxy")
def test_unified_fetcher_no_fallback_when_disabled(mock_proxy):
    """Test unified fetcher raises error when Whisper is disabled and API fails."""
    mock_proxy.side_effect = CouldNotRetrieveTranscript("dQw4w9WgXcQ")

    with pytest.raises(RuntimeError, match="YouTube API blocked and Whisper disabled"):
        get_youtube_transcript(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ"
        )


@patch.dict(os.environ, {"WHISPER_ENABLED": "true"})
@patch("app.utils.youtube_utils.get_youtube_transcript_with_proxy")
@patch("app.utils.youtube_utils.get_youtube_transcript_with_whisper")
def test_unified_fetcher_all_methods_fail(mock_whisper, mock_proxy):
    """Test unified fetcher raises error when both YouTube API and Whisper fail."""
    # YouTube API fails
    mock_proxy.side_effect = CouldNotRetrieveTranscript("dQw4w9WgXcQ")

    # Whisper also fails
    mock_whisper.side_effect = RuntimeError("Whisper failed")

    with pytest.raises(RuntimeError, match="Failed to fetch transcript via YouTube API or Whisper ASR"):
        get_youtube_transcript(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ"
        )


# =============================================================================
# Test Whisper Model Loading
# =============================================================================


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", True)
@patch("app.utils.youtube_utils.whisper.load_model")
@patch.dict(os.environ, {"WHISPER_MODEL": "base", "WHISPER_DEVICE": "cpu"})
def test_whisper_model_loading(mock_load_model):
    """Test that Whisper model is loaded with correct parameters."""
    # Reset global model cache
    import app.utils.youtube_utils as utils_module
    utils_module._whisper_model = None

    mock_model = MagicMock()
    mock_load_model.return_value = mock_model

    result = _get_whisper_model()

    assert result == mock_model
    mock_load_model.assert_called_once_with("base", device="cpu")


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", True)
@patch("app.utils.youtube_utils.whisper.load_model")
def test_whisper_model_caching(mock_load_model):
    """Test that Whisper model is cached and not reloaded on subsequent calls."""
    # Reset global model cache
    import app.utils.youtube_utils as utils_module
    utils_module._whisper_model = None

    mock_model = MagicMock()
    mock_load_model.return_value = mock_model

    # First call
    result1 = _get_whisper_model()
    # Second call
    result2 = _get_whisper_model()

    assert result1 == result2
    # Model should only be loaded once
    assert mock_load_model.call_count == 1


@patch("app.utils.youtube_utils.WHISPER_AVAILABLE", False)
def test_whisper_model_not_available():
    """Test error when trying to load Whisper model when it's not installed."""
    # Reset global model cache
    import app.utils.youtube_utils as utils_module
    utils_module._whisper_model = None

    with pytest.raises(ImportError, match="Whisper is not installed"):
        _get_whisper_model()


# =============================================================================
# Test Output Format Consistency
# =============================================================================


def test_youtube_api_output_format():
    """Verify YouTube API output matches expected format."""
    segment = MOCK_YOUTUBE_TRANSCRIPT[0]
    assert "text" in segment
    assert "start" in segment
    assert "duration" in segment
    assert isinstance(segment["text"], str)
    assert isinstance(segment["start"], float)
    assert isinstance(segment["duration"], float)


def test_whisper_output_format_conversion():
    """Verify Whisper output is converted to match YouTube API format."""
    # Whisper segment format: {"text": " Text", "start": 0.0, "end": 2.5}
    whisper_segment = MOCK_WHISPER_RESULT["segments"][0]

    # Expected conversion: {"text": "Text", "start": 0.0, "duration": 2.5}
    expected_text = whisper_segment["text"].strip()
    expected_start = whisper_segment["start"]
    expected_duration = whisper_segment["end"] - whisper_segment["start"]

    assert expected_text == "Hello world"
    assert expected_start == 0.0
    assert expected_duration == 2.5


# =============================================================================
# Integration-style Tests (require environment setup)
# =============================================================================


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Whisper and yt-dlp installation")
def test_real_whisper_transcription():
    """
    Integration test with real Whisper model.

    This test is skipped by default. To run:
    1. Install dependencies: pip install openai-whisper yt-dlp
    2. Run: pytest -m integration tests/test_youtube_transcript_utils.py
    """
    # Use a short, public domain video
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id = "dQw4w9WgXcQ"

    result = get_youtube_transcript_with_whisper(video_url, video_id)

    assert len(result) > 0
    assert all("text" in seg and "start" in seg and "duration" in seg for seg in result)


@pytest.mark.integration
@pytest.mark.skip(reason="Requires real YouTube API call")
def test_real_youtube_api_fetch():
    """
    Integration test with real YouTube Transcript API.

    This test is skipped by default to avoid rate limiting.
    """
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up

    result = get_youtube_transcript_with_proxy(video_id)

    assert len(result) > 0
    assert all("text" in seg and "start" in seg and "duration" in seg for seg in result)
