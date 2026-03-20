"""Rule engine for data quality validation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .models import QualityDimension, RuleDefinition, RuleType, RuleViolation


_ALLOWED_EVAL_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "round": round,
}


class DataQualityRuleEngine:
    """Rule CRUD and execution engine."""

    def __init__(self) -> None:
        self._rules: Dict[str, RuleDefinition] = {}

    def list_rules(self, enabled_only: bool = False) -> List[RuleDefinition]:
        rules = sorted(self._rules.values(), key=lambda item: (item.priority, item.rule_id))
        if enabled_only:
            return [item for item in rules if item.enabled]
        return rules

    def get_rule(self, rule_id: str) -> Optional[RuleDefinition]:
        return self._rules.get(rule_id)

    def create_rule(self, rule: RuleDefinition) -> RuleDefinition:
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule '{rule.rule_id}' already exists")
        self._rules[rule.rule_id] = rule
        return rule

    def update_rule(self, rule_id: str, **updates: Any) -> RuleDefinition:
        rule = self._rules.get(rule_id)
        if not rule:
            raise KeyError(f"Rule '{rule_id}' not found")

        for key, value in updates.items():
            if value is None:
                continue
            if key == "dimension":
                value = QualityDimension(value)
            if key == "rule_type":
                value = RuleType(value)
            setattr(rule, key, value)

        rule.version += 1
        self._rules[rule_id] = rule
        return rule

    def delete_rule(self, rule_id: str) -> None:
        if rule_id not in self._rules:
            raise KeyError(f"Rule '{rule_id}' not found")
        del self._rules[rule_id]

    def set_rule_enabled(self, rule_id: str, enabled: bool) -> RuleDefinition:
        rule = self._rules.get(rule_id)
        if not rule:
            raise KeyError(f"Rule '{rule_id}' not found")
        if rule.enabled != enabled:
            rule.enabled = enabled
            rule.version += 1
        return rule

    def load_preset_rules(self, replace: bool = False) -> List[RuleDefinition]:
        if self._rules and not replace:
            return self.list_rules(enabled_only=False)

        if replace:
            self._rules.clear()

        for rule in default_preset_rules():
            self._rules[rule.rule_id] = rule
        return self.list_rules(enabled_only=False)

    def execute(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        violations: List[RuleViolation] = []
        rule_stats: Dict[str, Dict[str, Any]] = {}
        dimension_stats: Dict[str, Dict[str, int]] = {
            item.value: {"total": 0, "failed": 0} for item in QualityDimension
        }

        for rule in self.list_rules(enabled_only=True):
            if rule.rule_type == RuleType.UNIQUE:
                checked, failed, rule_violations = self._apply_unique_rule(rule, records)
            else:
                checked, failed, rule_violations = self._apply_standard_rule(rule, records)

            violations.extend(rule_violations)
            dimension_key = rule.dimension.value
            dimension_stats[dimension_key]["total"] += checked
            dimension_stats[dimension_key]["failed"] += failed
            rule_stats[rule.rule_id] = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "dimension": rule.dimension.value,
                "checked": checked,
                "failed": failed,
                "pass_rate": 1.0 if checked == 0 else (checked - failed) / checked,
                "version": rule.version,
                "enabled": rule.enabled,
            }

        return {
            "violations": violations,
            "rule_stats": rule_stats,
            "dimension_stats": dimension_stats,
            "enabled_rules": len(self.list_rules(enabled_only=True)),
        }

    def _apply_unique_rule(
        self, rule: RuleDefinition, records: List[Dict[str, Any]]
    ) -> tuple[int, int, List[RuleViolation]]:
        index_map: Dict[Any, List[int]] = {}
        for idx, row in enumerate(records):
            value = row.get(rule.field)
            if _is_missing(value):
                continue
            index_map.setdefault(value, []).append(idx)

        violations: List[RuleViolation] = []
        for value, indices in index_map.items():
            if len(indices) <= 1:
                continue
            for row_index in indices:
                violations.append(
                    RuleViolation(
                        rule_id=rule.rule_id,
                        rule_name=rule.name,
                        dimension=rule.dimension,
                        row_index=row_index,
                        field=rule.field,
                        value=value,
                        message=f"Duplicate value '{value}' for unique field '{rule.field}'",
                        severity=rule.config.get("severity", "high"),
                    )
                )

        checked = sum(len(indices) for indices in index_map.values())
        failed = len(violations)
        return checked, failed, violations

    def _apply_standard_rule(
        self, rule: RuleDefinition, records: List[Dict[str, Any]]
    ) -> tuple[int, int, List[RuleViolation]]:
        violations: List[RuleViolation] = []
        checked = 0

        for idx, row in enumerate(records):
            checked += 1
            valid, message = self._validate_cell(rule, row, idx, records)
            if valid:
                continue
            violations.append(
                RuleViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    dimension=rule.dimension,
                    row_index=idx,
                    field=rule.field,
                    value=row.get(rule.field),
                    message=message,
                    severity=rule.config.get("severity", "medium"),
                )
            )

        return checked, len(violations), violations

    def _validate_cell(
        self,
        rule: RuleDefinition,
        row: Dict[str, Any],
        row_index: int,
        records: List[Dict[str, Any]],
    ) -> tuple[bool, str]:
        value = row.get(rule.field)

        if rule.rule_type == RuleType.REQUIRED:
            if _is_missing(value):
                return False, f"Required field '{rule.field}' is missing"
            return True, ""

        if _is_missing(value):
            return True, ""

        if rule.rule_type == RuleType.RANGE:
            return _check_range(rule.field, value, rule.config)

        if rule.rule_type == RuleType.TYPE:
            return _check_type(rule.field, value, rule.config)

        if rule.rule_type == RuleType.REGEX:
            return _check_regex(rule.field, value, rule.config)

        if rule.rule_type == RuleType.ENUM:
            return _check_enum(rule.field, value, rule.config)

        if rule.rule_type == RuleType.EXPRESSION:
            return _check_expression(rule.field, row, rule.config)

        if rule.rule_type == RuleType.TEMPORAL_CONTINUITY:
            return _check_temporal_continuity(
                rule.field,
                value,
                rule.config,
                row_index,
                records,
            )

        return True, ""


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _check_range(field: str, value: Any, config: Dict[str, Any]) -> tuple[bool, str]:
    min_value = config.get("min")
    max_value = config.get("max")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False, f"Field '{field}' expects numeric value for range check"

    if min_value is not None and numeric < float(min_value):
        return False, f"Field '{field}' value {numeric} < min {min_value}"
    if max_value is not None and numeric > float(max_value):
        return False, f"Field '{field}' value {numeric} > max {max_value}"
    return True, ""


def _check_type(field: str, value: Any, config: Dict[str, Any]) -> tuple[bool, str]:
    expected = str(config.get("expected", "str")).lower()

    type_map = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
    }

    if expected == "number":
        if isinstance(value, bool):
            return False, f"Field '{field}' expects number, got bool"
        if isinstance(value, (int, float)):
            return True, ""
        return False, f"Field '{field}' expects number"

    expected_type = type_map.get(expected)
    if not expected_type:
        return False, f"Unsupported type '{expected}' in rule config"

    if not isinstance(value, expected_type):
        return False, f"Field '{field}' expects type '{expected}'"
    return True, ""


def _check_regex(field: str, value: Any, config: Dict[str, Any]) -> tuple[bool, str]:
    pattern = config.get("pattern")
    if not pattern:
        return False, f"Field '{field}' regex rule missing pattern"
    if re.fullmatch(str(pattern), str(value)):
        return True, ""
    return False, f"Field '{field}' value '{value}' does not match pattern"


def _check_enum(field: str, value: Any, config: Dict[str, Any]) -> tuple[bool, str]:
    allowed = config.get("allowed")
    if not isinstance(allowed, Iterable):
        return False, f"Field '{field}' enum rule missing allowed list"
    allowed_values = list(allowed)
    if value not in allowed_values:
        return False, f"Field '{field}' value '{value}' not in allowed set"
    return True, ""


def _check_expression(field: str, row: Dict[str, Any], config: Dict[str, Any]) -> tuple[bool, str]:
    expression = config.get("expression")
    if not expression:
        return False, f"Expression rule for '{field}' missing expression"

    local_env = {
        "row": row,
        "value": row.get(field),
        "is_missing": _is_missing,
    }
    try:
        result = bool(eval(expression, {"__builtins__": {}}, {**_ALLOWED_EVAL_FUNCTIONS, **local_env}))
    except Exception as exc:  # pragma: no cover - defensive path
        return False, f"Expression execution failed: {exc}"

    if result:
        return True, ""
    return False, f"Expression check failed for field '{field}'"


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _check_temporal_continuity(
    field: str,
    value: Any,
    config: Dict[str, Any],
    row_index: int,
    records: List[Dict[str, Any]],
) -> tuple[bool, str]:
    if row_index == 0:
        return True, ""

    current = _parse_datetime(value)
    previous = _parse_datetime(records[row_index - 1].get(field))
    if current is None or previous is None:
        return False, f"Field '{field}' has invalid datetime format"

    max_gap_seconds = int(config.get("max_gap_seconds", 86400))
    gap_seconds = (current - previous).total_seconds()
    if gap_seconds < 0:
        return False, f"Field '{field}' is not monotonic by time"
    if gap_seconds > max_gap_seconds:
        return False, f"Field '{field}' has time gap {gap_seconds:.0f}s > {max_gap_seconds}s"

    return True, ""


def default_preset_rules() -> List[RuleDefinition]:
    """Build 20+ preset rules for common geospatial sampling datasets."""

    presets: List[RuleDefinition] = [
        RuleDefinition("dq_required_id", "ID required", QualityDimension.COMPLETENESS, RuleType.REQUIRED, "id", priority=10),
        RuleDefinition("dq_required_x", "X required", QualityDimension.COMPLETENESS, RuleType.REQUIRED, "x", priority=10),
        RuleDefinition("dq_required_y", "Y required", QualityDimension.COMPLETENESS, RuleType.REQUIRED, "y", priority=10),
        RuleDefinition("dq_required_value", "Value required", QualityDimension.COMPLETENESS, RuleType.REQUIRED, "value", priority=10),
        RuleDefinition("dq_required_timestamp", "Timestamp required", QualityDimension.COMPLETENESS, RuleType.REQUIRED, "timestamp", priority=10),
        RuleDefinition("dq_type_x", "X number", QualityDimension.ACCURACY, RuleType.TYPE, "x", {"expected": "number"}, priority=20),
        RuleDefinition("dq_type_y", "Y number", QualityDimension.ACCURACY, RuleType.TYPE, "y", {"expected": "number"}, priority=20),
        RuleDefinition("dq_type_value", "Value number", QualityDimension.ACCURACY, RuleType.TYPE, "value", {"expected": "number"}, priority=20),
        RuleDefinition("dq_range_x", "X in lon range", QualityDimension.ACCURACY, RuleType.RANGE, "x", {"min": -180, "max": 180}, priority=30),
        RuleDefinition("dq_range_y", "Y in lat range", QualityDimension.ACCURACY, RuleType.RANGE, "y", {"min": -90, "max": 90}, priority=30),
        RuleDefinition("dq_range_value", "Value in safe range", QualityDimension.ACCURACY, RuleType.RANGE, "value", {"min": -1000000, "max": 1000000}, priority=30),
        RuleDefinition("dq_format_id", "ID format", QualityDimension.VALIDITY, RuleType.REGEX, "id", {"pattern": r"[A-Za-z0-9_-]{3,64}"}, priority=40),
        RuleDefinition("dq_enum_status", "Status allowed", QualityDimension.VALIDITY, RuleType.ENUM, "status", {"allowed": ["raw", "cleaned", "verified", "archived"]}, priority=40),
        RuleDefinition("dq_enum_quality_level", "Quality level allowed", QualityDimension.VALIDITY, RuleType.ENUM, "quality_level", {"allowed": ["high", "medium", "low"]}, priority=40),
        RuleDefinition("dq_enum_source", "Source allowed", QualityDimension.VALIDITY, RuleType.ENUM, "source", {"allowed": ["sensor", "manual", "import", "simulated"]}, priority=40),
        RuleDefinition("dq_unique_id", "ID unique", QualityDimension.UNIQUENESS, RuleType.UNIQUE, "id", priority=50),
        RuleDefinition("dq_unique_time_loc", "Timestamp unique per point", QualityDimension.UNIQUENESS, RuleType.EXPRESSION, "timestamp", {"expression": "not is_missing(row.get('x')) and not is_missing(row.get('y')) and not is_missing(value)"}, priority=50),
        RuleDefinition("dq_consistency_non_negative", "Non-negative value", QualityDimension.CONSISTENCY, RuleType.EXPRESSION, "value", {"expression": "is_missing(value) or value >= 0"}, priority=60),
        RuleDefinition("dq_consistency_status_quality", "Status vs quality consistency", QualityDimension.CONSISTENCY, RuleType.EXPRESSION, "status", {"expression": "row.get('status') != 'verified' or row.get('quality_level') in ('high', 'medium')"}, priority=60),
        RuleDefinition("dq_temporal_continuity", "Timestamp continuity", QualityDimension.CONSISTENCY, RuleType.TEMPORAL_CONTINUITY, "timestamp", {"max_gap_seconds": 604800}, priority=70),
        RuleDefinition("dq_validity_value_not_nan", "Value is not NaN", QualityDimension.VALIDITY, RuleType.EXPRESSION, "value", {"expression": "is_missing(value) or value == value"}, priority=80),
        RuleDefinition("dq_validity_category", "Category format", QualityDimension.VALIDITY, RuleType.REGEX, "category", {"pattern": r"[A-Za-z0-9_\- ]{1,32}"}, priority=80),
    ]
    return presets
