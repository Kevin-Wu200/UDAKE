"""SQLAlchemy engine and session helpers for the auth database."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


def get_auth_database_url() -> str:
    """Resolve database URL with auth-specific setting first."""
    db_url = settings.AUTH_DATABASE_URL or settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "Missing database URL. Set AUTH_DATABASE_URL or DATABASE_URL in environment."
        )
    return db_url


def build_engine_options() -> Dict[str, Any]:
    """Return the configured PostgreSQL connection pool options."""
    return {
        "pool_size": settings.AUTH_DB_POOL_SIZE,
        "max_overflow": settings.AUTH_DB_MAX_OVERFLOW,
        "pool_timeout": settings.AUTH_DB_POOL_TIMEOUT,
        "pool_recycle": settings.AUTH_DB_POOL_RECYCLE,
        "pool_pre_ping": settings.AUTH_DB_PRE_PING,
        "future": True,
    }


def create_auth_engine(database_url: Optional[str] = None) -> Engine:
    """Create SQLAlchemy engine for auth database."""
    return create_engine(database_url or get_auth_database_url(), **build_engine_options())


def create_auth_session_factory(engine: Engine) -> sessionmaker:
    """Create session factory bound to the supplied engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ping_database(engine: Engine) -> bool:
    """Execute a lightweight query to verify database connectivity."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
