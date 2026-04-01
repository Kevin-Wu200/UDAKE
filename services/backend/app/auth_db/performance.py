"""Auth DB performance helpers: query stats, read-write routing, and replication monitor."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


@dataclass
class QuerySample:
    statement: str
    elapsed_ms: float


class QueryStatsCollector:
    """Track slow/frequent query patterns for diagnostics."""

    def __init__(self, slow_ms: int = 100, max_samples: int = 1000) -> None:
        self._slow_ms = max(1, int(slow_ms))
        self._max_samples = max(100, int(max_samples))
        self._samples: List[QuerySample] = []
        self._freq: Dict[str, int] = {}
        self._lock = threading.RLock()

    def record(self, statement: str, elapsed_ms: float) -> None:
        normalized = " ".join(str(statement).split())
        with self._lock:
            self._freq[normalized] = self._freq.get(normalized, 0) + 1
            if elapsed_ms >= self._slow_ms:
                if len(self._samples) >= self._max_samples:
                    self._samples.pop(0)
                self._samples.append(QuerySample(statement=normalized, elapsed_ms=float(elapsed_ms)))

    def report(self, top_n: int = 10) -> Dict[str, Any]:
        with self._lock:
            slow_queries = sorted(self._samples, key=lambda item: item.elapsed_ms, reverse=True)[: max(1, int(top_n))]
            frequent = sorted(self._freq.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_n))]
        return {
            "slow_queries": [{"sql": item.statement, "elapsed_ms": round(item.elapsed_ms, 2)} for item in slow_queries],
            "frequent_queries": [{"sql": sql, "count": count} for sql, count in frequent],
            "tracked_queries": sum(freq for _, freq in frequent),
        }


class ReadWriteSessionRouter:
    """Route writes to primary and reads to replicas (fallback to primary)."""

    def __init__(
        self,
        primary_session_factory: sessionmaker,
        replica_session_factories: Optional[List[sessionmaker]] = None,
    ) -> None:
        self._primary = primary_session_factory
        self._replicas = replica_session_factories or []
        self._replica_idx = 0
        self._lock = threading.RLock()
        self._tx_local = threading.local()

    @contextmanager
    def transaction(self):
        setattr(self._tx_local, "in_tx", True)
        session: Session = self._primary()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            setattr(self._tx_local, "in_tx", False)

    def _next_replica(self) -> sessionmaker:
        with self._lock:
            factory = self._replicas[self._replica_idx % len(self._replicas)]
            self._replica_idx = (self._replica_idx + 1) % len(self._replicas)
            return factory

    @contextmanager
    def read_session(self):
        in_tx = bool(getattr(self._tx_local, "in_tx", False))
        factory = self._primary if (in_tx or not self._replicas) else self._next_replica()
        session: Session = factory()
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def write_session(self):
        session: Session = self._primary()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class ReplicaSyncMonitor:
    """Monitor replica lag and state for health checks and alerting."""

    def __init__(
        self,
        check_fn: Callable[[], List[Dict[str, Any]]],
        lag_warn_seconds: Optional[int] = None,
    ) -> None:
        self._check_fn = check_fn
        self._lag_warn = max(1, int(lag_warn_seconds or settings.AUTH_DB_REPLICA_LAG_WARN_SECONDS))

    def snapshot(self) -> Dict[str, Any]:
        status_rows = self._check_fn()
        max_lag = 0.0
        degraded = False
        for row in status_rows:
            lag = float(row.get("lag_seconds", 0.0) or 0.0)
            max_lag = max(max_lag, lag)
            if lag >= self._lag_warn or not bool(row.get("healthy", True)):
                degraded = True
        return {
            "replicas": status_rows,
            "max_lag_seconds": round(max_lag, 3),
            "healthy": not degraded,
            "checked_at": int(time.time()),
        }


def build_default_replica_status_checker(replica_engines: List[Engine]) -> Callable[[], List[Dict[str, Any]]]:
    def _check() -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx, engine in enumerate(replica_engines):
            healthy = True
            error = ""
            lag_seconds = 0.0
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    if engine.dialect.name == "postgresql":
                        lag = conn.execute(
                            text(
                                "SELECT COALESCE(EXTRACT(EPOCH FROM now() - pg_last_xact_replay_timestamp()), 0)"
                            )
                        ).scalar_one_or_none()
                        lag_seconds = float(lag or 0.0)
            except Exception as exc:  # pylint: disable=broad-except
                healthy = False
                error = str(exc)
            rows.append(
                {
                    "replica": f"replica-{idx + 1}",
                    "dialect": engine.dialect.name,
                    "healthy": healthy,
                    "lag_seconds": round(lag_seconds, 3),
                    "error": error,
                }
            )
        return rows

    return _check
