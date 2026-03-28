"""
移动端 GPS 同步接口
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..services.mobile_gps_service import mobile_gps_service


router = APIRouter(prefix="/api/mobile-gps", tags=["移动端GPS"])


class GPSSampleSyncRequest(BaseModel):
    client_id: str = Field(default="unknown_client")
    project_id: str = Field(default="default_mobile_project")
    strategy: Literal["client-wins", "server-wins", "latest-wins", "manual"] = Field(default="latest-wins")
    samples: List[Dict[str, Any]] = Field(default_factory=list)


class RollbackRequest(BaseModel):
    to_version: Optional[int] = None


@router.post("/sync/batch")
async def sync_batch(payload: GPSSampleSyncRequest) -> Dict[str, Any]:
    try:
        result = mobile_gps_service.upsert_samples(
            client_id=payload.client_id,
            samples=payload.samples,
            strategy=payload.strategy
        )
        return {
            "success": True,
            "project_id": payload.project_id,
            **result
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(exc)}") from exc


@router.get("/samples")
async def list_samples(
    project_id: Optional[str] = Query(default=None),
    since: Optional[int] = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=20000)
) -> Dict[str, Any]:
    rows = mobile_gps_service.get_samples(project_id=project_id, since=since, limit=limit)
    return {
        "success": True,
        "count": len(rows),
        "samples": rows
    }


@router.get("/summary")
async def summary(project_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    return {
        "success": True,
        **mobile_gps_service.get_summary(project_id=project_id)
    }


@router.get("/conflicts")
async def list_conflicts(project_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    rows = mobile_gps_service.list_conflicts(project_id=project_id)
    return {
        "success": True,
        "count": len(rows),
        "items": rows
    }


@router.post("/samples/{sample_id}/rollback")
async def rollback(sample_id: str, payload: RollbackRequest) -> Dict[str, Any]:
    try:
        sample = mobile_gps_service.rollback(sample_id, to_version=payload.to_version)
        return {
            "success": True,
            "sample": sample
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"回滚失败: {str(exc)}") from exc


@router.get("/export/{project_id}")
async def export_project(project_id: str, format: Literal["geojson", "csv"] = Query(default="geojson")):
    if format == "geojson":
        return mobile_gps_service.export_geojson(project_id)
    return PlainTextResponse(
        content=mobile_gps_service.export_csv(project_id),
        media_type="text/csv; charset=utf-8"
    )
