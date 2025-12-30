import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)


class SlidingSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that implements sliding session expiration.

    On each successful request from an authenticated user, this middleware
    refreshes the authentication cookie with a new 24-hour expiration time.
    This ensures users remain logged in as long as they're active, while
    inactive sessions expire after 24 hours.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Check if user is authenticated by looking for the auth cookie
        auth_cookie = request.cookies.get("surfsense_auth")

        if auth_cookie and response.status_code < 400:
            # User is authenticated and request was successful
            # Refresh the cookie with a new 24h expiration
            from app.users import cookie_transport

            # Set the cookie again with fresh 24h expiration
            response.set_cookie(
                key="surfsense_auth",
                value=auth_cookie,
                max_age=86400,  # 24 hours
                httponly=True,
                secure=cookie_transport.cookie_secure,
                samesite=cookie_transport.cookie_samesite,
                path=cookie_transport.cookie_path,
                domain=cookie_transport.cookie_domain,
            )

            logger.debug("Refreshed authentication cookie for sliding session")

        return response
