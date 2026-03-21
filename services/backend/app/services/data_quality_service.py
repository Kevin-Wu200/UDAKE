"""Data quality service orchestration."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..data_quality import (
    DataQualityAnomalyDetector,
    DataQualityEvaluator,
    DataQualityRuleEngine,
    QualityDimension,
    RuleDefinition,
    RuleType,
)


class DataQualityService:
    """Application service for quality evaluation and rule management."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.rule_engine = DataQualityRuleEngine()
        self.rule_engine.load_preset_rules(replace=True)
        self.evaluator = DataQualityEvaluator()
        self.anomaly_detector = DataQualityAnomalyDetector()

        self._reports: Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def evaluate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        dataset_id = str(payload.get("dataset_id") or "dataset")
        records = payload.get("records") or []
        if not isinstance(records, list):
            raise ValueError("records must be a list")

        for row in records:
            if not isinstance(row, dict):
                raise ValueError("each record must be an object")

        report = self.evaluator.evaluate(
            dataset_id=dataset_id,
            records=records,
            rule_engine=self.rule_engine,
            anomaly_detector=self.anomaly_detector,
            value_field=payload.get("value_field", "value"),
            x_field=payload.get("x_field", "x"),
            y_field=payload.get("y_field", "y"),
            weights=payload.get("weights"),
        )

        report_dict = report.to_dict()
        with self._lock:
            self._reports[report.report_id] = report_dict
            history_items = self._history.setdefault(dataset_id, [])
            history_items.append(
                {
                    "report_id": report.report_id,
                    "dataset_id": dataset_id,
                    "overall_score": report.overall_score,
                    "grade": report.grade,
                    "generated_at": report.generated_at.isoformat(),
                    "anomaly_count": len(report.anomalies),
                }
            )
            if len(history_items) > 100:
                self._history[dataset_id] = history_items[-100:]

        return report_dict

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        return self._reports.get(report_id)

    def get_report_anomalies(self, report_id: str) -> List[Dict[str, Any]]:
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"report '{report_id}' not found")
        return report.get("anomalies", [])

    def get_report_suggestions(self, report_id: str) -> List[str]:
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"report '{report_id}' not found")
        return report.get("suggestions", [])

    def get_history(self, dataset_id: str) -> List[Dict[str, Any]]:
        return list(self._history.get(dataset_id, []))

    def list_rules(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.rule_engine.list_rules(enabled_only=enabled_only)]

    def create_rule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        rule = RuleDefinition(
            rule_id=str(payload.get("rule_id") or f"custom_{uuid4().hex[:12]}"),
            name=str(payload["name"]),
            dimension=QualityDimension(str(payload["dimension"])),
            rule_type=RuleType(str(payload["rule_type"])),
            field=str(payload["field"]),
            config=dict(payload.get("config") or {}),
            description=str(payload.get("description") or ""),
            enabled=bool(payload.get("enabled", True)),
            priority=int(payload.get("priority", 100)),
        )
        created = self.rule_engine.create_rule(rule)
        return created.to_dict()

    def update_rule(self, rule_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        updated = self.rule_engine.update_rule(rule_id, **payload)
        return updated.to_dict()

    def delete_rule(self, rule_id: str) -> None:
        self.rule_engine.delete_rule(rule_id)

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> Dict[str, Any]:
        updated = self.rule_engine.set_rule_enabled(rule_id, enabled)
        return updated.to_dict()

    def export_report(self, report_id: str, fmt: str = "json") -> Dict[str, Any]:
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"report '{report_id}' not found")

        format_key = fmt.lower()
        if format_key == "json":
            return {"format": "json", "content": report}
        if format_key == "markdown":
            return {"format": "markdown", "content": self._to_markdown(report)}
        if format_key == "html":
            return {"format": "html", "content": self._to_html(report)}

        raise ValueError("unsupported format, expected one of: json, markdown, html")

    def _to_markdown(self, report: Dict[str, Any]) -> str:
        lines = [
            f"# Data Quality Report: {report['dataset_id']}",
            "",
            f"- Report ID: {report['report_id']}",
            f"- Generated At: {report['generated_at']}",
            f"- Overall Score: {report['overall_score']}",
            f"- Grade: {report['grade']}",
            "",
            "## Dimension Scores",
        ]

        for name, score in report.get("dimension_scores", {}).items():
            lines.append(f"- {name}: {score}")

        lines.append("")
        lines.append("## Suggestions")
        for item in report.get("suggestions", []):
            lines.append(f"- {item}")

        lines.append("")
        lines.append("## Anomalies")
        lines.append(f"- Count: {len(report.get('anomalies', []))}")

        return "\n".join(lines)

    def _to_html(self, report: Dict[str, Any]) -> str:
        dim_rows = "".join(
            f"<tr><td>{name}</td><td>{score}</td></tr>"
            for name, score in report.get("dimension_scores", {}).items()
        )
        suggestions = "".join(f"<li>{item}</li>" for item in report.get("suggestions", []))

        return (
            "<html><head><meta charset='utf-8'><title>Data Quality Report</title></head><body>"
            f"<h1>Data Quality Report - {report['dataset_id']}</h1>"
            f"<p><b>Report ID:</b> {report['report_id']}</p>"
            f"<p><b>Generated At:</b> {report['generated_at']}</p>"
            f"<p><b>Overall Score:</b> {report['overall_score']} ({report['grade']})</p>"
            "<h2>Dimension Scores</h2>"
            "<table border='1' cellpadding='4' cellspacing='0'><tr><th>Dimension</th><th>Score</th></tr>"
            f"{dim_rows}</table>"
            f"<h2>Anomaly Count</h2><p>{len(report.get('anomalies', []))}</p>"
            f"<h2>Suggestions</h2><ul>{suggestions}</ul>"
            "</body></html>"
        )


# shared singleton instance
_data_quality_service: Optional[DataQualityService] = None


def get_data_quality_service() -> DataQualityService:
    global _data_quality_service
    if _data_quality_service is None:
        _data_quality_service = DataQualityService()
    return _data_quality_service


data_quality_service = get_data_quality_service()
