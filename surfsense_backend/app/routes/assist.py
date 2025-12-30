import hashlib
import logging
import os
import re
import time

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any, AsyncGenerator, Dict, Literal, Optional

from app.db import User, UserSearchSpacePreference, get_async_session
from app.dependencies.limiter import limiter
from app.services.llm_service import get_user_llm_instance, LLMRole
from app.users import current_active_user
from app.utils.logger import get_logger
from app.utils.sensitive_data_filter import sanitize_exception_message

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/assist", tags=["assist"])

# Task 1: slowapi compatibility note
# slowapi is compatible with FastAPI async endpoints and streaming responses.
# Tested with FastAPI 0.115+ and works correctly with Server-Sent Events (SSE).
# The rate limiter uses the first Request parameter to extract client IP.

# Configuration constants (Task 12)
# Input validation limits
MAX_INPUT_LENGTH = 10000
MAX_CONTEXT_LENGTH = 10000

# Cache configuration
# Environment-configurable for production flexibility
CACHE_MAX_SIZE = int(os.getenv("AI_ASSIST_CACHE_MAX_SIZE", "1000"))
CACHE_TTL_SECONDS = int(os.getenv("AI_ASSIST_CACHE_TTL", "3600"))  # 1 hour default

# Task 7: TTL-based response cache
# Caches responses to reduce LLM costs and improve latency for repeated requests
# Max size prevents unbounded memory growth, TTL ensures fresh responses
_response_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)


# Task 8: Prompt injection detection
def contains_prompt_injection(text: str) -> bool:
    """
    Detect potential prompt injection attempts in user input.

    Checks for suspicious patterns that might manipulate the LLM:
    - System instructions ("ignore previous", "disregard", "new instructions")
    - Role manipulation attempts
    - Command injection patterns

    Returns:
        True if suspicious patterns detected, False otherwise
    """
    if not text:
        return False

    text_lower = text.lower()
    suspicious_patterns = [
        r"ignore\s+(previous|all|above)",
        r"disregard\s+(previous|all|above)",
        r"forget\s+(previous|all|above)",
        r"new\s+instructions?:",
        r"system\s*:",
        r"assistant\s*:",
        r"<\s*system\s*>",
        r"act\s+as\s+if",
        r"pretend\s+(you|to)\s+are",
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, text_lower):
            logger.warning(
                "prompt_injection_detected",
                pattern=pattern,
                text_preview=text[:100]
            )
            return True

    return False


# Helper function for cache key generation
def generate_cache_key(command: str, user_input: Optional[str], context: Optional[str]) -> str:
    """
    Generate deterministic cache key for request caching.

    Uses SHA256 hash of command, user_input, and context to create a unique
    key for caching LLM responses. Same inputs always produce the same key.

    Args:
        command: The command type (draft, improve, shorten, etc.)
        user_input: User's input text (optional)
        context: Additional context (optional)

    Returns:
        64-character hexadecimal cache key (SHA256 hash)
    """
    cache_string = f"{command}:{user_input or ''}:{context or ''}"
    return hashlib.sha256(cache_string.encode()).hexdigest()


# Task 10: Extract prompt building logic
def build_prompt(command: str, user_input: Optional[str], context: Optional[str]) -> str:
    """
    Build LLM prompt based on command type and inputs.

    Args:
        command: The command type (draft, improve, shorten, etc.)
        user_input: User's input text (required for most commands)
        context: Additional context (required for draft command)

    Returns:
        Formatted prompt string for the LLM

    Raises:
        ValueError: If required inputs are missing for the command
    """
    if command == "draft":
        if not context:
            raise ValueError("Context required for draft command")
        return f"Based on the following context, write a helpful response:\n\nContext: {context}\n\nResponse:"

    elif command == "improve":
        if not user_input:
            raise ValueError("User input required for improve command")
        return f"Improve the following text while keeping its meaning. Make it clearer and more engaging:\n\n{user_input}\n\nImproved version:"

    elif command == "shorten":
        if not user_input:
            raise ValueError("User input required for shorten command")
        return f"Make the following text more concise while preserving the key information:\n\n{user_input}\n\nShortened version:"

    elif command == "translate":
        if not user_input:
            raise ValueError("User input required for translate command")
        return f"Translate the following text to English:\n\n{user_input}\n\nTranslation:"

    elif command == "formal":
        if not user_input:
            raise ValueError("User input required for formal command")
        return f"Rewrite the following text in a more professional and formal tone:\n\n{user_input}\n\nFormal version:"

    elif command == "casual":
        if not user_input:
            raise ValueError("User input required for casual command")
        return f"Rewrite the following text in a more casual and friendly tone:\n\n{user_input}\n\nCasual version:"

    else:
        raise ValueError(f"Unknown command: {command}")


