"""新密钥系统性能测试。"""

from __future__ import annotations

import os
import tempfile
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.admin_api import router as admin_router
from app.auth import ProductKeyRegistry, get_auth_service, reset_auth_service
from app.auth_db.models import Base, Company, ProductKey, User
from app.auth_db.session import get_auth_db_session


@pytest.fixture()
def perf_client(monkeypatch: pytest.MonkeyPatch):
    """构建用于性能测试的独立 API 客户端与数据库。"""
    monkeypatch.setenv("AUTH_JWT_SECRET", "product-key-perf-secret")
    reset_auth_service()

    fd, db_path = tempfile.mkstemp(prefix="product-key-perf-", suffix=".sqlite3")
    os.close(fd)
    db_url = f"sqlite+pysqlite:///{db_path}"

    engine = create_engine(
        db_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        company = Company(id=1, name="性能测试企业", status="active")
        super_admin = User(
            id=1,
            username="super_admin",
            email="super_admin@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
        )
        company_admin = User(
            id=2,
            username="company_admin",
            email="company_admin@example.com",
            password_hash="hash",
            role="company_admin",
            status="active",
            company_id=1,
        )
        db.add_all([company, super_admin, company_admin])
        db.commit()

    app = FastAPI()
    app.include_router(admin_router, prefix="/api")

    def override_get_auth_db_session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_auth_db_session] = override_get_auth_db_session

    service = get_auth_service()
    tokens = {
        "super_admin": service.jwt.generate_access_token(user_id=1, role="super_admin", permissions=["*"]),
        "company_admin": service.jwt.generate_access_token(user_id=2, role="company_admin", permissions=["*"]),
    }

    with TestClient(app) as client:
        yield {
            "client": client,
            "tokens": tokens,
            "db_url": db_url,
            "db_path": db_path,
            "session_factory": SessionLocal,
        }

    reset_auth_service()
    engine.dispose()
    if Path(db_path).exists():
        Path(db_path).unlink()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _p95(values: list[float]) -> float:
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int(len(sorted_values) * 0.95) - 1))
    return sorted_values[index]


def _create_enterprise_keys(client: TestClient, token: str, count: int) -> list[int]:
    resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": count, "company_id": 1},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    return [item["id"] for item in resp.json()["data"]["keys"]]


def test_single_key_generation_performance() -> None:
    registry = ProductKeyRegistry()
    times_ms = []

    for _ in range(100):
        started = time.perf_counter()
        registry.generate_enterprise_key(
            company_name="性能测试企业",
            company_id=1,
            key_type="enterprise_standard",
        )
        times_ms.append((time.perf_counter() - started) * 1000)

    assert mean(times_ms) < 10
    assert _p95(times_ms) < 20


def test_batch_key_generation_performance() -> None:
    registry = ProductKeyRegistry()

    started_100 = time.perf_counter()
    keys_100 = registry.generate_keys(
        key_type="enterprise_trial",
        count=100,
        company_id=1,
        company_name="性能测试企业",
    )
    duration_100 = (time.perf_counter() - started_100) * 1000
    assert len(keys_100) == 100
    assert duration_100 < 1000

    started_1000 = time.perf_counter()
    keys_1000 = registry.generate_keys(
        key_type="enterprise_trial",
        count=1000,
        company_id=1,
        company_name="性能测试企业",
    )
    duration_1000 = (time.perf_counter() - started_1000) * 1000
    assert len(keys_1000) == 1000
    assert duration_1000 < 10000


def test_api_response_performance(perf_client) -> None:
    client: TestClient = perf_client["client"]
    company_admin_token = perf_client["tokens"]["company_admin"]

    create_times = []
    for _ in range(30):
        started = time.perf_counter()
        resp = client.post(
            "/api/admin/product-keys",
            json={"type": "enterprise_standard", "count": 1, "company_id": 1},
            headers=_auth_header(company_admin_token),
        )
        create_times.append((time.perf_counter() - started) * 1000)
        assert resp.status_code == 200, resp.text

    query_times = []
    for _ in range(50):
        started = time.perf_counter()
        resp = client.get(
            "/api/admin/product-keys?page=1&page_size=20",
            headers=_auth_header(company_admin_token),
        )
        query_times.append((time.perf_counter() - started) * 1000)
        assert resp.status_code == 200, resp.text

    assert mean(create_times) < 500
    assert _p95(query_times) < 200


