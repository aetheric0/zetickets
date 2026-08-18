from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import SessionDep
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User as UserModel
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserResponse

router = APIRouter()

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    tags=["Register"],
)
async def register(
    user_in: UserCreate,
    db: SessionDep,
) -> Any:
    """
    Register a new user account. Checks for existing email,
    hashes the password, and persists the record.
    """
    # 0. Check if email already exists
    stmt = select(UserModel).where(UserModel.email == user_in.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    # 1. Instantiate and persist new user
    user = UserModel(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=getattr(user_in, "full_name", None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

@router.post(
    "/login",
    response_model=Token,
    summary="OAuth2 compatible token login",
    tags=["Login"],
)
async def login_access_token(
    db: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Any:
    """
    Authenticate email and password, returning a signed JWT access token
    Note: OAuth2 spec uses 'username', which maps to the user's email.
    """
    #0. Query user by email
    stmt = select(UserModel).where(UserModel.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    #1. Verify existence and password match
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    #2. Check active status
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    #3. Generate JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(user.id),
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=token,
        token_type="bearer",
    )