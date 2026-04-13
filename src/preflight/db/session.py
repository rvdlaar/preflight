"""
Database session management for Preflight.

Async-first — all database access goes through async sessions.
Phase 1 uses SQLite for local dev (no pgvector), PostgreSQL for production.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

from preflight.db.models import Base


def get_database_url() -> str:
    import os

    url = os.environ.get("PREFLIGHT_DATABASE_URL")
    if url:
        return url
    data_dir = Path.home() / ".preflight"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "preflight.db"
    return f"sqlite+aiosqlite:///{db_path}"


def get_sync_url() -> str:
    import os

    url = os.environ.get("PREFLIGHT_DATABASE_URL")
    if url:
        return url.replace("+aiosqlite", "").replace("+asyncpg", "")
    data_dir = Path.home() / ".preflight"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "preflight.db"
    return f"sqlite:///{db_path}"


_async_engine: AsyncEngine | None = None
_sync_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def get_async_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        url = get_database_url()
        _async_engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    return _async_engine


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        url = get_sync_url()
        _sync_engine = create_engine(url, echo=False, pool_pre_ping=True)
    return _sync_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_factory


def get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(get_sync_engine(), expire_on_commit=False)
    return _sync_session_factory


async def init_db() -> None:
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync() -> None:
    engine = get_sync_engine()
    Base.metadata.create_all(engine)
