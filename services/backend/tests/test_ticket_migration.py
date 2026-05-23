"""Tests for isolated ticket migration upgrade/downgrade."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "001_create_tickets_table.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("tickets_migration_001", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ticket_migration_upgrade_and_downgrade() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    module = _load_migration_module()

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY)"))

        migration_context = MigrationContext.configure(conn)
        module.op = Operations(migration_context)

        module.upgrade()

        inspector = inspect(conn)
        assert "tickets" in inspector.get_table_names()

        columns = {item["name"] for item in inspector.get_columns("tickets")}
        expected_columns = {
            "id",
            "ticket_type",
            "status",
            "email",
            "phone",
            "industry",
            "usage_purpose",
            "key_type",
            "existing_key",
            "processed_by",
            "processed_at",
            "approval_notes",
            "assigned_key",
            "response_message",
            "created_at",
            "updated_at",
        }
        assert expected_columns.issubset(columns)

        index_names = {item["name"] for item in inspector.get_indexes("tickets")}
        assert {"ix_tickets_email", "ix_tickets_status", "ix_tickets_created_at", "ix_tickets_ticket_type"}.issubset(
            index_names
        )

        module.downgrade()
        assert "tickets" not in inspect(conn).get_table_names()

    engine.dispose()
