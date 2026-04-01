"""工作流数据迁移工具测试。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_db.models import Base, Workflow
from app.auth_db.workflow_migration import ImportOptions, WorkflowMigrationToolkit
from app.services.智能工作流服务 import SmartWorkflowService


def _build_definition() -> dict:
    return {
        "workflow_id": "wf_migration_case_01",
        "name": "migration-case-01",
        "nodes": [
            {"node_id": "input", "kind": "input", "node_type": "input.constant", "params": {"value": [1, 2, 3]}},
            {"node_id": "output", "kind": "output", "node_type": "output.collect", "params": {"fields": ["value"]}},
        ],
        "edges": [{"source": "input", "target": "output"}],
    }


def _prepare_service_data() -> SmartWorkflowService:
    service = SmartWorkflowService(auto_start_scheduler=False)
    workflow = service.create_workflow(_build_definition())
    workflow_id = str(workflow["workflow_id"])

    service.set_collaborators(
        workflow_id,
        [
            {"user_id": "alice", "role": "admin"},
            {"user_id": "bob", "role": "editor"},
            {"user_id": "charlie", "role": "commenter"},
        ],
    )
    team = service.create_team(name="迁移团队A", owner_user_id="alice", description="for migration")
    service.add_team_member(team["team_id"], "bob", role="viewer")
    service.bind_team_to_workflow(workflow_id, team["team_id"])
    service.create_permission_delegation(
        workflow_id=workflow_id,
        from_user_id="alice",
        to_user_id="bob",
        permission="edit_workflow",
        ttl_hours=24,
    )
    service.apply_collaboration_operation(
        workflow_id,
        {
            "actor_id": "bob",
            "operation_type": "set_metadata",
            "data": {"key": "region", "value": "shanghai"},
            "base_revision": 0,
        },
    )
    service.update_collaboration_cursor(workflow_id, "bob", {"node_id": "input", "x": 1, "y": 2})
    service.add_comment(workflow_id, "bob", "请 @charlie 看下这个结果")
    service.stop_scheduler()
    return service


def _build_toolkit_with_sqlite() -> WorkflowMigrationToolkit:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return WorkflowMigrationToolkit(session_factory=session_factory)


def test_export_validate_and_reload_snapshot(tmp_path: Path) -> None:
    service = _prepare_service_data()
    toolkit = WorkflowMigrationToolkit(session_factory=None)

    result = toolkit.export_from_memory_service(
        service=service,
        output_dir=tmp_path / "export",
        incremental_since=None,
        resume=True,
        compress=True,
    )
    assert Path(result["manifest"]).exists()
    assert result["counts"]["workflows"] == 1
    assert result["counts"]["teams"] == 1
    assert result["counts"]["operations"] >= 1
    assert result["counts"]["comments"] >= 1
    assert result["counts"]["notifications"] >= 1
    assert Path(result["compressed_file"]).exists()

    snapshot = toolkit.load_snapshot(result["output_dir"])
    toolkit.validate_snapshot(snapshot)
    assert len(snapshot["workflows"]) == 1


def test_import_verify_and_rollback(tmp_path: Path) -> None:
    service = _prepare_service_data()
    export_toolkit = WorkflowMigrationToolkit(session_factory=None)
    export_result = export_toolkit.export_from_memory_service(
        service=service,
        output_dir=tmp_path / "export_case2",
        resume=True,
        compress=False,
    )

    toolkit = _build_toolkit_with_sqlite()
    journal_path = tmp_path / "journal.json"
    import_report = toolkit.import_snapshot(
        source=export_result["output_dir"],
        options=ImportOptions(batch_size=50, workers=2, conflict_strategy="upsert"),
        journal_path=journal_path,
    )
    assert import_report["success"] is True
    assert import_report["processed"]["workflows"] == 1
    assert journal_path.exists()

    verify_report = toolkit.verify_snapshot_vs_database(export_result["output_dir"])
    assert verify_report["counts"]["workflows_export"] == 1
    assert verify_report["counts"]["workflows_db_matched"] == 1
    assert verify_report["fk_integrity"]["healthy"] is True
    assert verify_report["index_integrity"]["healthy"] is True

    rollback_report = toolkit.rollback_from_journal(journal_path, output_log=tmp_path / "rollback.json")
    assert rollback_report["success"] is True

    with toolkit._session_factory() as session:  # type: ignore[attr-defined]
        assert session.query(Workflow).count() == 0

    rollback_payload = json.loads((tmp_path / "rollback.json").read_text(encoding="utf-8"))
    assert rollback_payload["success"] is True
