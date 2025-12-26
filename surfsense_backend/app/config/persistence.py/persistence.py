"""Persistence configuration for message checkpointer.

Configures database connections, session management, and cleanup policies
for storing conversation history and agent state.
"""

import logging
from typing import Optional
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


@dataclass
class PersistenceConfig:
    """Configuration settings for message persistence layer."""
    
    # Database connection
    database_url: str
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    
    # Cleanup policies
    checkpoint_retention_days: int = 30
    max_checkpoints_per_conversation: int = 100
    cleanup_batch_size: int = 1000
    
    # Performance settings
    enable_connection_pooling: bool = True
    enable_query_cache: bool = True
    cache_ttl_seconds: int = 3600
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.database_url:
            raise ValueError("database_url is required")
        if self.pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        if self.checkpoint_retention_days < 1:
            raise ValueError("checkpoint_retention_days must be at least 1")
        logger.info("PersistenceConfig initialized with database_url=%s", 
                   self.database_url[:20] + "...")


def get_persistence_config() -> PersistenceConfig:
    """Load persistence configuration from environment variables.
    
    Returns:
        PersistenceConfig: Configured persistence settings
        
    Raises:
        ValueError: If required environment variables are missing
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    config = PersistenceConfig(
        database_url=database_url,
        pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        pool_timeout=float(os.getenv("DB_POOL_TIMEOUT", "30.0")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
        checkpoint_retention_days=int(os.getenv("CHECKPOINT_RETENTION_DAYS", "30")),
        max_checkpoints_per_conversation=int(os.getenv("MAX_CHECKPOINTS", "100")),
        cleanup_batch_size=int(os.getenv("CLEANUP_BATCH_SIZE", "1000")),
        enable_connection_pooling=os.getenv("ENABLE_DB_POOLING", "true").lower() == "true",
        enable_query_cache=os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true",
        cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "3600")),
    )
    
    logger.info("Persistence configuration loaded successfully")
    return config


# Global configuration instance
_persistence_config: Optional[PersistenceConfig] = None


def initialize_config(config: Optional[PersistenceConfig] = None) -> PersistenceConfig:
    """Initialize global persistence configuration.
    
    Args:
        config: Configuration instance. If None, loads from environment.
        
    Returns:
        PersistenceConfig: The initialized configuration
    """
    global _persistence_config
    if config is None:
        config = get_persistence_config()
    _persistence_config = config
    logger.info("Persistence configuration initialized")
    return config


def get_config() -> PersistenceConfig:
    """Get the global persistence configuration instance.
    
    Returns:
        PersistenceConfig: The configured persistence settings
        
    Raises:
        RuntimeError: If configuration has not been initialized
    """
    if _persistence_config is None:
        raise RuntimeError("Persistence configuration has not been initialized. "
                          "Call initialize_config() first.")
    return _persistence_config
