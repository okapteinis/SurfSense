from contextlib import asynccontextmanager
import logging
import os
import subprocess
import traceback

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import config
from app.config.jsonata_templates import CONNECTOR_TEMPLATES
from app.db import SiteConfiguration, User, create_db_and_tables, get_async_session
from app.dependencies.limiter import limiter
from app.routes import router as crud_router
from app.schemas import UserCreate, UserRead, UserUpdate
from app.services.jsonata_transformer import transformer
from app.users import SECRET, auth_backend, current_active_user, fastapi_users
from app.utils.logger import configure_logging, get_logger
from app.utils.sensitive_data_filter import sanitize_data, sanitize_exception_message

# Configure structured logging at startup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
configure_logging(LOG_LEVEL)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await create_db_and_tables()

    # Register JSONata transformation templates for connectors
    for connector_type, template in CONNECTOR_TEMPLATES.items():
        transformer.register_template(connector_type, template)

    logger.info(
        "jsonata_templates_registered",
        template_count=len(CONNECTOR_TEMPLATES),
        connectors=list(CONNECTOR_TEMPLATES.keys()),
    )

    # Task 2: Check ffmpeg availability for YouTube audio extraction
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=10  # Longer timeout prevents false negatives on slow systems or during high load
        )
        logger.info("ffmpeg detected successfully - YouTube videos without subtitles can use audio transcription")
    except FileNotFoundError:
        logger.warning(
            "ffmpeg not found - YouTube videos without subtitles will fail. "
            "Install ffmpeg to enable audio transcription fallback."
        )
    except subprocess.CalledProcessError as e:
        logger.warning(f"ffmpeg check failed: {e}")
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg version check timed out after 10 seconds")

    yield


async def registration_allowed(session: AsyncSession = Depends(get_async_session)):
    # Check environment variable first
    if not config.REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled by system configuration"
        )

    # Check site configuration database toggle
    result = await session.execute(select(SiteConfiguration).where(SiteConfiguration.id == 1))
    site_config = result.scalar_one_or_none()

    if site_config and site_config.disable_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled. Please contact the administrator if you need access."
        )

    return True


app = FastAPI(lifespan=lifespan)

# Register shared rate limiter with FastAPI app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to prevent stack trace exposure to external users.

    Logs full error details server-side while returning user-friendly error messages.

    Args:
        request: The request that caused the exception
        exc: The exception that was raised

    Returns:
        JSONResponse with user-friendly error message
    """
    # Log full error details (server-side only) with sanitization
    logger.error(
        "Unhandled exception",
        extra={
            "path": str(request.url),
            "method": request.method,
            "error_type": type(exc).__name__,
            "error_message": sanitize_exception_message(str(exc)),
            "traceback": traceback.format_exc()
        }
    )

    # Return generic error to user (no stack trace exposure)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors without exposing internal details.

    Args:
        request: The request that failed validation
        exc: The validation exception

    Returns:
        JSONResponse with validation errors
    """
    # Log validation errors with sanitization (may contain sensitive user input)
    logger.warning(
        "Request validation failed",
        extra={
            "path": str(request.url),
            "errors": sanitize_data(exc.errors())
        }
    )

    # Return user-friendly validation errors
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "message": "The request contains invalid data",
            "details": [
                {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"]
                }
                for error in exc.errors()
            ]
        }
    )

# ========================================
# MIDDLEWARE CONFIGURATION
# ========================================
# IMPORTANT: Middleware execution order matters!
#
# FastAPI/Starlette middleware wraps handlers in reverse order of registration:
# - First registered middleware = outermost wrapper (runs first on request, last on response)
# - Last registered middleware = innermost wrapper (runs last on request, first on response)
#
# REQUEST FLOW (top to bottom):
# 1. ProxyHeadersMiddleware - Detects HTTPS from X-Forwarded-Proto (MUST be first!)
# 2. CORSMiddleware - Validates origin and handles preflight OPTIONS requests
# 3. SecurityHeadersMiddleware - Adds security headers (HSTS, CSP, etc.)
# 4. SlidingSessionMiddleware - Refreshes auth cookie based on token expiration
# 5. Rate limiter - Enforces rate limits (registered separately with exception handler)
#
# RESPONSE FLOW (bottom to top):
# 5. Rate limiter sets rate limit headers
# 4. SlidingSessionMiddleware refreshes cookie if needed
# 3. SecurityHeadersMiddleware adds security headers
# 2. CORSMiddleware adds CORS headers
# 1. ProxyHeadersMiddleware completes
#
# WHY THIS ORDER:
# - ProxyHeaders MUST be first so cookie_secure flag works correctly behind reverse proxy
# - CORS must be early to handle preflight requests before other middleware
# - Security headers should be added to all responses
# - Session refresh happens after security checks pass
# ========================================

