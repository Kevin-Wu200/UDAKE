"""
APK 下载接口
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter()
APK_MEDIA_TYPE = "application/vnd.android.package-archive"


def _get_apk_root() -> Path:
    return Path(settings.ANDROID_APK_DIR).resolve()


def _ensure_apk_root_exists() -> Path:
    apk_root = _get_apk_root()
    if not apk_root.exists() or not apk_root.is_dir():
        raise HTTPException(status_code=404, detail=f"APK 目录不存在: {apk_root}")
    return apk_root


def _apk_files() -> List[Path]:
    apk_root = _ensure_apk_root_exists()
    files = [p for p in apk_root.glob("*.apk") if p.is_file()]
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files


def _safe_resolve(filename: str) -> Path:
    apk_root = _ensure_apk_root_exists()
    candidate = (apk_root / filename).resolve()
    try:
        candidate.relative_to(apk_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法文件路径") from exc

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="APK 文件不存在")

    if candidate.suffix.lower() != ".apk":
        raise HTTPException(status_code=400, detail="仅允许下载 APK 文件")

    return candidate


def _version_payload(apk_file: Path) -> Dict[str, object]:
    stat = apk_file.stat()
    return {
        "version_id": apk_file.stem,
        "filename": apk_file.name,
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "download_url": f"/android_downloads/{apk_file.name}",
    }


def _latest_apk() -> Path:
    files = _apk_files()
    if not files:
        raise HTTPException(status_code=404, detail="暂无可下载的 APK 文件")

    preferred = _get_apk_root() / "app-release.apk"
    if preferred.exists() and preferred.is_file():
        return preferred
    return files[0]


@router.get("/download-apk")
async def download_latest_apk():
    """下载最新 APK。"""
    latest = _latest_apk()
    return FileResponse(path=str(latest), filename=latest.name, media_type=APK_MEDIA_TYPE)


@router.get("/versions")
async def list_apk_versions():
    """返回可下载 APK 版本列表。"""
    files = _apk_files()
    if not files:
        return {"latest": None, "versions": []}

    versions = [_version_payload(item) for item in files]
    latest = _version_payload(_latest_apk())
    return {"latest": latest, "versions": versions}


@router.get("/version/{version_id}")
async def get_apk_version(version_id: str):
    """根据版本 ID 获取 APK 元信息。"""
    normalized = version_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="version_id 不能为空")

    for apk_file in _apk_files():
        if normalized in {apk_file.stem, apk_file.name}:
            safe_file = _safe_resolve(apk_file.name)
            return _version_payload(safe_file)

    # 兼容传入 app-release-v1.0 但文件名为 app-release-v1.0.apk
    if not normalized.endswith(".apk"):
        fallback_name = f"{normalized}.apk"
        safe_file = _safe_resolve(fallback_name)
        return _version_payload(safe_file)

    raise HTTPException(status_code=404, detail=f"未找到版本: {version_id}")
