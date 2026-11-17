
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models import User
from ..audit.service import record_audit_event

from .security import (
    hash_password,
    verify_password
)


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


# Register a new user
def register_user(
    db: Session,
    email: str,
    password: str
):

    email = email.strip().lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise UserAlreadyExistsError(
            "An account with this email already exists."
        )

    try:

        # Create user with hashed password
        user = User(
            email=email,
            password_hash=hash_password(password),
            role="VIEWER",
            is_active=True
        )

        db.add(user)
        db.flush()

        # Record registration event
        record_audit_event(
            db,
            event_type="USER_REGISTERED",
            outcome="SUCCESS",
            message="New user registered successfully",
            actor_id=user.id,
            event_data={
                "email": email
            }
        )

        db.commit()
        db.refresh(user)

        return user

    except IntegrityError:

        db.rollback()

        # Handle duplicate email registration race condition
        existing_user = db.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            raise UserAlreadyExistsError(
                "An account with this email already exists."
            )

        raise

    except Exception:

        db.rollback()
        raise


# Authenticate an existing user
def authenticate_user(
    db: Session,
    email: str,
    password: str
):

    email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    # Verify password only when user exists
    password_valid = (
        verify_password(password, user.password_hash)
        if user is not None
        else False
    )

    # Reject invalid credentials or inactive accounts
    if user is None or not password_valid or not user.is_active:

        try:

            record_audit_event(
                db,
                event_type="AUTH_LOGIN_FAILED",
                outcome="DENIED",
                message="Invalid login credentials",
                actor_id=user.id if user else None,
                event_data={
                    "email": email
                }
            )

            db.commit()

        except Exception:
            db.rollback()
            raise

        raise InvalidCredentialsError(
            "Incorrect email or password."
        )

    try:

        # Record successful login
        record_audit_event(
            db,
            event_type="USER_LOGIN",
            outcome="SUCCESS",
            message="User logged in successfully",
            actor_id=user.id,
            event_data={
                "email": user.email
            }
        )

        db.commit()

        return user

    except Exception:
        db.rollback()
        raise
