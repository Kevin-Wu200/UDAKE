"""SmartWorkflowService 数据访问层。"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
)

from app.auth_db.database import create_auth_engine
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    and_,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DAOError(RuntimeError):
    """DAO 统一错误类型。"""


class DAONotFoundError(DAOError):
    """DAO 未找到记录。"""


@dataclass
class PageResult(Generic[T]):
    items: List[T]
    total: int
    offset: int
    limit: int


class BaseDAO(Protocol, Generic[T]):
    def get(self, entity_id: str) -> Optional[T]:
        ...

    def upsert(self, entity_id: str, payload: Mapping[str, Any]) -> T:
        ...

    def delete(self, entity_id: str) -> bool:
        ...

    def paginate(self, offset: int = 0, limit: int = 100) -> PageResult[T]:
        ...

    def bulk_upsert(self, rows: Iterable[Tuple[str, Mapping[str, Any]]]) -> int:
        ...


class WorkflowDAO(BaseDAO[Dict[str, Any]], Protocol):
    def list_items(self) -> List[Dict[str, Any]]:
        ...


class TeamDAO(BaseDAO[Dict[str, Any]], Protocol):
    def list_items(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        ...


class CommentDAO(BaseDAO[Dict[str, Any]], Protocol):
    def list_by_workflow(self, workflow_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        ...


class NotificationDAO(BaseDAO[Dict[str, Any]], Protocol):
    def list_by_user(
        self,
        workflow_id: str,
        user_id: str,
        unread_only: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        ...


class DatabaseRetryPolicy:
    """数据库重试策略，处理连接失败与死锁类瞬时错误。"""

    def __init__(self, retries: int = 2, base_delay: float = 0.05) -> None:
        self._retries = max(0, int(retries))
        self._base_delay = max(0.0, float(base_delay))

    def run(self, fn):  # type: ignore[no-untyped-def]
        for attempt in range(self._retries + 1):
            try:
                return fn()
            except OperationalError as exc:
                if attempt >= self._retries:
                    raise
                message = str(exc).lower()
                if "deadlock" not in message and "timeout" not in message and "connection" not in message:
                    raise
                time.sleep(self._base_delay * (attempt + 1))


class DatabaseConnectionManager:
    """数据库连接池管理与健康检查。"""

    def __init__(self, engine: Engine, session_factory: sessionmaker) -> None:
        self.engine = engine
        self.session_factory = session_factory

    def health(self) -> Dict[str, Any]:
        try:
            with self.engine.connect() as conn:
                conn.execute(select(1))
            healthy = True
            error = ""
        except Exception as exc:  # pylint: disable=broad-except
            healthy = False
            error = str(exc)
        pool = self.engine.pool
        status = pool.status() if hasattr(pool, "status") else "unknown"
        return {
            "healthy": healthy,
            "pool_status": status,
            "dialect": self.engine.dialect.name,
            "error": error,
        }


class KVBase(DeclarativeBase):
    """DAO 专用模型基类。"""


class SmartWorkflowKV(KVBase):
    __tablename__ = "smart_workflow_kv"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_unread: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    payload_created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_smart_workflow_kv_type_id"),
        Index(
            "ix_smart_workflow_kv_type_workflow_created",
            "entity_type",
            "workflow_id",
            "payload_created_at",
        ),
        Index(
            "ix_smart_workflow_kv_type_workflow_user_unread_created",
            "entity_type",
            "workflow_id",
            "user_id",
            "is_unread",
            "payload_created_at",
        ),
        Index("ix_smart_workflow_kv_type_updated", "entity_type", "updated_at"),
    )


class QueryResultCache:
    """轻量 TTL 查询缓存，降低高频重复查询的数据库压力。"""

    def __init__(self, ttl_seconds: float = 2.0, max_entries: int = 1024) -> None:
        self._ttl = max(0.1, float(ttl_seconds))
        self._max_entries = max(16, int(max_entries))
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            value = self._store.get(key)
            if value is None:
                return None
            expires_at, payload = value
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            return payload

    def set(self, key: str, payload: Any) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._store) >= self._max_entries:
                oldest_key = min(self._store.items(), key=lambda item: item[1][0])[0]
                self._store.pop(oldest_key, None)
            self._store[key] = (now + self._ttl, payload)

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._store if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
            return len(keys)


class SQLAlchemyKVDAO(BaseDAO[Dict[str, Any]]):
    """通用 KV DAO，支持 CRUD/分页/批量操作。"""

    def __init__(
        self,
        entity_type: str,
        session_factory: sessionmaker,
        retry_policy: Optional[DatabaseRetryPolicy] = None,
        query_cache: Optional[QueryResultCache] = None,
    ) -> None:
        self._entity_type = entity_type
        self._session_factory = session_factory
        self._retry = retry_policy or DatabaseRetryPolicy()
        self._cache = query_cache or QueryResultCache()

    @staticmethod
    def _normalize_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes"}:
                return True
            if normalized in {"false", "0", "no"}:
                return False
        return bool(value)

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                return None
        return None

    @classmethod
    def _extract_index_fields(cls, payload: Mapping[str, Any]) -> Dict[str, Any]:
        workflow_id = payload.get("workflow_id")
        user_id = payload.get("user_id")
        read_value = payload.get("read")
        created_at = payload.get("created_at")
        return {
            "workflow_id": str(workflow_id) if workflow_id is not None else None,
            "user_id": str(user_id) if user_id is not None else None,
            "is_unread": None if read_value is None else not bool(cls._normalize_bool(read_value)),
            "payload_created_at": cls._parse_datetime(created_at),
        }

    @contextmanager
    def _tx(self):
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _run(self, fn):  # type: ignore[no-untyped-def]
        try:
            return self._retry.run(fn)
        except IntegrityError as exc:
            raise DAOError(str(exc)) from exc
        except SQLAlchemyError as exc:
            raise DAOError(str(exc)) from exc

    def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{self._entity_type}:get:{entity_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return dict(cached) if cached else None

        def _do():
            with self._tx() as session:
                row = session.scalar(
                    select(SmartWorkflowKV).where(
                        SmartWorkflowKV.entity_type == self._entity_type,
                        SmartWorkflowKV.entity_id == str(entity_id),
                    )
                )
                return dict(row.payload) if row else None

        result = self._run(_do)
        self._cache.set(cache_key, result)
        return result

    def upsert(self, entity_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = dict(payload)
        indexed = self._extract_index_fields(normalized)

        def _do():
            with self._tx() as session:
                row = session.scalar(
                    select(SmartWorkflowKV).where(
                        SmartWorkflowKV.entity_type == self._entity_type,
                        SmartWorkflowKV.entity_id == str(entity_id),
                    )
                )
                if row:
                    row.payload = normalized
                    row.workflow_id = indexed["workflow_id"]
                    row.user_id = indexed["user_id"]
                    row.is_unread = indexed["is_unread"]
                    row.payload_created_at = indexed["payload_created_at"]
                    row.updated_at = datetime.now(timezone.utc)
                else:
                    row = SmartWorkflowKV(
                        entity_type=self._entity_type,
                        entity_id=str(entity_id),
                        payload=normalized,
                        workflow_id=indexed["workflow_id"],
                        user_id=indexed["user_id"],
                        is_unread=indexed["is_unread"],
                        payload_created_at=indexed["payload_created_at"],
                    )
                    session.add(row)
                return normalized

        result = self._run(_do)
        self._cache.invalidate_prefix(f"{self._entity_type}:")
        return result

    def delete(self, entity_id: str) -> bool:
        def _do():
            with self._tx() as session:
                row = session.scalar(
                    select(SmartWorkflowKV).where(
                        SmartWorkflowKV.entity_type == self._entity_type,
                        SmartWorkflowKV.entity_id == str(entity_id),
                    )
                )
                if not row:
                    return False
                session.delete(row)
                return True

        deleted = bool(self._run(_do))
        if deleted:
            self._cache.invalidate_prefix(f"{self._entity_type}:")
        return deleted

    def paginate(self, offset: int = 0, limit: int = 100) -> PageResult[Dict[str, Any]]:
        cache_key = f"{self._entity_type}:paginate:{int(offset)}:{int(limit)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        def _do():
            start = max(0, int(offset))
            size = max(1, min(int(limit), 1000))
            with self._tx() as session:
                rows = list(
                    session.scalars(
                        select(SmartWorkflowKV)
                        .where(SmartWorkflowKV.entity_type == self._entity_type)
                        .order_by(SmartWorkflowKV.id.desc())
                        .offset(start)
                        .limit(size)
                    )
                )
                total = int(
                    session.query(SmartWorkflowKV)
                    .filter(SmartWorkflowKV.entity_type == self._entity_type)
                    .count()
                )
                return PageResult(
                    items=[dict(row.payload) for row in rows],
                    total=total,
                    offset=start,
                    limit=size,
                )

        result = self._run(_do)
        self._cache.set(cache_key, result)
        return result

    def bulk_upsert(self, rows: Iterable[Tuple[str, Mapping[str, Any]]]) -> int:
        def _do():
            normalized_rows = [(str(entity_id), dict(payload)) for entity_id, payload in rows]
            if not normalized_rows:
                return 0
            with self._tx() as session:
                entity_ids = [entity_id for entity_id, _ in normalized_rows]
                existing_rows = list(
                    session.scalars(
                        select(SmartWorkflowKV).where(
                            SmartWorkflowKV.entity_type == self._entity_type,
                            SmartWorkflowKV.entity_id.in_(entity_ids),
                        )
                    )
                )
                existing_map = {row.entity_id: row for row in existing_rows}
                for entity_id, payload in normalized_rows:
                    indexed = self._extract_index_fields(payload)
                    row = existing_map.get(entity_id)
                    if row is None:
                        session.add(
                            SmartWorkflowKV(
                                entity_type=self._entity_type,
                                entity_id=entity_id,
                                payload=payload,
                                workflow_id=indexed["workflow_id"],
                                user_id=indexed["user_id"],
                                is_unread=indexed["is_unread"],
                                payload_created_at=indexed["payload_created_at"],
                            )
                        )
                        continue
                    row.payload = payload
                    row.workflow_id = indexed["workflow_id"]
                    row.user_id = indexed["user_id"]
                    row.is_unread = indexed["is_unread"]
                    row.payload_created_at = indexed["payload_created_at"]
                    row.updated_at = datetime.now(timezone.utc)
            return len(normalized_rows)

        count = int(self._run(_do))
        if count:
            self._cache.invalidate_prefix(f"{self._entity_type}:")
        return count


class InMemoryDAO(BaseDAO[Dict[str, Any]]):
    """内存 DAO，保持测试/无数据库场景兼容。"""

    def __init__(self, store: MutableMapping[str, Dict[str, Any]]) -> None:
        self._store = store
        self._lock = RLock()

    def get(self, entity_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._store.get(str(entity_id))
            return dict(item) if item else None

    def upsert(self, entity_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        with self._lock:
            normalized = dict(payload)
            self._store[str(entity_id)] = normalized
            return dict(normalized)

    def delete(self, entity_id: str) -> bool:
        with self._lock:
            return self._store.pop(str(entity_id), None) is not None

    def paginate(self, offset: int = 0, limit: int = 100) -> PageResult[Dict[str, Any]]:
        with self._lock:
            rows = list(self._store.values())
        start = max(0, int(offset))
        size = max(1, min(int(limit), 1000))
        return PageResult(items=[dict(item) for item in rows[start : start + size]], total=len(rows), offset=start, limit=size)

    def bulk_upsert(self, rows: Iterable[Tuple[str, Mapping[str, Any]]]) -> int:
        count = 0
        for entity_id, payload in rows:
            self.upsert(entity_id, payload)
            count += 1
        return count


class InMemoryWorkflowDAO(InMemoryDAO, WorkflowDAO):
    def list_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._store.values()]


class InMemoryTeamDAO(InMemoryDAO, TeamDAO):
    def list_items(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        uid = str(user_id or "").strip()
        with self._lock:
            rows = [dict(item) for item in self._store.values()]
        if uid:
            rows = [item for item in rows if uid in (item.get("members") or {})]
        return rows


class InMemoryCommentDAO(InMemoryDAO, CommentDAO):
    def list_by_workflow(self, workflow_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = [
            item
            for item in self._store.values()
            if str(item.get("workflow_id") or "") == str(workflow_id)
        ]
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return [dict(item) for item in rows[: max(1, min(int(limit), 1000))]]


class InMemoryNotificationDAO(InMemoryDAO, NotificationDAO):
    def list_by_user(
        self,
        workflow_id: str,
        user_id: str,
        unread_only: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        rows = [
            item
            for item in self._store.values()
            if str(item.get("workflow_id") or "") == str(workflow_id)
            and str(item.get("user_id") or "") == str(user_id)
        ]
        if unread_only:
            rows = [item for item in rows if not bool(item.get("read", False))]
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return [dict(item) for item in rows[: max(1, min(int(limit), 500))]]


class SQLAlchemyWorkflowDAO(SQLAlchemyKVDAO, WorkflowDAO):
    def list_items(self) -> List[Dict[str, Any]]:
        page = self.paginate(offset=0, limit=5000)
        return page.items


class SQLAlchemyTeamDAO(SQLAlchemyKVDAO, TeamDAO):
    def list_items(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.paginate(offset=0, limit=5000).items
        uid = str(user_id or "").strip()
        if uid:
            rows = [item for item in rows if uid in (item.get("members") or {})]
        return rows


class SQLAlchemyCommentDAO(SQLAlchemyKVDAO, CommentDAO):
    def list_by_workflow(self, workflow_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        size = max(1, min(int(limit), 1000))
        cache_key = f"comment:list:{workflow_id}:{size}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        def _do():
            with self._tx() as session:
                rows = list(
                    session.scalars(
                        select(SmartWorkflowKV)
                        .where(
                            SmartWorkflowKV.entity_type == "comment",
                            SmartWorkflowKV.workflow_id == str(workflow_id),
                        )
                        .order_by(
                            SmartWorkflowKV.payload_created_at.desc().nullslast(),
                            SmartWorkflowKV.id.desc(),
                        )
                        .limit(size)
                    )
                )
                return [dict(row.payload) for row in rows]

        result = self._run(_do)
        self._cache.set(cache_key, result)
        return result


class SQLAlchemyNotificationDAO(SQLAlchemyKVDAO, NotificationDAO):
    def list_by_user(
        self,
        workflow_id: str,
        user_id: str,
        unread_only: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        size = max(1, min(int(limit), 500))
        cache_key = f"notification:list:{workflow_id}:{user_id}:{int(unread_only)}:{size}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        def _do():
            with self._tx() as session:
                filters = [
                    SmartWorkflowKV.entity_type == "notification",
                    SmartWorkflowKV.workflow_id == str(workflow_id),
                    SmartWorkflowKV.user_id == str(user_id),
                ]
                if unread_only:
                    filters.append(
                        and_(
                            SmartWorkflowKV.is_unread.isnot(None),
                            SmartWorkflowKV.is_unread.is_(True),
                        )
                    )
                rows = list(
                    session.scalars(
                        select(SmartWorkflowKV)
                        .where(*filters)
                        .order_by(
                            SmartWorkflowKV.payload_created_at.desc().nullslast(),
                            SmartWorkflowKV.id.desc(),
                        )
                        .limit(size)
                    )
                )
                return [dict(row.payload) for row in rows]

        result = self._run(_do)
        self._cache.set(cache_key, result)
        return result


@dataclass
class SmartWorkflowDAOBundle:
    backend: str
    workflow_dao: WorkflowDAO
    team_dao: TeamDAO
    comment_dao: CommentDAO
    notification_dao: NotificationDAO
    connection_manager: Optional[DatabaseConnectionManager]


def build_smart_workflow_daos(
    *,
    backend: str,
    workflows_store: MutableMapping[str, Dict[str, Any]],
    teams_store: MutableMapping[str, Dict[str, Any]],
    comments_store: MutableMapping[str, Dict[str, Any]],
    notifications_store: MutableMapping[str, Dict[str, Any]],
) -> SmartWorkflowDAOBundle:
    backend_name = str(backend or "auto").strip().lower()
    if backend_name not in {"auto", "database", "memory"}:
        backend_name = "auto"

    if backend_name in {"auto", "database"}:
        try:
            engine = create_auth_engine()
            session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
            KVBase.metadata.create_all(engine, tables=[SmartWorkflowKV.__table__])
            retry = DatabaseRetryPolicy()
            return SmartWorkflowDAOBundle(
                backend="database",
                workflow_dao=SQLAlchemyWorkflowDAO("workflow", session_factory, retry),
                team_dao=SQLAlchemyTeamDAO("team", session_factory, retry),
                comment_dao=SQLAlchemyCommentDAO("comment", session_factory, retry),
                notification_dao=SQLAlchemyNotificationDAO("notification", session_factory, retry),
                connection_manager=DatabaseConnectionManager(engine=engine, session_factory=session_factory),
            )
        except Exception as exc:  # pylint: disable=broad-except
            if backend_name == "database":
                raise DAOError(f"初始化数据库 DAO 失败: {exc}") from exc
            logger.warning("smart workflow DAO fallback to memory: %s", exc)

    return SmartWorkflowDAOBundle(
        backend="memory",
        workflow_dao=InMemoryWorkflowDAO(workflows_store),
        team_dao=InMemoryTeamDAO(teams_store),
        comment_dao=InMemoryCommentDAO(comments_store),
        notification_dao=InMemoryNotificationDAO(notifications_store),
        connection_manager=None,
    )
