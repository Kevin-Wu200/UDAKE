from __future__ import annotations

from pathlib import Path

from app.runtime_config_manager import RuntimeConfigManager


def test_runtime_config_versioning_diff_rollback_and_reload(tmp_path: Path):
    config_path = tmp_path / "validation_config.yaml"
    config_path.write_text("a: 1\nb: 2\n", encoding="utf-8")

    manager = RuntimeConfigManager(config_path=str(config_path), max_history=20)
    current = manager.current()
    assert current["version"] == 1
    assert current["data"]["a"] == 1

    updated = manager.update({"b": 3, "c": True}, actor="tester", comment="first_update")
    assert updated["version"] == 2
    assert updated["data"]["b"] == 3
    assert updated["data"]["c"] is True

    diff = manager.diff(1, 2)
    assert diff["changed_count"] >= 2
    changed_keys = {item["key"] for item in diff["changed"]}
    assert "b" in changed_keys
    assert "c" in changed_keys

    rolled = manager.rollback(1, actor="tester")
    assert rolled["version"] == 3
    assert rolled["data"]["a"] == 1
    assert rolled["data"]["b"] == 2

    config_path.write_text("a: 9\nd: hot\n", encoding="utf-8")
    reloaded = manager.check_reload(actor="watcher")
    assert reloaded["reloaded"] is True

    latest = manager.current()
    assert latest["version"] == 4
    assert latest["data"]["a"] == 9
    assert latest["data"]["d"] == "hot"
