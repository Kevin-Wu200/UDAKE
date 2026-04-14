"""示例集合可运行性验证脚本。"""

from __future__ import annotations

import subprocess
import sys
import time
import os
from pathlib import Path


EXAMPLES: list[tuple[str, str]] = [
    ("异常检测使用示例", "anomaly_inference_demo.py"),
    ("空间插值使用示例", "spatial_interpolation_adapter_usage_demo.py"),
    ("不确定性使用示例", "uncertainty_inference_demo.py"),
    ("融合模型使用示例", "fusion_adapter_usage_demo.py"),
    ("强化学习使用示例", "rl_adapter_usage_demo.py"),
    ("多模型对比示例", "anomaly_multi_model_comparison_demo.py"),
    ("高级用法示例", "advanced_usage_demo.py"),
]


def main() -> None:
    root = Path(__file__).resolve().parent
    repo_root = root.parents[1]
    pythonpath_entries = [str(repo_root), str(root)]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath_entries.append(existing)
    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = ":".join(pythonpath_entries)

    failures: list[str] = []

    print("开始验证示例集合可运行性...\n")
    for name, rel in EXAMPLES:
        target = root / rel
        if not target.exists():
            failures.append(f"{name}: 文件不存在 -> {rel}")
            print(f"[FAIL] {name} ({rel}) 文件不存在")
            continue

        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(target)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=240,
            env=run_env,
        )
        duration = time.perf_counter() - start
        if proc.returncode == 0:
            print(f"[PASS] {name} ({rel}) {duration:.2f}s")
        else:
            failures.append(f"{name}: exit={proc.returncode}")
            print(f"[FAIL] {name} ({rel}) {duration:.2f}s")
            stderr = (proc.stderr or "").strip().splitlines()
            stdout = (proc.stdout or "").strip().splitlines()
            preview = (stderr + stdout)[:8]
            for line in preview:
                print(f"  {line}")
        print()

    if failures:
        print("验证失败：")
        for item in failures:
            print(f"- {item}")
        raise SystemExit(1)

    print("全部示例验证通过。")


if __name__ == "__main__":
    main()
