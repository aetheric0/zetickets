from datetime import UTC, datetime, timedelta
import secrets
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, settings
from app.core.deps import get_current_user
from app.core.security import create_access_token


@pytest.fixture
def test_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = secrets.token_urlsafe(48)
    monkeypatch.setattr(settings, "JWT_SECRET", SecretStr(secret))
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    return secret


class UserLookup:
    def __init__(self, user: object | None = None) -> None:
        self.user = user
        self.lookups: list[tuple[object, object]] = []

    async def get(self, model: object, identity: object) -> object | None:
        self.lookups.append((model, identity))
        return self.user


def encode_token(secret: str, *, claims: dict[str, object]) -> str:
    return jose_jwt.encode(claims, secret, algorithm="HS256")


def assert_secret_not_present(secret: str, output: str) -> None:
    if secret in output:
        pytest.fail("Sensitive test value was exposed in output")


@pytest.mark.asyncio
async def test_application_created_token_is_verified_by_application(test_jwt_secret: str) -> None:
    user_id = uuid4()
    user = object()
    db = UserLookup(user)
    token = create_access_token(user_id)

    resolved_user = await get_current_user(db, token)

    assert resolved_user is user
    assert db.lookups[0][1] == str(user_id)
    decoded = jwt.decode(token, test_jwt_secret, algorithms=["HS256"])
    assert decoded["sub"] == str(user_id)


@pytest.mark.asyncio
async def test_token_signed_with_different_secret_is_rejected(
    test_jwt_secret: str, caplog: pytest.LogCaptureFixture
) -> None:
    other_secret = secrets.token_urlsafe(48)
    token = encode_token(
        other_secret,
        claims={"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
    )
    db = UserLookup(object())

    with pytest.raises(HTTPException) as raised:
        await get_current_user(db, token)

    assert raised.value.status_code == 401
    assert db.lookups == []
    assert_secret_not_present(other_secret, str(raised.value.detail))
    assert_secret_not_present(other_secret, caplog.text)
    assert_secret_not_present(token, caplog.text)


@pytest.mark.asyncio
async def test_token_signed_with_unconfigured_algorithm_is_rejected(test_jwt_secret: str) -> None:
    token = jose_jwt.encode(
        {"sub": str(uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        test_jwt_secret,
        algorithm="HS384",
    )
    db = UserLookup(object())

    with pytest.raises(HTTPException) as raised:
        await get_current_user(db, token)

    assert raised.value.status_code == 401
    assert db.lookups == []


@pytest.mark.asyncio
async def test_invalid_token_is_rejected_without_database_lookup(test_jwt_secret: str) -> None:
    db = UserLookup(object())

    with pytest.raises(HTTPException) as raised:
        await get_current_user(db, "not.a.valid-token")

    assert raised.value.status_code == 401
    assert db.lookups == []


@pytest.mark.asyncio
async def test_expired_token_is_rejected(test_jwt_secret: str) -> None:
    token = encode_token(
        test_jwt_secret,
        claims={"sub": str(uuid4()), "exp": datetime.now(UTC) - timedelta(seconds=1)},
    )
    db = UserLookup(object())

    with pytest.raises(HTTPException) as raised:
        await get_current_user(db, token)

    assert raised.value.status_code == 401
    assert db.lookups == []


@pytest.mark.asyncio
async def test_missing_or_invalid_subject_claim_is_rejected(test_jwt_secret: str) -> None:
    token = encode_token(
        test_jwt_secret,
        claims={"exp": datetime.now(UTC) + timedelta(minutes=5), "sub": None},
    )
    db = UserLookup(object())

    with pytest.raises(HTTPException) as raised:
        await get_current_user(db, token)

    assert raised.value.status_code == 401
    assert db.lookups == []


def test_missing_jwt_secret_fails_settings_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError) as raised:
        Settings(_env_file=None, ALGORITHM="HS256")

    message = str(raised.value)
    assert "JWT_SECRET" in message
    assert "token" not in message.lower()


def test_short_jwt_secret_fails_without_echoing_value() -> None:
    generated_invalid_secret = secrets.token_urlsafe(8)

    with pytest.raises(ValueError) as raised:
        Settings(_env_file=None, JWT_SECRET=generated_invalid_secret, ALGORITHM="HS256")

    assert "JWT_SECRET" in str(raised.value)
    assert_secret_not_present(generated_invalid_secret, str(raised.value))


def test_secret_setting_uses_secret_str_representation() -> None:
    generated_secret = secrets.token_urlsafe(48)
    configured = Settings(
        _env_file=None,
        JWT_SECRET=generated_secret,
        ALGORITHM="HS256",
    )

    assert isinstance(configured.JWT_SECRET, SecretStr)
    assert_secret_not_present(generated_secret, repr(configured))
    assert_secret_not_present(generated_secret, str(configured.JWT_SECRET))
