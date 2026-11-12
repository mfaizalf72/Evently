"""
Evently Application Configuration Module
Uses Pydantic Settings (v2) to load configuration from environment variables and .env file.
"""

from typing import Optional
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Settings
    PROJECT_NAME: str = "Evently"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # PostgreSQL Database Credentials
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "1234"
    POSTGRES_DB: str = "evently_dev"

    # Direct Database URLs (optional overrides)
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_SYNC: Optional[str] = None
    TEST_DATABASE_URL: Optional[str] = None
    TEST_DATABASE_URL_SYNC: Optional[str] = None

    @computed_field
    @property
    def async_database_url(self) -> str:
        """
        Async connection string for FastAPI runtime using SQLAlchemy asyncpg driver.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """
        Synchronous connection string for Alembic migrations and sync scripts using psycopg driver.
        """
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def test_async_database_url(self) -> str:
        """
        Async connection string for test runner using evently_test database.
        """
        if self.TEST_DATABASE_URL:
            return self.TEST_DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/evently_test"
        )

    @computed_field
    @property
    def test_sync_database_url(self) -> str:
        """
        Synchronous connection string for test runner setup/teardown using psycopg driver.
        """
        if self.TEST_DATABASE_URL_SYNC:
            return self.TEST_DATABASE_URL_SYNC
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/evently_test"
        )


# Global settings singleton instance
settings = Settings()
