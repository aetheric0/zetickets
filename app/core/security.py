from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jose import jwt as jose_jwt
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

    encoded_jwt = jose_jwt.encode(
        to_encode,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a token using the same validated key and algorithm as signing."""
    return jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[settings.ALGORITHM],
    )
