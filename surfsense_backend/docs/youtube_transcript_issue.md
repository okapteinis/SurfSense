# YouTube Transcript Extraction Issue

**Date:** January 2, 2026
**Status:** In Progress - Implementing Fallback Solution

---

## Problem Statement

YouTube transcript extraction is failing intermittently or consistently from VPS environment. Users report that transcripts cannot be retrieved for videos that clearly have captions available.

## Root Cause Analysis

The `youtube-transcript-api` library works by scraping YouTube web pages rather than using official YouTube Data API. This makes it vulnerable to:

### 1. **IP-based Blocking**
- Cloud provider IPs (like VPS at 46.62.230.195) are often flagged as bots by YouTube
- Datacenter IP ranges are known and blocked more aggressively than residential IPs
- Similar to Al Jazeera crawler issue, but YouTube's bot detection is more sophisticated

### 2. **Rate Limiting**
- Too many requests from same IP trigger temporary blocks
- YouTube enforces stricter limits on suspected bot traffic
- No backoff mechanism in current implementation

### 3. **Bot Detection**
YouTube uses sophisticated detection mechanisms including:
- **Browser fingerprinting**: Headless browsers have distinct fingerprints
- **Traffic pattern analysis**: Rapid sequential requests are suspicious
- **CAPTCHA challenges**: May be served to suspected bots
- **Geographic restrictions**: Some videos restrict transcripts by region

### 4. **API Method Vulnerabilities**
- The library scrapes HTML rather than using official API
- Changes to YouTube's page structure can break extraction
- No official support or guarantees

## Evidence

**Common Error Messages:**
```python
RequestBlocked: The request was blocked by YouTube
TranscriptsDisabled: Transcripts are disabled for this video (false positive when blocked)
NoTranscriptFound: Could not retrieve a transcript (timeout due to blocking)
CouldNotRetrieveTranscript: Generic failure (often blocking-related)
```

**Observed Patterns:**
- Works reliably from residential IPs (local development)
- Fails frequently from cloud IPs (VPS production)
- Success rate correlates with request frequency
- Blocking is often temporary (cleared after hours/days)

## Current Implementation

**Location:** `surfsense_backend/app/utils/youtube_utils.py` (to be created/located)

**Current Flow:**
1. Extract video ID from URL
2. Call `YouTubeTranscriptApi.get_transcript(video_id)`
3. Return transcript or propagate error

**Limitations:**
- ❌ No retry mechanism
- ❌ No proxy support
- ❌ No fallback when API fails
- ❌ No rate limiting protection
- ❌ No error differentiation (blocking vs. truly disabled)
- ❌ No caching to reduce requests

## Proposed Solution Architecture

Implement **multi-tier fallback system** with automatic degradation:

### Tier 1: YouTube Transcript API with Enhancements ⭐

**Improvements:**
- ✅ Add proxy support (configurable via `.env`)
- ✅ Implement rate limiting (max N requests per minute)
- ✅ Add exponential backoff retry (3 attempts with increasing delays)
- ✅ Better error handling and logging
- ✅ Distinguish between blocking errors and true unavailability

**Implementation:**
```python
@retry(
    retry=retry_if_exception_type(CouldNotRetrieveTranscript),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
@sleep_and_retry
@limits(calls=10, period=60)  # 10 requests per minute
async def get_youtube_transcript_with_proxy(video_id: str) -> list[dict]:
    # Try with proxy if configured
    # Retry with exponential backoff
    # Return transcript segments
```

### Tier 2: Whisper ASR Local Transcription (Fallback) 🎯

When Tier 1 fails due to blocking or unavailability:

**Process:**
1. Use `yt-dlp` to download audio-only (m4a/mp3, ~1-5 MB per minute)
2. Load Whisper model (base or small for speed/accuracy balance)
3. Transcribe audio locally on VPS
4. Format output to match YouTube transcript format
5. Delete temporary audio file

**Advantages:**
- ✅ No external API dependencies (after audio download)
- ✅ Works regardless of YouTube blocking
- ✅ High accuracy (Whisper models are state-of-the-art)
- ✅ Offline capability (after model download)

**Tradeoffs:**
- ⚠️ Slower than API (30-60s for 10-min video on CPU)
- ⚠️ Requires disk space for temporary audio files
- ⚠️ Requires Whisper model download (~100MB for base model)
- ⚠️ CPU-intensive (can use GPU if available)

**Implementation:**
```python
async def get_youtube_transcript_with_whisper(video_url: str, video_id: str) -> list[dict]:
    # Download audio with yt-dlp
    # Load Whisper model (cached globally)
    # Transcribe audio
    # Format segments: [{'text': '...', 'start': 0.0, 'duration': 2.5}]
    # Cleanup temporary files
```

### Tier 3: Premium Services (Future Enhancement) 💡

For future consideration if local transcription is insufficient:
- **AssemblyAI API**: Fast, accurate, paid ($0.65/hour of audio)
- **Rev.ai API**: Human-level accuracy, higher cost ($1.50/hour)
- **Google Speech-to-Text API**: Official Google solution, complex setup

Not implemented in this phase.

## Implementation Requirements

### Python Dependencies

Add to `requirements.txt` or `pyproject.toml`:
```txt
youtube-transcript-api>=0.6.0
yt-dlp>=2023.0.0
openai-whisper>=20230918
# Alternative: faster-whisper (faster inference, lower memory)
tenacity>=8.2.0  # Retry logic
ratelimit>=2.2.1  # Rate limiting
```

