"""Auth DB index maintenance script for product key validation workload.

Usage:
  python services/backend/scripts/auth_db_index_maintenance.py --db-url postgresql+psycopg2://user:password@localhost:5432/udake_auth
  python services/backend/scripts/auth_db_index_maintenance.py --execute
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect, text


@dataclass(frozen=True)
class RequiredIndex:
    name: str
    columns: tuple[str, ...]
    unique: bool


REQUIRED_INDEXES = (
    RequiredIndex(name="uq_product_keys_key", columns=("product_key",), unique=True),
    RequiredIndex(name="ix_product_keys_status", columns=("status",), unique=False),
    RequiredIndex(name="idx_product_keys_key_status", columns=("product_key", "status"), unique=False),
)


def _resolve_db_url(value: Optional[str]) -> str:
    if value:
        return value
    env_url = os.getenv("AUTH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return "postgresql+psycopg2://localhost:5432/udake_auth"


def _existing_indexes(engine, table_name: str) -> Dict[str, Dict[str, Any]]:
    inspector = inspect(engine)
    rows = inspector.get_indexes(table_name)
    payload = {
        str(item.get("name") or ""): {
            "name": str(item.get("name") or ""),
            "columns": tuple(item.get("column_names") or []),
            "unique": bool(item.get("unique", False)),
        }
        for item in rows
        if item.get("name")
    }
    for unique in inspector.get_unique_constraints(table_name):
        name = str(unique.get("name") or "")
        if not name:
            continue
        payload[name] = {
            "name": name,
            "columns": tuple(unique.get("column_names") or []),
            "unique": True,
        }
    return payload


def _create_index_sql(dialect: str, table_name: str, idx: RequiredIndex) -> str:
    unique = "UNIQUE " if idx.unique else ""
    cols = ", ".join(idx.columns)
    if dialect == "postgresql":
        return f"CREATE {unique}INDEX IF NOT EXISTS {idx.name} ON {table_name} ({cols})"
    return f"CREATE {unique}INDEX {idx.name} ON {table_name} ({cols})"


def _explain_query(engine, sql: str, params: Dict[str, Any]) -> List[Any]:
    dialect = engine.dialect.name
    explain_sql = sql
    if dialect == "postgresql":
        explain_sql = f"EXPLAIN {sql}"
    else:
        explain_sql = f"EXPLAIN {sql}"
    with engine.connect() as conn:
        rows = conn.execute(text(explain_sql), params).fetchall()
    return rows


def run(db_url: str, *, execute: bool) -> Dict[str, Any]:
    engine = create_engine(db_url, future=True)
    existing = _existing_indexes(engine, "product_keys")
    dialect = engine.dialect.name

    missing: List[Dict[str, Any]] = []
    present: List[Dict[str, Any]] = []
    for item in REQUIRED_INDEXES:
        matched = existing.get(item.name)
        if matched and tuple(matched["columns"]) == item.columns and bool(matched["unique"]) == item.unique:
            present.append({"name": item.name, "columns": list(item.columns), "unique": item.unique})
            continue
        missing.append(
            {
                "name": item.name,
                "columns": list(item.columns),
                "unique": item.unique,
                "sql": _create_index_sql(dialect, "product_keys", item),
            }
        )

    executed_sql: List[str] = []
    if execute and missing:
        with engine.begin() as conn:
            for item in missing:
                conn.execute(text(item["sql"]))
                executed_sql.append(item["sql"])

    explain_samples: Dict[str, Any] = {}
    try:
        explain_samples["product_key_lookup"] = [
            str(row)
            for row in _explain_query(
                engine,
                "SELECT id, status FROM product_keys WHERE product_key = :product_key LIMIT 1",
                {"product_key": "UDA-0000-0000-0000"},
            )
        ]
    except Exception as exc:  # pylint: disable=broad-except
        explain_samples["product_key_lookup"] = [f"explain_failed: {exc}"]

    try:
        explain_samples["status_lookup"] = [
            str(row)
            for row in _explain_query(
                engine,
                "SELECT id FROM product_keys WHERE status = :status LIMIT 20",
                {"status": "unused"},
            )
        ]
    except Exception as exc:  # pylint: disable=broad-except
        explain_samples["status_lookup"] = [f"explain_failed: {exc}"]

    return {
        "db_url": db_url,
        "dialect": dialect,
        "present": present,
        "missing": missing,
        "executed": executed_sql,
        "explain": explain_samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain product_keys indexes")
    parser.add_argument("--db-url", default=None, help="Database URL, default from AUTH_DATABASE_URL / DATABASE_URL")
    parser.add_argument("--execute", action="store_true", help="Execute missing index creation SQL")
    args = parser.parse_args()

    report = run(_resolve_db_url(args.db_url), execute=bool(args.execute))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
