"""SQLAlchemy engine and session helpers for the auth database."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


def get_auth_database_url() -> str:
    """Resolve database URL with auth-specific setting first."""
    db_url = settings.AUTH_DATABASE_URL or settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError(
            "Missing database URL. Set AUTH_DATABASE_URL or DATABASE_URL in environment."
        )
    return db_url


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgresql+psycopg2://")


def _ensure_query_param(url: str, *, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _build_ssl_connect_args(database_url: str) -> Dict[str, Any]:
    if not _is_postgres_url(database_url):
        return {}
    connect_args: Dict[str, Any] = {"sslmode": settings.AUTH_DB_SSLMODE}
    cert_mapping = {
        "sslcert": settings.AUTH_DB_SSLCERT,
        "sslkey": settings.AUTH_DB_SSLKEY,
        "sslrootcert": settings.AUTH_DB_SSLROOTCERT,
    }
    for key, path in cert_mapping.items():
        if not path:
            continue
        cert_path = Path(path).expanduser()
        if not cert_path.exists():
            raise ValueError(f"{key} 证书路径不存在: {cert_path}")
        connect_args[key] = str(cert_path)
    return connect_args


def _build_engine_options(database_url: str) -> Dict[str, Any]:
    options = {
        "pool_size": settings.AUTH_DB_POOL_SIZE,
        "max_overflow": settings.AUTH_DB_MAX_OVERFLOW,
        "pool_timeout": settings.AUTH_DB_POOL_TIMEOUT,
        "pool_recycle": settings.AUTH_DB_POOL_RECYCLE,
        "pool_pre_ping": settings.AUTH_DB_PRE_PING,
        "future": True,
    }
    connect_args = _build_ssl_connect_args(database_url)
    if connect_args:
        options["connect_args"] = connect_args
    return options


def build_engine_options() -> Dict[str, Any]:
    """Return the configured PostgreSQL connection pool options."""
    db_url = settings.AUTH_DATABASE_URL or settings.DATABASE_URL or os.getenv("DATABASE_URL") or ""
    if not db_url:
        return _build_engine_options("postgresql://placeholder")
    return _build_engine_options(db_url)


def _enable_slow_query_logging(engine: Engine) -> None:
    threshold_ms = max(1, int(settings.AUTH_DB_LOG_SLOW_QUERY_MS))

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        start_stack = conn.info.get("query_start_time") or []
        if not start_stack:
            return
        start = start_stack.pop()
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= threshold_ms:
            logger.warning("slow query %.2fms sql=%s", elapsed_ms, " ".join(str(statement).split())[:500])


def create_auth_engine(database_url: Optional[str] = None) -> Engine:
    """Create SQLAlchemy engine for auth database."""
    resolved_url = database_url or get_auth_database_url()
    if settings.AUTH_DB_REQUIRE_SSL and _is_postgres_url(resolved_url):
        resolved_url = _ensure_query_param(resolved_url, key="sslmode", value=settings.AUTH_DB_SSLMODE)
    engine = create_engine(resolved_url, **_build_engine_options(resolved_url))
    if settings.AUTH_DB_SLOW_QUERY_ENABLED:
        _enable_slow_query_logging(engine)
    return engine


def create_auth_session_factory(engine: Engine) -> sessionmaker:
    """Create session factory bound to the supplied engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ping_database(engine: Engine) -> bool:
    """Execute a lightweight query to verify database connectivity."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
