from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database.session import get_db

from app.core.dependencies import (
    get_current_user,
)

from app.core.security import (
    create_access_token,
)

from app.models.user import User

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserUpdateRequest,
)

from app.services import user_service

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):

    user = user_service.create_user(
        db=db,
        user_data=user_data,
    )

    return UserResponse.model_validate(
        user
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = user_service.authenticate_user(
        db=db,
        email=form_data.username,   # Swagger sends username
        password=form_data.password,
    )

    access_token = create_access_token(
        data={"sub": user.email}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return UserResponse.model_validate(
        current_user
    )


@router.patch(
    "/me",
    response_model=UserResponse,
)
def update_me(
    update_data: UserUpdateRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    updated_user = user_service.update_user(
        db=db,
        user=current_user,
        update_data=update_data,
    )

    return UserResponse.model_validate(
        updated_user
    )