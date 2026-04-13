from __future__ import annotations

from pathlib import Path

import pytest

from services.backend.app.dl_services.unified_framework import (
    FrameworkErrorCode,
    UnifiedConfigError,
    UnifiedConfigManager,
    UnifiedErrorHandler,
)


def test_unified_config_manager_load_version_and_docs(tmp_path: Path) -> None:
    config_path = tmp_path / "unified_framework_config.json"
    manager = UnifiedConfigManager(config_path=config_path)

    config = manager.load()
    assert config["meta"]["name"] == "unified_framework"
    assert config_path.exists()

    versions = manager.versions()
    assert len(versions) >= 1
    assert versions[-1]["source"] in {"bootstrap", "load"}

    docs = manager.generate_docs()
    assert "# 统一配置文档" in docs
    assert "runtime.max_workers" in docs


def test_unified_config_manager_hot_update_validate_and_backup_restore(tmp_path: Path) -> None:
    config_path = tmp_path / "unified_framework_config.json"
    manager = UnifiedConfigManager(config_path=config_path)
    manager.load()

    backup_path = manager.backup(note="before_update")
    assert backup_path.exists()

    updated = manager.hot_update({"runtime": {"max_workers": 8}}, note="scale_up")
    assert updated["runtime"]["max_workers"] == 8

    with pytest.raises(UnifiedConfigError) as exc_info:
        manager.hot_update({"runtime": {"max_workers": 0}}, note="invalid")
    assert exc_info.value.code == FrameworkErrorCode.CONFIG_VALIDATE_FAILED

    restored = manager.restore(backup_path)
    assert restored["runtime"]["max_workers"] == 4


def test_unified_error_handler_capture_recovery_and_notify() -> None:
    handler = UnifiedErrorHandler()
    notices: list[dict[str, object]] = []

    handler.register_notifier(lambda event: notices.append({"code": event.code, "id": event.event_id}))
    handler.register_recovery(FrameworkErrorCode.CONFIG_HOT_RELOAD_FAILED, lambda _: True)

    event = handler.capture(
        UnifiedConfigError(
            "hot update failed",
            code=FrameworkErrorCode.CONFIG_HOT_RELOAD_FAILED,
            recoverable=True,
        ),
        context={"phase": "unit_test"},
    )

    assert event.code == FrameworkErrorCode.CONFIG_HOT_RELOAD_FAILED
    assert event.recoverable is True
    assert event.recovered is True
    assert len(notices) == 1
    assert len(handler.events()) == 1


def test_unified_error_handler_capture_context_and_docs() -> None:
    handler = UnifiedErrorHandler()

    with handler.capture_context(context={"phase": "capture_context"}, recoverable=True):
        raise RuntimeError("boom")

    events = handler.events()
    assert len(events) == 1
    assert events[0]["code"] == FrameworkErrorCode.EXECUTION_FAILED
    assert events[0]["recoverable"] is True

    docs = handler.generate_docs()
    assert "# 统一错误处理文档" in docs
    assert "FWK_1002" in docs
