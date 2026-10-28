"""
User Authentication and Management Service for UNDOX.

Handles:
- User registration with unique username and email validation.
- Secure credential authentication.
- Retrieval of user records.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.security import hash_password, verify_password
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import UserRegisterRequest


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class AuthError(Exception):
    """Base exception for authentication service errors."""
    pass


class UserAlreadyExistsError(AuthError):
    """Raised when registering a username or email that already exists."""
    pass


class InvalidCredentialsError(AuthError):
    """Raised when authentication credentials do not match."""
    pass


class InactiveUserError(AuthError):
    """Raised when an inactive user attempts to authenticate."""
    pass


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------

def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    """Retrieves a user by primary key UUID."""
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieves a user by unique username."""
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Retrieves a user by unique email."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def register_user(db: Session, request: UserRegisterRequest) -> User:
    """
    Registers a new user account with hashed password and assigned role.
    Raises UserAlreadyExistsError if username or email is already registered.
    """
    # Check duplicate username
    if get_user_by_username(db, request.username):
        raise UserAlreadyExistsError(f"Username '{request.username}' is already registered.")

    # Check duplicate email
    if get_user_by_email(db, request.email):
        raise UserAlreadyExistsError(f"Email '{request.email}' is already registered.")

    role_val = request.role.value if request.role else UserRole.VIEWER.value
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=role_val,
        is_active=True,
    )

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User:
    """
    Validates user credentials. Returns the User record upon success.
    Raises InvalidCredentialsError or InactiveUserError on failure.
    """
    user = get_user_by_username(db, username)
    if user is None:
        raise InvalidCredentialsError("Invalid username or password.")

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid username or password.")

    if not user.is_active:
        raise InactiveUserError(f"User account '{username}' is disabled.")

    return user
