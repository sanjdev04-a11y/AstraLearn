from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr

    full_name: str = Field(
        min_length=2,
        max_length=100
    )

    password: str = Field(
        min_length=8
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a number")

        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain a letter")

        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserUpdateRequest(BaseModel):
    full_name: str | None = None