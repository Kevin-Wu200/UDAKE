"""
移动端 GPS 同步接口
"""

from __future__ import annotations

import base64
import gzip
import json
import zlib
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .common import raise_api_error
from ..services.mobile_gps_service import mobile_gps_service

try:
    import brotli  # type: ignore
except Exception:  # pragma: no cover - 可选依赖
    brotli = None  # type: ignore

try:
    import zstandard as zstd  # type: ignore
except Exception:  # pragma: no cover - 可选依赖
    zstd = None  # type: ignore

try:
    import lz4.frame as lz4_frame  # type: ignore
except Exception:  # pragma: no cover - 可选依赖
    lz4_frame = None  # type: ignore


router = APIRouter(prefix="/api/mobile-gps", tags=["移动端GPS"])


class GPSSampleSyncRequest(BaseModel):
    client_id: str = Field(default="unknown_client", max_length=120)
    project_id: str = Field(default="default_mobile_project", max_length=120)
    strategy: Literal["client-wins", "server-wins", "latest-wins", "manual"] = Field(default="latest-wins")
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    message_id: Optional[str] = Field(default=None, max_length=120)
    compression: Optional[Literal["gzip", "deflate", "brotli", "zstd", "lz4"]] = None
    encoding: Optional[Literal["base64"]] = None
    compressed_payload: Optional[str] = None

    batch_size: int = Field(default=1000, ge=1, le=5000)
    enable_adaptive_batch: bool = Field(default=False)
    network_rtt_ms: Optional[int] = Field(default=None, ge=0, le=60_000)
    network_bandwidth_kbps: Optional[int] = Field(default=None, ge=1, le=10_000_000)
    enable_diff_sync: bool = Field(default=False)
    diff_base_fingerprint: Optional[str] = Field(default=None, max_length=128)
    rate_limit_kbps: Optional[int] = Field(default=None, ge=1, le=1_000_000)


class RollbackRequest(BaseModel):
    to_version: Optional[int] = None
    user_id: str = Field(default="system", max_length=80)
    verification_token: str = Field(default="", max_length=160)


class SensitiveOperationTokenRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    action: Literal["rollback", "restore_backup"] = Field(...)
    ttl_seconds: int = Field(default=300, ge=60, le=3600)


class BackupCreateRequest(BaseModel):
    mode: Literal["full", "incremental"] = Field(default="full")
    user_id: str = Field(default="system", max_length=80)


class BackupRestoreRequest(BaseModel):
    user_id: str = Field(default="system", max_length=80)
    verification_token: str = Field(default="", max_length=160)


@router.post("/sync/batch")
async def sync_batch(payload: GPSSampleSyncRequest) -> Dict[str, Any]:
    try:
        decoded_payload = _decode_compressed_payload(payload)
        client_id = str(decoded_payload.get("client_id") or payload.client_id)
        project_id = str(decoded_payload.get("project_id") or payload.project_id)
        strategy = decoded_payload.get("strategy") or payload.strategy
        message_id = decoded_payload.get("message_id") or payload.message_id
        samples = decoded_payload.get("samples") if "samples" in decoded_payload else payload.samples

        limiter = mobile_gps_service.check_request_rate_limit(client_id, action="sync_batch", limit=180, window_seconds=60)
        if not bool(limiter.get("allowed")):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请在 {int(limiter['retry_after_seconds'])} 秒后重试",
            )

        result = mobile_gps_service.upsert_samples(
            client_id=client_id,
            samples=samples or [],
            strategy=strategy,
            message_id=message_id,
            batch_size=int(decoded_payload.get("batch_size") or payload.batch_size),
            adaptive_batch=bool(decoded_payload.get("enable_adaptive_batch", payload.enable_adaptive_batch)),
            network_rtt_ms=decoded_payload.get("network_rtt_ms", payload.network_rtt_ms),
            network_bandwidth_kbps=decoded_payload.get("network_bandwidth_kbps", payload.network_bandwidth_kbps),
            enable_diff_sync=bool(decoded_payload.get("enable_diff_sync", payload.enable_diff_sync)),
            diff_base_fingerprint=decoded_payload.get("diff_base_fingerprint", payload.diff_base_fingerprint),
            rate_limit_kbps=decoded_payload.get("rate_limit_kbps", payload.rate_limit_kbps),
        )
        return {
            "success": True,
            "project_id": project_id,
            "rate_limit": limiter,
            **result,
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="同步失败")


