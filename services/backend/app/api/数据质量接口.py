"""Data quality API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.data_quality_service import data_quality_service

router = APIRouter()


class RuleCreateRequest(BaseModel):
    rule_id: Optional[str] = Field(default=None, description="Rule ID, auto-generated when omitted")
    name: str = Field(..., min_length=1, max_length=128)
    dimension: Literal["completeness", "accuracy", "consistency", "uniqueness", "validity"]
    rule_type: Literal[
        "required",
        "range",
        "type",
        "unique",
        "regex",
        "enum",
        "expression",
        "temporal_continuity",
    ]
    field: str = Field(..., min_length=1, max_length=64)
    config: Dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="", max_length=500)
    enabled: bool = Field(default=True)
    priority: int = Field(default=100, ge=1, le=1000)


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    dimension: Optional[Literal["completeness", "accuracy", "consistency", "uniqueness", "validity"]] = None
    rule_type: Optional[
        Literal[
            "required",
            "range",
            "type",
            "unique",
            "regex",
            "enum",
            "expression",
            "temporal_continuity",
        ]
    ] = None
    field: Optional[str] = Field(default=None, min_length=1, max_length=64)
    config: Optional[Dict[str, Any]] = None
    description: Optional[str] = Field(default=None, max_length=500)
    enabled: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=1000)


class RuleToggleRequest(BaseModel):
    enabled: bool


class QualityEvaluateRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, max_length=128)
    records: List[Dict[str, Any]] = Field(..., min_length=1)
    value_field: str = Field(default="value")
    x_field: str = Field(default="x")
    y_field: str = Field(default="y")
    weights: Optional[Dict[str, float]] = None


class QualityEvaluateSummary(BaseModel):
    report_id: str
    dataset_id: str
    overall_score: float
    grade: str
    dimension_scores: Dict[str, float]
    total_records: int
    anomaly_count: int
    suggestion_count: int
    generated_at: str


@router.get("/data-quality/health")
async def quality_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "module": "data_quality",
        "preset_rule_count": len(data_quality_service.list_rules(enabled_only=False)),
    }


@router.get("/data-quality/rules")
async def list_quality_rules(enabled_only: bool = Query(default=False)) -> Dict[str, Any]:
    return {"rules": data_quality_service.list_rules(enabled_only=enabled_only)}


@router.post("/data-quality/rules")
async def create_quality_rule(payload: RuleCreateRequest) -> Dict[str, Any]:
    try:
        rule = data_quality_service.create_rule(payload.model_dump())
        return {"rule": rule}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/data-quality/rules/{rule_id}")
async def update_quality_rule(rule_id: str, payload: RuleUpdateRequest) -> Dict[str, Any]:
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    try:
        rule = data_quality_service.update_rule(rule_id, updates)
        return {"rule": rule}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/data-quality/rules/{rule_id}/enabled")
async def toggle_quality_rule(rule_id: str, payload: RuleToggleRequest) -> Dict[str, Any]:
    try:
        rule = data_quality_service.set_rule_enabled(rule_id, payload.enabled)
        return {"rule": rule}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/data-quality/rules/{rule_id}")
async def delete_quality_rule(rule_id: str) -> Dict[str, Any]:
    try:
        data_quality_service.delete_rule(rule_id)
        return {"message": "rule deleted"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/data-quality/evaluate", response_model=QualityEvaluateSummary)
async def evaluate_data_quality(payload: QualityEvaluateRequest) -> QualityEvaluateSummary:
    try:
        report = data_quality_service.evaluate(payload.model_dump())
        return QualityEvaluateSummary(
            report_id=report["report_id"],
            dataset_id=report["dataset_id"],
            overall_score=report["overall_score"],
            grade=report["grade"],
            dimension_scores=report["dimension_scores"],
            total_records=report["total_records"],
            anomaly_count=len(report.get("anomalies", [])),
            suggestion_count=len(report.get("suggestions", [])),
            generated_at=report["generated_at"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/data-quality/reports/{report_id}")
async def get_quality_report(report_id: str) -> Dict[str, Any]:
    report = data_quality_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.get("/data-quality/reports/{report_id}/anomalies")
async def get_quality_report_anomalies(report_id: str) -> Dict[str, Any]:
    try:
        anomalies = data_quality_service.get_report_anomalies(report_id)
        return {"report_id": report_id, "anomalies": anomalies, "count": len(anomalies)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/data-quality/reports/{report_id}/suggestions")
async def get_quality_report_suggestions(report_id: str) -> Dict[str, Any]:
    try:
        suggestions = data_quality_service.get_report_suggestions(report_id)
        return {"report_id": report_id, "suggestions": suggestions, "count": len(suggestions)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/data-quality/reports/{report_id}/export")
async def export_quality_report(
    report_id: str,
    fmt: Literal["json", "markdown", "html"] = Query(default="json"),
) -> Dict[str, Any]:
    try:
        return data_quality_service.export_report(report_id, fmt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/data-quality/history/{dataset_id}")
async def get_quality_history(dataset_id: str) -> Dict[str, Any]:
    history = data_quality_service.get_history(dataset_id)
    return {
        "dataset_id": dataset_id,
        "history": history,
        "count": len(history),
    }
