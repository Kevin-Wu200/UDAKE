"""数据安全增强 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..services.数据安全服务 import get_data_security_service

router = APIRouter(prefix="/security")


def _ok(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _extract_client_scheme(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    if forwarded:
        return forwarded
    return request.url.scheme


def _extract_client_host(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip().lower()
    return host


class TransportValidateRequest(BaseModel):
    scheme: Optional[str] = Field(default=None, description="可选，默认自动读取请求协议")
    host: Optional[str] = Field(default=None, description="可选，默认自动读取请求 Host")
    tls_version: Optional[str] = Field(default=None, description="例如 TLSv1.3")


class EncryptFieldRequest(BaseModel):
    plaintext: str = Field(..., max_length=4096)
    key_id: Optional[str] = Field(default=None, max_length=64)


class DecryptFieldRequest(BaseModel):
    ciphertext: str = Field(..., max_length=8192)


class KMSRotateRequest(BaseModel):
    key_id: str = Field(..., max_length=64)
    key_material: str = Field(..., min_length=8, max_length=256)
    user_id: Optional[str] = Field(default=None, max_length=64)


class RegisterUserAccessRequest(BaseModel):
    user_id: str = Field(..., max_length=64)
    role: str = Field(..., max_length=64)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GrantPermissionRequest(BaseModel):
    role: str = Field(..., max_length=64)
    permission: str = Field(..., max_length=128)


class ABACRuleRequest(BaseModel):
    rule_id: str = Field(..., max_length=64)
    action: str = Field(..., max_length=128)
    effect: str = Field(default="allow", max_length=16)
    conditions: Dict[str, Any] = Field(default_factory=dict)


class AccessCheckRequest(BaseModel):
    user_id: str = Field(..., max_length=64)
    action: str = Field(..., max_length=128)
    resource_attributes: Dict[str, Any] = Field(default_factory=dict)
    context_attributes: Dict[str, Any] = Field(default_factory=dict)


class RevokeUserRequest(BaseModel):
    reason: str = Field(default="manual_revoke", max_length=128)


class StaticMaskRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    fields: List[str] = Field(default_factory=list)


class DynamicMaskRequest(BaseModel):
    record: Dict[str, Any] = Field(default_factory=dict)
    viewer_role: str = Field(..., max_length=64)
    sensitive_fields: List[str] = Field(default_factory=list)


class AnonymizeRequest(BaseModel):
    record: Dict[str, Any] = Field(default_factory=dict)


class DifferentialPrivacyRequest(BaseModel):
    values: List[float] = Field(default_factory=list)
    epsilon: float = Field(default=1.0, gt=0)
    sensitivity: float = Field(default=1.0, gt=0)
    seed: Optional[int] = Field(default=None)


class AppendAuditRequest(BaseModel):
    action: str = Field(..., max_length=128)
    user_id: Optional[str] = Field(default=None, max_length=64)
    success: bool = Field(default=True)
    details: Dict[str, Any] = Field(default_factory=dict)
    severity: str = Field(default="info", max_length=32)


class BackupCreateRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    mode: str = Field(default="full", max_length=16)
    user_id: Optional[str] = Field(default=None, max_length=64)
    regions: List[str] = Field(default_factory=list)


class TrainingRequest(BaseModel):
    user_id: str = Field(..., max_length=64)
    topic: str = Field(default="general", max_length=64)


@router.post("/transport/validate")
def validate_transport(payload: TransportValidateRequest, request: Request):
    service = get_data_security_service()
    scheme = payload.scheme or _extract_client_scheme(request)
    host = payload.host or _extract_client_host(request)
    result = service.validate_transport_security(
        scheme=scheme,
        host=host,
        tls_version=payload.tls_version or request.headers.get("x-tls-version"),
    )
    return _ok("传输安全校验完成", result)


@router.get("/kms/status")
def kms_status():
    service = get_data_security_service()
    return _ok("KMS 状态获取成功", service.kms_status())


@router.post("/kms/rotate")
def rotate_kms(payload: KMSRotateRequest):
    service = get_data_security_service()
    try:
        result = service.rotate_kms_key(payload.key_id, payload.key_material, user_id=payload.user_id)
        return _ok("KMS 密钥轮换成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/encrypt/field")
def encrypt_field(payload: EncryptFieldRequest):
    service = get_data_security_service()
    try:
        result = service.encrypt_field(payload.plaintext, key_id=payload.key_id)
        return _ok("字段加密成功", {"ciphertext": result})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/decrypt/field")
def decrypt_field(payload: DecryptFieldRequest):
    service = get_data_security_service()
    try:
        result = service.decrypt_field(payload.ciphertext)
        return _ok("字段解密成功", {"plaintext": result})
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/access/users")
def register_user_access(payload: RegisterUserAccessRequest):
    service = get_data_security_service()
    try:
        result = service.register_user(payload.user_id, payload.role, payload.attributes)
        return _ok("访问用户注册成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/access/permissions/grant")
def grant_permission(payload: GrantPermissionRequest):
    service = get_data_security_service()
    try:
        result = service.grant_permission(payload.role, payload.permission)
        return _ok("权限授予成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/access/permissions/revoke")
def revoke_permission(payload: GrantPermissionRequest):
    service = get_data_security_service()
    result = service.revoke_permission(payload.role, payload.permission)
    return _ok("权限回收成功", result)


@router.post("/access/abac/rules")
def add_abac_rule(payload: ABACRuleRequest):
    service = get_data_security_service()
    try:
        result = service.add_abac_rule(
            rule_id=payload.rule_id,
            action=payload.action,
            effect=payload.effect,
            conditions=payload.conditions,
        )
        return _ok("ABAC 规则添加成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/access/check")
def check_access(payload: AccessCheckRequest):
    service = get_data_security_service()
    try:
        result = service.check_access(
            user_id=payload.user_id,
            action=payload.action,
            resource_attributes=payload.resource_attributes,
            context_attributes=payload.context_attributes,
        )
        return _ok("访问控制判定完成", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/access/users/{user_id}/revoke")
def revoke_user_access(user_id: str, payload: RevokeUserRequest):
    service = get_data_security_service()
    try:
        result = service.revoke_user_access(user_id, reason=payload.reason)
        return _ok("用户权限已回收", result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/mask/static")
def mask_static(payload: StaticMaskRequest):
    service = get_data_security_service()
    result = service.static_mask_data(payload.records, payload.fields)
    return _ok("静态脱敏完成", {"items": result, "count": len(result)})


@router.post("/mask/dynamic")
def mask_dynamic(payload: DynamicMaskRequest):
    service = get_data_security_service()
    result = service.dynamic_mask_data(
        payload.record,
        viewer_role=payload.viewer_role,
        sensitive_fields=payload.sensitive_fields,
    )
    return _ok("动态脱敏完成", {"item": result})


@router.post("/mask/anonymize")
def anonymize(payload: AnonymizeRequest):
    service = get_data_security_service()
    result = service.anonymize_data(payload.record)
    return _ok("匿名化处理完成", {"item": result})


@router.post("/privacy/differential")
def differential_privacy(payload: DifferentialPrivacyRequest):
    service = get_data_security_service()
    try:
        result = service.differential_privacy(
            payload.values,
            epsilon=payload.epsilon,
            sensitivity=payload.sensitivity,
            seed=payload.seed,
        )
        return _ok("差分隐私计算完成", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/audit/events")
def append_audit(payload: AppendAuditRequest):
    service = get_data_security_service()
    result = service.append_audit_event(
        action=payload.action,
        user_id=payload.user_id,
        success=payload.success,
        details=payload.details,
        severity=payload.severity,
    )
    return _ok("审计事件记录成功", result)


@router.get("/audit/logs")
def audit_logs(limit: int = Query(default=100, ge=1, le=1000)):
    service = get_data_security_service()
    items = service.list_audit_logs(limit=limit)
    return _ok("审计日志查询成功", {"items": items, "count": len(items)})


@router.get("/audit/report")
def audit_report():
    service = get_data_security_service()
    return _ok("安全审计报告生成成功", service.security_report())


@router.get("/compliance/check")
def compliance_check():
    service = get_data_security_service()
    return _ok("合规性检查完成", service.compliance_check())


@router.post("/backup")
def create_backup(payload: BackupCreateRequest):
    service = get_data_security_service()
    try:
        result = service.create_backup(
            payload=payload.payload,
            mode=payload.mode,
            user_id=payload.user_id,
            regions=payload.regions,
        )
        return _ok("安全备份创建成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/backup/{backup_id}/restore")
def restore_backup(backup_id: str, user_id: Optional[str] = Query(default=None, max_length=64)):
    service = get_data_security_service()
    try:
        result = service.restore_backup(backup_id, user_id=user_id)
        return _ok("备份恢复成功", result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/backup/{backup_id}/verify")
def verify_backup(backup_id: str):
    service = get_data_security_service()
    try:
        result = service.verify_backup(backup_id)
        return _ok("备份验证完成", result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/testing/vulnerability-scan")
def vulnerability_scan():
    service = get_data_security_service()
    return _ok("漏洞扫描完成", service.vulnerability_scan())


@router.post("/testing/training")
def record_training(payload: TrainingRequest):
    service = get_data_security_service()
    try:
        result = service.record_security_training(payload.user_id, payload.topic)
        return _ok("安全培训记录成功", result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/testing/emergency-plan")
def emergency_plan(incident_type: str = Query(default="general", max_length=64)):
    service = get_data_security_service()
    return _ok("应急响应方案生成成功", service.emergency_response_plan(incident_type))
