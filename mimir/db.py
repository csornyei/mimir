from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mimir.config import config

# Base is defined in mimir.models to avoid circular imports.
# Import it here so existing code that does `from mimir.db import Base` keeps working.
from mimir.models import Base  # noqa: F401

engine = create_async_engine(config.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager session for use outside FastAPI's dependency injection (e.g. scheduler jobs)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
