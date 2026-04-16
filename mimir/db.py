from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Re-export Base so existing code that does `from mimir.db import Base` keeps working.
from mimir.base import Base  # noqa: F401

_engine = None
_async_session_factory = None


def initialize_db(database_url: str) -> None:
    """Initialize the database engine. Must be called once per app at startup."""
    global _engine, _async_session_factory
    _engine = create_async_engine(database_url)
    _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_db() -> None:
    """Dispose of the database engine and clean up resources."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions. Requires initialize_db() to be called at startup."""
    if _async_session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_db(database_url) at app startup."
        )
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager session for use outside FastAPI's dependency injection (e.g. scheduler jobs).
    Requires initialize_db() to be called at startup."""
    if _async_session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call initialize_db(database_url) at app startup."
        )
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
