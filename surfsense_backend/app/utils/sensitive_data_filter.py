"""
Utilities for sanitizing sensitive data in logs and output.

This module provides functions to detect and redact sensitive information
such as passwords, API keys, tokens, and email addresses before logging.
"""

import re
from typing import Any, Dict, List, Set


# Sensitive keys to redact
SENSITIVE_KEYS: Set[str] = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api-key",
    "access_token",
    "refresh_token",
    "private_key",
    "session_id",
    "cookie",
    "authorization",
    "auth",
    "key",
    "passphrase",
    "credential",
    "value",  # For SOPS secrets
    "bearer",
}

# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = [
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),  # Base64-like strings
    re.compile(r"sk-[A-Za-z0-9]{32,}"),  # OpenAI-style API keys
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub personal access tokens
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),  # Slack tokens
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),  # Bearer tokens
]


def is_sensitive_key(key: str) -> bool:
    """
    Check if a key name indicates sensitive data.

    Args:
        key: Dictionary key to check

    Returns:
        True if key name suggests sensitive data
    """
    key_lower = key.lower().replace("-", "_").replace(" ", "_")
    return any(sensitive in key_lower for sensitive in SENSITIVE_KEYS)


def is_sensitive_value(value: str) -> bool:
    """
    Check if a value looks like sensitive data.

    Args:
        value: String value to check

    Returns:
        True if value looks like a secret/token
    """
    if not isinstance(value, str):
        return False

    # Skip short values
    if len(value) < 8:
        return False

    # Check for long strings without spaces (likely secrets)
    if len(value) > 30 and " " not in value:
        return True

    # Check against known patterns (use search() to find patterns anywhere in string)
    return any(pattern.search(value) for pattern in SENSITIVE_PATTERNS)


def sanitize_email(email: str) -> str:
    """
    Sanitize email address for logging.

    Shows only first 2 characters of local part and full domain.

    Args:
        email: Email address to sanitize

    Returns:
        Sanitized email (e.g., "jo***@example.com")

    Examples:
        >>> sanitize_email("john.doe@example.com")
        'jo***@example.com'
        >>> sanitize_email("a@test.com")
        'a***@test.com'
    """
    if not email or "@" not in email:
        return "***"

    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local}***@{domain}"
    return f"{local[:2]}***@{domain}"


def redact_value(value: str, show_chars: int = 4) -> str:
    """
    Redact a sensitive value, showing only first/last few characters.

    Args:
        value: Value to redact
        show_chars: Number of characters to show at start/end

    Returns:
        Redacted value (e.g., "sk-1...xyz")

    Examples:
        >>> redact_value("sk-1234567890abcdef", show_chars=4)
        'sk-1...cdef'
        >>> redact_value("short")
        '***'
    """
    if not value or len(value) <= show_chars * 2:
        return "***"

    return f"{value[:show_chars]}...{value[-show_chars:]}"


def sanitize_data(data: Any, show_values: bool = False) -> Any:
    """
    Recursively sanitize sensitive data from any structure.

    Args:
        data: Data to sanitize (dict, list, or primitive)
        show_values: If True, skip sanitization (for --show-values flag)

    Returns:
        Sanitized data structure

    Examples:
        >>> sanitize_data({"password": "secret123"})
        {'password': '***REDACTED***'}
        >>> sanitize_data({"user": {"api_key": "sk-123"}})
        {'user': {'api_key': '***REDACTED***'}}
    """
    if show_values:
        return data

    if isinstance(data, dict):
        return {
            key: "***REDACTED***"
            if is_sensitive_key(key)
            else sanitize_data(value, show_values)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [sanitize_data(item, show_values) for item in data]
    elif isinstance(data, str):
        if is_sensitive_value(data):
            return redact_value(data)
        return data
    else:
        return data


def sanitize_data_strict(data: Any) -> Any:
    """
    Strictly sanitize data by redacting ALL string values in a structure.
    Used for logging entire configuration objects or decrypted secrets
    where any string value could be sensitive.

    Args:
        data: Data to sanitize

    Returns:
        Structure with all string values redacted

    Examples:
        >>> sanitize_data_strict({"url": "http://secret", "user": "admin"})
        {'url': '***REDACTED***', 'user': '***REDACTED***'}
    """
    if isinstance(data, dict):
        return {key: sanitize_data_strict(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_data_strict(item) for item in data]
    elif isinstance(data, str):
        return "***REDACTED***"
    else:
        return data



def sanitize_model_string(model_string: str) -> str:
    """
    Remove any embedded credentials from model string.

    Useful for LLM model strings that might contain API keys in URLs.

    Args:
        model_string: Raw model string (may contain credentials)

    Returns:
        Sanitized model string safe for logging

    Examples:
        >>> sanitize_model_string("openai/gpt-4?api_key=sk-123")
        'openai/gpt-4?api_key=***'
        >>> sanitize_model_string("provider/model")
        'provider/model'
    """
    # Patterns for common API key formats in URLs/strings
    patterns = [
        (r"api[_-]?key[=:][^&\s]+", r"api_key=***"),
        (r"token[=:][^&\s]+", r"token=***"),
        (r"password[=:][^&\s]+", r"password=***"),
        (r"secret[=:][^&\s]+", r"secret=***"),
    ]

    sanitized = model_string
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    return sanitized


def sanitize_exception_message(exc: Exception) -> str:
    """
    Sanitize exception message to remove sensitive data.

    Args:
        exc: Exception to sanitize

    Returns:
        Sanitized error message safe for user display

    Examples:
        >>> sanitize_exception_message(ValueError("Invalid API key: sk-123"))
        'Invalid API key: ***'
    """
    message = str(exc)

    # Redact anything that looks like a secret
    for pattern in SENSITIVE_PATTERNS:
        message = pattern.sub("***", message)

    return message


def safe_repr(obj: Any, max_length: int = 100) -> str:
    """
    Create a safe string representation of an object for logging.

    Truncates long strings and sanitizes sensitive data.

    Args:
        obj: Object to represent
        max_length: Maximum length of output

    Returns:
        Safe string representation

    Examples:
        >>> safe_repr({"password": "secret"})
        "{'password': '***REDACTED***'}"
    """
    sanitized = sanitize_data(obj)
    repr_str = repr(sanitized)

    if len(repr_str) > max_length:
        return repr_str[:max_length] + "..."

    return repr_str
