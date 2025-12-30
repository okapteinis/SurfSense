import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import User, UserSearchSpacePreference, get_async_session
from app.services.llm_service import get_user_fast_llm
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assist", tags=["assist"])


class AssistRequest(BaseModel):
    user_input: str
    context: str | None = None
    command: str  # "draft", "improve", "shorten", "translate", "formal", "casual"


@router.post("/")
async def assist(
    request: AssistRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    AI assistant endpoint for text generation and improvement.

    Supports commands:
    - draft: Generate a draft based on context
    - improve: Improve existing text
    - shorten: Make text more concise
    - translate: Translate to English
    - formal: Make text more professional
    - casual: Make text more casual
    """

    try:
        # Get user's first search space to access LLM configuration
        result = await session.execute(
            select(UserSearchSpacePreference)
            .where(UserSearchSpacePreference.user_id == user.id)
            .limit(1)
        )
        preference = result.scalars().first()

        if not preference:
            raise HTTPException(
                status_code=400, detail="No search space configured for user"
            )

        # Get LLM instance for this user
        llm = await get_user_fast_llm(
            session, str(user.id), preference.search_space_id
        )

        if not llm:
            raise HTTPException(
                status_code=500, detail="Failed to initialize LLM for user"
            )

        # Build prompt based on command
        if request.command == "draft":
            if not request.context:
                raise HTTPException(
                    status_code=400, detail="Context required for draft command"
                )
            prompt = f"Based on the following context, write a helpful response:\n\nContext: {request.context}\n\nResponse:"

        elif request.command == "improve":
            if not request.user_input:
                raise HTTPException(
                    status_code=400, detail="User input required for improve command"
                )
            prompt = f"Improve the following text while keeping its meaning. Make it clearer and more engaging:\n\n{request.user_input}\n\nImproved version:"

        elif request.command == "shorten":
            if not request.user_input:
                raise HTTPException(
                    status_code=400, detail="User input required for shorten command"
                )
            prompt = f"Make the following text more concise while preserving the key information:\n\n{request.user_input}\n\nShortened version:"

        elif request.command == "translate":
            if not request.user_input:
                raise HTTPException(
                    status_code=400, detail="User input required for translate command"
                )
            prompt = f"Translate the following text to English:\n\n{request.user_input}\n\nTranslation:"

        elif request.command == "formal":
            if not request.user_input:
                raise HTTPException(
                    status_code=400, detail="User input required for formal command"
                )
            prompt = f"Rewrite the following text in a more professional and formal tone:\n\n{request.user_input}\n\nFormal version:"

        elif request.command == "casual":
            if not request.user_input:
                raise HTTPException(
                    status_code=400, detail="User input required for casual command"
                )
            prompt = f"Rewrite the following text in a more casual and friendly tone:\n\n{request.user_input}\n\nCasual version:"

        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown command: {request.command}"
            )

        logger.info(f"AI assist request from user {user.id}: command={request.command}")

        # Stream the response
        async def generate():
            try:
                async for chunk in llm.astream(prompt):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                    else:
                        yield str(chunk)
            except Exception as e:
                logger.error(f"Error during AI assist streaming: {e}", exc_info=True)
                yield f"Error: {str(e)}"

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error in AI assist endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
