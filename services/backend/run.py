#!/usr/bin/env python3
"""
后端服务启动脚本
"""
import argparse
import asyncio
import atexit
import gc
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import warnings
from urllib.parse import urlparse
from typing import List, Optional

# 尽早配置 warning 过滤，避免导入期噪声污染启动日志。
warnings.filterwarnings("ignore", message=".*urllib3.*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")

import sys; print(f'DEBUG PATH: {sys.path}')
import uvicorn

ENV_CHOICES = ("development", "testing", "production")
PORT_STRATEGIES = ("prompt", "kill", "auto", "exit")
_RUNTIME_CLEANED_UP = False


def _normalize_environment(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in ENV_CHOICES:
        raise ValueError(f"不支持的环境: {value}")
    return normalized


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动后端服务")
    parser.add_argument(
        "--env",
        choices=ENV_CHOICES,
        help="运行环境，可选: development/testing/production",
    )
    parser.add_argument(
        "--redis-timeout",
        type=float,
        default=6.0,
        help="Redis 自动启动检测超时时间（秒）",
    )
    parser.add_argument(
        "--redis-retries",
        type=int,
        default=2,
        help="Redis 自动启动重试次数",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="覆盖配置文件中的监听端口",
    )
    parser.add_argument(
        "--port-strategy",
        choices=PORT_STRATEGIES,
        default="prompt",
        help="端口占用处理策略: prompt(交互)/kill(自动清理)/auto(自动换端口)/exit(直接退出)",
    )
    parser.add_argument(
        "--port-scan-limit",
        type=int,
        default=50,
        help="自动换端口时最多向后扫描的端口数量",
    )
    return parser.parse_args()


def _select_environment(args: argparse.Namespace) -> str:
    if args.env:
        env = _normalize_environment(args.env)
        os.environ["ENVIRONMENT"] = env
        print(f"✓ 使用命令行环境: {env}")
        return env

    env_from_var = os.getenv("ENVIRONMENT", "").strip().lower()
    if not sys.stdin.isatty():
        fallback = env_from_var if env_from_var in ENV_CHOICES else "development"
        os.environ["ENVIRONMENT"] = fallback
        print(f"ℹ️ 检测到非交互终端，使用环境: {fallback}")
        return fallback

    print("\n请选择运行环境:")
    print("1. development (开发环境)")
    print("2. testing (测试环境)")
    print("3. production (生产环境)")
    default_env = env_from_var if env_from_var in ENV_CHOICES else "development"
    default_choice = {"development": "1", "testing": "2", "production": "3"}[default_env]
    choice = input(f"请输入选择 (1-3，默认 {default_choice}): ").strip()
    env_map = {"1": "development", "2": "testing", "3": "production"}
    selected_env = env_map.get(choice, default_env)
    os.environ["ENVIRONMENT"] = selected_env
    print(f"✓ 已选择环境: {selected_env}")
    return selected_env


def _is_redis_running(host: str = "127.0.0.1", port: int = 6379, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _resolve_redis_command() -> Optional[List[str]]:
    system_name = platform.system().lower()
    candidate_commands: list[list[str]] = []
    if "windows" in system_name:
        candidate_commands.extend(
            [["redis-server.exe"], ["redis-server"], ["memurai.exe"], ["memurai"]]
        )
    else:
        candidate_commands.extend(
            [["redis-server"], ["/usr/local/bin/redis-server"], ["/opt/homebrew/bin/redis-server"]]
        )

    for command in candidate_commands:
        executable = command[0]
        if os.path.isabs(executable) and os.path.exists(executable):
            return command
        if shutil.which(executable):
            return command
    return None


def _try_start_redis_once(start_command: list[str], startup_timeout: float) -> bool:
    subprocess.Popen(
        start_command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.time() + max(startup_timeout, 1.0)
    while time.time() < deadline:
        if _is_redis_running():
            return True
        time.sleep(0.2)
    return _is_redis_running()


def _is_local_redis_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def _resolve_redis_target(
    redis_url: Optional[str],
    redis_host: str,
    redis_port: int,
) -> tuple[str, int]:
    if redis_url:
        parsed = urlparse(redis_url)
        if parsed.hostname:
            return parsed.hostname, int(parsed.port or 6379)
    return redis_host, int(redis_port)


def ensure_redis_running(
    startup_timeout: float = 6.0,
    retries: int = 2,
    redis_url: Optional[str] = None,
    redis_host: str = "127.0.0.1",
    redis_port: int = 6379,
) -> bool:
    target_host, target_port = _resolve_redis_target(redis_url, redis_host, redis_port)
    if _is_redis_running(host=target_host, port=target_port):
        print(f"✓ Redis 已运行 ({target_host}:{target_port})")
        return True

    if not _is_local_redis_host(target_host):
        print(
            f"ℹ️ Redis({target_host}:{target_port}) 未就绪，跳过本地 redis-server 自动拉起，将继续启动并按运行时策略回退"
        )
        return False

    start_command = _resolve_redis_command()
    if not start_command:
        print("⚠️ 未找到 redis-server 可执行文件，将继续启动并使用内存后端")
        return False

    total_attempts = max(retries, 1)
    print(f"ℹ️ Redis 未运行，准备自动启动（命令: {' '.join(start_command)}）")
    for attempt in range(1, total_attempts + 1):
        try:
            print(f"⏳ 正在启动 Redis（第 {attempt}/{total_attempts} 次）...")
            if _try_start_redis_once(start_command, startup_timeout=startup_timeout):
                print("✓ Redis 启动成功")
                return True
        except Exception as exc:
            print(f"⚠️ Redis 启动异常（第 {attempt}/{total_attempts} 次）: {exc}")

    print("⚠️ Redis 启动失败，将继续启动服务并回退到内存后端")
    return False


def _is_port_available(host: str, port: int) -> bool:
    bind_host = "0.0.0.0" if host in ("", "0.0.0.0", "::") else host
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, int(port)))
            return True
        except OSError:
            return False


def _get_processes_using_port(port: int) -> list[dict[str, str]]:
    if platform.system().lower().startswith("win"):
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return []
        processes: list[dict[str, str]] = []
        seen: set[str] = set()
        suffix = f":{port}"
        for line in result.stdout.splitlines():
            text = line.strip()
            if not text or "LISTENING" not in text.upper() or suffix not in text:
                continue
            parts = text.split()
            if len(parts) < 5:
                continue
            pid = parts[-1]
            if pid and pid not in seen:
                seen.add(pid)
                processes.append({"pid": pid, "command": "unknown"})
        return processes

    if not shutil.which("lsof"):
        return []

    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []

    processes: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        command, pid = parts[0], parts[1]
        if pid and pid not in seen:
            seen.add(pid)
            processes.append({"pid": pid, "command": command})
    return processes


def _terminate_processes_on_port(
    port: int,
    processes: list[dict[str, str]],
    wait_seconds: float = 3.0,
) -> bool:
    if not processes:
        return True
    pids = [proc["pid"] for proc in processes if proc.get("pid")]
    if not pids:
        return True

    is_windows = platform.system().lower().startswith("win")
    for pid in pids:
        try:
            if is_windows:
                subprocess.run(
                    ["taskkill", "/PID", pid, "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.run(
                    ["kill", "-TERM", pid],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as exc:
            print(f"⚠️ 终止进程 {pid} 失败: {exc}")

    deadline = time.time() + max(wait_seconds, 0.5)
    while time.time() < deadline:
        if _is_port_available("0.0.0.0", port):
            return True
        time.sleep(0.2)

    if is_windows:
        return _is_port_available("0.0.0.0", port)

    # Unix 下补充一次 SIGKILL，尽量确保端口释放。
    time.sleep(0.3)
    for pid in pids:
        try:
            subprocess.run(
                ["kill", "-0", pid],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["kill", "-KILL", pid],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue
    return _is_port_available("0.0.0.0", port)


def _find_next_available_port(host: str, base_port: int, scan_limit: int) -> Optional[int]:
    upper = int(base_port) + max(scan_limit, 1)
    for candidate in range(int(base_port), upper + 1):
        if _is_port_available(host, candidate):
            return candidate
    return None


def _resolve_port_conflict(
    host: str,
    port: int,
    strategy: str = "prompt",
    scan_limit: int = 50,
) -> Optional[int]:
    target_port = int(port)
    if _is_port_available(host, target_port):
        return target_port

    processes = _get_processes_using_port(target_port)
    print(f"⚠️ 端口 {target_port} 已被占用")
    if processes:
        print("占用进程列表:")
        for process in processes:
            print(f"  PID={process['pid']} CMD={process['command']}")
    else:
        print("⚠️ 未能识别占用进程，可能缺少 lsof 或权限不足")

    active_strategy = strategy
    if strategy == "prompt" and not sys.stdin.isatty():
        active_strategy = "auto"
        print("ℹ️ 非交互终端，自动切换为 auto 策略")

    if active_strategy == "exit":
        return None

    if active_strategy == "kill":
        if not processes:
            print("⚠️ 无法确定占用进程，无法执行自动清理")
            return None
        print(f"⏳ 尝试终止占用端口 {target_port} 的进程...")
        if _terminate_processes_on_port(target_port, processes):
            print(f"✓ 端口 {target_port} 已释放")
            return target_port
        print(f"⚠️ 端口 {target_port} 清理后仍不可用")
        return None

    if active_strategy == "auto":
        next_port = _find_next_available_port(host, target_port + 1, scan_limit)
        if next_port is None:
            print("✗ 自动寻找可用端口失败")
            return None
        print(f"✓ 端口自动切换: {target_port} -> {next_port}")
        return next_port

    # prompt 模式（交互终端）
    print("\n请选择端口冲突处理方式:")
    print("1. 终止占用进程并继续")
    print("2. 自动选择下一个可用端口")
    print("3. 退出")
    choice = input("请输入选择 (1-3，默认 2): ").strip()
    if choice == "1":
        if not processes:
            print("⚠️ 无法确定占用进程，无法执行清理")
            return None
        print(f"⏳ 尝试终止占用端口 {target_port} 的进程...")
        if _terminate_processes_on_port(target_port, processes):
            print(f"✓ 端口 {target_port} 已释放")
            return target_port
        print(f"⚠️ 端口 {target_port} 清理后仍不可用")
        return None

    if choice == "3":
        return None

    next_port = _find_next_available_port(host, target_port + 1, scan_limit)
    if next_port is None:
        print("✗ 自动寻找可用端口失败")
        return None
    print(f"✓ 端口自动切换: {target_port} -> {next_port}")
    return next_port


def _cleanup_runtime_resources() -> None:
    """
    主进程退出前清理资源，减少 unclosed socket/file 告警。
    这里不抛异常，避免影响退出路径。
    """
    global _RUNTIME_CLEANED_UP
    if _RUNTIME_CLEANED_UP:
        return
    _RUNTIME_CLEANED_UP = True

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and not loop.is_closed():
        try:
            pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending_tasks:
                task.cancel()
            if pending_tasks:
                loop.run_until_complete(
                    asyncio.gather(*pending_tasks, return_exceptions=True)
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            if hasattr(loop, "shutdown_default_executor"):
                loop.run_until_complete(loop.shutdown_default_executor())
        except Exception as exc:  # pylint: disable=broad-except
            print(f"⚠️ 运行时资源清理异常: {exc}")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    try:
        logging.shutdown()
    except Exception:
        pass
    gc.collect()


atexit.register(_cleanup_runtime_resources)


def run_backend(cli_args: Optional[argparse.Namespace] = None) -> int:
    cli_args = cli_args or _parse_args()
    selected_env = _select_environment(cli_args)

    # 在设置 ENVIRONMENT 后再导入配置，确保读取到正确环境配置文件。
    from app.config import settings
    # 同步关键配置到进程环境变量，避免子模块仅从 os.environ 读取时与 settings 不一致。
    os.environ["REDIS_ENABLED"] = "true" if bool(getattr(settings, "REDIS_ENABLED", False)) else "false"
    os.environ["REDIS_URL"] = str(getattr(settings, "REDIS_URL", "") or "")
    os.environ["REDIS_HOST"] = str(getattr(settings, "REDIS_HOST", "") or "")
    os.environ["REDIS_PORT"] = str(getattr(settings, "REDIS_PORT", 6379) or 6379)
    os.environ["REDIS_DB"] = str(getattr(settings, "REDIS_DB", 0) or 0)

    configured_port = int(cli_args.port or settings.PORT)
    startup_port = _resolve_port_conflict(
        host=settings.HOST,
        port=configured_port,
        strategy=cli_args.port_strategy,
        scan_limit=cli_args.port_scan_limit,
    )
    if startup_port is None:
        print("✗ 端口冲突未解决，服务退出")
        return 1

    redis_enabled = bool(getattr(settings, "REDIS_ENABLED", False))
    redis_url = getattr(settings, "REDIS_URL", None)
    redis_host = str(getattr(settings, "REDIS_HOST", "127.0.0.1"))
    redis_port = int(getattr(settings, "REDIS_PORT", 6379))

    if redis_enabled or redis_url:
        ensure_redis_running(
            startup_timeout=cli_args.redis_timeout,
            retries=cli_args.redis_retries,
            redis_url=redis_url,
            redis_host=redis_host,
            redis_port=redis_port,
        )
    else:
        print("ℹ️ REDIS_ENABLED=False 且未配置 REDIS_URL，跳过 Redis 自动拉起检查")

    print(f"🚀 启动 {settings.APP_NAME}")
    print(f"🌍 环境: {selected_env}")
    print(f"📍 地址: http://{settings.HOST}:{startup_port}")
    print(f"📖 API文档: http://{settings.HOST}:{startup_port}/docs")

    try:
        uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=startup_port,
            reload=settings.DEBUG,
            log_level="info",
        )
    finally:
        _cleanup_runtime_resources()
    return 0


if __name__ == "__main__":
    sys.exit(run_backend())