# Add ProxyHeaders middleware FIRST to trust proxy headers (e.g., from Cloudflare, nginx)
# This ensures FastAPI correctly detects HTTPS when behind a reverse proxy
# CRITICAL for security: Enables proper Secure cookie flag functionality, ensuring
# authentication cookies are only sent over HTTPS connections
# The middleware reads X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Host headers
# SECURITY: Only trust specific proxy hosts in production (ai.kapteinis.lv, localhost)
# Set TRUSTED_HOSTS env var to comma-separated list of trusted proxy IPs/hosts
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=config.TRUSTED_HOSTS)

# Add CORS middleware
# SECURITY: Restrict to specific methods and headers for better security
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,  # Configurable via CORS_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
)

# Add security headers middleware
# Adds security headers to all responses to protect against common web vulnerabilities
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.session_refresh import SlidingSessionMiddleware
from app.users import SECRET

app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=True,  # Enable HSTS in production
    enable_csp=True,  # Enable Content Security Policy
)

# Add sliding session middleware
# Refreshes auth cookie on each request to implement sliding expiration
# Requires JWT secret key for token decoding and expiration checks
app.add_middleware(SlidingSessionMiddleware, secret_key=SECRET)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(registration_allowed)],  # blocks registration when disabled
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# SECURITY: OAuth CSRF protection via state parameter is automatically handled by fastapi-users
# The get_oauth_router generates a JWT state token during authorization and validates it in the callback
if config.AUTH_TYPE == "GOOGLE":
    from app.users import google_oauth_client

    app.include_router(
        fastapi_users.get_oauth_router(
            google_oauth_client, auth_backend, SECRET, is_verified_by_default=True
        )
        if not config.BACKEND_URL
        else fastapi_users.get_oauth_router(
            google_oauth_client,
            auth_backend,
            SECRET,
            is_verified_by_default=True,
            redirect_url=f"{config.BACKEND_URL}/auth/google/callback",
        ),
        prefix="/auth/google",
        tags=["auth"],
        dependencies=[
            Depends(registration_allowed)
        ],  # blocks OAuth registration when disabled
    )

app.include_router(crud_router, prefix="/api/v1", tags=["crud"])

# Include JSONata transformation routes
from app.routes.jsonata_routes import router as jsonata_router

app.include_router(jsonata_router)

# Include AI assist routes
from app.routes.assist import router as assist_router

app.include_router(assist_router)

# Include health check routes (no rate limiting, for monitoring/load balancers)
from app.routes.health_routes import router as health_router
from app.routes.csrf_routes import router as csrf_router
app.include_router(health_router)
app.include_router(csrf_router)


@app.get("/verify-token")
async def verify_token(
    user: User = Depends(current_active_user),
):
    """
    Verify JWT token and return user information.

    This endpoint validates the Bearer token provided in the Authorization header
    and returns the authenticated user's information if valid.

    Authentication:
        - Requires valid JWT token in Authorization header
        - Token lifetime: 24 hours with sliding expiration (extends on activity)
        - User must be active

    Returns:
        User verification response with complete user data

    Raises:
        HTTPException: 401 if token is invalid or expired
        HTTPException: 403 if user is inactive
    """
    logger.info(
        "token_verified",
        user_id=str(user.id),
        user_email=user.email,
        is_superuser=user.is_superuser,
    )

    return {
        "valid": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "is_verified": user.is_verified,
            "pages_limit": user.pages_limit,
            "pages_used": user.pages_used,
        }
    }
