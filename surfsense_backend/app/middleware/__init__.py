"""
Middleware package for SurfSense backend.

This package contains custom middleware components for the application.
"""

from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.session_refresh import SlidingSessionMiddleware

__all__ = ["SecurityHeadersMiddleware", "SlidingSessionMiddleware"]