class AssistRequest(BaseModel):
    """
    Request model for AI assist endpoint.

    Attributes:
        user_input: Text to process (max 10,000 characters)
        context: Additional context for draft command. Provides background information
                 that the AI uses to generate contextually relevant responses.

                 **Context Format & Examples:**

                 For drafting email replies:
                 ```
                 Context: "user: Can you help me reset my password?
                 assistant: Of course! Click the 'Forgot Password' link...
                 user: Thanks! What about enabling 2FA?"
                 ```

                 For generating blog post drafts:
                 ```
                 Context: "Topic: Introduction to Machine Learning
                 Audience: Beginners with basic Python knowledge
                 Tone: Educational but friendly
                 Key points: supervised learning, unsupervised learning, practical examples"
                 ```

                 For product descriptions:
                 ```
                 Context: "Product: Wireless Bluetooth Headphones
                 Features: 40-hour battery, noise cancellation, comfortable fit
                 Target audience: Commuters and travelers
                 Price point: Mid-range ($100-150)"
                 ```

                 **Best Practices:**
                 - Include relevant background information only
                 - Format as key-value pairs or conversation history
                 - Keep context focused on the task at hand
                 - Respect the 10,000 character limit

        command: Type of assistance requested (draft, improve, shorten, etc.)
    """
    # Task 2, 6: Input validation with size limits
    user_input: str = Field(
        default="",
        max_length=MAX_INPUT_LENGTH,
        description="Text to process or improve"
    )
    context: str | None = Field(
        default=None,
        max_length=MAX_CONTEXT_LENGTH,
        description="Additional context for generating responses"
    )
    # Task 3: Command validation with Literal type
    command: Literal["draft", "improve", "shorten", "translate", "formal", "casual"] = Field(
        description="Type of AI assistance to perform"
    )

    # Task 8: Validate against prompt injection
    @field_validator("user_input", "context")
    @classmethod
    def validate_no_injection(cls, v: str | None) -> str | None:
        if v and contains_prompt_injection(v):
            raise ValueError("Input contains suspicious patterns")
        return v


