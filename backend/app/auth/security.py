"""
Cryptographic security utilities for UNDOX Authentication.

Provides:
- Secure password hashing using PBKDF2-HMAC-SHA256 (NIST SP 800-132 / OWASP recommended).
- Constant-time verification to prevent timing attack vulnerabilities.
- RFC 7519-compliant JWT token creation and verification using HMAC-SHA256.
- Zero external C-dependency requirements (standard library hashlib, hmac, secrets).
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.app.config import settings


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TokenError(Exception):
    """Base exception for JWT token validation errors."""
    pass


class InvalidTokenError(TokenError):
    """Raised when token signature, format, or payload is invalid."""
    pass


class TokenExpiredError(TokenError):
    """Raised when token expiration timestamp (exp) has passed."""
    pass


# ---------------------------------------------------------------------------
# Password Hashing & Verification
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using PBKDF2-HMAC-SHA256 with a unique random salt.
    Format: pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>
    """
    salt = secrets.token_bytes(16)
    iterations = 100_000
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${salt.hex()}${hash_bytes.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    Expected format: pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>
    """
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
        header, salt_hex, expected_hash_hex = parts
        prefix_parts = header.split(":")
        if len(prefix_parts) != 3 or prefix_parts[0] != "pbkdf2" or prefix_parts[1] != "sha256":
            return False
        iterations = int(prefix_parts[2])

        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(expected_hash_hex)

        computed_hash = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Base64URL Helpers for RFC 7519 JWT
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    """Base64URL encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data_str: str) -> bytes:
    """Base64URL decode with added padding if necessary."""
    rem = len(data_str) % 4
    if rem > 0:
        data_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode("ascii"))


# ---------------------------------------------------------------------------
# JWT Creation & Verification
# ---------------------------------------------------------------------------

def create_access_token(
    payload_data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates an RFC 7519 HMAC-SHA256 signed JWT access token.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    claims = dict(payload_data)
    claims["iat"] = int(now.timestamp())
    claims["exp"] = int(expire.timestamp())

    header = {"alg": settings.ALGORITHM, "typ": "JWT"}
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(claims, separators=(",", ":"), default=str).encode("utf-8")

    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token:
    - Verifies HMAC-SHA256 signature using constant-time comparison.
    - Validates expiration timestamp (exp).
    - Returns payload claims dictionary.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidTokenError("Malformed JWT token string.")

    header_b64, payload_b64, sig_b64 = parts

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise InvalidTokenError("Invalid token signature encoding.") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise InvalidTokenError("Token signature verification failed.")

    try:
        payload_bytes = _b64url_decode(payload_b64)
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise InvalidTokenError("Invalid token payload JSON.") from exc

    # Validate expiration
    exp = claims.get("exp")
    if exp is not None:
        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts > exp:
            raise TokenExpiredError("Token has expired.")

    return claims
