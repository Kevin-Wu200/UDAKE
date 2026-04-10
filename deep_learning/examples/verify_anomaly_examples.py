"""批量验证异常检测示例可运行。"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


EXAMPLES = [
    "deep_learning/examples/anomaly_vae_full_demo.py",
    "deep_learning/examples/anomaly_gcae_full_demo.py",
    "deep_learning/examples/anomaly_gan_full_demo.py",
    "deep_learning/examples/anomaly_contrastive_full_demo.py",
    "deep_learning/examples/anomaly_multi_model_comparison_demo.py",
    "deep_learning/examples/anomaly_batch_processing_demo.py",
    "deep_learning/examples/anomaly_custom_visualization_demo.py",
    "deep_learning/examples/anomaly_performance_optimization_demo.py",
]


def run_one(script: str) -> tuple[bool, float, str]:
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, script], capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - start
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, elapsed, output.strip()


def main() -> None:
    failed: list[str] = []
    total_start = time.perf_counter()
    for script in EXAMPLES:
        ok, elapsed, output = run_one(script)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {script} ({elapsed:.2f}s)")
        if not ok:
            failed.append(script)
            print(output)

    total_elapsed = time.perf_counter() - total_start
    print(f"\n总耗时: {total_elapsed:.2f}s")
    print(f"通过: {len(EXAMPLES) - len(failed)}/{len(EXAMPLES)}")
    if failed:
        print("失败脚本:")
        for item in failed:
            print("-", item)
        raise SystemExit(1)

    output_dir = Path("deep_learning/examples/output")
    if output_dir.exists():
        print("输出目录:", output_dir)


if __name__ == "__main__":
    main()
