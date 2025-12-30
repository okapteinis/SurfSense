import hashlib
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Literal

from app.db import User, UserSearchSpacePreference, get_async_session
from app.dependencies.limiter import limiter
from app.services.llm_service import get_user_llm_instance
from app.users import current_active_user
from app.utils.logger import get_logger
from app.utils.sensitive_data_filter import sanitize_exception_message

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/assist", tags=["assist"])

# Task 11: Simple in-memory cache for responses
_response_cache = {}


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


# Task 10: Extract prompt building logic
def build_prompt(command: str, user_input: str | None, context: str | None) -> str:
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
        context: Additional context for draft command. This provides background
                 information that the AI uses to generate contextually relevant
                 responses. For example, when drafting a reply to an email, the
                 context would contain the original email content.
        command: Type of assistance requested (draft, improve, shorten, etc.)
    """
    # Task 2, 6: Input validation with size limits
    user_input: str = Field(
        default="",
        max_length=10000,
        description="Text to process or improve"
    )
    context: str | None = Field(
        default=None,
        max_length=10000,
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
        # Task 12: Telemetry - Log request details
        logger.info(
            "ai_assist_request",
            user_id=str(user.id),
            command=request.command,
            input_length=len(request.user_input or ""),
            context_length=len(request.context or ""),
        )

        # Task 11: Check cache first
        cache_key = hashlib.sha256(
            f"{request.command}:{request.user_input or ''}:{request.context or ''}".encode()
        ).hexdigest()

        if cache_key in _response_cache:
            logger.info("ai_assist_cache_hit", cache_key=cache_key)
            cached_response = _response_cache[cache_key]
            async def serve_cached():
                yield cached_response
            return StreamingResponse(serve_cached(), media_type="text/plain")

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

        # Task 1: Switch to standard LLM (not fast LLM)
        llm = await get_user_llm_instance(
            session, str(user.id), preference.search_space_id
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
        async def generate():
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

                # Task 11: Cache the complete response
                _response_cache[cache_key] = accumulated_response

                # Task 12: Log successful completion
                logger.info(
                    "ai_assist_success",
                    user_id=str(user.id),
                    command=request.command,
                    response_length=len(accumulated_response)
                )

            except Exception as e:
                # Task 4, 7: Sanitized error handling
                error_msg = sanitize_exception_message(str(e))
                logger.error(
                    "ai_assist_streaming_error",
                    user_id=str(user.id),
                    command=request.command,
                    error=error_msg,
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
