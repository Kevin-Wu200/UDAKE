"""Data quality evaluation and scoring."""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from .anomaly_detection import DataQualityAnomalyDetector
from .models import DimensionMetric, QualityDimension, QualityReport, RuleViolation
from .rule_engine import DataQualityRuleEngine


class DataQualityEvaluator:
    """Evaluate dataset quality with weighted multi-dimension scores."""

    DEFAULT_WEIGHTS: Dict[str, float] = {
        QualityDimension.COMPLETENESS.value: 0.25,
        QualityDimension.ACCURACY.value: 0.25,
        QualityDimension.CONSISTENCY.value: 0.2,
        QualityDimension.UNIQUENESS.value: 0.15,
        QualityDimension.VALIDITY.value: 0.15,
    }

    def evaluate(
        self,
        dataset_id: str,
        records: List[Dict[str, Any]],
        rule_engine: DataQualityRuleEngine,
        anomaly_detector: DataQualityAnomalyDetector,
        value_field: str = "value",
        x_field: str = "x",
        y_field: str = "y",
        weights: Optional[Dict[str, float]] = None,
    ) -> QualityReport:
        start = time.perf_counter()
        execution = rule_engine.execute(records)
        anomalies = anomaly_detector.detect_from_records(
            records,
            value_field=value_field,
            x_field=x_field,
            y_field=y_field,
        )

        violations: List[RuleViolation] = execution["violations"]
        dimension_stats = execution["dimension_stats"]

        metrics: List[DimensionMetric] = []
        dimension_scores: Dict[str, float] = {}

        for dimension in QualityDimension:
            stat = dimension_stats.get(dimension.value, {"total": 0, "failed": 0})
            total = int(stat.get("total", 0))
            failed = int(stat.get("failed", 0))
            score = 100.0 if total == 0 else max(0.0, (1.0 - failed / total) * 100.0)
            pass_rate = 1.0 if total == 0 else (total - failed) / total
            metrics.append(
                DimensionMetric(
                    dimension=dimension,
                    score=round(score, 2),
                    total_checks=total,
                    failed_checks=failed,
                    pass_rate=round(pass_rate, 4),
                )
            )
            dimension_scores[dimension.value] = round(score, 2)

        normalized_weights = self._normalize_weights(weights)
        overall_score = round(
            sum(dimension_scores[key] * weight for key, weight in normalized_weights.items()),
            2,
        )

        report = QualityReport(
            report_id=self._build_report_id(dataset_id),
            dataset_id=dataset_id,
            generated_at=datetime.utcnow(),
            total_records=len(records),
            overall_score=overall_score,
            grade=self._score_grade(overall_score),
            dimension_scores=dimension_scores,
            metrics=metrics,
            violations=violations,
            anomalies=anomalies,
            suggestions=self._build_suggestions(
                dimension_scores=dimension_scores,
                violations=violations,
                anomalies=anomalies,
                total_records=len(records),
                weights=normalized_weights,
            ),
            execution_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return report

    def _normalize_weights(self, custom: Optional[Dict[str, float]]) -> Dict[str, float]:
        if not custom:
            return dict(self.DEFAULT_WEIGHTS)

        merged = dict(self.DEFAULT_WEIGHTS)
        for key, value in custom.items():
            if key not in merged:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            merged[key] = max(0.0, numeric)

        weight_sum = sum(merged.values())
        if weight_sum <= 0:
            return dict(self.DEFAULT_WEIGHTS)

        return {key: value / weight_sum for key, value in merged.items()}

    def _build_report_id(self, dataset_id: str) -> str:
        safe_dataset = re.sub(r"[^A-Za-z0-9_-]", "_", dataset_id.strip() or "dataset")
        return f"dq_{safe_dataset}_{int(time.time() * 1000)}"

    def _score_grade(self, score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "E"

    def _build_suggestions(
        self,
        dimension_scores: Dict[str, float],
        violations: List[RuleViolation],
        anomalies: List[Any],
        total_records: int,
        weights: Dict[str, float],
    ) -> List[str]:
        suggestions: List[str] = []

        for dim, score in dimension_scores.items():
            if score >= 85:
                continue
            weight = weights.get(dim, 0.0)
            if dim == QualityDimension.COMPLETENESS.value:
                suggestions.append(
                    f"完整性得分仅 {score:.2f}，建议补齐必填字段并增加采集校验（权重 {weight:.2f}）。"
                )
            elif dim == QualityDimension.ACCURACY.value:
                suggestions.append(
                    f"准确性得分仅 {score:.2f}，建议增加值域校验和类型校验（权重 {weight:.2f}）。"
                )
            elif dim == QualityDimension.CONSISTENCY.value:
                suggestions.append(
                    f"一致性得分仅 {score:.2f}，建议补充跨字段逻辑规则和时序约束（权重 {weight:.2f}）。"
                )
            elif dim == QualityDimension.UNIQUENESS.value:
                suggestions.append(
                    f"唯一性得分仅 {score:.2f}，建议启用业务键去重流程（权重 {weight:.2f}）。"
                )
            elif dim == QualityDimension.VALIDITY.value:
                suggestions.append(
                    f"有效性得分仅 {score:.2f}，建议加强枚举、格式和合规性检查（权重 {weight:.2f}）。"
                )

        if anomalies:
            ratio = (len(anomalies) / max(total_records, 1)) * 100
            suggestions.append(
                f"检测到 {len(anomalies)} 条异常记录（约 {ratio:.2f}%），建议进入异常复核工作流。"
            )

        if violations:
            top_fields = Counter(item.field for item in violations).most_common(3)
            if top_fields:
                field_desc = ", ".join(f"{field}({count})" for field, count in top_fields)
                suggestions.append(f"高频问题字段：{field_desc}，建议优先治理。")

        if not suggestions:
            suggestions.append("数据质量表现稳定，建议保持现有规则并持续监控评分趋势。")

        return suggestions
