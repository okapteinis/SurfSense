"""
Logging utilities for sanitizing sensitive data from log messages.

This module provides functions to redact sensitive information before logging,
preventing credential leaks and other security issues.
"""

import re
from typing import Any


# Sensitive field patterns to redact
SENSITIVE_PATTERNS = [
    # API keys, tokens, secrets
    (r'"(?:api_key|apikey|api-key)"\s*:\s*"([^"]+)"', '"api_key": "[REDACTED]"'),
    (r'"(?:access_token|accesstoken|access-token)"\s*:\s*"([^"]+)"', '"access_token": "[REDACTED]"'),
    (r'"(?:refresh_token|refreshtoken|refresh-token)"\s*:\s*"([^"]+)"', '"refresh_token": "[REDACTED]"'),
    (r'"(?:secret|api_secret|apisecret|api-secret)"\s*:\s*"([^"]+)"', '"secret": "[REDACTED]"'),
    (r'"(?:password|passwd|pwd)"\s*:\s*"([^"]+)"', '"password": "[REDACTED]"'),
    (r'"(?:token|auth_token|authtoken|auth-token)"\s*:\s*"([^"]+)"', '"token": "[REDACTED]"'),
    (r'"(?:bearer|authorization)"\s*:\s*"([^"]+)"', '"authorization": "[REDACTED]"'),

    # Dictionary/object access patterns
    (r'(?:api_key|apikey|api-key)=([^\s,\)]+)', 'api_key=[REDACTED]'),
    (r'(?:access_token|accesstoken|access-token)=([^\s,\)]+)', 'access_token=[REDACTED]'),
    (r'(?:password|passwd|pwd)=([^\s,\)]+)', 'password=[REDACTED]'),
    (r'(?:token|auth_token|authtoken|auth-token)=([^\s,\)]+)', 'token=[REDACTED]'),

    # Environment variable patterns
    (r'(?:API_KEY|APIKEY)=([^\s]+)', 'API_KEY=[REDACTED]'),
    (r'(?:ACCESS_TOKEN|ACCESSTOKEN)=([^\s]+)', 'ACCESS_TOKEN=[REDACTED]'),
    (r'(?:PASSWORD|PASSWD)=([^\s]+)', 'PASSWORD=[REDACTED]'),
    (r'(?:SECRET|API_SECRET)=([^\s]+)', 'SECRET=[REDACTED]'),

    # Bearer token patterns
    (r'Bearer\s+([a-zA-Z0-9_\-\.]+)', 'Bearer [REDACTED]'),

    # Common credential patterns (basic auth, JWT, etc.)
    (r'Basic\s+([a-zA-Z0-9+/=]+)', 'Basic [REDACTED]'),
]

# Fields to redact from dictionaries
SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd',
    'api_key', 'apikey', 'api-key',
    'access_token', 'accesstoken', 'access-token',
    'refresh_token', 'refreshtoken', 'refresh-token',
    'secret', 'api_secret', 'apisecret', 'api-secret',
    'token', 'auth_token', 'authtoken', 'auth-token',
    'bearer', 'authorization',
    'client_secret', 'clientsecret', 'client-secret',
    'private_key', 'privatekey', 'private-key',
}


def sanitize_string(text: str) -> str:
    """
    Sanitize a string by redacting sensitive information.

    Args:
        text: String that may contain sensitive data

    Returns:
        Sanitized string with sensitive data redacted
    """
    if not isinstance(text, str):
        return text

    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def _sanitize_list(data: list[Any]) -> list[Any]:
    """
    Recursively sanitize a list by sanitizing its elements.

    Args:
        data: List that may contain sensitive data

    Returns:
        New list with sensitive values redacted
    """
    sanitized = []
    for item in data:
        if isinstance(item, dict):
            sanitized.append(sanitize_dict(item))
        elif isinstance(item, str):
            sanitized.append(sanitize_string(item))
        elif isinstance(item, list):
            sanitized.append(_sanitize_list(item))
        else:
            sanitized.append(item)
    return sanitized


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively sanitize a dictionary by redacting sensitive keys.

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        New dictionary with sensitive values redacted
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        # Check if key is sensitive
        if key.lower() in SENSITIVE_KEYS:
            sanitized[key] = "[REDACTED]"
        # Recursively sanitize nested dictionaries
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        # Recursively sanitize lists
        elif isinstance(value, list):
            sanitized[key] = _sanitize_list(value)
        # Sanitize string values
        elif isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        else:
            sanitized[key] = value

    return sanitized


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize an exception message by redacting sensitive information.

    Args:
        error: Exception to sanitize

    Returns:
        Sanitized error message
    """
    error_msg = str(error)
    return sanitize_string(error_msg)


def safe_repr(obj: Any, max_length: int = 500) -> str:
    """
    Create a safe string representation of an object for logging.

    Sanitizes sensitive data and truncates long strings.

    Args:
        obj: Object to represent
        max_length: Maximum length of the output string

    Returns:
        Safe string representation
    """
    try:
        if isinstance(obj, dict):
            obj = sanitize_dict(obj)

        repr_str = repr(obj)
        sanitized = sanitize_string(repr_str)

        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "... [truncated]"

        return sanitized
    except Exception:
        return "[Unable to represent object safely]"
