"""工作流协作数据迁移工具：内存导出、数据库导入、校验与回滚。"""

from __future__ import annotations

import copy
import json
import logging
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from app.auth_db.models import (
    CollaborationOperation,
    Comment,
    Delegation,
    Notification,
    Team,
    TeamMember,
    User,
    Workflow,
    WorkflowVersion,
)

logger = logging.getLogger(__name__)


ISO_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

SECTION_NAMES = (
    "workflows",
    "teams",
    "members",
    "operations",
    "comments",
    "notifications",
)

REQUIRED_FIELDS: Dict[str, Tuple[str, ...]] = {
    "workflows": ("workflow_id", "name", "current", "versions"),
    "teams": ("team_id", "name", "owner_user_id"),
    "members": ("team_id", "user_id", "role"),
    "operations": ("workflow_id", "actor_id", "operation_type", "created_at"),
    "comments": ("workflow_id", "comment_id", "user_id", "content", "created_at"),
    "notifications": ("workflow_id", "notification_id", "user_id", "event_type", "created_at"),
}

EXPECTED_INDEXES: Dict[str, Set[str]] = {
    "workflows": {"ix_workflows_owner_id", "ix_workflows_is_public", "ix_workflows_created_at"},
    "workflow_versions": {"ix_workflow_versions_workflow_id", "ix_workflow_versions_version_number"},
    "teams": {"ix_teams_owner_id"},
    "team_members": {"ix_team_members_team_id", "ix_team_members_user_id"},
    "comments": {"ix_comments_workflow_id", "ix_comments_parent_id", "ix_comments_user_id"},
    "notifications": {"ix_notifications_user_id", "ix_notifications_is_read", "ix_notifications_type"},
    "collaboration_operations": {
        "ix_collaboration_operations_workflow_id",
        "ix_collaboration_operations_user_id",
        "ix_collaboration_operations_created_at",
    },
    "delegations": {"ix_delegations_workflow_id", "ix_delegations_delegator_id", "ix_delegations_delegate_id"},
}


class MigrationValidationError(ValueError):
    """迁移数据验证失败。"""


def _to_iso(value: Any, *, default: Optional[str] = None) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    return default or datetime.now(timezone.utc).isoformat()


def _to_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return ISO_EPOCH
    return ISO_EPOCH


def _ensure_mapping(item: Any, *, section: str) -> Mapping[str, Any]:
    if not isinstance(item, Mapping):
        raise MigrationValidationError(f"{section} 条目必须是对象")
    return item


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(dict(_ensure_mapping(json.loads(text), section=str(path.name))))
    return rows


def _append_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(dict(row), ensure_ascii=False) + "\n")


