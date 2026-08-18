from typing import Annotated, Any, Literal, cast

from pydantic import (
    AnyUrl,
    BeforeValidator,
    computed_field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy.engine import URL


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str):
        if not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v
    elif isinstance(v, list):
        return [str(i) for i in cast(list[object], v)]
    elif isinstance(v, str):
        return v
    raise ValueError(f"Invalid CORS origins format: {v}")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore"
    )
    API_V1_STR: str = "/api/v1"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 3
    FRONTEND_HOST: str = ""
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    PROJECT_NAME: str = "zetickets"

    POSTGRES_SERVER: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    PAYSTACK_SECRET_KEY: str = ""
    JWT_SECRET: str = ""
    ALGORITHM: str = ""
    SECRET_KEY: str = ""

    LOG_FILE: str | None = ""

    @computed_field
    @property
    def SQL_ALCHEMY_DATABASE_URI(self) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

settings = Settings()