@router.post("/sync/security/verification-token")
async def issue_verification_token(payload: SensitiveOperationTokenRequest) -> Dict[str, Any]:
    try:
        result = mobile_gps_service.issue_sensitive_operation_token(
            user_id=payload.user_id,
            action=payload.action,
            ttl_seconds=payload.ttl_seconds,
        )
        return {"success": True, "user_id": payload.user_id, "action": payload.action, **result}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="签发验证令牌失败")


@router.get("/sync/security/audit/integrity")
async def verify_audit_integrity() -> Dict[str, Any]:
    result = mobile_gps_service.verify_audit_integrity()
    return {"success": True, **result}


@router.get("/sync/security/audit/logs")
async def list_audit_logs(limit: int = Query(default=100, ge=1, le=2000)) -> Dict[str, Any]:
    rows = mobile_gps_service.list_audit_logs(limit=limit)
    return {"success": True, "count": len(rows), "items": rows}


@router.post("/sync/backup")
async def create_sync_backup(payload: BackupCreateRequest) -> Dict[str, Any]:
    try:
        backup = mobile_gps_service.create_backup(mode=payload.mode, user_id=payload.user_id)
        return {"success": True, "backup": backup}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="创建备份失败")


@router.get("/sync/backup/{backup_id}/verify")
async def verify_sync_backup(backup_id: str) -> Dict[str, Any]:
    try:
        result = mobile_gps_service.verify_backup(backup_id)
        return {"success": True, **result}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="校验备份失败")


@router.post("/sync/backup/{backup_id}/restore")
async def restore_sync_backup(backup_id: str, payload: BackupRestoreRequest) -> Dict[str, Any]:
    try:
        if not mobile_gps_service.verify_sensitive_operation_token(
            token=payload.verification_token,
            user_id=payload.user_id,
            action="restore_backup",
        ):
            raise PermissionError("二次验证失败或验证令牌已过期")
        result = mobile_gps_service.restore_backup(backup_id=backup_id, user_id=payload.user_id)
        return {"success": True, **result}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="恢复备份失败")


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
        if not mobile_gps_service.verify_sensitive_operation_token(
            token=payload.verification_token,
            user_id=payload.user_id,
            action="rollback",
        ):
            raise PermissionError("二次验证失败或验证令牌已过期")
        sample = mobile_gps_service.rollback(sample_id, to_version=payload.to_version)
        return {
            "success": True,
            "sample": sample
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="回滚失败")


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

    try:
        compressed = base64.b64decode(payload.compressed_payload.encode("ascii"))
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail="base64 解码失败") from exc

    compression = payload.compression or "gzip"
    if compression == "gzip":
        raw = gzip.decompress(compressed)
    elif compression == "deflate":
        raw = zlib.decompress(compressed)
    elif compression == "brotli":
        if brotli is None:
            raise HTTPException(status_code=400, detail="当前环境未安装 brotli 依赖")
        raw = brotli.decompress(compressed)
    elif compression == "zstd":
        if zstd is None:
            raise HTTPException(status_code=400, detail="当前环境未安装 zstd 依赖")
        raw = zstd.ZstdDecompressor().decompress(compressed)
    elif compression == "lz4":
        if lz4_frame is None:
            raise HTTPException(status_code=400, detail="当前环境未安装 lz4 依赖")
        raw = lz4_frame.decompress(compressed)
    else:
        raise HTTPException(status_code=400, detail=f"未知压缩算法: {compression}")

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="压缩负载不是合法 JSON") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="压缩负载必须是 JSON 对象")
    return parsed
