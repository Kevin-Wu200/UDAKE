import argparse
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def run_module():
    module_path = Path(__file__).resolve().parents[1] / "run.py"
    spec = importlib.util.spec_from_file_location("backend_run_stage6", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    data = {
        "env": None,
        "redis_timeout": 0.2,
        "redis_retries": 1,
        "port": None,
        "port_strategy": "prompt",
        "port_scan_limit": 10,
    }
    data.update(overrides)
    return argparse.Namespace(**data)


def test_redis_auto_start_skip_when_running(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_redis_running", lambda: True)

    def _should_not_call():
        raise AssertionError("_resolve_redis_command 不应被调用")

    monkeypatch.setattr(run_module, "_resolve_redis_command", _should_not_call)
    assert run_module.ensure_redis_running() is True


def test_redis_auto_start_success(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_redis_running", lambda: False)
    monkeypatch.setattr(run_module, "_resolve_redis_command", lambda: ["redis-server"])
    monkeypatch.setattr(run_module, "_try_start_redis_once", lambda *args, **kwargs: True)
    assert run_module.ensure_redis_running(startup_timeout=0.1, retries=2) is True


def test_redis_auto_start_degrade_when_failed(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_redis_running", lambda: False)
    monkeypatch.setattr(run_module, "_resolve_redis_command", lambda: ["redis-server"])
    monkeypatch.setattr(run_module, "_try_start_redis_once", lambda *args, **kwargs: False)
    assert run_module.ensure_redis_running(startup_timeout=0.1, retries=2) is False


def test_select_environment_from_cli_arg(run_module, monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    selected = run_module._select_environment(_args(env="production"))
    assert selected == "production"
    assert os.environ["ENVIRONMENT"] == "production"


def test_select_environment_interactive_choice(run_module, monkeypatch):
    monkeypatch.setattr(run_module.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "2")
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    selected = run_module._select_environment(_args())
    assert selected == "testing"
    assert os.environ["ENVIRONMENT"] == "testing"


def test_select_environment_env_fallback_in_non_tty(run_module, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(run_module.sys.stdin, "isatty", lambda: False)

    selected = run_module._select_environment(_args())
    assert selected == "production"


def test_port_conflict_keep_when_available(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_port_available", lambda host, port: True)
    assert run_module._resolve_port_conflict("127.0.0.1", 8000, strategy="exit") == 8000


def test_port_conflict_kill_success(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_port_available", lambda host, port: False)
    monkeypatch.setattr(run_module, "_get_processes_using_port", lambda port: [{"pid": "123", "command": "python"}])
    monkeypatch.setattr(run_module, "_terminate_processes_on_port", lambda *args, **kwargs: True)

    resolved = run_module._resolve_port_conflict("127.0.0.1", 8000, strategy="kill")
    assert resolved == 8000


def test_port_conflict_kill_failure(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_port_available", lambda host, port: False)
    monkeypatch.setattr(run_module, "_get_processes_using_port", lambda port: [{"pid": "456", "command": "python"}])
    monkeypatch.setattr(run_module, "_terminate_processes_on_port", lambda *args, **kwargs: False)

    resolved = run_module._resolve_port_conflict("127.0.0.1", 8000, strategy="kill")
    assert resolved is None


def test_port_conflict_prompt_switches_to_auto_in_non_tty(run_module, monkeypatch):
    monkeypatch.setattr(run_module, "_is_port_available", lambda host, port: False)
    monkeypatch.setattr(run_module, "_get_processes_using_port", lambda port: [])
    monkeypatch.setattr(run_module, "_find_next_available_port", lambda host, base_port, scan_limit: 8001)
    monkeypatch.setattr(run_module.sys.stdin, "isatty", lambda: False)

    resolved = run_module._resolve_port_conflict("127.0.0.1", 8000, strategy="prompt")
    assert resolved == 8001


def test_run_backend_integration_success(run_module, monkeypatch):
    fake_config = types.ModuleType("app.config")
    fake_config.settings = types.SimpleNamespace(
        PORT=9000,
        HOST="127.0.0.1",
        DEBUG=False,
        APP_NAME="UDAKE-Backend-Test",
    )
    monkeypatch.setitem(sys.modules, "app.config", fake_config)

    calls = {"uvicorn": 0, "redis": 0, "cleanup": 0}
    monkeypatch.setattr(run_module, "_select_environment", lambda args: "development")
    monkeypatch.setattr(run_module, "_resolve_port_conflict", lambda **kwargs: 9010)
    monkeypatch.setattr(run_module, "ensure_redis_running", lambda **kwargs: calls.__setitem__("redis", calls["redis"] + 1) or True)

    def _fake_uvicorn_run(*args, **kwargs):
        calls["uvicorn"] += 1

    monkeypatch.setattr(run_module.uvicorn, "run", _fake_uvicorn_run)

    def _fake_cleanup():
        calls["cleanup"] += 1

    monkeypatch.setattr(run_module, "_cleanup_runtime_resources", _fake_cleanup)

    exit_code = run_module.run_backend(_args(env="development", port=9000, port_strategy="auto"))

    assert exit_code == 0
    assert calls["redis"] == 1
    assert calls["uvicorn"] == 1
    assert calls["cleanup"] == 1


def test_run_backend_exits_on_unresolved_port(run_module, monkeypatch):
    fake_config = types.ModuleType("app.config")
    fake_config.settings = types.SimpleNamespace(
        PORT=8000,
        HOST="0.0.0.0",
        DEBUG=True,
        APP_NAME="UDAKE-Backend-Test",
    )
    monkeypatch.setitem(sys.modules, "app.config", fake_config)

    monkeypatch.setattr(run_module, "_select_environment", lambda args: "testing")
    monkeypatch.setattr(run_module, "_resolve_port_conflict", lambda **kwargs: None)

    uvicorn_called = {"value": False}
    monkeypatch.setattr(run_module.uvicorn, "run", lambda *args, **kwargs: uvicorn_called.__setitem__("value", True))

    exit_code = run_module.run_backend(_args(env="testing", port=8000, port_strategy="exit"))

    assert exit_code == 1
    assert uvicorn_called["value"] is False
