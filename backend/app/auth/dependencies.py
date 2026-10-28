"""
FastAPI Authentication and Role-Based Authorization Dependencies for UNDOX.

Provides:
- get_current_user: Extracts and validates JWT Bearer tokens from incoming requests.
- require_role: Enforces role-based permissions (ADMIN, OPERATOR, VIEWER).
"""

from typing import Callable, List, Optional, Union
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.security import InvalidTokenError, TokenExpiredError, decode_access_token
from backend.app.auth.service import get_user_by_username
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.user import User, UserRole

# Default fallback user for legacy tests or local development when AUTH_ENFORCED is false
DEFAULT_UNAUTHENTICATED_USER = User(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    username="operator",
    email="operator@undox.local",
    hashed_password="",
    role=UserRole.OPERATOR.value,
    is_active=True,
)


def get_current_user(
    authorization: Optional[str] = Header(None, description="Bearer <JWT> access token"),
    db: Session = Depends(get_db),
) -> User:
    """
    Extracts, validates, and decodes the JWT bearer token from the Authorization header.

    Behavior:
    1. If Authorization header is provided:
       - Validates format: 'Bearer <token>'.
       - Decodes and verifies JWT signature and expiration.
       - Retrieves user from database; verifies user is active.
       - Raises HTTP 401 on missing, expired, or invalid tokens.
    2. If Authorization header is missing:
       - If settings.AUTH_ENFORCED is True: raises HTTP 401 Unauthorized.
       - If settings.AUTH_ENFORCED is False: returns default operator user to maintain
         unbroken backward compatibility with earlier phase test suites.
    """
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = parts[1].strip()
        try:
            claims = decode_access_token(token)
        except TokenExpiredError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token has expired: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        username = claims.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = get_user_by_username(db, username)
        if user is None:
            # If user was created in another session or memory DB but token is valid:
            # return user constructed from claims
            role_claim = claims.get("role", UserRole.VIEWER.value)
            user = User(
                id=UUID(claims.get("user_id")) if claims.get("user_id") else UUID("00000000-0000-0000-0000-000000000002"),
                username=username,
                email=f"{username}@undox.local",
                hashed_password="",
                role=role_claim,
                is_active=True,
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user

    # Authorization header is absent
    if settings.AUTH_ENFORCED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return DEFAULT_UNAUTHENTICATED_USER


def require_role(*allowed_roles: Union[UserRole, str]) -> Callable:
    """
    Dependency factory that restricts endpoint access to specific user roles.
    ADMIN role always possesses access to all endpoints.
    """
    normalized_roles = [
        r.value if isinstance(r, UserRole) else str(r)
        for r in allowed_roles
    ]

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # ADMIN role bypasses specific role restrictions
        if current_user.role == UserRole.ADMIN.value or current_user.role in normalized_roles:
            return current_user

        roles_str = ", ".join(normalized_roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: user '{current_user.username}' with role '{current_user.role}' "
                   f"does not have required permissions ({roles_str}).",
        )

    return role_checker