def test_validate_key_performance() -> None:
    registry = ProductKeyRegistry()
    record = registry.generate_key(
        key_type="personal_standard",
        user_id=9527,
    )

    times_ms = []
    for _ in range(1000):
        started = time.perf_counter()
        validated = registry.validate_key(record.product_key)
        times_ms.append((time.perf_counter() - started) * 1000)
        assert validated.product_key == record.product_key

    assert mean(times_ms) < 100


def test_database_query_performance(perf_client) -> None:
    session_factory = perf_client["session_factory"]
    registry = ProductKeyRegistry()

    with session_factory() as db:
        for idx in range(5000):
            key_record = registry.generate_key(
                key_type="enterprise_standard",
                company_id=1,
                company_name="性能测试企业",
                user_id=2,
                metadata={"seed_index": idx},
            )
            db.add(
                ProductKey(
                    id=10_000 + idx,
                    user_id=2,
                    product_key=key_record.product_key,
                    key_type=key_record.key_type,
                    key_sub_type=key_record.key_sub_type,
                    status="unused",
                    company_id=1,
                    total_quota=1000,
                    used_count=0,
                    generation_seed=key_record.generation_seed,
                    key_metadata='{"benchmark": true}',
                    issued_at=datetime.now(timezone.utc),
                )
            )
        db.commit()

        single_times = []
        for _ in range(100):
            started = time.perf_counter()
            db.execute(text("SELECT * FROM product_keys WHERE id = :id"), {"id": 10_010}).fetchone()
            single_times.append((time.perf_counter() - started) * 1000)

        indexed_times = []
        for _ in range(100):
            started = time.perf_counter()
            db.execute(
                text(
                    "SELECT id, key_type, status FROM product_keys "
                    "WHERE key_type = :key_type AND status = :status LIMIT 100"
                ),
                {"key_type": "enterprise_standard", "status": "unused"},
            ).fetchall()
            indexed_times.append((time.perf_counter() - started) * 1000)

    assert mean(single_times) < 10
    assert mean(indexed_times) < 100


def test_concurrent_key_generation_performance() -> None:
    registry = ProductKeyRegistry()

    def _task(task_id: int) -> tuple[str, float]:
        started = time.perf_counter()
        key, _ = registry.generate_enterprise_key(
            company_name=f"并发企业{task_id}",
            company_id=task_id + 1,
            key_type="enterprise_standard",
        )
        return key, (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(_task, range(100)))

    keys = [item[0] for item in results]
    durations = [item[1] for item in results]

    assert len(set(keys)) == len(keys)
    assert mean(durations) < 50


def test_concurrent_api_query_performance(perf_client) -> None:
    token = perf_client["tokens"]["company_admin"]

    # 预热写入数据
    with TestClient(perf_client["client"].app) as seed_client:
        _create_enterprise_keys(seed_client, token, 200)

    def _query_once() -> tuple[int, float]:
        with TestClient(perf_client["client"].app) as local_client:
            started = time.perf_counter()
            resp = local_client.get(
                "/api/admin/product-keys?page=1&page_size=20",
                headers=_auth_header(token),
            )
            duration_ms = (time.perf_counter() - started) * 1000
            return resp.status_code, duration_ms

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(lambda _: _query_once(), range(100)))

    statuses = [item[0] for item in results]
    durations = [item[1] for item in results]
    success_rate = sum(1 for code in statuses if code == 200) / len(statuses)

    assert success_rate >= 0.95
    assert _p95(durations) < 1000


def test_memory_and_network_baseline(perf_client) -> None:
    client: TestClient = perf_client["client"]
    token = perf_client["tokens"]["company_admin"]

    _create_enterprise_keys(client, token, 200)

    tracemalloc.start()
    started = time.perf_counter()
    response = client.get(
        "/api/admin/product-keys?page=1&page_size=200",
        headers=_auth_header(token),
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert response.status_code == 200, response.text
    payload_bytes = len(response.content)
    throughput_mbps = (payload_bytes / 1024 / 1024) / max(elapsed, 1e-6)

    assert peak / (1024 * 1024) < 70
    assert throughput_mbps > 0.1