@router.post("/")
@limiter.limit("20/minute")  # Task 5: Rate limiting
async def assist(
    http_request: Request,  # Required for rate limiting
    request: AssistRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    AI assistant endpoint for text generation and improvement.

    **Rate Limited**: 20 requests per minute per IP address

    **Supports commands:**
    - draft: Generate a draft based on context
    - improve: Improve existing text
    - shorten: Make text more concise
    - translate: Translate to English
    - formal: Make text more professional
    - casual: Make text more casual

    **Security:**
    - Input validation (max 10,000 characters)
    - Prompt injection detection
    - Error message sanitization
    - Response caching

    Args:
        http_request: FastAPI request object (for rate limiting)
        request: Validated request with user_input, context, and command
        user: Authenticated user
        session: Database session

    Returns:
        StreamingResponse with AI-generated text

    Raises:
        HTTPException: 400 for invalid input, 429 for rate limit, 500 for server errors
    """

    try:
        # Task 12: Redundant length validation (defense in depth against Pydantic bypasses)
        if len(request.user_input) > MAX_INPUT_LENGTH:
            raise HTTPException(
                status_code=413,
                detail=f"Input too long: {len(request.user_input)} characters (max: {MAX_INPUT_LENGTH})"
            )
        if request.context and len(request.context) > MAX_CONTEXT_LENGTH:
            raise HTTPException(
                status_code=413,
                detail=f"Context too long: {len(request.context)} characters (max: {MAX_CONTEXT_LENGTH})"
            )

        # Task 8: Enhanced telemetry - Log request details with timing
        start_time = time.time()
        logger.info(
            "ai_assist_request",
            user_id=str(user.id),
            command=request.command,
            input_length=len(request.user_input or ""),
            context_length=len(request.context or ""),
            client_ip=http_request.client.host if http_request.client else "unknown",
        )

        # Task 7: Check TTL cache first
        cache_key = generate_cache_key(request.command, request.user_input, request.context)

        # Try to retrieve from cache with error handling
        try:
            if cache_key in _response_cache:
                logger.info(
                    "ai_assist_cache_hit",
                    cache_key=cache_key,
                    user_id=str(user.id)
                )
                cached_response = _response_cache[cache_key]
                async def serve_cached() -> AsyncGenerator[str, None]:
                    yield cached_response
                return StreamingResponse(serve_cached(), media_type="text/plain")
        except Exception as cache_error:
            # Cache read error - log and continue without cache
            logger.warning(
                "ai_assist_cache_read_error",
                cache_key=cache_key,
                error=str(cache_error),
                user_id=str(user.id)
            )

        # Get user's first search space to access LLM configuration
        result = await session.execute(
            select(UserSearchSpacePreference)
            .where(UserSearchSpacePreference.user_id == user.id)
            .limit(1)
        )
        preference = result.scalars().first()

        if not preference:
            # Task 4: Sanitized error message
            raise HTTPException(
                status_code=400,
                detail="No search space configured. Please configure your search space first."
            )

        # Task 11: LLM Selection - Using standard LLM for quality
        # Standard LLM provides better quality for text improvement tasks compared to fast LLM.
        # Fast LLM prioritizes speed over quality and may produce lower-quality outputs for
        # creative tasks like improving text, drafting responses, or formal/casual rewrites.
        #
        # For simple tasks like shortening or translation, fast LLM might be sufficient,
        # but we prioritize consistent quality across all commands.
        #
        # Alternative: Implement per-command LLM selection:
        # command_llm_map = {
        #     "draft": get_user_llm_instance,      # Quality matters
        #     "improve": get_user_llm_instance,    # Quality matters
        #     "shorten": get_user_fast_llm,        # Speed acceptable
        #     "translate": get_user_fast_llm,      # Speed acceptable
        #     "formal": get_user_llm_instance,     # Quality matters
        #     "casual": get_user_llm_instance,     # Quality matters
        # }
        llm = await get_user_llm_instance(
            session, str(user.id), preference.search_space_id, role=LLMRole.LONG_CONTEXT
        )

        if not llm:
            # Task 4: Sanitized error message
            raise HTTPException(
                status_code=500,
                detail="AI service temporarily unavailable. Please try again later."
            )

        # Task 10: Use extracted prompt building logic
        try:
            prompt = build_prompt(request.command, request.user_input, request.context)
        except ValueError as e:
            # Task 4: Convert ValueError to HTTPException with sanitized message
            raise HTTPException(status_code=400, detail=str(e))

        # Stream the response with improved error handling
        async def generate() -> AsyncGenerator[str, None]:
            accumulated_response = ""
            try:
                # Task 7: Improved streaming error handling
                async for chunk in llm.astream(prompt):
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    else:
                        content = str(chunk)

                    accumulated_response += content
                    yield content

                # Task 7: Cache the complete response with error handling
                try:
                    _response_cache[cache_key] = accumulated_response
                except Exception as cache_error:
                    # Cache write error - log but don't fail the request
                    logger.warning(
                        "ai_assist_cache_write_error",
                        cache_key=cache_key,
                        error=str(cache_error),
                        user_id=str(user.id)
                    )

                # Task 8: Enhanced telemetry - Log successful completion with all metrics
                duration_seconds = time.time() - start_time
                logger.info(
                    "ai_assist_success",
                    user_id=str(user.id),
                    command=request.command,
                    input_length=len(request.user_input or ""),
                    context_length=len(request.context or ""),
                    response_length=len(accumulated_response),
                    duration_seconds=f"{duration_seconds:.2f}",
                    cached=False,
                )

            except TimeoutError as e:
                # LLM service timeout
                logger.error(
                    "ai_assist_timeout",
                    user_id=str(user.id),
                    command=request.command,
                    error=str(e),
                    exc_info=True
                )
                yield "\n\n[Error: Request timed out. The AI service is taking too long to respond. Please try again.]"
            except ConnectionError as e:
                # Network/connection issues
                logger.error(
                    "ai_assist_connection_error",
                    user_id=str(user.id),
                    command=request.command,
                    error=str(e),
                    exc_info=True
                )
                yield "\n\n[Error: Connection to AI service failed. Please check your network and try again.]"
            except Exception as e:
                # Task 4, 7: Sanitized error handling for other exceptions
                error_msg = sanitize_exception_message(str(e))
                logger.error(
                    "ai_assist_streaming_error",
                    user_id=str(user.id),
                    command=request.command,
                    error=error_msg,
                    error_type=type(e).__name__,
                    exc_info=True
                )
                yield "\n\n[Error: Unable to complete the request. Please try again.]"

        return StreamingResponse(generate(), media_type="text/plain")

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise

    except Exception as e:
        # Task 4: Sanitize unexpected errors
        error_msg = sanitize_exception_message(str(e))
        logger.error(
            "ai_assist_error",
            user_id=str(user.id) if user else "unknown",
            error=error_msg,
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )
