"""
YouTube video document processor.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

import aiohttp
import yt_dlp
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp.utils import DownloadError

from app.db import Document, DocumentType
from app.services.llm_service import get_user_long_context_llm
from app.services.stt_service import stt_service
from app.services.task_logging_service import TaskLoggingService
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)

from .base import (
    check_document_by_unique_identifier,
)


def get_youtube_video_id(url: str) -> str | None:
    """
    Extract video ID from various YouTube URL formats.

    Args:
        url: YouTube URL

    Returns:
        Video ID if found, None otherwise
    """
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname

    if hostname == "youtu.be":
        return parsed_url.path[1:]
    if hostname in ("www.youtube.com", "youtube.com"):
        if parsed_url.path == "/watch":
            query_params = parse_qs(parsed_url.query)
            return query_params.get("v", [None])[0]
        if parsed_url.path.startswith("/embed/"):
            return parsed_url.path.split("/")[2]
        if parsed_url.path.startswith("/v/"):
            return parsed_url.path.split("/")[2]
    return None


logger = logging.getLogger(__name__)


def extract_audio_and_transcribe(video_url: str, video_id: str) -> dict:
    """
    Download audio from YouTube video and transcribe using STT service.

    This function runs synchronously and should be called via asyncio.to_thread().

    Configuration (via environment variables):
        YOUTUBE_MIN_DISK_SPACE_GB: Minimum free disk space in GB (default: 1)
        YOUTUBE_AUDIO_QUALITY: Audio bitrate in kbps (default: 96)
            Lower quality reduces file size and processing time but may impact
            transcription accuracy for noisy audio. 96kbps is optimized for speech.
        YOUTUBE_MAX_FILESIZE_MB: Maximum audio file size in decimal megabytes/MB (10^6 bytes, default: 500)
            Prevents resource exhaustion from extremely large audio files.

    Args:
        video_url: Full YouTube video URL
        video_id: YouTube video ID for logging

    Returns:
        Dictionary with 'text' (transcribed text) and 'language' (detected language),
        or empty dict if transcription fails. Empty dict allows fallback to subtitle
        transcription if available.
    """
    logger.info(f"Extracting audio and transcribing video {video_id}")

    # Task 6: Check ffmpeg availability - warn instead of error to allow subtitle fallback
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=10  # Task 8: Increased from 5s to prevent false negatives on slow systems
        )
    except FileNotFoundError:
        logger.warning(
            "ffmpeg not found - YouTube STT fallback unavailable. "
            "Install ffmpeg to enable audio transcription for videos without subtitles."
        )
        return {}
    except subprocess.CalledProcessError as e:
        logger.warning(f"ffmpeg check failed: {e}. STT fallback unavailable.")
        return {}
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg version check timed out. STT fallback may be unavailable.")
        return {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Task 2: Make disk space threshold configurable
        min_space_gb_str = os.getenv("YOUTUBE_MIN_DISK_SPACE_GB", "1")
        try:
            min_space_gb = int(min_space_gb_str)
        except ValueError:
            logger.warning(
                f"Invalid YOUTUBE_MIN_DISK_SPACE_GB value '{min_space_gb_str}', using default 1GB. "
                "Ensure the environment variable contains only numeric characters."
            )
            min_space_gb = 1
        # Use 1000^3 (decimal gigabytes) to match the "GB" naming convention
        # not 1024^3 (binary gibibytes/GiB)
        min_space_bytes = min_space_gb * 1_000_000_000

        stat = shutil.disk_usage(tmp_dir)
        if stat.free < min_space_bytes:
            logger.error(
                f"Insufficient disk space for video {video_id}: "
                f"{stat.free / 1_000_000_000:.2f}GB free, need at least {min_space_gb}GB. "
                f"Free up disk space in temp directory or adjust YOUTUBE_MIN_DISK_SPACE_GB "
                f"environment variable."
            )
            return {}

        # Task 1: Fix audio path construction - use explicit base path
        audio_base = os.path.join(tmp_dir, "audio")
        audio_path = audio_base + ".wav"

        # Task 3: Make audio quality configurable
        # Lower quality reduces file size and processing time but may impact
        # transcription accuracy for noisy audio. 96kbps is optimized for speech.
        audio_quality = os.getenv("YOUTUBE_AUDIO_QUALITY", "96")

        # Task 6: Make max filesize configurable
        # Configure via YOUTUBE_MAX_FILESIZE_MB environment variable (default: 500MB)
        # Prevents resource exhaustion from extremely large audio files
        max_filesize_mb_str = os.getenv("YOUTUBE_MAX_FILESIZE_MB", "500")
        try:
            max_filesize_mb = int(max_filesize_mb_str)
        except ValueError:
            logger.warning(
                f"Invalid YOUTUBE_MAX_FILESIZE_MB value '{max_filesize_mb_str}', using default 500MB. "
                "Ensure the environment variable contains only numeric characters."
            )
            max_filesize_mb = 500
        MAX_AUDIO_FILESIZE_BYTES = max_filesize_mb * 1_000_000

        # Task 6: Add max filesize limit & Task 3: Configurable quality
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": audio_quality,
                }
            ],
            "outtmpl": audio_base,  # No extension - yt-dlp adds it
            "quiet": True,
            "no_warnings": True,
            "max_filesize": MAX_AUDIO_FILESIZE_BYTES,
        }

        try:
            # Task 7 & 11: Download audio with specific error handling
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
            except DownloadError as e:
                # Task 7: Check for filesize limit errors specifically
                error_str = str(e).lower()
                if "filesize" in error_str or "file size" in error_str or "too large" in error_str:
                    logger.error(
                        f"Video {video_id} audio exceeds configured size limit ({max_filesize_mb}MB). "
                        f"Adjust YOUTUBE_MAX_FILESIZE_MB environment variable if needed."
                    )
                else:
                    logger.error(f"yt-dlp failed to download video {video_id}: {e}")
                return {}

            # Verify audio file was created
            if not os.path.exists(audio_path):
                logger.error(
                    f"Audio file not found after download for video {video_id}"
                )
                return {}

            # Log file size for monitoring
            file_size = os.path.getsize(audio_path)
            logger.info(
                f"Downloaded audio for video {video_id}: "
                f"{file_size / 1_000_000:.2f}MB"
            )

            # Task 7: Separate STT error handling from download errors
            try:
                logger.info(f"Transcribing audio for video {video_id}")
                result = stt_service.transcribe_file(audio_path)

                transcript_text = result.get("text", "")
                language = result.get("language", "unknown")

                logger.info(
                    f"Successfully transcribed {len(transcript_text)} characters "
                    f"from video {video_id} (detected language: {language})"
                )

                # Task 8: Return language info for storage
                return {
                    "text": transcript_text,
                    "language": language
                }

            except Exception as e:
                logger.error(
                    f"STT transcription failed for video {video_id}: {e}",
                    exc_info=True
                )
                return {}

        except Exception as e:
            logger.error(
                f"Unexpected error during audio extraction for video {video_id}: {e}",
                exc_info=True,
            )
            return {}


async def add_youtube_video_document(
    session: AsyncSession, url: str, search_space_id: int, user_id: str
) -> Document:
    """
    Process a YouTube video URL, extract transcripts, and store as a document.

    Args:
        session: Database session for storing the document
        url: YouTube video URL (supports standard, shortened, and embed formats)
        search_space_id: ID of the search space to add the document to
        user_id: ID of the user

    Returns:
        Document: The created document object

    Raises:
        ValueError: If the YouTube video ID cannot be extracted from the URL
        SQLAlchemyError: If there's a database error
        RuntimeError: If the video processing fails
    """
    task_logger = TaskLoggingService(session, search_space_id)

    # Log task start
    log_entry = await task_logger.log_task_start(
        task_name="youtube_video_document",
        source="background_task",
        message=f"Starting YouTube video processing for: {url}",
        metadata={"url": url, "user_id": str(user_id)},
    )

    try:
        # Extract video ID from URL
        await task_logger.log_task_progress(
            log_entry,
            f"Extracting video ID from URL: {url}",
            {"stage": "video_id_extraction"},
        )

        # Get video ID
        video_id = get_youtube_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        await task_logger.log_task_progress(
            log_entry,
            f"Video ID extracted: {video_id}",
            {"stage": "video_id_extracted", "video_id": video_id},
        )

        # Get video metadata
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching video metadata for: {video_id}",
            {"stage": "metadata_fetch"},
        )

        params = {
            "format": "json",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        oembed_url = "https://www.youtube.com/oembed"

        async with (
            aiohttp.ClientSession() as http_session,
            http_session.get(oembed_url, params=params) as response,
        ):
            video_data = await response.json()

        await task_logger.log_task_progress(
            log_entry,
            f"Video metadata fetched: {video_data.get('title', 'Unknown')}",
            {
                "stage": "metadata_fetched",
                "title": video_data.get("title"),
                "author": video_data.get("author_name"),
            },
        )

        # Get video transcript
        await task_logger.log_task_progress(
            log_entry,
            f"Fetching transcript for video: {video_id}",
            {"stage": "transcript_fetch"},
        )

        try:
            ytt_api = YouTubeTranscriptApi()
            captions = ytt_api.fetch(video_id)
            # Include complete caption information with timestamps
            transcript_segments = []
            for line in captions:
                start_time = line.start
                duration = line.duration
                text = line.text
                timestamp = f"[{start_time:.2f}s-{start_time + duration:.2f}s]"
                transcript_segments.append(f"{timestamp} {text}")
            transcript_text = "\n".join(transcript_segments)

            await task_logger.log_task_progress(
                log_entry,
                f"Transcript fetched successfully: {len(captions)} segments",
                {
                    "stage": "transcript_fetched",
                    "segments_count": len(captions),
                    "transcript_length": len(transcript_text),
                },
            )
        except Exception as e:
            # No subtitles available - attempt STT fallback
            await task_logger.log_task_progress(
                log_entry,
                f"No subtitles found for video {video_id}, attempting STT transcription",
                {"stage": "stt_fallback_attempt", "subtitle_error": str(e)},
            )
            logger.info(
                f"No subtitles found for video {video_id}, attempting STT transcription"
            )

            video_url = f"https://www.youtube.com/watch?v={video_id}"

            # Task 4: Add timeout handling for large video downloads (15 minutes)
            try:
                stt_result = await asyncio.wait_for(
                    asyncio.to_thread(
                        extract_audio_and_transcribe, video_url, video_id
                    ),
                    timeout=900.0  # 15 minutes
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"STT transcription timed out for video {video_id} after 15 minutes"
                )
                await task_logger.log_task_progress(
                    log_entry,
                    f"STT transcription timed out for video {video_id}",
                    {"stage": "stt_transcription_timeout"},
                )
                stt_result = {}

            # Task 8: Extract text and detected language from result
            transcript_text = stt_result.get("text", "")
            detected_language = stt_result.get("language", "unknown")

            if transcript_text:
                await task_logger.log_task_progress(
                    log_entry,
                    f"Successfully obtained transcript via STT for video {video_id}",
                    {
                        "stage": "stt_transcription_success",
                        "transcript_length": len(transcript_text),
                        "detected_language": detected_language,
                    },
                )
                logger.info(
                    f"Successfully obtained transcript via STT for video {video_id} "
                    f"(detected language: {detected_language})"
                )
                # Task 8: Store detected language in video metadata
                video_data["detected_language"] = detected_language
            else:
                transcript_text = f"No captions available for this video. Subtitle error: {e!s}. STT transcription also failed."
                await task_logger.log_task_progress(
                    log_entry,
                    f"STT transcription also failed for video {video_id}",
                    {"stage": "stt_transcription_failed"},
                )
                logger.warning(
                    f"STT transcription also failed for video {video_id}"
                )

        # Format document
        await task_logger.log_task_progress(
            log_entry,
            f"Processing video content: {video_data.get('title', 'YouTube Video')}",
            {"stage": "content_processing"},
        )

        # Format document metadata in a more maintainable way
        metadata_sections = [
            (
                "METADATA",
                [
                    f"TITLE: {video_data.get('title', 'YouTube Video')}",
                    f"URL: {url}",
                    f"VIDEO_ID: {video_id}",
                    f"AUTHOR: {video_data.get('author_name', 'Unknown')}",
                    f"THUMBNAIL: {video_data.get('thumbnail_url', '')}",
                ],
            ),
            (
                "CONTENT",
                ["FORMAT: transcript", "TEXT_START", transcript_text, "TEXT_END"],
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

        # Generate unique identifier hash for this YouTube video
        unique_identifier_hash = generate_unique_identifier_hash(
            DocumentType.YOUTUBE_VIDEO, video_id, search_space_id
        )

        # Generate content hash
        content_hash = generate_content_hash(combined_document_string, search_space_id)

        # Check if document with this unique identifier already exists
        await task_logger.log_task_progress(
            log_entry,
            f"Checking for existing video: {video_id}",
            {"stage": "duplicate_check", "video_id": video_id},
        )

        existing_document = await check_document_by_unique_identifier(
            session, unique_identifier_hash
        )

        if existing_document:
            # Document exists - check if content has changed
            if existing_document.content_hash == content_hash:
                await task_logger.log_task_success(
                    log_entry,
                    f"YouTube video document unchanged: {video_data.get('title', 'YouTube Video')}",
                    {
                        "duplicate_detected": True,
                        "existing_document_id": existing_document.id,
                        "video_id": video_id,
                    },
                )
                logging.info(
                    f"Document for YouTube video {video_id} unchanged. Skipping."
                )
                return existing_document
            else:
                # Content has changed - update the existing document
                logging.info(
                    f"Content changed for YouTube video {video_id}. Updating document."
                )
                await task_logger.log_task_progress(
                    log_entry,
                    f"Updating YouTube video document: {video_data.get('title', 'YouTube Video')}",
                    {"stage": "document_update", "video_id": video_id},
                )

        # Get LLM for summary generation (needed for both create and update)
        await task_logger.log_task_progress(
            log_entry,
            f"Preparing for summary generation: {video_data.get('title', 'YouTube Video')}",
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
            f"Generating summary for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "summary_generation"},
        )

        # Generate summary with metadata
        document_metadata = {
            "url": url,
            "video_id": video_id,
            "title": video_data.get("title", "YouTube Video"),
            "author": video_data.get("author_name", "Unknown"),
            "thumbnail": video_data.get("thumbnail_url", ""),
            "document_type": "YouTube Video Document",
            "has_transcript": "No captions available" not in transcript_text,
        }
        summary_content, summary_embedding = await generate_document_summary(
            combined_document_string, user_llm, document_metadata
        )

        # Process chunks
        await task_logger.log_task_progress(
            log_entry,
            f"Processing content chunks for video: {video_data.get('title', 'YouTube Video')}",
            {"stage": "chunk_processing"},
        )

        chunks = await create_document_chunks(combined_document_string)

        # Update or create document
        if existing_document:
            # Update existing document
            await task_logger.log_task_progress(
                log_entry,
                f"Updating YouTube video document in database: {video_data.get('title', 'YouTube Video')}",
                {"stage": "document_update", "chunks_count": len(chunks)},
            )

            existing_document.title = video_data.get("title", "YouTube Video")
            existing_document.content = summary_content
            existing_document.content_hash = content_hash
            existing_document.embedding = summary_embedding
            existing_document.document_metadata = {
                "url": url,
                "video_id": video_id,
                "video_title": video_data.get("title", "YouTube Video"),
                "author": video_data.get("author_name", "Unknown"),
                "thumbnail": video_data.get("thumbnail_url", ""),
            }
            existing_document.chunks = chunks

            await session.commit()
            await session.refresh(existing_document)
            document = existing_document
        else:
            # Create new document
            await task_logger.log_task_progress(
                log_entry,
                f"Creating YouTube video document in database: {video_data.get('title', 'YouTube Video')}",
                {"stage": "document_creation", "chunks_count": len(chunks)},
            )

            document = Document(
                title=video_data.get("title", "YouTube Video"),
                document_type=DocumentType.YOUTUBE_VIDEO,
                document_metadata={
                    "url": url,
                    "video_id": video_id,
                    "video_title": video_data.get("title", "YouTube Video"),
                    "author": video_data.get("author_name", "Unknown"),
                    "thumbnail": video_data.get("thumbnail_url", ""),
                },
                content=summary_content,
                embedding=summary_embedding,
                chunks=chunks,
                search_space_id=search_space_id,
                content_hash=content_hash,
                unique_identifier_hash=unique_identifier_hash,
            )

            session.add(document)
            await session.commit()
            await session.refresh(document)

        # Log success
        await task_logger.log_task_success(
            log_entry,
            f"Successfully processed YouTube video: {video_data.get('title', 'YouTube Video')}",
            {
                "document_id": document.id,
                "video_id": video_id,
                "title": document.title,
                "content_hash": content_hash,
                "chunks_count": len(chunks),
                "summary_length": len(summary_content),
                "has_transcript": "No captions available" not in transcript_text,
            },
        )

        return document
    except SQLAlchemyError as db_error:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Database error while processing YouTube video: {url}",
            str(db_error),
            {
                "error_type": "SQLAlchemyError",
                "video_id": video_id if "video_id" in locals() else None,
            },
        )
        raise db_error
    except Exception as e:
        await session.rollback()
        await task_logger.log_task_failure(
            log_entry,
            f"Failed to process YouTube video: {url}",
            str(e),
            {
                "error_type": type(e).__name__,
                "video_id": video_id if "video_id" in locals() else None,
            },
        )
        logging.error(f"Failed to process YouTube video: {e!s}")
        raise
