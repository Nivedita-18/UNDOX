"""
Authentication API Router for UNDOX.

Endpoints:
- POST /api/v1/auth/register: User account creation.
- POST /api/v1/auth/login: User credential verification and JWT access token issuance.
- GET /api/v1/auth/me: Current authenticated user profile lookup.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.security import create_access_token
from backend.app.auth.service import (
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Authorization"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user account with unique username and email, securely hashing the password.",
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user = register_user(db, request)
        return UserResponse.model_validate(user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates credentials and issues an RFC 7519 JWT access token.",
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user = authenticate_user(db, request.username, request.password)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_claims = {
        "sub": user.username,
        "user_id": str(user.id),
        "role": user.role,
    }
    access_token = create_access_token(token_claims, expires_delta=expires_delta)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        username=user.username,
        role=user.role,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns profile information for the authenticated bearer token holder.",
)
def get_me(
    authorization: str = Header(..., description="Bearer <token>"),
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Directly validates the Authorization header to guarantee that /auth/me strictly
    enforces a valid token regardless of ambient settings.
    """
    user = get_current_user(authorization=authorization, db=db)
    return UserResponse.model_validate(user)
