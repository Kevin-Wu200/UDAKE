"""API 版本管理：版本解析、兼容路由与废弃告警。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)

SUPPORTED_API_VERSIONS = ("1.0", "2.0")
DEFAULT_API_VERSION = "1.0"
CURRENT_API_VERSION = "2.0"
DEPRECATED_API_VERSIONS = {
    "1.0": {
        "sunset": "2026-12-31",
        "replacement": "/api/v2",
    }
}


@dataclass(frozen=True)
class VersionResolution:
    version: str
    rewritten_path: Optional[str]
    from_deprecated_path: bool


def _normalize_version(raw_version: Optional[str]) -> Optional[str]:
    if raw_version is None:
        return None
    value = str(raw_version).strip().lower()
    if not value:
        return None
    if value.startswith("v"):
        value = value[1:]
    if value == "1":
        value = "1.0"
    if value == "2":
        value = "2.0"
    return value


def _rewrite_versioned_path(path: str) -> tuple[Optional[str], Optional[str]]:
    if path == "/api/v1":
        return "1.0", "/api"
    if path.startswith("/api/v1/"):
        return "1.0", "/api" + path[len("/api/v1") :]
    if path == "/api/v2":
        return "2.0", "/api"
    if path.startswith("/api/v2/"):
        return "2.0", "/api" + path[len("/api/v2") :]
    return None, None


def _extract_version_from_path(path: str) -> Optional[str]:
    if not path.startswith("/api/v"):
        return None
    chunks = path.split("/")
    if len(chunks) < 3:
        return None
    return _normalize_version(chunks[2])


def _bad_request(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_api_version",
            "detail": detail,
            "supported_versions": list(SUPPORTED_API_VERSIONS),
            "current_version": CURRENT_API_VERSION,
        },
    )


def resolve_api_version(path: str, header_version: Optional[str]) -> VersionResolution:
    normalized_header_version = _normalize_version(header_version)
    if normalized_header_version and normalized_header_version not in SUPPORTED_API_VERSIONS:
        raise ValueError(f"请求头版本不受支持: {header_version}")

    path_version, rewritten_path = _rewrite_versioned_path(path)
    if path.startswith("/api/v") and path_version is None:
        invalid_path_version = _extract_version_from_path(path)
        raise ValueError(f"路径版本不受支持: {invalid_path_version or path}")

    if path_version and normalized_header_version and path_version != normalized_header_version:
        raise ValueError(
            f"路径版本({path_version})与请求头版本({normalized_header_version})不一致"
        )

    resolved_version = path_version or normalized_header_version or DEFAULT_API_VERSION
    if resolved_version not in SUPPORTED_API_VERSIONS:
        raise ValueError(f"版本不受支持: {resolved_version}")

    return VersionResolution(
        version=resolved_version,
        rewritten_path=rewritten_path,
        from_deprecated_path=bool(path_version and path_version in DEPRECATED_API_VERSIONS),
    )


async def api_versioning_middleware(request: Request, call_next):
    path = request.scope.get("path", request.url.path)
    if not path.startswith("/api"):
        return await call_next(request)

    raw_header_version = request.headers.get("X-API-Version")
    try:
        resolution = resolve_api_version(path=path, header_version=raw_header_version)
    except ValueError as exc:
        return _bad_request(str(exc))

    if resolution.rewritten_path:
        request.scope["path"] = resolution.rewritten_path

    request.state.api_version = resolution.version
    response = await call_next(request)

    response.headers["X-API-Version"] = resolution.version
    response.headers["X-API-Supported-Versions"] = ", ".join(SUPPORTED_API_VERSIONS)

    deprecated_meta = DEPRECATED_API_VERSIONS.get(resolution.version)
    if deprecated_meta:
        response.headers["X-API-Deprecated"] = "true"
        response.headers["X-API-Sunset"] = deprecated_meta["sunset"]
        response.headers["Link"] = (
            f'<{deprecated_meta["replacement"]}>; rel="successor-version"'
        )
        response.headers["Warning"] = (
            f'299 - "API v{resolution.version} is deprecated and '
            f'will be removed after {deprecated_meta["sunset"]}"'
        )
        # 仅在调用方显式使用废弃版本时记录告警，避免默认回退产生噪声日志。
        if raw_header_version is not None or resolution.from_deprecated_path:
            LOGGER.warning(
                "检测到废弃 API 版本调用: version=%s path=%s",
                resolution.version,
                path,
            )

    return response


router = APIRouter(prefix="/api/versioning", tags=["API版本管理"])


@router.get("/status")
async def version_status():
    return {
        "current_version": CURRENT_API_VERSION,
        "default_version": DEFAULT_API_VERSION,
        "supported_versions": list(SUPPORTED_API_VERSIONS),
        "deprecated_versions": DEPRECATED_API_VERSIONS,
        "generated_at": date.today().isoformat(),
    }
