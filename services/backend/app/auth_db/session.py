"""Session dependency helpers for auth database APIs."""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from .database import create_auth_engine, create_auth_session_factory


@lru_cache(maxsize=1)
def get_auth_session_factory() -> sessionmaker:
    """Build and cache auth DB session factory."""
    engine = create_auth_engine()
    return create_auth_session_factory(engine)


def get_auth_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields an auth DB session."""
    try:
        session_factory = get_auth_session_factory()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": f"认证数据库未配置: {exc}", "data": {}},
        ) from exc
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
