"""
Pytest Test Fixtures Configuration
Provides async test client, database session overrides, and lifecycle fixtures.
"""

from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.database.session import get_db
from app.main import app
from app.models.base import Base

# Synchronous test engine for schema migrations / table setup
test_sync_engine = create_engine(
    settings.test_sync_database_url,
    pool_pre_ping=True,
)

# Async test engine with NullPool to prevent event loop connection leaks
test_async_engine = create_async_engine(
    settings.test_async_database_url,
    poolclass=NullPool,
    echo=False,
    future=True,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Creates all tables synchronously before the test session and cleans them up after.
    Using synchronous psycopg avoids any pytest-asyncio event-loop scope mismatch.
    """
    Base.metadata.create_all(bind=test_sync_engine)
    yield
    Base.metadata.drop_all(bind=test_sync_engine)
    test_sync_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an async database session for a test function.
    Rolls back any changes when the test finishes.
    """
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an AsyncClient bound to the FastAPI application with get_db overridden.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
