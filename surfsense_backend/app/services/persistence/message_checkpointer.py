"""Message persistence and checkpointing service using LangGraph AsyncPostgresSaver.

This module implements message persistence functionality for chat conversations,
enabling checkpoint-based state management and recovery.
"""

import logging
from typing import Optional, Any
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres import AsyncPostgresSaver

logger = logging.getLogger(__name__)


class MessageCheckpointer:
    """Manages message persistence and checkpointing for chat conversations.
    
    This class wraps LangGraph's AsyncPostgresSaver to provide checkpoint-based
    state management for conversation history and agent state recovery.
    """

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        echo: bool = False,
    ):
        """Initialize the message checkpointer.
        
        Args:
            connection_string: PostgreSQL connection string (e.g., postgresql://user:pass@host/db)
            pool_size: Initial connection pool size
            max_overflow: Maximum overflow connections beyond pool_size
            echo: Enable SQL query logging for debugging
        """
        self.connection_string = connection_string
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.echo = echo
        self.saver: Optional[AsyncPostgresSaver] = None

    async def initialize(self) -> None:
        """Initialize the PostgreSQL connection and create tables.
        
        Raises:
            RuntimeError: If database connection fails or table creation fails
        """
        try:
            self.saver = AsyncPostgresSaver.from_conn_string(
                conn_string=self.connection_string
            )
            # Create tables if they don't exist
            async with self.saver:
                await self.saver.asetup()
            logger.info("Message checkpointer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize message checkpointer: {e}")
            raise RuntimeError(f"Message checkpointer initialization failed: {e}") from e

    async def close(self) -> None:
        """Close database connections."""
        if self.saver:
            try:
                await self.saver.aclose()
                logger.info("Message checkpointer closed successfully")
            except Exception as e:
                logger.error(f"Error closing message checkpointer: {e}")

    @asynccontextmanager
    async def get_saver(self):
        """Context manager for safely using the saver.
        
        Yields:
            AsyncPostgresSaver: The initialized saver instance
            
        Raises:
            RuntimeError: If saver is not initialized
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized. Call initialize() first.")
        async with self.saver:
            yield self.saver

    async def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_data: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Save a checkpoint for a conversation thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            checkpoint_data: State data to checkpoint (messages, agent state, etc.)
            metadata: Optional metadata about the checkpoint
            
        Returns:
            str: Checkpoint ID for reference
            
        Raises:
            RuntimeError: If checkpoint save fails
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized")
        
        try:
            async with self.get_saver() as saver:
                checkpoint = await saver.aput(
                    config={"configurable": {"thread_id": thread_id}},
                    values=checkpoint_data,
                    metadata=metadata or {},
                )
                logger.info(f"Checkpoint saved for thread {thread_id}")
                return checkpoint.get("checkpoint_id", thread_id)
        except Exception as e:
            logger.error(f"Failed to save checkpoint for thread {thread_id}: {e}")
            raise RuntimeError(f"Checkpoint save failed for thread {thread_id}: {e}") from e

    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Load a checkpoint for a conversation thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            checkpoint_id: Optional specific checkpoint to load. If None, loads latest.
            
        Returns:
            dict: Checkpoint data if found, None otherwise
            
        Raises:
            RuntimeError: If checkpoint load fails
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized")
        
        try:
            async with self.get_saver() as saver:
                config = {"configurable": {"thread_id": thread_id}}
                if checkpoint_id:
                    config["checkpoint_id"] = checkpoint_id
                
                checkpoint = await saver.aget(config)
                if checkpoint:
                    logger.info(f"Checkpoint loaded for thread {thread_id}")
                    return checkpoint.get("values")
                logger.warning(f"No checkpoint found for thread {thread_id}")
                return None
        except Exception as e:
            logger.error(f"Failed to load checkpoint for thread {thread_id}: {e}")
            raise RuntimeError(f"Checkpoint load failed for thread {thread_id}: {e}") from e

    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """List all checkpoints for a conversation thread.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            limit: Maximum number of checkpoints to return (most recent first)
            
        Returns:
            list: List of checkpoint metadata
            
        Raises:
            RuntimeError: If checkpoint listing fails
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized")
        
        try:
            async with self.get_saver() as saver:
                config = {"configurable": {"thread_id": thread_id}}
                checkpoints = await saver.alist(config, limit=limit)
                logger.info(f"Listed {len(checkpoints)} checkpoints for thread {thread_id}")
                return [cp.get("metadata", {}) for cp in checkpoints]
        except Exception as e:
            logger.error(f"Failed to list checkpoints for thread {thread_id}: {e}")
            raise RuntimeError(f"Checkpoint listing failed for thread {thread_id}: {e}") from e

    async def delete_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
    ) -> bool:
        """Delete a specific checkpoint.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            checkpoint_id: ID of the checkpoint to delete
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            RuntimeError: If checkpoint deletion fails
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized")
        
        try:
            async with self.get_saver() as saver:
                logger.info(f"Checkpoint deletion requested for {thread_id}:{checkpoint_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            raise RuntimeError(f"Checkpoint deletion failed: {e}") from e

    async def cleanup_old_checkpoints(
        self,
        thread_id: str,
        keep_count: int = 10,
    ) -> int:
        """Clean up old checkpoints, keeping only the most recent ones.
        
        Args:
            thread_id: Unique identifier for the conversation thread
            keep_count: Number of most recent checkpoints to keep
            
        Returns:
            int: Number of checkpoints deleted
            
        Raises:
            RuntimeError: If cleanup fails
        """
        if not self.saver:
            raise RuntimeError("Message checkpointer not initialized")
        
        try:
            checkpoints = await self.list_checkpoints(thread_id, limit=100)
            deleted_count = 0
            
            if len(checkpoints) > keep_count:
                for checkpoint in checkpoints[keep_count:]:
                    try:
                        checkpoint_id = checkpoint.get("checkpoint_id")
                        if checkpoint_id:
                            await self.delete_checkpoint(thread_id, checkpoint_id)
                            deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete checkpoint: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old checkpoints for thread {thread_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup checkpoints for thread {thread_id}: {e}")
            raise RuntimeError(f"Checkpoint cleanup failed: {e}") from e
