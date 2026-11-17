
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy.orm import Session

from ..database import get_db

from ..auth import service

from ..auth.security import create_access_token

from ..auth.dependencies import get_current_user

from ..schemas.auth import (
    UserRegister,
    LoginRequest,
    UserRead,
    TokenResponse
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# Register a new user
@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register(
    request: UserRegister,
    db: Session = Depends(get_db)
):

    try:

        user = service.register_user(
            db=db,
            email=request.email,
            password=request.password
        )

        return user

    except service.UserAlreadyExistsError as error:

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error)
        )


# Authenticate user and generate JWT token
@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and generate access token"
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):

    try:

        user = service.authenticate_user(
            db=db,
            email=request.email,
            password=request.password
        )

        access_token = create_access_token(
            user_id=user.id
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer"
        )

    except service.InvalidCredentialsError as error:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )


# Retrieve current authenticated user's profile
@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current authenticated user"
)
def get_profile(
    current_user=Depends(get_current_user)
):

    return current_user
