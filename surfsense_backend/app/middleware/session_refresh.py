import logging
import time
from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)

# Only refresh cookie if remaining lifetime is less than this threshold
# 0.5 means refresh when less than 50% of lifetime remains (12h for 24h token)
REFRESH_THRESHOLD = 0.5


class SlidingSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that implements sliding session expiration.

    On each successful request from an authenticated user, this middleware
    refreshes the authentication cookie with a new 24-hour expiration time.
    This ensures users remain logged in as long as they're active, while
    inactive sessions expire after 24 hours.

    Cookie refresh is optimized to only occur when the token has less than
    50% of its lifetime remaining (12 hours for 24-hour tokens). This reduces
    unnecessary cookie operations while maintaining the sliding session behavior.
    """

    def _should_refresh_cookie(self, token: str, secret: str) -> bool:
        """
        Determine if the cookie should be refreshed based on token age.

        Only refreshes if remaining lifetime is less than REFRESH_THRESHOLD
        (50%) of total lifetime. This prevents unnecessary cookie updates on
        every request.

        Args:
            token: JWT token string
            secret: Secret key used to sign the token

        Returns:
            True if cookie should be refreshed, False otherwise
        """
        try:
            # Decode JWT without verification (we just need to read the exp claim)
            # The token has already been validated by fastapi-users
            payload = jwt.decode(token, secret, options={"verify_signature": False})

            # Get expiration timestamp from token
            exp = payload.get("exp")
            if not exp:
                # No expiration claim, refresh to be safe
                return True

            current_time = time.time()

            # Calculate remaining lifetime and total lifetime
            remaining_time = exp - current_time

            # Estimate issued time (exp - 24 hours for 24h tokens)
            # This is approximate but sufficient for threshold check
            total_lifetime = 86400  # 24 hours in seconds

            # Refresh if remaining time is less than threshold percentage
            if remaining_time < (total_lifetime * REFRESH_THRESHOLD):
                logger.info(
                    f"Cookie refresh needed: {remaining_time:.0f}s remaining "
                    f"({remaining_time/3600:.1f}h) < threshold {total_lifetime * REFRESH_THRESHOLD:.0f}s"
                )
                return True
            else:
                logger.debug(
                    f"Cookie refresh skipped: {remaining_time:.0f}s remaining "
                    f"({remaining_time/3600:.1f}h) >= threshold {total_lifetime * REFRESH_THRESHOLD:.0f}s"
                )
                return False

        except JWTError as e:
            # Token decode error - don't refresh invalid token
            logger.warning(f"Failed to decode JWT for refresh check: {e}")
            return False
        except Exception as e:
            # Unexpected error - refresh to be safe
            logger.error(f"Unexpected error checking token refresh: {e}", exc_info=True)
            return True

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Check if user is authenticated by looking for the auth cookie
        auth_cookie = request.cookies.get("surfsense_auth")

        if auth_cookie and response.status_code < 400:
            # User is authenticated and request was successful
            # Check if cookie needs refreshing based on threshold
            from app.users import SECRET, cookie_transport

            if self._should_refresh_cookie(auth_cookie, SECRET):
                # Refresh the cookie with a new 24h expiration
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

                logger.info("Refreshed authentication cookie for sliding session")

        return response
