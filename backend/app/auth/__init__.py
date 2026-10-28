"""
Authentication package for UNDOX.
"""

from backend.app.auth.dependencies import get_current_user, require_role
from backend.app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.app.auth.service import (
    authenticate_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    register_user,
)

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "register_user",
    "authenticate_user",
    "get_user_by_id",
    "get_user_by_username",
    "get_user_by_email",
    "get_current_user",
    "require_role",
]
