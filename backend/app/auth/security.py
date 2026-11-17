
from datetime import datetime, timedelta, timezone

import jwt

from pwdlib import PasswordHash

from ..config import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES
)


# Argon2 password hashing
password_hasher = PasswordHash.recommended()


# Hash user password
def hash_password(password: str) -> str:

    if not password:
        raise ValueError("Password cannot be empty")

    return password_hasher.hash(password)


# Verify password against stored hash
def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    if not plain_password or not hashed_password:
        return False

    try:
        return password_hasher.verify(
            plain_password,
            hashed_password
        )

    except (ValueError, TypeError):
        return False


# Generate JWT access token
def create_access_token(user_id: int) -> str:

    if user_id <= 0:
        raise ValueError("Invalid user ID")

    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        raise ValueError(
            "Token expiration must be greater than zero"
        )

    now = datetime.now(timezone.utc)

    expiration = now + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expiration,
        "token_type": "access"
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


# Decode and validate JWT access token
def decode_access_token(token: str):

    if not token:
        raise jwt.InvalidTokenError(
            "Token is missing"
        )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={
            "require": ["sub", "iat", "exp", "token_type"]
        }
    )

    if payload.get("token_type") != "access":
        raise jwt.InvalidTokenError(
            "Invalid token type"
        )

    return payload
