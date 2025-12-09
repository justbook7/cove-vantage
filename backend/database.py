"""
Database connection and session management.

This module provides SQLAlchemy setup for the Cove database,
including connection management and session handling.
"""

import os
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Base class for ORM models
Base = declarative_base()

# Database URL from environment or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/cove.db")

# Convert sqlite:// to sqlite+aiosqlite:// for async support
if DATABASE_URL.startswith("sqlite://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Create async engine
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    future=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Synchronous engine for migrations and one-time operations
sync_engine = create_engine(
    DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://"),
    echo=False,
)

SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine,
)


async def init_db():
    """
    Initialize database by creating all tables.
    Called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db():
    """
    Async context manager for database sessions.

    Usage:
        async with get_db() as db:
            result = await db.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db():
    """
    Synchronous database session for migration scripts.

    Usage:
        with get_sync_db() as db:
            result = db.execute(...)
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
