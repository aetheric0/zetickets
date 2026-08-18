import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User as UserModel
from app.schemas.token import TokenPayload
from app.services.db import AsyncSessionLocal, async_engine

logging.basicConfig(filename=settings.LOG_FILE, level=logging.INFO, encoding="utf-8", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl = f"{settings.API_V1_STR}/auth/login"
)

@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Manages application startup and shutdown database lifecycle.
    Attaches the session factory to app.state and gracefully disposes connection pools on shutdown.
    """
    app.state.session_factory = AsyncSessionLocal
    yield
    await async_engine.dispose()

async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Yields an isolated AsyncSession for the request lifecycle,
    ensuring it is safely closed afterward.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Type Aliases for Clean Endpoint Signatures
SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]

async def get_current_user(
        db: SessionDep,
        token: TokenDep,
) -> UserModel:
    """
    Validate JWT access token and return the authenticated user record from DB.
    """
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise credentials_exception
    except (jwt.PyJWTError, ValidationError) as e:
        logger.warning(f"JWT Validation failed: {e}")
        raise credentials_exception

    # Retrieve user ORM instance from database
    user = await db.get(UserModel, token_data.sub)
    if not user:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "User not found",
        )
    return user

async def get_current_active_user(
        current_user: Annotated[UserModel, Depends(get_current_user)]
) -> UserModel:
    """
    Ensure the authenticated user account is active.
    """
    if not getattr(current_user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )
    return current_user

async def get_current_superuser(
        current_user: Annotated[UserModel, Depends(get_current_active_user)]
) -> UserModel:
    """
    Ensure the authenticated user has superuser privileges.
    """
    user_role = getattr(current_user, "role", None)
    if user_role not in ("admin", "superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator privileges, contact Admin to provide authorization"
        )
    return current_user

# Type Aliases for Route Handlers just for convenience
CurrentUser = Annotated[UserModel, Depends(get_current_active_user)]
CurrentSuperUser = Annotated[UserModel, Depends(get_current_superuser)]

