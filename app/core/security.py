from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

password_hash = PasswordHash((BcryptHasher(),))

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against an existing bcrypt hash.
    """
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return password_hash.hash(password)

def create_access_token(
        subject: str | Any, 
        expires_delta: timedelta | None = None,
    ) -> str:
    """
    Generate a signed JWT token containing the user identifier
    (subject) and an expiration timestamp (exp).
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode: dict[str, Any] = {
        "exp": expire,
        "sub": str(subject),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt