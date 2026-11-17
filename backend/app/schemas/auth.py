
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)


# User registration request
class UserRegister(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    password: str = Field(
        min_length=8,
        max_length=128
    )


# User login request
class LoginRequest(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    password: str = Field(
        min_length=1,
        max_length=128
    )


# User profile response
class UserRead(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime


# JWT access token response
class TokenResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"
