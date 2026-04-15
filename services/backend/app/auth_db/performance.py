"""Auth DB performance helpers: query stats, slow-query insights, read-write routing, and replication monitor."""

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


@dataclass
class SlowQuerySample:
    statement: str
    elapsed_ms: float
    occurred_at: int


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


class SlowQueryMonitor:
    """Collect and analyze slow-query behaviour for diagnostics and alerting."""

    def __init__(
        self,
        *,
        threshold_ms: int = 100,
        max_samples: int = 1000,
        alert_p95_ms: int = 500,
        alert_slow_ratio: float = 0.2,
    ) -> None:
        self._threshold_ms = max(1, int(threshold_ms))
        self._max_samples = max(100, int(max_samples))
        self._alert_p95_ms = max(1, int(alert_p95_ms))
        self._alert_slow_ratio = max(0.0, min(1.0, float(alert_slow_ratio)))
        self._lock = threading.RLock()
        self._slow_samples: List[SlowQuerySample] = []
        self._elapsed_all: List[float] = []
        self._sql_frequency: Dict[str, int] = {}
        self._sql_slow_frequency: Dict[str, int] = {}
        self._total_queries = 0
        self._slow_queries = 0

    @staticmethod
    def _normalize_sql(statement: str) -> str:
        return " ".join(str(statement).split())

    def observe(self, *, statement: str, elapsed_ms: float) -> None:
        sql = self._normalize_sql(statement)
        elapsed = float(elapsed_ms)
        now = int(time.time())
        with self._lock:
            self._total_queries += 1
            self._sql_frequency[sql] = self._sql_frequency.get(sql, 0) + 1
            self._elapsed_all.append(elapsed)
            if len(self._elapsed_all) > self._max_samples:
                self._elapsed_all.pop(0)

            if elapsed >= self._threshold_ms:
                self._slow_queries += 1
                self._sql_slow_frequency[sql] = self._sql_slow_frequency.get(sql, 0) + 1
                self._slow_samples.append(
                    SlowQuerySample(statement=sql, elapsed_ms=elapsed, occurred_at=now)
                )
                if len(self._slow_samples) > self._max_samples:
                    self._slow_samples.pop(0)

    def _percentile(self, values: List[float], ratio: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = int((len(ordered) - 1) * ratio)
        return float(ordered[max(0, min(len(ordered) - 1, idx))])

    def snapshot(self, *, top_n: int = 10) -> Dict[str, Any]:
        with self._lock:
            elapsed = list(self._elapsed_all)
            slow_rows = sorted(self._slow_samples, key=lambda item: item.elapsed_ms, reverse=True)[: max(1, int(top_n))]
            frequent_slow = sorted(self._sql_slow_frequency.items(), key=lambda item: item[1], reverse=True)[
                : max(1, int(top_n))
            ]
            total = self._total_queries
            slow = self._slow_queries
        avg = float(sum(elapsed) / len(elapsed)) if elapsed else 0.0
        p95 = self._percentile(elapsed, 0.95)
        p99 = self._percentile(elapsed, 0.99)
        slow_ratio = (float(slow) / float(total)) if total else 0.0
        return {
            "threshold_ms": self._threshold_ms,
            "total_queries": total,
            "slow_queries": slow,
            "slow_ratio": round(slow_ratio, 4),
            "avg_ms": round(avg, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "max_ms": round(max(elapsed), 2) if elapsed else 0.0,
            "slow_top_sql": [{"sql": sql, "count": count} for sql, count in frequent_slow],
            "recent_slow_samples": [
                {"sql": item.statement, "elapsed_ms": round(item.elapsed_ms, 2), "occurred_at": item.occurred_at}
                for item in slow_rows
            ],
            "alerts": self.alerts(min_samples=20),
        }

    def alerts(self, *, min_samples: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            total = self._total_queries
            slow = self._slow_queries
            elapsed = list(self._elapsed_all)
        rows: List[Dict[str, Any]] = []
        if total < max(1, int(min_samples)):
            return rows
        p95 = self._percentile(elapsed, 0.95)
        ratio = (float(slow) / float(total)) if total else 0.0
        if p95 >= self._alert_p95_ms:
            rows.append(
                {
                    "level": "warning",
                    "type": "slow_query_p95",
                    "message": f"P95查询耗时达到 {round(p95, 2)}ms，超过阈值 {self._alert_p95_ms}ms",
                }
            )
        if ratio >= self._alert_slow_ratio:
            rows.append(
                {
                    "level": "warning",
                    "type": "slow_query_ratio",
                    "message": f"慢查询占比 {round(ratio * 100, 2)}%，超过阈值 {round(self._alert_slow_ratio * 100, 2)}%",
                }
            )
        return rows


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
