"""跨模型 Stage2 测试辅助工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class ModelComparisonRecord:
    model_id: str
    latency_ms: float
    accuracy_score: float
    explanation_consistency: float
    stability_score: float
    error_rate: float = 0.0


@dataclass(frozen=True)
class RegressionThreshold:
    latency_ratio_limit: float = 1.2
    accuracy_drop_limit: float = 0.02
    stability_drop_limit: float = 0.03


class CrossModelStage2Toolkit:
    """用于第二阶段跨模型测试的对比、回归与报告生成。"""

    def compare_models(self, records: list[ModelComparisonRecord]) -> dict[str, Any]:
        if not records:
            return {
                "summary": {
                    "model_count": 0,
                    "best_model": "",
                    "mean_latency_ms": 0.0,
                    "mean_accuracy": 0.0,
                    "mean_stability": 0.0,
                },
                "ranking": [],
            }

        mean_latency = sum(max(0.0, r.latency_ms) for r in records) / len(records)
        mean_accuracy = sum(max(0.0, r.accuracy_score) for r in records) / len(records)
        mean_stability = sum(max(0.0, r.stability_score) for r in records) / len(records)

        scored: list[dict[str, Any]] = []
        for row in records:
            # 综合准确率、解释一致性、稳定性，并对高时延和错误率做惩罚。
            quality = 0.45 * row.accuracy_score + 0.25 * row.explanation_consistency + 0.30 * row.stability_score
            latency_penalty = min(0.4, max(0.0, row.latency_ms / max(1.0, mean_latency) - 1.0) * 0.2)
            error_penalty = min(0.6, max(0.0, row.error_rate) * 2.0)
            final_score = max(0.0, min(1.0, quality - latency_penalty - error_penalty))
            scored.append(
                {
                    "model_id": row.model_id,
                    "latency_ms": round(row.latency_ms, 3),
                    "accuracy_score": round(row.accuracy_score, 6),
                    "explanation_consistency": round(row.explanation_consistency, 6),
                    "stability_score": round(row.stability_score, 6),
                    "error_rate": round(row.error_rate, 6),
                    "final_score": round(final_score, 6),
                }
            )

        ranking = sorted(scored, key=lambda item: item["final_score"], reverse=True)
        return {
            "summary": {
                "model_count": len(records),
                "best_model": ranking[0]["model_id"],
                "mean_latency_ms": round(mean_latency, 3),
                "mean_accuracy": round(mean_accuracy, 6),
                "mean_stability": round(mean_stability, 6),
            },
            "ranking": ranking,
        }

    def detect_regressions(
        self,
        baseline: dict[str, ModelComparisonRecord],
        current: dict[str, ModelComparisonRecord],
        threshold: RegressionThreshold | None = None,
    ) -> dict[str, Any]:
        cfg = threshold or RegressionThreshold()
        rows: list[dict[str, Any]] = []
        for model_id, base in baseline.items():
            now = current.get(model_id)
            if now is None:
                rows.append({"model_id": model_id, "status": "missing_in_current", "regression": True})
                continue

            latency_ratio = now.latency_ms / max(1e-9, base.latency_ms)
            accuracy_drop = base.accuracy_score - now.accuracy_score
            stability_drop = base.stability_score - now.stability_score
            regression = (
                latency_ratio > cfg.latency_ratio_limit
                or accuracy_drop > cfg.accuracy_drop_limit
                or stability_drop > cfg.stability_drop_limit
            )
            rows.append(
                {
                    "model_id": model_id,
                    "latency_ratio": round(latency_ratio, 6),
                    "accuracy_drop": round(accuracy_drop, 6),
                    "stability_drop": round(stability_drop, 6),
                    "regression": regression,
                    "status": "regression" if regression else "ok",
                }
            )

        regression_count = sum(1 for row in rows if row.get("regression") is True)
        return {
            "summary": {
                "checked_models": len(rows),
                "regression_count": regression_count,
                "passed": regression_count == 0,
            },
            "details": rows,
        }

    def find_bottlenecks(self, records: list[ModelComparisonRecord], latency_threshold_ms: float) -> dict[str, Any]:
        if not records:
            return {"summary": {"bottleneck_count": 0, "threshold_ms": float(latency_threshold_ms)}, "items": []}

        items = [
            {
                "model_id": row.model_id,
                "latency_ms": round(row.latency_ms, 3),
                "error_rate": round(row.error_rate, 6),
                "is_bottleneck": row.latency_ms > latency_threshold_ms,
            }
            for row in sorted(records, key=lambda x: x.latency_ms, reverse=True)
        ]
        bottlenecks = [item for item in items if item["is_bottleneck"]]
        return {
            "summary": {
                "bottleneck_count": len(bottlenecks),
                "threshold_ms": float(latency_threshold_ms),
                "max_latency_ms": round(max(row.latency_ms for row in records), 3),
            },
            "items": items,
        }

    @staticmethod
    def schedule_next_run(last_run_iso: str, interval_minutes: int) -> dict[str, Any]:
        last = datetime.fromisoformat(last_run_iso)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        next_run = last + timedelta(minutes=max(1, int(interval_minutes)))
        now = datetime.now(timezone.utc)
        return {
            "last_run": last.isoformat(),
            "next_run": next_run.isoformat(),
            "due": now >= next_run,
            "remaining_seconds": max(0.0, (next_run - now).total_seconds()),
        }

    def build_markdown_report(
        self,
        *,
        comparison: dict[str, Any],
        regression: dict[str, Any],
        performance: dict[str, Any],
        stability: dict[str, Any],
        stress: dict[str, Any],
        compatibility: dict[str, Any],
    ) -> str:
        lines: list[str] = [
            "# 跨模型测试第二阶段报告",
            "",
            "## 1. 跨模型对比测试",
            f"- 模型数量: {comparison.get('summary', {}).get('model_count', 0)}",
            f"- 最优模型: {comparison.get('summary', {}).get('best_model', '')}",
            f"- 平均时延(ms): {comparison.get('summary', {}).get('mean_latency_ms', 0.0)}",
            "",
            "## 2. 回归测试",
            f"- 检查模型数: {regression.get('summary', {}).get('checked_models', 0)}",
            f"- 回归数量: {regression.get('summary', {}).get('regression_count', 0)}",
            f"- 是否通过: {regression.get('summary', {}).get('passed', False)}",
            "",
            "## 3. 性能对比测试",
            f"- 瓶颈数量: {performance.get('summary', {}).get('bottleneck_count', 0)}",
            f"- 阈值(ms): {performance.get('summary', {}).get('threshold_ms', 0.0)}",
            f"- 最大时延(ms): {performance.get('summary', {}).get('max_latency_ms', 0.0)}",
            "",
            "## 4. 稳定性测试",
            f"- 重复次数: {stability.get('repeat_count', 0)}",
            f"- 签名稳定率: {stability.get('signature_stability', 0.0)}",
            f"- 异常恢复通过: {stability.get('recovery_ok', False)}",
            "",
            "## 5. 压力测试（多模型并发）",
            f"- 请求总数: {stress.get('total_requests', 0)}",
            f"- 完成率: {stress.get('completion_rate', 0.0)}",
            f"- 错误率: {stress.get('error_rate', 0.0)}",
            "",
            "## 6. 兼容性测试",
            f"- 浏览器覆盖: {compatibility.get('browsers', [])}",
            f"- 操作系统覆盖: {compatibility.get('os', [])}",
            f"- Python 版本覆盖: {compatibility.get('python_versions', [])}",
            f"- 依赖检查通过: {compatibility.get('dependency_check', False)}",
        ]
        return "\n".join(lines).strip() + "\n"
