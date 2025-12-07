"""
URL validation utility to prevent SSRF (Server-Side Request Forgery) attacks.

This module provides functions to validate URLs before making HTTP requests,
preventing attacks against internal services and localhost.
"""

import ipaddress
import re
from urllib.parse import urlparse

from fastapi import HTTPException


# Private/internal IP ranges to block
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    ipaddress.ip_network("10.0.0.0/8"),  # Private network
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("172.16.0.0/12"),  # Private network
    ipaddress.ip_network("192.168.0.0/16"),  # Private network
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
]

# Blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "0.0.0.0",
    "127.0.0.1",
    "[::]",
    "[::1]",
    "metadata.google.internal",  # GCP metadata service
    "169.254.169.254",  # AWS metadata service
}


def is_ip_blocked(ip_str: str) -> bool:
    """
    Check if an IP address is in a blocked range.

    Args:
        ip_str: IP address as string

    Returns:
        True if IP is blocked, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in blocked_range for blocked_range in BLOCKED_IP_RANGES)
    except ValueError:
        return False


def validate_url_safe_for_ssrf(url: str, allow_private: bool = False) -> str:
    """
    Validate that a URL is safe to make requests to, preventing SSRF attacks.

    Args:
        url: The URL to validate
        allow_private: If True, allow private IP ranges (use with caution)

    Returns:
        The validated URL

    Raises:
        HTTPException: If URL is unsafe or invalid
    """
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Invalid URL provided")

    url = url.strip()

    # Ensure URL has a scheme
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="URL must start with http:// or https://",
        )

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid URL format: {e!s}",
        ) from e

    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Only http and https schemes are allowed",
        )

    # Validate hostname exists
    if not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail="URL must contain a valid hostname",
        )

    hostname = parsed.hostname.lower()

    # Check blocked hostnames
    if hostname in BLOCKED_HOSTNAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Access to {hostname} is not allowed",
        )

    # Check for localhost variations
    if "localhost" in hostname or hostname.startswith("127."):
        raise HTTPException(
            status_code=400,
            detail="Access to localhost is not allowed",
        )

    # If allow_private is False, check IP ranges
    if not allow_private:
        # Try to resolve hostname to IP and check if it's in blocked ranges
        # First check if hostname is already an IP
        if is_ip_blocked(hostname):
            raise HTTPException(
                status_code=400,
                detail="Access to private IP addresses is not allowed",
            )

        # Check for IP address in square brackets (IPv6)
        ipv6_match = re.match(r"\[([0-9a-fA-F:]+)\]", hostname)
        if ipv6_match:
            if is_ip_blocked(ipv6_match.group(1)):
                raise HTTPException(
                    status_code=400,
                    detail="Access to private IP addresses is not allowed",
                )

    # Additional validation: check for URL encoding tricks
    if "%" in url:
        # Decode and re-validate to prevent bypass via encoding
        from urllib.parse import unquote

        decoded_url = unquote(url)
        if decoded_url != url:
            # Recursively validate the decoded URL
            return validate_url_safe_for_ssrf(decoded_url, allow_private)

    return url


def validate_connector_url(url: str, connector_type: str = "external") -> str:
    """
    Validate URL for connector services.

    This is a convenience wrapper around validate_url_safe_for_ssrf
    with connector-specific error messages.

    Args:
        url: The URL to validate
        connector_type: Type of connector (for error messages)

    Returns:
        The validated URL

    Raises:
        HTTPException: If URL is unsafe
    """
    try:
        return validate_url_safe_for_ssrf(url, allow_private=False)
    except HTTPException as e:
        # Re-raise with connector-specific context
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {connector_type} URL: {e.detail}",
        ) from e