def _iter_chunks(rows: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    chunk_size = max(1, int(size))
    for index in range(0, len(rows), chunk_size):
        yield rows[index : index + chunk_size]


def _extract_legacy_user_ids(snapshot: Mapping[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for item in snapshot.get("workflows", []):
        workflow = dict(_ensure_mapping(item, section="workflows"))
        owner_id = str(workflow.get("owner_user_id") or "").strip()
        if owner_id:
            ids.add(owner_id)
        for collab in workflow.get("collaborators", []) or []:
            user_id = str((collab or {}).get("user_id") or "").strip()
            if user_id:
                ids.add(user_id)
    for team in snapshot.get("teams", []):
        owner = str((team or {}).get("owner_user_id") or "").strip()
        if owner:
            ids.add(owner)
    for member in snapshot.get("members", []):
        uid = str((member or {}).get("user_id") or "").strip()
        if uid:
            ids.add(uid)
    for delegation in snapshot.get("delegations", []):
        item = dict(_ensure_mapping(delegation, section="delegations"))
        from_uid = str(item.get("from_user_id") or "").strip()
        to_uid = str(item.get("to_user_id") or "").strip()
        if from_uid:
            ids.add(from_uid)
        if to_uid:
            ids.add(to_uid)
    for section in ("operations", "comments", "notifications"):
        for row in snapshot.get(section, []):
            item = dict(_ensure_mapping(row, section=section))
            uid = str(item.get("user_id") or item.get("actor_id") or "").strip()
            if uid:
                ids.add(uid)
    return ids


@dataclass
class ImportOptions:
    """导入配置。"""

    batch_size: int = 200
    retry_times: int = 2
    continue_on_error: bool = True
    conflict_strategy: str = "upsert"  # upsert | skip | error
    partial_commit: bool = True
    workers: int = 4


class WorkflowMigrationToolkit:
    """提供导出、导入、校验、回滚能力。"""

    def __init__(self, session_factory: Optional[sessionmaker] = None) -> None:
        self._session_factory = session_factory
    def _next_id(self, session: Session, model: Any) -> int:
        max_id = session.query(model.id).order_by(model.id.desc()).limit(1).scalar()
        return int(max_id or 0) + 1

    # -------- 导出 --------
    def export_from_memory_service(
        self,
        service: Any,
        output_dir: str | Path,
        *,
        incremental_since: Optional[str] = None,
        resume: bool = True,
        compress: bool = True,
    ) -> Dict[str, Any]:
        snapshot = self.build_snapshot_from_service(service, incremental_since=incremental_since)
        self.validate_snapshot(snapshot)
        return self.write_snapshot(snapshot, output_dir=output_dir, resume=resume, compress=compress)

    def build_snapshot_from_service(self, service: Any, *, incremental_since: Optional[str] = None) -> Dict[str, Any]:
        since = _to_dt(incremental_since) if incremental_since else None
        workflows: List[Dict[str, Any]] = []
        teams: List[Dict[str, Any]] = []
        members: List[Dict[str, Any]] = []
        operations: List[Dict[str, Any]] = []
        comments: List[Dict[str, Any]] = []
        notifications: List[Dict[str, Any]] = []
        delegations: List[Dict[str, Any]] = []

        memory_workflows = copy.deepcopy(getattr(service, "_workflows", {}))
        memory_teams = copy.deepcopy(getattr(service, "_teams", {}))
        memory_delegations = copy.deepcopy(getattr(service, "_delegations", {}))

        for workflow in memory_workflows.values():
            item = dict(_ensure_mapping(workflow, section="workflows"))
            updated_at = _to_dt(item.get("updated_at"))
            if since and updated_at < since:
                continue
            workflows.append(item)

            state = dict(item.get("collab_state") or {})
            for op in state.get("operation_log", []) or []:
                op_item = dict(_ensure_mapping(op, section="operations"))
                op_item["workflow_id"] = item.get("workflow_id")
                operations.append(op_item)
            for comment in state.get("comments", []) or []:
                comment_item = dict(_ensure_mapping(comment, section="comments"))
                comment_item["workflow_id"] = item.get("workflow_id")
                comments.append(comment_item)
            for notification in state.get("notifications", []) or []:
                ntf_item = dict(_ensure_mapping(notification, section="notifications"))
                ntf_item["workflow_id"] = item.get("workflow_id")
                notifications.append(ntf_item)

        for team in memory_teams.values():
            item = dict(_ensure_mapping(team, section="teams"))
            if since and _to_dt(item.get("updated_at")) < since:
                continue
            teams.append(item)
            for member in (item.get("members") or {}).values():
                member_item = dict(_ensure_mapping(member, section="members"))
                member_item["team_id"] = item.get("team_id")
                members.append(member_item)

        for delegation in memory_delegations.values():
            item = dict(_ensure_mapping(delegation, section="delegations"))
            if since and _to_dt(item.get("created_at")) < since:
                continue
            delegations.append(item)

        now = datetime.now(timezone.utc).isoformat()
        return {
            "meta": {
                "schema_version": "1.0.0",
                "exported_at": now,
                "incremental_since": incremental_since or "",
                "counts": {
                    "workflows": len(workflows),
                    "teams": len(teams),
                    "members": len(members),
                    "operations": len(operations),
                    "comments": len(comments),
                    "notifications": len(notifications),
                    "delegations": len(delegations),
                },
            },
            "workflows": workflows,
            "teams": teams,
            "members": members,
            "operations": operations,
            "comments": comments,
            "notifications": notifications,
            "delegations": delegations,
        }

    def validate_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        if not isinstance(snapshot, Mapping):
            raise MigrationValidationError("快照必须是 JSON 对象")
        meta = snapshot.get("meta")
        if not isinstance(meta, Mapping):
            raise MigrationValidationError("缺少 meta 字段")
        if not str(meta.get("schema_version") or "").strip():
            raise MigrationValidationError("meta.schema_version 不能为空")

        for section, fields in REQUIRED_FIELDS.items():
            rows = snapshot.get(section)
            if rows is None:
                raise MigrationValidationError(f"缺少段落: {section}")
            if not isinstance(rows, list):
                raise MigrationValidationError(f"{section} 必须是数组")
            for index, row in enumerate(rows):
                item = dict(_ensure_mapping(row, section=section))
                for field in fields:
                    value = item.get(field)
                    if value is None or (isinstance(value, str) and not value.strip()):
                        raise MigrationValidationError(f"{section}[{index}] 缺少必填字段 {field}")

        for row in snapshot.get("workflows", []):
            item = dict(_ensure_mapping(row, section="workflows"))
            current = item.get("current")
            versions = item.get("versions")
            if not isinstance(current, Mapping):
                raise MigrationValidationError("workflow.current 必须是对象")
            if not isinstance(versions, list) or not versions:
                raise MigrationValidationError("workflow.versions 必须是非空数组")

    def write_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        output_dir: str | Path,
        resume: bool = True,
        compress: bool = True,
    ) -> Dict[str, Any]:
        out_dir = Path(output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        state_path = out_dir / ".export_state.json"
        state: Dict[str, int] = {}
        if resume and state_path.exists():
            raw = _read_json(state_path)
            if isinstance(raw, Mapping):
                state = {str(k): int(v) for k, v in raw.items()}

        _write_json(out_dir / "metadata.json", snapshot.get("meta", {}))
        result_files: Dict[str, str] = {}
        for section in SECTION_NAMES:
            rows = list(snapshot.get(section, []) or [])
            section_file = out_dir / f"{section}.jsonl"
            start = 0
            if resume and section_file.exists():
                start = max(0, int(state.get(section, 0)))
            if start >= len(rows):
                result_files[section] = str(section_file)
                continue
            _append_jsonl(section_file, rows[start:])
            state[section] = len(rows)
            _write_json(state_path, state)
            result_files[section] = str(section_file)

        manifest = {
            "meta": snapshot.get("meta", {}),
            "files": result_files,
            "resume_state_file": str(state_path),
        }
        _write_json(out_dir / "manifest.json", manifest)

        package_path = ""
        if compress:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            package = out_dir / f"workflow_migration_export_{stamp}.tar.gz"
            with tarfile.open(package, mode="w:gz") as archive:
                for name in ("metadata.json", "manifest.json", *[f"{s}.jsonl" for s in SECTION_NAMES]):
                    file_path = out_dir / name
                    if file_path.exists():
                        archive.add(file_path, arcname=name)
            package_path = str(package)

        return {
            "output_dir": str(out_dir),
            "manifest": str(out_dir / "manifest.json"),
            "compressed_file": package_path,
            "counts": copy.deepcopy(snapshot.get("meta", {}).get("counts", {})),
        }

    # -------- 加载包 --------
    def load_snapshot(self, source: str | Path) -> Dict[str, Any]:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"迁移包不存在: {path}")

        if path.is_file() and path.suffixes[-2:] == [".tar", ".gz"]:
            with tempfile.TemporaryDirectory(prefix="workflow_migration_unpack_") as temp_dir:
                with tarfile.open(path, mode="r:gz") as archive:
                    archive.extractall(path=temp_dir)
                return self._load_snapshot_from_dir(Path(temp_dir))
        if path.is_dir():
            return self._load_snapshot_from_dir(path)
        raise ValueError(f"不支持的迁移包类型: {path}")

    def _load_snapshot_from_dir(self, root: Path) -> Dict[str, Any]:
        metadata = _read_json(root / "metadata.json")
        snapshot: Dict[str, Any] = {"meta": metadata}
        for section in SECTION_NAMES:
            snapshot[section] = _read_jsonl(root / f"{section}.jsonl")
        snapshot["delegations"] = _read_jsonl(root / "delegations.jsonl")
        self.validate_snapshot(snapshot)
        return snapshot

    # -------- 导入 --------
    def import_snapshot(
        self,
        source: str | Path,
        *,
        options: Optional[ImportOptions] = None,
        journal_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        if self._session_factory is None:
            raise ValueError("导入需要提供 session_factory")

        opt = options or ImportOptions()
        if opt.conflict_strategy not in {"upsert", "skip", "error"}:
            raise ValueError("conflict_strategy 仅支持 upsert/skip/error")
        snapshot = self.load_snapshot(source)
        started = time.time()

        journal: Dict[str, Any] = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": str(source),
            "inserted": {
                "workflows": [],
                "workflow_versions": [],
                "teams": [],
                "team_members": [],
                "delegations": [],
                "operations": [],
                "comments": [],
                "notifications": [],
            },
            "updated": {"workflows": {}, "teams": {}},
            "errors": [],
        }

        counts = {
            "workflows": 0,
            "teams": 0,
            "members": 0,
            "delegations": 0,
            "operations": 0,
            "comments": 0,
            "notifications": 0,
        }

        with self._session_factory() as session:
            user_map = self._ensure_users(session, _extract_legacy_user_ids(snapshot))
            workflow_map = self._import_workflows(session, snapshot, user_map, opt, journal, counts)
            team_map = self._import_teams(session, snapshot, user_map, opt, journal, counts)
            self._import_members(session, snapshot, user_map, team_map, opt, journal, counts)
            self._import_delegations(session, snapshot, user_map, workflow_map, opt, journal, counts)
            self._import_operations(session, snapshot, user_map, workflow_map, opt, journal, counts)
            self._import_comments(session, snapshot, user_map, workflow_map, opt, journal, counts)
            self._import_notifications(session, snapshot, user_map, opt, journal, counts)
            if opt.partial_commit:
                session.commit()

        elapsed = max(0.001, time.time() - started)
        processed_total = sum(counts.values())
        report = {
            "success": True,
            "processed": counts,
            "total_processed": processed_total,
            "elapsed_seconds": round(elapsed, 3),
            "speed_per_second": round(processed_total / elapsed, 3),
            "error_count": len(journal["errors"]),
            "journal_path": "",
        }

        if journal_path:
            journal_file = Path(journal_path).expanduser().resolve()
            _write_json(journal_file, journal)
            report["journal_path"] = str(journal_file)
        return report

    def _ensure_users(self, session: Session, legacy_ids: Set[str]) -> Dict[str, int]:
        if not legacy_ids:
            return {}
        ids = sorted(legacy_ids)
        existed = session.query(User).filter(User.username.in_(ids)).all()
        result = {str(item.username): int(item.id) for item in existed}

        missing = [uid for uid in ids if uid not in result]
        for uid in missing:
            payload: Dict[str, Any] = dict(
                username=uid,
                email=f"{uid}@migration.local",
                password_hash="migrated-not-loginable",
                role="user",
                status="active",
                is_email_verified=True,
            )
            user = User(**payload)
            session.add(user)
            session.flush()
            result[uid] = int(user.id)
        session.commit()
        return result

    def _load_existing_workflows(self, session: Session) -> Dict[str, Workflow]:
        existing: Dict[str, Workflow] = {}
        for row in session.query(Workflow).all():
            definition = row.definition or {}
            ext_id = str((definition or {}).get("workflow_id") or "").strip()
            if ext_id:
                existing[ext_id] = row
        return existing

    def _import_workflows(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> Dict[str, int]:
        existing = self._load_existing_workflows(session)
        result: Dict[str, int] = {}
        rows = list(snapshot.get("workflows", []) or [])

        for row in rows:
            item = dict(_ensure_mapping(row, section="workflows"))
            workflow_id = str(item["workflow_id"])
            owner_user = str(item.get("owner_user_id") or "system")
            owner_id = int(user_map.get(owner_user) or next(iter(user_map.values())))
            name = str(item.get("name") or workflow_id)
            description = str(item.get("description") or "")
            definition = copy.deepcopy(item.get("current") or {})
            if "workflow_id" not in definition:
                definition["workflow_id"] = workflow_id

            existed = existing.get(workflow_id)
            if existed:
                if opt.conflict_strategy == "skip":
                    result[workflow_id] = int(existed.id)
                    continue
                if opt.conflict_strategy == "error":
                    raise ValueError(f"workflow 冲突: {workflow_id}")
                journal["updated"]["workflows"][str(existed.id)] = {
                    "name": existed.name,
                    "description": existed.description,
                    "definition": existed.definition,
                    "owner_id": existed.owner_id,
                    "is_public": bool(existed.is_public),
                }
                existed.name = name
                existed.description = description
                existed.definition = definition
                existed.owner_id = owner_id
                session.flush()
                result[workflow_id] = int(existed.id)
            else:
                payload = dict(
                    name=name,
                    description=description,
                    definition=definition,
                    owner_id=owner_id,
                    is_public=bool(item.get("is_public", False)),
                )
                record = Workflow(**payload)
                session.add(record)
                session.flush()
                result[workflow_id] = int(record.id)
                journal["inserted"]["workflows"].append(int(record.id))

            existing_row = session.get(Workflow, result[workflow_id])
            if existing_row is None:
                continue
            versions = list(item.get("versions") or [])
            known_versions = {
                int(v.version_number)
                for v in session.query(WorkflowVersion).filter(WorkflowVersion.workflow_id == existing_row.id).all()
            }
            for version in versions:
                v = dict(_ensure_mapping(version, section="workflow_versions"))
                ver_no = int(v.get("version") or v.get("version_number") or 0)
                if ver_no <= 0 or ver_no in known_versions:
                    continue
                created_by_name = str(v.get("created_by") or owner_user)
                created_by_id = int(user_map.get(created_by_name) or owner_id)
                payload = dict(
                    workflow_id=int(existing_row.id),
                    version_number=ver_no,
                    definition=copy.deepcopy(v.get("definition") or definition),
                    created_by_id=created_by_id,
                    created_at=_to_dt(v.get("created_at")),
                )
                row_ver = WorkflowVersion(**payload)
                session.add(row_ver)
                session.flush()
                journal["inserted"]["workflow_versions"].append(int(row_ver.id))

            counts["workflows"] += 1
            if opt.partial_commit and counts["workflows"] % max(1, opt.batch_size) == 0:
                session.commit()
        if not opt.partial_commit:
            session.commit()
        return result

    def _import_teams(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> Dict[str, int]:
        existing = {(row.name, int(row.owner_id)): row for row in session.query(Team).all()}
        team_map: Dict[str, int] = {}
        for row in snapshot.get("teams", []) or []:
            item = dict(_ensure_mapping(row, section="teams"))
            legacy_team_id = str(item["team_id"])
            owner_user = str(item.get("owner_user_id") or "system")
            owner_id = int(user_map.get(owner_user) or next(iter(user_map.values())))
            team_name = str(item.get("name") or legacy_team_id)
            description = str(item.get("description") or "")
            key = (team_name, owner_id)
            existed = existing.get(key)
            if existed:
                if opt.conflict_strategy == "skip":
                    team_map[legacy_team_id] = int(existed.id)
                    continue
                if opt.conflict_strategy == "error":
                    raise ValueError(f"team 冲突: {legacy_team_id}")
                journal["updated"]["teams"][str(existed.id)] = {
                    "name": existed.name,
                    "description": existed.description,
                    "owner_id": existed.owner_id,
                }
                existed.description = description
                team_map[legacy_team_id] = int(existed.id)
            else:
                payload = dict(
                    name=team_name,
                    description=description,
                    owner_id=owner_id,
                    created_at=_to_dt(item.get("created_at")),
                )
                team = Team(**payload)
                session.add(team)
                session.flush()
                team_map[legacy_team_id] = int(team.id)
                journal["inserted"]["teams"].append(int(team.id))
                existing[key] = team
            counts["teams"] += 1
        if opt.partial_commit:
            session.commit()
        return team_map

    def _import_members(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        team_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> None:
        existed = {(int(row.team_id), int(row.user_id)) for row in session.query(TeamMember).all()}
        for row in snapshot.get("members", []) or []:
            item = dict(_ensure_mapping(row, section="members"))
            team_id = int(team_map.get(str(item.get("team_id") or "")) or 0)
            user_id = int(user_map.get(str(item.get("user_id") or "")) or 0)
            if team_id <= 0 or user_id <= 0:
                continue
            key = (team_id, user_id)
            if key in existed:
                continue
            payload = dict(
                team_id=team_id,
                user_id=user_id,
                role=str(item.get("role") or "member"),
                joined_at=_to_dt(item.get("joined_at")),
            )
            member = TeamMember(**payload)
            session.add(member)
            session.flush()
            existed.add(key)
            journal["inserted"]["team_members"].append(int(member.id))
            counts["members"] += 1
            if opt.partial_commit and counts["members"] % max(1, opt.batch_size) == 0:
                session.commit()
        if opt.partial_commit:
            session.commit()

    def _import_delegations(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        workflow_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> None:
        rows = list(snapshot.get("delegations", []) or [])
        for row in rows:
            item = dict(_ensure_mapping(row, section="delegations"))
            workflow_id = int(workflow_map.get(str(item.get("workflow_id") or "")) or 0)
            from_user = int(user_map.get(str(item.get("from_user_id") or "")) or 0)
            to_user = int(user_map.get(str(item.get("to_user_id") or "")) or 0)
            if workflow_id <= 0 or from_user <= 0 or to_user <= 0:
                continue
            payload = dict(
                workflow_id=workflow_id,
                delegator_id=from_user,
                delegate_id=to_user,
                permissions={"permission": str(item.get("permission") or "")},
                granted_at=_to_dt(item.get("created_at")),
                expires_at=_to_dt(item.get("expires_at")),
            )
            delegation = Delegation(**payload)
            session.add(delegation)
            session.flush()
            journal["inserted"]["delegations"].append(int(delegation.id))
            counts["delegations"] += 1
        if opt.partial_commit:
            session.commit()

    def _map_rows_parallel(
        self,
        rows: Sequence[Mapping[str, Any]],
        mapper: Callable[[Mapping[str, Any]], Optional[Any]],
        workers: int,
    ) -> List[Any]:
        if workers <= 1 or len(rows) <= 1:
            return [item for item in (mapper(row) for row in rows) if item is not None]
        with ThreadPoolExecutor(max_workers=max(2, workers)) as pool:
            mapped = list(pool.map(mapper, rows))
        return [item for item in mapped if item is not None]

    def _import_operations(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        workflow_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> None:
        rows = list(snapshot.get("operations", []) or [])

        def mapper(row: Mapping[str, Any]) -> Optional[CollaborationOperation]:
            item = dict(_ensure_mapping(row, section="operations"))
            workflow_id = int(workflow_map.get(str(item.get("workflow_id") or "")) or 0)
            user_id = int(user_map.get(str(item.get("actor_id") or item.get("user_id") or "")) or 0)
            if workflow_id <= 0 or user_id <= 0:
                return None
            payload = dict(
                workflow_id=workflow_id,
                user_id=user_id,
                operation_type=str(item.get("operation_type") or "unknown"),
                operation_data=copy.deepcopy(item.get("data") or {}),
                created_at=_to_dt(item.get("created_at")),
            )
            return CollaborationOperation(**payload)

        for batch in _iter_chunks(rows, opt.batch_size):
            entities = self._map_rows_parallel([dict(_ensure_mapping(r, section="operations")) for r in batch], mapper, opt.workers)
            for entity in entities:
                session.add(entity)
            session.flush()
            for entity in entities:
                journal["inserted"]["operations"].append(int(entity.id))
                counts["operations"] += 1
            if opt.partial_commit:
                session.commit()
        if opt.partial_commit:
            session.commit()

    def _import_comments(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        workflow_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> None:
        rows = sorted(
            [dict(_ensure_mapping(row, section="comments")) for row in snapshot.get("comments", []) or []],
            key=lambda item: (_to_dt(item.get("created_at")), str(item.get("comment_id"))),
        )
        source_to_db: Dict[str, int] = {}

        for batch in _iter_chunks(rows, opt.batch_size):
            for item in batch:
                workflow_id = int(workflow_map.get(str(item.get("workflow_id") or "")) or 0)
                user_id = int(user_map.get(str(item.get("user_id") or "")) or 0)
                if workflow_id <= 0 or user_id <= 0:
                    continue
                parent_src = str(item.get("parent_comment_id") or "").strip()
                parent_id = int(source_to_db.get(parent_src) or 0) if parent_src else None
                payload = dict(
                    workflow_id=workflow_id,
                    parent_id=parent_id,
                    user_id=user_id,
                    content=str(item.get("content") or ""),
                    created_at=_to_dt(item.get("created_at")),
                    updated_at=_to_dt(item.get("created_at")),
                )
                comment = Comment(**payload)
                session.add(comment)
                session.flush()
                source_to_db[str(item.get("comment_id") or "")] = int(comment.id)
                journal["inserted"]["comments"].append(int(comment.id))
                counts["comments"] += 1
            if opt.partial_commit:
                session.commit()
        if opt.partial_commit:
            session.commit()

    def _import_notifications(
        self,
        session: Session,
        snapshot: Mapping[str, Any],
        user_map: Mapping[str, int],
        opt: ImportOptions,
        journal: Dict[str, Any],
        counts: Dict[str, int],
    ) -> None:
        rows = list(snapshot.get("notifications", []) or [])
        for batch in _iter_chunks(rows, opt.batch_size):
            for row in batch:
                item = dict(_ensure_mapping(row, section="notifications"))
                user_id = int(user_map.get(str(item.get("user_id") or "")) or 0)
                if user_id <= 0:
                    continue
                payload = dict(
                    user_id=user_id,
                    notification_type=str(item.get("event_type") or "migration"),
                    title=str(item.get("event_type") or "migration"),
                    content=str(item.get("message") or ""),
                    is_read=bool(item.get("read", False)),
                    created_at=_to_dt(item.get("created_at")),
                    reference_id=None,
                )
                notification = Notification(**payload)
                session.add(notification)
                session.flush()
                journal["inserted"]["notifications"].append(int(notification.id))
                counts["notifications"] += 1
            if opt.partial_commit:
                session.commit()
        if opt.partial_commit:
            session.commit()

    # -------- 验证 --------
    def verify_snapshot_vs_database(self, source: str | Path) -> Dict[str, Any]:
        if self._session_factory is None:
            raise ValueError("校验需要提供 session_factory")
        snapshot = self.load_snapshot(source)
        report: Dict[str, Any] = {
            "counts": {},
            "content_diff": [],
            "fk_integrity": {},
            "index_integrity": {},
        }

        with self._session_factory() as session:
            workflow_external_ids = {
                str((item or {}).get("workflow_id") or "")
                for item in snapshot.get("workflows", []) or []
                if str((item or {}).get("workflow_id") or "").strip()
            }
            db_workflows = self._load_existing_workflows(session)
            matched = {wid: db_workflows.get(wid) for wid in workflow_external_ids}
            report["counts"]["workflows_export"] = len(workflow_external_ids)
            report["counts"]["workflows_db_matched"] = sum(1 for row in matched.values() if row is not None)
            report["counts"]["teams_export"] = len(snapshot.get("teams", []) or [])
            report["counts"]["teams_db"] = int(session.query(Team).count())
            report["counts"]["comments_export"] = len(snapshot.get("comments", []) or [])
            report["counts"]["comments_db"] = int(session.query(Comment).count())
            report["counts"]["operations_export"] = len(snapshot.get("operations", []) or [])
            report["counts"]["operations_db"] = int(session.query(CollaborationOperation).count())
            report["counts"]["notifications_export"] = len(snapshot.get("notifications", []) or [])
            report["counts"]["notifications_db"] = int(session.query(Notification).count())

            for row in snapshot.get("workflows", []) or []:
                item = dict(_ensure_mapping(row, section="workflows"))
                ext_id = str(item.get("workflow_id") or "")
                db_row = matched.get(ext_id)
                if db_row is None:
                    report["content_diff"].append({"workflow_id": ext_id, "type": "missing_in_db"})
                    continue
                src_def = item.get("current") or {}
                db_def = db_row.definition or {}
                if src_def != db_def:
                    report["content_diff"].append({"workflow_id": ext_id, "type": "definition_mismatch"})

            report["fk_integrity"] = self._check_foreign_keys(session)
            report["index_integrity"] = self._check_indexes(session)
        return report

    def _check_foreign_keys(self, session: Session) -> Dict[str, Any]:
        checks = {
            "comments_workflow_fk": int(
                session.query(Comment)
                .outerjoin(Workflow, Comment.workflow_id == Workflow.id)
                .filter(Workflow.id.is_(None))
                .count()
            ),
            "comments_user_fk": int(
                session.query(Comment).outerjoin(User, Comment.user_id == User.id).filter(User.id.is_(None)).count()
            ),
            "operations_workflow_fk": int(
                session.query(CollaborationOperation)
                .outerjoin(Workflow, CollaborationOperation.workflow_id == Workflow.id)
                .filter(Workflow.id.is_(None))
                .count()
            ),
            "operations_user_fk": int(
                session.query(CollaborationOperation)
                .outerjoin(User, CollaborationOperation.user_id == User.id)
                .filter(User.id.is_(None))
                .count()
            ),
            "notifications_user_fk": int(
                session.query(Notification)
                .outerjoin(User, Notification.user_id == User.id)
                .filter(User.id.is_(None))
                .count()
            ),
        }
        return {"orphan_counts": checks, "healthy": all(value == 0 for value in checks.values())}

    def _check_indexes(self, session: Session) -> Dict[str, Any]:
        inspector = inspect(session.bind)
        missing: Dict[str, List[str]] = {}
        for table, expected_names in EXPECTED_INDEXES.items():
            actual_names = {str(item.get("name")) for item in inspector.get_indexes(table)}
            loss = sorted(name for name in expected_names if name not in actual_names)
            if loss:
                missing[table] = loss
        return {"healthy": not bool(missing), "missing_indexes": missing}

    # -------- 回滚 --------
    def rollback_from_journal(self, journal_path: str | Path, *, output_log: Optional[str | Path] = None) -> Dict[str, Any]:
        if self._session_factory is None:
            raise ValueError("回滚需要提供 session_factory")
        path = Path(journal_path).expanduser().resolve()
        journal = _read_json(path)
        if not isinstance(journal, Mapping):
            raise ValueError("journal 格式错误")
        inserted = dict(journal.get("inserted") or {})
        updated = dict(journal.get("updated") or {})
        restored = {"workflows": 0, "teams": 0}
        deleted = {k: 0 for k in inserted.keys()}

        with self._session_factory() as session:
            # 先删除子表，再删父表。
            delete_order = [
                ("notifications", Notification),
                ("comments", Comment),
                ("operations", CollaborationOperation),
                ("delegations", Delegation),
                ("team_members", TeamMember),
                ("workflow_versions", WorkflowVersion),
                ("teams", Team),
                ("workflows", Workflow),
            ]
            for key, model in delete_order:
                ids = [int(item) for item in inserted.get(key, []) or []]
                if not ids:
                    continue
                deleted[key] = int(session.query(model).filter(model.id.in_(ids)).delete(synchronize_session=False))

            for workflow_id, raw in (updated.get("workflows") or {}).items():
                row = session.get(Workflow, int(workflow_id))
                if row is None:
                    continue
                payload = dict(raw or {})
                row.name = str(payload.get("name") or row.name)
                row.description = payload.get("description")
                row.definition = copy.deepcopy(payload.get("definition") or row.definition)
                row.owner_id = int(payload.get("owner_id") or row.owner_id)
                row.is_public = bool(payload.get("is_public", row.is_public))
                restored["workflows"] += 1

            for team_id, raw in (updated.get("teams") or {}).items():
                row = session.get(Team, int(team_id))
                if row is None:
                    continue
                payload = dict(raw or {})
                row.name = str(payload.get("name") or row.name)
                row.description = payload.get("description")
                row.owner_id = int(payload.get("owner_id") or row.owner_id)
                restored["teams"] += 1
            session.commit()

        result = {
            "success": True,
            "journal": str(path),
            "deleted": deleted,
            "restored": restored,
            "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        }
        if output_log:
            _write_json(Path(output_log).expanduser().resolve(), result)
        return result
