"""Conversation storage adapter for message persistence.

This module provides a bridge between application code and the message checkpointer,
offering high-level APIs for saving and retrieving conversation state.
"""

import logging
from typing import Optional, Any
from .message_checkpointer import MessageCheckpointer, get_checkpointer

logger = logging.getLogger(__name__)


class ConversationStorage:
    """Bridge between application code and message checkpointer.
    
    Provides high-level APIs for saving and retrieving conversation state,
    including message history and agent state.
    """
    
    def __init__(self, checkpointer: Optional[MessageCheckpointer] = None):
        """Initialize the conversation storage adapter.
        
        Args:
            checkpointer: MessageCheckpointer instance. If None, uses global instance.
        """
        self.checkpointer = checkpointer
    
    async def _get_checkpointer(self) -> MessageCheckpointer:
        """Get the checkpointer instance, initializing if necessary.
        
        Returns:
            MessageCheckpointer: The configured checkpointer instance
        """
        if self.checkpointer is None:
            self.checkpointer = await get_checkpointer()
        return self.checkpointer
    
    async def save_message(
        self,
        conversation_id: str,
        message: dict[str, Any],
        checkpoint_id: Optional[str] = None,
    ) -> str:
        """Save a message and create a checkpoint for conversation state.
        
        Args:
            conversation_id: Unique identifier for the conversation
            message: Message data to save (content, role, metadata, etc.)
            checkpoint_id: Optional checkpoint ID for grouping messages
        
        Returns:
            str: Checkpoint ID for reference
        
        Raises:
            RuntimeError: If save operation fails
        """
        try:
            checkpointer = await self._get_checkpointer()
            checkpoint_data = {
                "message": message,
                "conversation_id": conversation_id,
            }
            saved_checkpoint_id = await checkpointer.save_checkpoint(
                thread_id=conversation_id,
                checkpoint_data=checkpoint_data,
                metadata={"type": "message", "checkpoint_id": checkpoint_id},
            )
            logger.info(f"Message saved for conversation {conversation_id}")
            return saved_checkpoint_id
        except Exception as e:
            logger.error(f"Failed to save message for conversation {conversation_id}: {e}")
            raise RuntimeError(f"Message save failed for {conversation_id}") from e
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve conversation message history.
        
        Args:
            conversation_id: Unique identifier for the conversation
            limit: Maximum number of messages to retrieve (most recent first)
        
        Returns:
            list: List of message dictionaries
        
        Raises:
            RuntimeError: If retrieval fails
        """
        try:
            checkpointer = await self._get_checkpointer()
            checkpoints = await checkpointer.list_checkpoints(
                thread_id=conversation_id,
                limit=limit,
            )
            # Extract messages from checkpoints (most recent first)
            messages = []
            for checkpoint in checkpoints:
                if checkpoint and "message" in checkpoint:
                    messages.append(checkpoint["message"])
            logger.info(f"Retrieved {len(messages)} messages for conversation {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Failed to retrieve history for conversation {conversation_id}: {e}")
            raise RuntimeError(f"History retrieval failed for {conversation_id}") from e
    
    async def save_agent_state(
        self,
        conversation_id: str,
        state: dict[str, Any],
        checkpoint_id: Optional[str] = None,
    ) -> None:
        """Persist agent state for a conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            state: Agent state dictionary (LLM context, memory, etc.)
            checkpoint_id: Optional checkpoint ID for reference
        
        Raises:
            RuntimeError: If save operation fails
        """
        try:
            checkpointer = await self._get_checkpointer()
            checkpoint_data = {
                "agent_state": state,
                "conversation_id": conversation_id,
            }
            await checkpointer.save_checkpoint(
                thread_id=conversation_id,
                checkpoint_data=checkpoint_data,
                metadata={"type": "agent_state", "checkpoint_id": checkpoint_id},
            )
            logger.info(f"Agent state saved for conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to save agent state for conversation {conversation_id}: {e}")
            raise RuntimeError(f"Agent state save failed for {conversation_id}") from e
    
    async def restore_agent_state(
        self,
        conversation_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Restore agent state from checkpoint.
        
        Args:
            conversation_id: Unique identifier for the conversation
            checkpoint_id: Optional specific checkpoint to restore from
        
        Returns:
            dict: Agent state dictionary, or empty dict if not found
        
        Raises:
            RuntimeError: If retrieval fails
        """
        try:
            checkpointer = await self._get_checkpointer()
            checkpoint = await checkpointer.load_checkpoint(
                thread_id=conversation_id,
                checkpoint_id=checkpoint_id,
            )
            if checkpoint and "agent_state" in checkpoint:
                logger.info(f"Agent state restored for conversation {conversation_id}")
                return checkpoint["agent_state"]
            logger.warning(f"No agent state found for conversation {conversation_id}")
            return {}
        except Exception as e:
            logger.error(f"Failed to restore agent state for conversation {conversation_id}: {e}")
            raise RuntimeError(f"Agent state restore failed for {conversation_id}") from e
    
    async def cleanup_old_checkpoints(
        self,
        conversation_id: str,
        keep_count: int = 100,
    ) -> int:
        """Clean up old checkpoints for a conversation.
        
        Args:
            conversation_id: Unique identifier for the conversation
            keep_count: Number of most recent checkpoints to keep
        
        Returns:
            int: Number of checkpoints deleted
        
        Raises:
            RuntimeError: If cleanup fails
        """
        try:
            checkpointer = await self._get_checkpointer()
            deleted = await checkpointer.cleanup_old_checkpoints(
                thread_id=conversation_id,
                keep_count=keep_count,
            )
            logger.info(f"Cleaned up {deleted} old checkpoints for conversation {conversation_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup checkpoints for conversation {conversation_id}: {e}")
            raise RuntimeError(f"Checkpoint cleanup failed for {conversation_id}") from e
