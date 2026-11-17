
import jwt

from fastapi import (
    Depends,
    HTTPException,
    status
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User

from .security import decode_access_token


# JWT Bearer authentication
bearer_scheme = HTTPBearer(
    auto_error=False
)


# Standard unauthorized response
def unauthorized_error():

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )


# Get authenticated user from JWT
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db)
):

    if credentials is None:
        raise unauthorized_error()

    # Only Bearer authentication is accepted
    if credentials.scheme.lower() != "bearer":
        raise unauthorized_error()

    try:

        # Decode and verify JWT
        payload = decode_access_token(
            credentials.credentials
        )

        subject = payload.get("sub")

        if not subject:
            raise unauthorized_error()

        user_id = int(subject)

        if user_id <= 0:
            raise unauthorized_error()

    except (
        jwt.InvalidTokenError,
        ValueError,
        TypeError
    ):

        raise unauthorized_error()

    # Retrieve user from database
    user = db.get(
        User,
        user_id
    )

    # Reject missing or inactive accounts
    if user is None or not user.is_active:
        raise unauthorized_error()

    return user


# Role-based authorization
def require_roles(*allowed_roles):

    valid_roles = {
        "ADMIN",
        "OPERATOR",
        "VIEWER"
    }

    if not allowed_roles:
        raise ValueError(
            "At least one allowed role must be specified"
        )

    if not set(allowed_roles).issubset(valid_roles):
        raise ValueError(
            "Invalid role specified"
        )

    def role_checker(
        current_user: User = Depends(get_current_user)
    ):

        if current_user.role not in allowed_roles:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You do not have permission "
                    "to perform this action."
                )
            )

        return current_user

    return role_checker
