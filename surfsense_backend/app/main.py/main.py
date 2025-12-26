"""FastAPI application with lifespan context manager for message persistence.

Configures the FastAPI application with proper initialization and cleanup
of database connections, message checkpointer, and persistence layer.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# Import configuration and initialization utilities
try:
    from app.config.persistence import initialize_config, get_config
    from app.services.persistence.message_checkpointer import (
        setup_checkpointer_tables,
        close_checkpointer,
        get_checkpointer
    )
except ImportError as e:
    logger.error(f"Failed to import persistence modules: {e}")
    raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.
    
    This context manager handles:
    - Initialization of persistence layer on startup
    - Setup of message checkpointer and database tables
    - Graceful shutdown and cleanup on application stop
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None during the application's running period
    """
    # Startup phase
    logger.info("Starting SurfSense application...")
    
    try:
        # Initialize persistence configuration
        logger.info("Initializing persistence configuration...")
        config = initialize_config()
        logger.info(f"Persistence config initialized: pool_size={config.pool_size}")
        
        # Setup checkpointer tables
        logger.info("Setting up message checkpointer tables...")
        await setup_checkpointer_tables()
        logger.info("Message checkpointer tables ready")
        
        # Verify checkpointer is available
        checkpointer = get_checkpointer()
        logger.info(f"Message checkpointer initialized: {checkpointer}")
        
        logger.info("SurfSense application startup complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise
    
    # Application is running
    yield
    
    # Shutdown phase
    logger.info("Shutting down SurfSense application...")
    
    try:
        # Close checkpointer connections
        logger.info("Closing message checkpointer...")
        await close_checkpointer()
        logger.info("Message checkpointer closed")
        
        logger.info("SurfSense application shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}", exc_info=True)


def create_app() -> FastAPI:
    """Create and configure FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Create FastAPI app with lifespan context manager
    app = FastAPI(
        title="SurfSense",
        description="AI-powered conversation assistant with persistent message storage",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on environment
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add application routes here
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "SurfSense"}
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "Welcome to SurfSense", "version": "1.0.0"}
    
    logger.info("FastAPI application created")
    return app


# Create the FastAPI application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
