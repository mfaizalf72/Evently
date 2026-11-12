"""
Evently Database Session Management
Configures SQLAlchemy 2.0 async and sync engines, session makers, and FastAPI dependencies.
"""

from typing import AsyncGenerator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Async Engine (Used for FastAPI request lifecycle)
async_engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Synchronous Engine (Used by Alembic and synchronous maintenance tasks)
sync_engine = create_engine(
    settings.sync_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Sync Session Factory
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an async database session per request.
    Ensures safe rollback on exception and guaranteed cleanup.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection(session: Optional[AsyncSession] = None) -> dict:
    """
    Utility function to verify active database connectivity.
    If an existing session is passed (e.g. from request dependency), it uses it;
    otherwise creates a temporary session.
    """
    try:
        if session is not None:
            await session.execute(text("SELECT 1"))
        else:
            async with AsyncSessionLocal() as temp_session:
                await temp_session.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        return {"status": "unhealthy", "database": "disconnected", "error": str(exc)}
