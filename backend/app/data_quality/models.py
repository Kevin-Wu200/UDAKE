"""Data quality models and shared value objects."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class QualityDimension(str, Enum):
    """Supported quality dimensions."""

    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    CONSISTENCY = "consistency"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"


class RuleType(str, Enum):
    """Supported rule types."""

    REQUIRED = "required"
    RANGE = "range"
    TYPE = "type"
    UNIQUE = "unique"
    REGEX = "regex"
    ENUM = "enum"
    EXPRESSION = "expression"
    TEMPORAL_CONTINUITY = "temporal_continuity"


@dataclass
class RuleDefinition:
    """A quality rule definition."""

    rule_id: str
    name: str
    dimension: QualityDimension
    rule_type: RuleType
    field: str
    config: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True
    priority: int = 100
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["dimension"] = self.dimension.value
        payload["rule_type"] = self.rule_type.value
        return payload


@dataclass
class RuleViolation:
    """A single rule violation record."""

    rule_id: str
    rule_name: str
    dimension: QualityDimension
    row_index: int
    field: str
    value: Any
    message: str
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["dimension"] = self.dimension.value
        return payload


@dataclass
class AnomalyRecord:
    """A detected anomaly record."""

    row_index: int
    field: str
    value: Any
    methods: List[str]
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DimensionMetric:
    """Evaluation metric for one quality dimension."""

    dimension: QualityDimension
    score: float
    total_checks: int
    failed_checks: int
    pass_rate: float

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["dimension"] = self.dimension.value
        return payload


@dataclass
class QualityReport:
    """Output report of one data quality evaluation."""

    report_id: str
    dataset_id: str
    generated_at: datetime
    total_records: int
    overall_score: float
    grade: str
    dimension_scores: Dict[str, float]
    metrics: List[DimensionMetric]
    violations: List[RuleViolation]
    anomalies: List[AnomalyRecord]
    suggestions: List[str]
    execution_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "dataset_id": self.dataset_id,
            "generated_at": self.generated_at.isoformat(),
            "total_records": self.total_records,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "dimension_scores": self.dimension_scores,
            "metrics": [item.to_dict() for item in self.metrics],
            "violations": [item.to_dict() for item in self.violations],
            "anomalies": [item.to_dict() for item in self.anomalies],
            "suggestions": self.suggestions,
            "execution_ms": self.execution_ms,
        }
