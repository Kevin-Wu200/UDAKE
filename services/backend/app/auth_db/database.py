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

from app.auth_db.performance import ReadWriteSessionRouter, SlowQueryMonitor
from app.config import settings

logger = logging.getLogger(__name__)
_SLOW_QUERY_MONITOR = SlowQueryMonitor(
    threshold_ms=int(getattr(settings, "AUTH_DB_LOG_SLOW_QUERY_MS", 100)),
    max_samples=2000,
)


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
    return {"sslmode": "disable"}


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
        _SLOW_QUERY_MONITOR.observe(statement=str(statement), elapsed_ms=float(elapsed_ms))
        if elapsed_ms >= threshold_ms:
            logger.warning("slow query %.2fms sql=%s", elapsed_ms, " ".join(str(statement).split())[:500])


def get_slow_query_report(top_n: int = 20) -> Dict[str, Any]:
    """Get aggregated slow-query metrics and alert hints."""
    return _SLOW_QUERY_MONITOR.snapshot(top_n=top_n)


def create_auth_engine(database_url: Optional[str] = None) -> Engine:
    """Create SQLAlchemy engine for auth database."""
    resolved_url = database_url or get_auth_database_url()
    if settings.AUTH_DB_REQUIRE_SSL and _is_postgres_url(resolved_url):
        resolved_url = _ensure_query_param(resolved_url, key="sslmode", value=settings.AUTH_DB_SSLMODE)
    engine = create_engine(resolved_url, **_build_engine_options(resolved_url))
    if settings.AUTH_DB_SLOW_QUERY_ENABLED:
        _enable_slow_query_logging(engine)
    return engine


def create_auth_replica_engines() -> list[Engine]:
    """Create read replica engines from AUTH_DB_READ_REPLICA_URLS."""
    replica_urls = settings.AUTH_DB_READ_REPLICA_URLS
    engines: list[Engine] = []
    for raw_url in replica_urls:
        url = str(raw_url or "").strip()
        if not url:
            continue
        replica_url = url
        if settings.AUTH_DB_REQUIRE_SSL and _is_postgres_url(replica_url):
            replica_url = _ensure_query_param(replica_url, key="sslmode", value=settings.AUTH_DB_SSLMODE)
        engines.append(create_engine(replica_url, **_build_engine_options(replica_url)))
    return engines


def create_auth_session_factory(engine: Engine) -> sessionmaker:
    """Create session factory bound to the supplied engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def create_read_write_router(
    primary_engine: Optional[Engine] = None,
    replica_engines: Optional[list[Engine]] = None,
) -> ReadWriteSessionRouter:
    """Build read/write router using primary and optional replica engines."""
    resolved_primary = primary_engine or create_auth_engine()
    resolved_replicas = replica_engines if replica_engines is not None else create_auth_replica_engines()
    primary_session_factory = create_auth_session_factory(resolved_primary)
    replica_factories = [create_auth_session_factory(engine) for engine in resolved_replicas]
    return ReadWriteSessionRouter(primary_session_factory=primary_session_factory, replica_session_factories=replica_factories)


def ping_database(engine: Engine) -> bool:
    """Execute a lightweight query to verify database connectivity."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
