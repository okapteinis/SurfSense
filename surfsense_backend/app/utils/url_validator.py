"""
URL validation utility to prevent SSRF (Server-Side Request Forgery) attacks.

This module provides functions to validate URLs before making HTTP requests,
preventing attacks against internal services and localhost.
"""

import asyncio
import ipaddress
import re
import socket
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


async def resolve_and_check_hostname(hostname: str) -> list[str]:
    """
    Resolve hostname to IP addresses and check if any resolve to blocked ranges.

    This prevents SSRF bypass attacks using domains that resolve to private IPs
    (e.g., 192.168.0.1.nip.io -> 192.168.0.1).

    To prevent TOCTOU (Time-Of-Check-Time-Of-Use) vulnerabilities from DNS
    rebinding attacks, this function returns the validated IP addresses that
    should be used immediately for requests instead of re-resolving the hostname.

    Args:
        hostname: Hostname to resolve and check

    Returns:
        List of validated safe IP addresses

    Raises:
        HTTPException: If hostname resolves to a blocked IP address or cannot be resolved
    """
    try:
        # Resolve hostname to IP addresses (both IPv4 and IPv6) using async DNS resolution
        # This prevents blocking the event loop
        loop = asyncio.get_running_loop()
        addr_info = await loop.getaddrinfo(hostname, None)

        validated_ips = []
        for family, _, _, _, sockaddr in addr_info:
            # Extract IP address from sockaddr tuple
            ip_str = sockaddr[0]

            # Check if resolved IP is blocked
            if is_ip_blocked(ip_str):
                raise HTTPException(
                    status_code=400,
                    detail=f"Hostname {hostname} resolves to blocked IP address {ip_str}",
                )

            validated_ips.append(ip_str)

        # Remove duplicates while preserving order using dict.fromkeys() - O(N) instead of O(N²)
        return list(dict.fromkeys(validated_ips))

    except socket.gaierror:
        # DNS resolution failed - hostname doesn't exist
        # This is a validation error, not an SSRF issue
        raise HTTPException(
            status_code=400,
            detail=f"Unable to resolve hostname: {hostname}",
        )
    except HTTPException:
        # Re-raise HTTPExceptions (blocked IP detected)
        raise
    except Exception as e:
        # Unexpected error during DNS resolution
        raise HTTPException(
            status_code=400,
            detail=f"Error resolving hostname {hostname}: {e!s}",
        ) from e


async def validate_url_safe_for_ssrf(
    url: str, allow_private: bool = False
) -> tuple[str, list[str] | None]:
    """
    Validate that a URL is safe to make requests to, preventing SSRF attacks.

    To prevent TOCTOU vulnerabilities from DNS rebinding attacks, this function
    returns validated IP addresses that should be used for the actual HTTP request
    instead of re-resolving the hostname.

    Args:
        url: The URL to validate
        allow_private: If True, allow private IP ranges (use with caution)

    Returns:
        Tuple of (validated_url, validated_ips):
            - validated_url: The validated URL string
            - validated_ips: List of safe IP addresses to use for requests,
                           or None if hostname is already an IP address

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

    # Track validated IPs to prevent TOCTOU attacks
    validated_ips: list[str] | None = None

    # If allow_private is False, check IP ranges
    if not allow_private:
        # First check if hostname is already an IP address
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

        # Resolve hostname to IP addresses and check for blocked IPs
        # This prevents bypass attacks using domains like 192.168.0.1.nip.io
        try:
            # Only attempt DNS resolution if hostname is not already an IP
            ipaddress.ip_address(hostname)
            # If we get here, hostname is already an IP (already checked above)
            # No need to track IPs separately since hostname IS the IP
        except ValueError:
            # Hostname is a domain name, resolve it to check IPs
            # Store the validated IPs to prevent DNS rebinding (TOCTOU)
            validated_ips = await resolve_and_check_hostname(hostname)

    # Additional validation: check for URL encoding tricks
    if "%" in url:
        # Decode and re-validate to prevent bypass via encoding
        from urllib.parse import unquote

        decoded_url = unquote(url)
        if decoded_url != url:
            # Recursively validate the decoded URL
            return await validate_url_safe_for_ssrf(decoded_url, allow_private)

    return url, validated_ips


async def validate_connector_url(
    url: str, connector_type: str = "external"
) -> tuple[str, list[str] | None]:
    """
    Validate URL for connector services.

    This is a wrapper around validate_url_safe_for_ssrf with connector-specific
    error messages. Returns both the validated URL and the validated IP addresses
    to prevent TOCTOU vulnerabilities.

    Args:
        url: The URL to validate
        connector_type: Type of connector (for error messages)

    Returns:
        Tuple of (validated_url, validated_ips):
            - validated_url: The validated URL string
            - validated_ips: List of safe IP addresses to use for requests,
                           or None if hostname is already an IP address

    Raises:
        HTTPException: If URL is unsafe
    """
    try:
        return await validate_url_safe_for_ssrf(url, allow_private=False)
    except HTTPException as e:
        # Re-raise with connector-specific context
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {connector_type} URL: {e.detail}",
        ) from e
