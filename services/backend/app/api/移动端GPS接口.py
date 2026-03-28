"""
移动端 GPS 同步接口
"""

from __future__ import annotations

import base64
import gzip
import json
import zlib
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
    message_id: Optional[str] = None
    compression: Optional[Literal["gzip", "deflate", "brotli", "zstd"]] = None
    encoding: Optional[Literal["base64"]] = None
    compressed_payload: Optional[str] = None


class RollbackRequest(BaseModel):
    to_version: Optional[int] = None


@router.post("/sync/batch")
async def sync_batch(payload: GPSSampleSyncRequest) -> Dict[str, Any]:
    try:
        decoded_payload = _decode_compressed_payload(payload)
        client_id = decoded_payload.get("client_id") or payload.client_id
        project_id = decoded_payload.get("project_id") or payload.project_id
        strategy = decoded_payload.get("strategy") or payload.strategy
        message_id = decoded_payload.get("message_id") or payload.message_id
        samples = decoded_payload.get("samples") if "samples" in decoded_payload else payload.samples

        result = mobile_gps_service.upsert_samples(
            client_id=client_id,
            samples=samples or [],
            strategy=strategy,
            message_id=message_id
        )
        return {
            "success": True,
            "project_id": project_id,
            **result
        }
    except HTTPException:
        raise
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


def _decode_compressed_payload(payload: GPSSampleSyncRequest) -> Dict[str, Any]:
    if not payload.compressed_payload:
        return {}

    if payload.encoding != "base64":
        raise HTTPException(status_code=400, detail="仅支持 base64 编码的压缩数据")

    compressed = base64.b64decode(payload.compressed_payload.encode("ascii"))
    compression = payload.compression or "gzip"

    if compression == "gzip":
        raw = gzip.decompress(compressed)
    elif compression == "deflate":
        raw = zlib.decompress(compressed)
    elif compression in {"brotli", "zstd"}:
        raise HTTPException(status_code=400, detail=f"当前服务暂不支持 {compression} 解压")
    else:
        raise HTTPException(status_code=400, detail=f"未知压缩算法: {compression}")

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="压缩负载不是合法 JSON") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="压缩负载必须是 JSON 对象")
    return parsed
