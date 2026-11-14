"""
Pytest Test Fixtures Configuration
Provides async test client, database session overrides, authentication fixtures, and lifecycle hooks.
"""

from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User

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


@pytest.fixture(autouse=True)
def clean_tables_between_tests():
    """
    Truncates all tables after each test so every test runs in complete database isolation,
    even when services perform explicit commits.
    """
    yield
    with test_sync_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE events, users RESTART IDENTITY CASCADE;"))


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
    Provides an unauthenticated AsyncClient bound to the FastAPI application with get_db overridden.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_organizer(db_session: AsyncSession) -> User:
    """Creates a persistent organizer user for integration tests."""
    user = User(
        email="organizer@evently.com",
        hashed_password=hash_password("Password123!"),
        full_name="Alice Organizer",
        role="organizer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def organizer_token(test_organizer: User) -> str:
    """Generates a valid JWT access token for the test organizer."""
    return create_access_token(subject=test_organizer.id, role=test_organizer.role)


@pytest.fixture
async def organizer_client(async_client: AsyncClient, organizer_token: str) -> AsyncClient:
    """Configures async_client with Bearer authentication for the organizer."""
    async_client.headers["Authorization"] = f"Bearer {organizer_token}"
    return async_client


@pytest.fixture
async def test_customer(db_session: AsyncSession) -> User:
    """Creates a persistent customer user for integration tests."""
    user = User(
        email="customer@evently.com",
        hashed_password=hash_password("Password123!"),
        full_name="Bob Customer",
        role="customer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def customer_token(test_customer: User) -> str:
    """Generates a valid JWT access token for the test customer."""
    return create_access_token(subject=test_customer.id, role=test_customer.role)


@pytest.fixture
async def customer_client(async_client: AsyncClient, customer_token: str) -> AsyncClient:
    """Configures async_client with Bearer authentication for the customer."""
    async_client.headers["Authorization"] = f"Bearer {customer_token}"
    return async_client


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Creates a persistent administrator user for integration tests."""
    user = User(
        email="admin@evently.com",
        hashed_password=hash_password("Password123!"),
        full_name="Carol Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_token(test_admin: User) -> str:
    """Generates a valid JWT access token for the test admin."""
    return create_access_token(subject=test_admin.id, role=test_admin.role)


@pytest.fixture
async def admin_client(async_client: AsyncClient, admin_token: str) -> AsyncClient:
    """Configures async_client with Bearer authentication for the admin."""
    async_client.headers["Authorization"] = f"Bearer {admin_token}"
    return async_client
