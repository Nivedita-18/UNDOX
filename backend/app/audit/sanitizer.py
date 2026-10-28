"""
Sanitization utility for UNDOX Audit History.

Ensures that passwords, tokens, API keys, credentials, and sensitive private data
are NEVER stored in audit records or exposed via audit logging endpoints.
"""

import re
from typing import Any, Dict, List, Optional, Union

# Sensitive dictionary keys (matched case-insensitively as substrings or exact keys)
SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "secret_key",
    "private_key",
    "privkey",
    "authorization",
    "auth_token",
    "bearer",
    "credential",
    "passwd",
    "card_number",
    "cvv",
    "ssn",
)

# Regular expressions for string content sanitization
BEARER_REGEX = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/]+=*")
BASIC_REGEX = re.compile(r"(?i)\b(Basic\s+)[A-Za-z0-9+/]+=*")
KEY_VALUE_SECRET_REGEX = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key|access[_-]?token|client[_-]?secret|credentials?)"
    r"(\s*[:=]\s*['\"]?)([^'\s,;&]+)(['\"]?)"
)
PRIVATE_KEY_REGEX = re.compile(
    r"-----BEGIN [A-Z0-9 ]+ PRIVATE KEY-----[\s\S]+?-----END [A-Z0-9 ]+ PRIVATE KEY-----"
)


def _is_sensitive_key(key: str) -> bool:
    """Checks whether a dictionary key indicates sensitive confidential data."""
    k_lower = key.lower()
    return any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS)


def sanitize_text(text: Optional[str]) -> str:
    """
    Sanitizes free-form text by masking passwords, Bearer tokens,
    API keys, and private key blocks.
    """
    if not text:
        return ""

    # Redact private key blocks
    cleaned = PRIVATE_KEY_REGEX.sub("[REDACTED_PRIVATE_KEY]", text)

    # Redact Authorization header values
    cleaned = BEARER_REGEX.sub(r"\1[REDACTED]", cleaned)
    cleaned = BASIC_REGEX.sub(r"\1[REDACTED]", cleaned)

    # Redact key-value pairs (e.g., password=secret123 or api_key: "abc-xyz")
    cleaned = KEY_VALUE_SECRET_REGEX.sub(r"\1\2[REDACTED]\4", cleaned)

    return cleaned


def sanitize_details(data: Optional[Union[Dict[str, Any], List[Any], Any]]) -> Optional[Any]:
    """
    Recursively inspects and sanitizes dictionary and list data structures,
    redacting any sensitive keys and sanitizing nested string values.
    """
    if data is None:
        return None

    if isinstance(data, dict):
        sanitized_dict: Dict[str, Any] = {}
        for k, v in data.items():
            str_key = str(k)
            if _is_sensitive_key(str_key):
                sanitized_dict[str_key] = "[REDACTED]"
            else:
                sanitized_dict[str_key] = sanitize_details(v)
        return sanitized_dict

    if isinstance(data, list):
        return [sanitize_details(item) for item in data]

    if isinstance(data, str):
        return sanitize_text(data)

    return data
