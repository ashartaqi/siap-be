from pathlib import Path
from typing import Any, Literal

from pydantic import (
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_ignore_empty=True, extra="ignore"
    )
    PROJECT_NAME: str = "SIAP"

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB_NAME: str

    ALLOWED_HOSTS: str
    SECRET_KEY: str
    ALGORITHM :str
    ACCESS_TOKEN_EXPIRE_MINUTES :int
    CRON_KEY : str
    FOOTBALL_DATA_API_KEY: str

    @computed_field
    @property
    def sqlalchemy_database_uri(self) -> MultiHostUrl:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB_NAME,
        )

settings = Settings()
