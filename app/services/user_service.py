from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    verify_password,
)

from app.models.user import User

from app.schemas.user import (
    UserCreate,
    UserUpdateRequest,
)


def get_user_by_email(
    db: Session,
    email: str,
):
    return (
        db.query(User)
        .filter(User.email == email.lower())
        .first()
    )


def get_user_by_id(
    db: Session,
    user_id: int,
):
    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )


def create_user(
    db: Session,
    user_data: UserCreate,
):

    email = user_data.email.lower()

    existing_user = get_user_by_email(
        db=db,
        email=email,
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = User(
        email=email,
        full_name=user_data.full_name.strip(),
        hashed_password=hash_password(
            user_data.password
        ),
        is_active=True,
        is_verified=False,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
):

    user = get_user_by_email(
        db,
        email.lower(),
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(
        password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return user


def update_user(
    db: Session,
    user: User,
    update_data: UserUpdateRequest,
):

    changes = update_data.model_dump(
        exclude_unset=True
    )

    for field, value in changes.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user