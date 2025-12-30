"""
CSRF (Cross-Site Request Forgery) protection routes.

This module provides endpoints for CSRF token generation and validation.
"""

import logging
import os
from fastapi import APIRouter, Depends, Response
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class CsrfSettings(BaseModel):
    """CSRF protection configuration settings."""

    secret_key: str = os.getenv("CSRF_SECRET_KEY", "change-this-in-production-use-env-var")
    cookie_name: str = "csrf_token"
    cookie_samesite: str = "lax"  # 'lax' allows same-site requests
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "FALSE").upper() == "TRUE"
    cookie_httponly: bool = False  # Must be False so JavaScript can read it
    cookie_domain: str | None = None
    header_name: str = "X-CSRF-Token"
    header_type: str | None = None
    token_location: str = "header"  # Can be 'header' or 'body'

    class Config:
        """Pydantic configuration."""
        validate_assignment = True


@CsrfProtect.load_config
def get_csrf_config():
    """
    Load CSRF protection configuration.

    Returns:
        CsrfSettings instance with current configuration
    """
    return CsrfSettings()


@router.get("/csrf-token")
async def get_csrf_token(
    response: Response,
    csrf_protect: CsrfProtect = Depends(),
):
    """
    Generate and return a CSRF token for the current session.

    The token is set as a cookie and also returned in the response body
    for flexibility in frontend implementation.

    Args:
        response: FastAPI response object to set the cookie
        csrf_protect: CSRF protection dependency

    Returns:
        dict: Contains the CSRF token and instructions

    Example:
        ```javascript
        // Frontend usage:
        const response = await fetch('/api/csrf-token');
        const { csrf_token } = await response.json();

        // Use in subsequent requests:
        await fetch('/api/some-endpoint', {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrf_token,
            },
            body: JSON.stringify(data),
        });
        ```
    """
    try:
        # Generate CSRF token and set cookie
        csrf_token, signed_token = csrf_protect.generate_csrf_tokens()

        # Set the token as a cookie
        csrf_protect.set_csrf_cookie(signed_token, response)

        logger.info("CSRF token generated successfully")

        return {
            "csrf_token": csrf_token,
            "message": "CSRF token generated. Include this token in X-CSRF-Token header for state-changing requests.",
            "usage": {
                "header_name": "X-CSRF-Token",
                "methods_requiring_token": ["POST", "PUT", "DELETE", "PATCH"],
                "cookie_name": "csrf_token",
            }
        }
    except CsrfProtectError as e:
        logger.error(f"CSRF token generation failed: {e!s}", exc_info=True)
        return {
            "error": "Failed to generate CSRF token",
            "message": str(e)
        }


@router.get("/csrf-status")
async def csrf_status():
    """
    Check CSRF protection status and configuration.

    This endpoint helps frontend developers understand the CSRF
    configuration without exposing sensitive values.

    Returns:
        dict: CSRF configuration status
    """
    config = get_csrf_config()

    return {
        "enabled": True,
        "cookie_name": config.cookie_name,
        "header_name": config.header_name,
        "cookie_samesite": config.cookie_samesite,
        "cookie_secure": config.cookie_secure,
        "protected_methods": ["POST", "PUT", "DELETE", "PATCH"],
        "message": "CSRF protection is enabled. Obtain token from /api/csrf-token before making state-changing requests.",
    }
