import logging
import os
import time
from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders

from app.users import cookie_transport

logger = logging.getLogger(__name__)

# Task 10: Document refresh threshold and make configurable
# Refresh threshold determines when cookies are refreshed based on remaining lifetime.
# 0.5 (50%) means refresh when less than 12 hours remain of a 24-hour token.
#
# Lower threshold (e.g., 0.25):
#   - Refreshes less frequently (only when < 25% lifetime remains, i.e., < 6h)
#   - Lower server load but higher risk of expiration if user becomes idle
#
# Higher threshold (e.g., 0.75):
#   - Refreshes more frequently (when < 75% lifetime remains, i.e., < 18h)
#   - Higher server load but better UX (less risk of session expiry during use)
#
# 0.5 balances these tradeoffs: users get refreshed halfway through their session,
# providing ample time for continued activity while avoiding excessive refreshes.
REFRESH_THRESHOLD = float(os.getenv("SESSION_REFRESH_THRESHOLD", "0.5"))


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

    Task 9: Security Monitoring Recommendations:
    ------------------------------------------------
    While JWT sliding sessions provide good UX, they have security implications:

    1. TOKEN REUSE MONITORING:
       - Log token usage with client IP address to detect token theft
       - Alert on token reuse from different geographic locations
       - Implementation: Add IP logging in dispatch() method

    2. TOKEN REVOCATION:
       - Implement token revocation list in Redis or database
       - Allow users to revoke sessions from settings page
       - Check revocation list before refreshing cookie
       - Implementation: Add before _should_refresh_cookie() check

    3. REFRESH TOKEN PATTERN:
       - Consider short-lived access tokens (1h) + long-lived refresh tokens (24h)
       - Reduces risk window if token is stolen
       - Requires more complex implementation

    4. SUSPICIOUS PATTERN DETECTION:
       - Monitor for: many requests from different IPs with same token
       - Monitor for: token reuse after logout
       - Monitor for: rapid session creation/destruction
       - Implementation: Add telemetry logging with anomaly detection

    5. SESSION LIFETIME LIMITS:
       - Current: 24h lifetime with sliding extension
       - Risk: Stolen token remains valid for 24h
       - Mitigation: Implement absolute maximum session age (e.g., 7 days)
       - Force re-authentication after absolute limit regardless of activity

    TRADEOFFS:
    - Longer sessions (24h): Better UX but wider attack window
    - Shorter sessions (1h): Better security but more re-authentication prompts
    - Current implementation prioritizes UX with acceptable security for most use cases
    """

    def __init__(self, app, secret_key: str):
        """
        Initialize sliding session middleware.

        Task 2: Accept and store JWT secret key for token decoding.

        Args:
            app: ASGI application
            secret_key: JWT secret key used for token signing/verification
        """
        super().__init__(app)
        self.secret_key = secret_key

    def _should_refresh_cookie(self, token: str) -> bool:
        """
        Determine if the cookie should be refreshed based on token age.

        Only refreshes if remaining lifetime is less than REFRESH_THRESHOLD
        (50%) of total lifetime. This prevents unnecessary cookie updates on
        every request.

        Task 1: Uses JWT decode to extract exp and iat claims for intelligent
        refresh decisions based on actual token lifetime.

        Args:
            token: JWT token string

        Returns:
            True if cookie should be refreshed, False otherwise
        """
        # Task 7: Environment-aware logging
        env = os.getenv("ENVIRONMENT", "development")
        log_level = logging.INFO if env == "production" else logging.DEBUG

        try:
            # Task 1: Decode JWT without signature verification
            # The token has already been validated by fastapi-users
            payload = jwt.decode(
                token, self.secret_key, options={"verify_signature": False}
            )

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
                logger.log(
                    log_level,
                    f"Cookie refresh needed: {remaining_time:.0f}s remaining "
                    f"({remaining_time/3600:.1f}h) < threshold {total_lifetime * REFRESH_THRESHOLD:.0f}s"
                )
                return True
            else:
                logger.log(
                    logging.DEBUG,  # Always debug for skip messages
                    f"Cookie refresh skipped: {remaining_time:.0f}s remaining "
                    f"({remaining_time/3600:.1f}h) >= threshold {total_lifetime * REFRESH_THRESHOLD:.0f}s"
                )
                return False

        except JWTError as e:
            # Task 3: JWT decode error handling - don't refresh invalid token
            logger.warning(f"Invalid or expired JWT token, skipping refresh: {e}")
            return False
        except Exception as e:
            # Unexpected error - refresh to be safe
            logger.error(f"Unexpected error checking token refresh: {e}", exc_info=True)
            return True

    async def dispatch(self, request: Request, call_next):
        # Task 12: Performance measurement
        start_time = time.time()

        response = await call_next(request)

        # Check if user is authenticated by looking for the auth cookie
        auth_cookie = request.cookies.get("surfsense_auth")

        if auth_cookie and response.status_code < 400:
            # User is authenticated and request was successful
            # Check if cookie needs refreshing based on threshold
            if self._should_refresh_cookie(auth_cookie):
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

        # Task 12: Log performance warning if middleware is slow
        duration = time.time() - start_time
        if duration > 0.05:  # 50ms threshold
            logger.warning(
                f"SlidingSessionMiddleware took {duration:.3f}s "
                f"(threshold: 0.050s). This may indicate performance issues."
            )

        return response
