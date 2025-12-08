"""
URL redirect validation to prevent open redirect vulnerabilities.

This module provides utilities to validate and build safe redirect URLs,
preventing phishing attacks via unvalidated redirects (CWE-601).
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from app.config import config

logger = logging.getLogger(__name__)


class RedirectValidator:
    """Validates redirect URLs to prevent phishing attacks."""

    def __init__(self):
        """Initialize with allowed redirect domains from config."""
        self.allowed_domains = self._get_allowed_domains()
        self.allowed_paths_pattern = re.compile(
            r"^/dashboard/[a-zA-Z0-9_-]+/connectors/add/[a-zA-Z0-9_-]+-connector$"
        )

    def _get_allowed_domains(self) -> set[str]:
        """Get allowed redirect domains from configuration."""
        domains = set()

        # Add configured frontend URL
        if hasattr(config, "NEXT_FRONTEND_URL") and config.NEXT_FRONTEND_URL:
            parsed = urlparse(config.NEXT_FRONTEND_URL)
            if parsed.hostname:
                domains.add(parsed.hostname.lower())

        # Always allow localhost for development
        if hasattr(config, "DEBUG") and config.DEBUG:
            domains.update(["localhost", "127.0.0.1", "::1"])

        return domains

    def validate_redirect_url(
        self, redirect_url: str, allowed_base: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a redirect URL.

        Args:
            redirect_url: The URL to validate
            allowed_base: Optional specific base URL to validate against

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            parsed = urlparse(redirect_url)

            # Check scheme
            if parsed.scheme not in ["http", "https"]:
                return False, f"Invalid URL scheme: {parsed.scheme}"

            # Check hostname exists
            if not parsed.hostname:
                return False, "URL must have a hostname"

            hostname = parsed.hostname.lower()

            # Check against allowed domains
            if not self._is_allowed_domain(hostname):
                logger.warning(
                    "Blocked redirect to untrusted domain", extra={"hostname": hostname}
                )
                return False, f"Redirect to {hostname} is not allowed"

            # If specific base URL provided, ensure redirect starts with it
            if allowed_base:
                if not redirect_url.startswith(allowed_base):
                    return False, "Redirect URL does not match expected base"

            # Validate path pattern for connector redirects
            if "/connectors/add/" in parsed.path:
                if not self.allowed_paths_pattern.match(parsed.path):
                    return False, "Invalid connector redirect path"

            return True, None

        except Exception as e:
            logger.error(f"Redirect validation error: {str(e)}")
            return False, "Invalid redirect URL"

    def _is_allowed_domain(self, hostname: str) -> bool:
        """Check if hostname is in allowed domains."""
        # Exact match
        if hostname in self.allowed_domains:
            return True

        # Check subdomains
        for allowed in self.allowed_domains:
            if allowed.startswith("*."):
                # Wildcard subdomain
                base = allowed[2:]
                if hostname.endswith(base) or hostname == base[1:]:
                    return True
            elif hostname == allowed:
                return True

        return False

    def build_safe_redirect(
        self,
        space_id: str,
        connector_name: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> str:
        """
        Build a safe redirect URL for connector callbacks.

        Args:
            space_id: The space ID
            connector_name: Name of the connector
            success: Whether operation succeeded
            error: Optional error message

        Returns:
            Validated redirect URL

        Raises:
            ValueError: If configuration is invalid
        """
        # Get base URL from config
        base_url = config.NEXT_FRONTEND_URL

        if not base_url:
            raise ValueError("NEXT_FRONTEND_URL not configured")

        # Validate base URL
        is_valid, error_msg = self.validate_redirect_url(base_url)
        if not is_valid:
            raise ValueError(f"Invalid frontend URL configuration: {error_msg}")

        # Sanitize inputs
        safe_space_id = self._sanitize_path_component(space_id)
        safe_connector = self._sanitize_path_component(connector_name)

        # Build path
        path = f"/dashboard/{safe_space_id}/connectors/add/{safe_connector}-connector"

        # Build full URL
        redirect_url = urljoin(base_url, path)

        # Add query parameters
        if success:
            redirect_url += "?success=true"
        elif error:
            # Sanitize error message (no user input in URL)
            redirect_url += "?error=connection_failed"

        # Final validation
        is_valid, error_msg = self.validate_redirect_url(redirect_url, base_url)
        if not is_valid:
            raise ValueError(f"Generated invalid redirect: {error_msg}")

        return redirect_url

    def _sanitize_path_component(self, component: str) -> str:
        """
        Sanitize path component to prevent path traversal.

        Args:
            component: Path component to sanitize

        Returns:
            Sanitized component

        Raises:
            ValueError: If component is invalid
        """
        # Remove dangerous characters
        safe = re.sub(r"[^a-zA-Z0-9_-]", "", component)

        # Prevent path traversal
        safe = safe.replace("..", "").replace("./", "")

        if not safe:
            raise ValueError("Invalid path component")

        return safe


# Global validator instance
redirect_validator = RedirectValidator()


def validate_redirect(url: str) -> tuple[bool, Optional[str]]:
    """Convenience function for redirect validation."""
    return redirect_validator.validate_redirect_url(url)


def build_connector_redirect(
    space_id: str,
    connector_name: str,
    success: bool = True,
    error: Optional[str] = None,
) -> str:
    """Convenience function to build safe connector redirect."""
    return redirect_validator.build_safe_redirect(space_id, connector_name, success, error)
