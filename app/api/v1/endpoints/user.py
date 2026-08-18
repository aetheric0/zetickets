from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import CurrentSuperUser, CurrentUser, SessionDep
from app.core.security import get_password_hash
from app.models.user import User as UserModel
from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserUpdateMe

router = APIRouter()

# Current User (Self) Endpoints

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def read_user_me(
    current_user: CurrentUser,
) -> Any:
    """
    Retrieve the profile details of the currently authenticated user.
    """
    return current_user

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
async def update_user_me(
    user_in: UserUpdateMe,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Update profile details for the currently authenticated user (e.g., name, email, password).
    """
    update_data = user_in.model_dump(exclude_unset=True)

    # If updating email, verify uniqueness
    if "email" in update_data and update_data["email"] != current_user:
        stmt = select(UserModel).where(UserModel.email == update_data["email"])
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists",
            )

    # Hash new password provided
    if "password" in update_data:
        password = update_data.pop("password")
        update_data["hashed_password"] = get_password_hash(password)

    # Apply updates
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return current_user


# Administrative User Management (Superuser Only)
@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users (Admin),"
)
async def read_users(
    db: SessionDep,
    _: CurrentSuperUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve a paginated list of users. Requires administrator privileges.
    """
    stmt = select(UserModel).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Admin)"
)
async def create_user(
    user_in: UserCreate,
    db: SessionDep,
    _: CurrentSuperUser,
) -> Any:
    """
    Create a new user record with designated permissions. Requires administrator privileges.
    """
    stmt = select(UserModel).where(UserModel.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    user = UserModel(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=getattr(user_in, "full_name", None),
        is_active=getattr(user_in, "is_active", True),
        is_superuser=getattr(user_in, "is_superuser", False),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
)
async def read_user_by_id(
    user_id: UUID,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Retrieve user details by UUID. Non-superusers can only access their own profile.
    """
    if not current_user.is_superuser and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this user record.",
        )

    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user by ID (Admin)"
)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: SessionDep,
    _: CurrentSuperUser,
) -> Any:
    """
    Update arbitrary user attributes (including active status and roles). Requires adminsitrator privileges.
    """
    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not foud.",
        )

    update_data = user_in.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] != user.email:
        stmt = select(UserModel).where(UserModel.email == update_data["email"])
        result = await db.execute(stmt)
        if result.scalar_one_or_one():
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

    if "password" in update_data:
        password = update_data.pop("password")
        update_data["hashed_password"] = get_password_hash(password)

    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

@router.delete(
    "/{user_id}",
    response_model=UserResponse,
    summary="Delete user (Admin)"
)
async def delete_user(
    user_id: UUID,
    db: SessionDep,
    current_user: CurrentSuperUser,
) -> Any:
    """
    Delete a user record by ID. Prevents administrators from deleting their own active account.
    """
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot delete their own active account.",
        )

    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.commit()

    return user