### Environment Variables

Add to `surfsense_backend/.env.example`:
```bash
# YouTube Transcript Configuration
YOUTUBE_PROXY_ENABLED=false
YOUTUBE_PROXY_URL=
YOUTUBE_RATE_LIMIT=10  # requests per minute

# Whisper ASR Fallback
WHISPER_ENABLED=true
WHISPER_MODEL=base  # tiny, base, small, medium, large
WHISPER_DEVICE=cpu  # or cuda for GPU
```

### System Dependencies (VPS)

Whisper requires `ffmpeg` for audio processing:
```bash
apt-get install ffmpeg  # Ubuntu/Debian
# Already installed on most systems
```

### Model Download (One-time)

On first run, Whisper will download model (~100 MB for base):
```python
# Automatic on first use:
model = whisper.load_model("base")  # Downloads to ~/.cache/whisper/
```

## Success Criteria

1. ✅ **95%+ transcript retrieval success rate**
   - Combine API success + Whisper fallback
   - Test with 20+ videos from VPS

2. ✅ **Fallback to Whisper when API blocked**
   - Automatic and transparent
   - Logged for monitoring

3. ✅ **Average processing time under 60 seconds**
   - API: <5 seconds (when successful)
   - Whisper: <60 seconds for 10-minute video on CPU

4. ✅ **Proper error handling and logging**
   - Clear distinction between blocking vs. unavailable
   - Debug logs for troubleshooting
   - No silent failures

5. ✅ **No temporary file leaks**
   - Clean up audio files even if transcription fails
   - Use try/finally blocks

6. ✅ **Format compatibility**
   - Whisper output matches YouTube API format
   - Consistent interface for consumers

## Testing Strategy

### Unit Tests
- Mock `YouTubeTranscriptApi` responses
- Test retry logic with simulated failures
- Test rate limiting enforcement
- Test Whisper output formatting

### Integration Tests
- Test with real short video (<2 min)
- Test API success path
- Test API failure → Whisper fallback
- Test cleanup of temporary files

### VPS Tests
- Test from production environment
- Verify proxy configuration (if enabled)
- Measure actual processing times
- Verify model caching works

## Performance Considerations

### Whisper Model Selection

| Model | Size | Speed (CPU) | Accuracy | Recommendation |
|-------|------|-------------|----------|----------------|
| tiny | 39 MB | ~5x realtime | Good | Testing only |
| base | 74 MB | ~3x realtime | Better | ⭐ Recommended |
| small | 244 MB | ~1x realtime | Best | If speed critical |
| medium | 769 MB | ~0.5x realtime | Excellent | GPU only |
| large | 1550 MB | ~0.3x realtime | Best | GPU only |

**Recommendation:** Use `base` model for production (good accuracy, acceptable speed).

### Memory Usage
- Whisper base model: ~1 GB RAM during inference
- Audio file: ~1 MB per minute of video
- Total peak: ~1.5 GB RAM

VPS has 30 GB RAM, so this is acceptable.

### Disk Usage
- Whisper model cache: ~100 MB (one-time)
- Temporary audio: ~5-10 MB per video (deleted after)
- Logs: Minimal

## Monitoring and Observability

Add logging to track:
- **API success rate**: How often Tier 1 succeeds
- **Whisper fallback rate**: How often we fall back
- **Processing times**: API vs. Whisper performance
- **Error types**: Differentiate blocking vs. unavailable

Example log messages:
```
INFO: Attempting YouTube API transcript for video dQw4w9WgXcQ
INFO: Successfully fetched 156 transcript segments via API
WARNING: YouTube API blocked for video abc123. Falling back to Whisper.
INFO: Whisper transcription complete: 89 segments, 45.2s processing time
ERROR: Both API and Whisper failed for video xyz789
```

## Migration Path

### Phase 1: Implementation (This PR)
- Implement proxy support for YouTube API
- Implement Whisper fallback
- Add configuration options
- Write comprehensive tests

### Phase 2: Deployment and Monitoring (Post-merge)
- Deploy to VPS
- Monitor success rates
- Tune rate limiting if needed
- Consider proxy service if API blocking persists

### Phase 3: Optimization (Future)
- Consider `faster-whisper` for better performance
- Implement caching layer for frequently accessed videos
- Add support for non-English transcripts
- Explore GPU acceleration if available

## Risks and Mitigation

### Risk 1: Whisper Processing Too Slow
**Mitigation:** Use async/background processing, show loading indicator to user

### Risk 2: YouTube Blocks yt-dlp Downloads
**Mitigation:** Similar to transcript API, yt-dlp is also scraping. May need proxy.

### Risk 3: Model Download Fails on VPS
**Mitigation:** Pre-download model during deployment, include in health checks

### Risk 4: Disk Space for Audio Files
**Mitigation:** Stream processing, delete immediately, monitor disk usage

## References

- YouTube Transcript API: https://github.com/jdepoix/youtube-transcript-api
- Whisper ASR: https://github.com/openai/whisper
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- Related Issue: Al Jazeera crawler (PR #303) - Similar blocking issue

---

**Status:** Ready for implementation
**Estimated Effort:** 2-3 hours
**Priority:** High (blocks YouTube connector functionality)
