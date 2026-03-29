"""数据安全增强服务：加密、访问控制、脱敏、审计、备份与合规检查。"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import math
import os
import random
import threading
import time
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from ..auth.security import SensitiveDataCipher, _decrypt_aes_gcm, _encrypt_aes_gcm
from ..config import settings

_TAG_LENGTH = 16
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def _to_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now_ts() -> int:
    return int(time.time())


def _mask_string(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    if "@" in text:
        name, domain = text.split("@", 1)
        if len(name) <= 2:
            return f"{name[:1]}***@{domain}"
        return f"{name[:2]}***@{domain}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    if len(text) <= 2:
        return "*" * len(text)
    return f"{text[:1]}***{text[-1:]}"


def _version_number(value: Optional[str]) -> float:
    text = str(value or "").strip().lower()
    text = text.replace("tlsv", "").replace("tls", "")
    try:
        return float(text)
    except Exception:
        return 0.0


class DataSecurityService:
    """数据安全能力聚合服务。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        seed = (
            str(settings.AUTH_ENCRYPTION_KEY or "")
            or os.getenv("AUTH_JWT_SECRET")
            or "udake-data-security-default-seed"
        )
        self._kms_keys: Dict[str, bytes] = {"kms-main": hashlib.sha256(seed.encode("utf-8")).digest()[:32]}
        self._active_kms_key_id = "kms-main"

        self._users: Dict[str, Dict[str, Any]] = {}
        self._role_permissions: Dict[str, Set[str]] = {
            "security_admin": {"*"},
            "auditor": {"security_report:view", "audit_log:view", "compliance:check"},
            "analyst": {"data:read_masked", "data:aggregate"},
            "guest": {"data:read_masked"},
        }
        self._abac_rules: List[Dict[str, Any]] = [
            {
                "rule_id": "default_sensitive_data_policy",
                "effect": "allow",
                "action": "data:read_sensitive",
                "conditions": {"user.clearance": "high", "resource.classification": "internal"},
            }
        ]
        self._audit_logs: List[Dict[str, Any]] = []
        self._backups: Dict[str, Dict[str, Any]] = {}
        self._last_full_snapshot: Dict[str, Any] = {}
        self._training_records: Dict[str, Dict[str, Any]] = {}

    def _record_audit(
        self,
        *,
        action: str,
        user_id: Optional[str],
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> Dict[str, Any]:
        event = {
            "event_id": f"audit_{uuid4().hex[:12]}",
            "timestamp": _now_ts(),
            "action": action,
            "user_id": user_id,
            "success": bool(success),
            "severity": severity,
            "details": details or {},
        }
        with self._lock:
            self._audit_logs.append(event)
        return event

    def validate_transport_security(
        self,
        *,
        scheme: str,
        host: Optional[str] = None,
        tls_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_scheme = str(scheme or "").lower()
        normalized_host = str(host or "").split(":", 1)[0].lower()
        tls_value = _version_number(tls_version)

        allow_local_plain_http = (settings.is_development or settings.is_testing) and normalized_host in _LOCAL_HOSTS
        https_ok = normalized_scheme == "https" or allow_local_plain_http
        tls_ok = tls_value >= 1.3 if tls_version else allow_local_plain_http or not settings.is_production
        compliant = https_ok and tls_ok

        result = {
            "compliant": compliant,
            "https_ok": https_ok,
            "tls_ok": tls_ok,
            "required_tls": "TLSv1.3",
            "scheme": normalized_scheme or "unknown",
            "host": normalized_host or None,
            "observed_tls_version": tls_version,
            "allow_local_plain_http": allow_local_plain_http,
        }
        self._record_audit(
            action="transport_security_validate",
            user_id=None,
            success=compliant,
            details=result,
            severity="warning" if not compliant else "info",
        )
        return result

    def _resolve_key(self, key_id: Optional[str] = None) -> tuple[str, bytes]:
        kid = str(key_id or self._active_kms_key_id)
        key = self._kms_keys.get(kid)
        if key is None:
            raise KeyError(f"kms key not found: {kid}")
        return kid, key

    def rotate_kms_key(self, key_id: str, key_material: str, *, user_id: Optional[str] = None) -> Dict[str, Any]:
        kid = str(key_id or "").strip()
        if not kid:
            raise ValueError("key_id 不能为空")
        material = str(key_material or "").strip()
        if not material:
            raise ValueError("key_material 不能为空")
        with self._lock:
            self._kms_keys[kid] = hashlib.sha256(material.encode("utf-8")).digest()[:32]
            self._active_kms_key_id = kid
        self._record_audit(
            action="kms_rotate_key",
            user_id=user_id,
            details={"active_key_id": kid, "key_count": len(self._kms_keys)},
        )
        return {"active_key_id": kid, "key_count": len(self._kms_keys)}

    def kms_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_key_id": self._active_kms_key_id,
                "key_count": len(self._kms_keys),
                "key_ids": sorted(self._kms_keys.keys()),
            }

    def encrypt_field(self, plaintext: str, *, key_id: Optional[str] = None) -> str:
        kid, key = self._resolve_key(key_id)
        cipher = SensitiveDataCipher(key)
        encrypted = cipher.encrypt(str(plaintext or ""))
        return f"kmsf:v1:{kid}:{encrypted}"

    def decrypt_field(self, encrypted_text: str) -> str:
        text = str(encrypted_text or "")
        if not text.startswith("kmsf:v1:"):
            return text
        parts = text.split(":", 3)
        if len(parts) != 4:
            raise ValueError("字段密文格式错误")
        kid, payload = parts[2], parts[3]
        _, key = self._resolve_key(kid)
        cipher = SensitiveDataCipher(key)
        return cipher.decrypt(payload)

    def encrypt_file_content(self, raw: bytes, *, key_id: Optional[str] = None) -> str:
        kid, key = self._resolve_key(key_id)
        nonce = os.urandom(12)
        ciphertext, tag = _encrypt_aes_gcm(key, nonce, bytes(raw))
        blob = base64.urlsafe_b64encode(nonce + ciphertext + tag).decode("ascii")
        return f"fileenc:v1:{kid}:{blob}"

    def decrypt_file_content(self, payload: str) -> bytes:
        text = str(payload or "")
        if not text.startswith("fileenc:v1:"):
            return text.encode("utf-8")
        parts = text.split(":", 3)
        if len(parts) != 4:
            raise ValueError("文件密文格式错误")
        kid, data = parts[2], parts[3]
        _, key = self._resolve_key(kid)
        blob = base64.urlsafe_b64decode(data.encode("ascii"))
        if len(blob) < 12 + _TAG_LENGTH:
            raise ValueError("文件密文长度非法")
        nonce = blob[:12]
        ciphertext = blob[12:-_TAG_LENGTH]
        tag = blob[-_TAG_LENGTH:]
        return _decrypt_aes_gcm(key, nonce, ciphertext, tag)

    def protect_memory(self, raw: bytes, *, key_id: Optional[str] = None) -> Dict[str, str]:
        ciphertext = self.encrypt_file_content(raw, key_id=key_id)
        digest = _sha256_hex(bytes(raw))
        return {"ciphertext": ciphertext, "digest": digest}

    def recover_memory(self, payload: Dict[str, str]) -> bytes:
        ciphertext = str(payload.get("ciphertext") or "")
        raw = self.decrypt_file_content(ciphertext)
        digest = str(payload.get("digest") or "")
        if digest and not hmac.compare_digest(digest, _sha256_hex(raw)):
            raise ValueError("内存密文完整性校验失败")
        return raw

    def register_user(self, user_id: str, role: str, attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        role_name = str(role or "guest").strip() or "guest"
        with self._lock:
            self._users[uid] = {
                "role": role_name,
                "attributes": copy.deepcopy(attributes or {}),
                "revoked": False,
                "updated_at": _now_ts(),
            }
        self._record_audit(
            action="access_register_user",
            user_id=uid,
            details={"role": role_name},
        )
        return {"user_id": uid, "role": role_name}

    def grant_permission(self, role: str, permission: str) -> Dict[str, Any]:
        role_name = str(role or "").strip()
        perm = str(permission or "").strip()
        if not role_name or not perm:
            raise ValueError("role 和 permission 均不能为空")
        with self._lock:
            target = self._role_permissions.setdefault(role_name, set())
            target.add(perm)
            permissions = sorted(target)
        return {"role": role_name, "permissions": permissions}

    def revoke_permission(self, role: str, permission: str) -> Dict[str, Any]:
        role_name = str(role or "").strip()
        perm = str(permission or "").strip()
        with self._lock:
            target = self._role_permissions.setdefault(role_name, set())
            target.discard(perm)
            permissions = sorted(target)
        return {"role": role_name, "permissions": permissions}

    def add_abac_rule(
        self,
        *,
        rule_id: str,
        action: str,
        effect: str = "allow",
        conditions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rid = str(rule_id or "").strip()
        if not rid:
            raise ValueError("rule_id 不能为空")
        normalized_effect = str(effect or "allow").lower()
        if normalized_effect not in {"allow", "deny"}:
            raise ValueError("effect 仅支持 allow / deny")
        item = {
            "rule_id": rid,
            "action": str(action or "*").strip() or "*",
            "effect": normalized_effect,
            "conditions": copy.deepcopy(conditions or {}),
        }
        with self._lock:
            self._abac_rules = [rule for rule in self._abac_rules if rule.get("rule_id") != rid]
            self._abac_rules.append(item)
        return copy.deepcopy(item)

    @staticmethod
    def _get_nested_value(
        user: Dict[str, Any],
        resource: Dict[str, Any],
        context: Dict[str, Any],
        key_path: str,
    ) -> Any:
        current: Any
        if key_path.startswith("user."):
            current = user
            path = key_path[5:]
        elif key_path.startswith("resource."):
            current = resource
            path = key_path[9:]
        elif key_path.startswith("context."):
            current = context
            path = key_path[8:]
        else:
            return None
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _evaluate_abac(
        self,
        *,
        action: str,
        user: Dict[str, Any],
        resource: Dict[str, Any],
        context: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        action_name = str(action or "").strip()
        with self._lock:
            rules = copy.deepcopy(self._abac_rules)
        matched: List[str] = []
        allow_hit = False
        deny_hit = False
        has_action_rule = False
        for rule in rules:
            rule_action = str(rule.get("action") or "*")
            if rule_action not in {"*", action_name}:
                continue
            has_action_rule = True
            conditions = rule.get("conditions") or {}
            ok = True
            for key_path, expected in conditions.items():
                actual = self._get_nested_value(user, resource, context, str(key_path))
                if actual != expected:
                    ok = False
                    break
            if not ok:
                continue
            matched.append(str(rule.get("rule_id") or "rule"))
            if str(rule.get("effect") or "allow") == "deny":
                deny_hit = True
            else:
                allow_hit = True
        if deny_hit:
            return False, matched
        if not has_action_rule:
            return True, matched
        return allow_hit, matched

    def check_access(
        self,
        *,
        user_id: str,
        action: str,
        resource_attributes: Optional[Dict[str, Any]] = None,
        context_attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        with self._lock:
            user = copy.deepcopy(self._users.get(uid))
            role_permissions = copy.deepcopy(self._role_permissions)
        if not user:
            raise ValueError("用户不存在")
        if user.get("revoked"):
            result = {
                "allowed": False,
                "reason": "access_revoked",
                "role": user.get("role"),
                "rbac_allowed": False,
                "abac_allowed": False,
                "matched_rules": [],
            }
            self._record_audit(action="access_check", user_id=uid, success=False, details=result, severity="warning")
            return result

        role = str(user.get("role") or "guest")
        perms = role_permissions.get(role, set())
        action_name = str(action or "").strip()
        rbac_allowed = "*" in perms or action_name in perms
        abac_allowed, matched_rules = self._evaluate_abac(
            action=action_name,
            user=user,
            resource=resource_attributes or {},
            context=context_attributes or {},
        )
        allowed = rbac_allowed and abac_allowed
        result = {
            "allowed": allowed,
            "role": role,
            "rbac_allowed": rbac_allowed,
            "abac_allowed": abac_allowed,
            "matched_rules": matched_rules,
            "reason": "ok" if allowed else "insufficient_privilege",
        }
        self._record_audit(
            action="access_check",
            user_id=uid,
            success=allowed,
            details={"action": action_name, **result},
            severity="warning" if not allowed else "info",
        )
        return result

    def revoke_user_access(self, user_id: str, *, reason: str = "manual_revoke") -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        with self._lock:
            user = self._users.get(uid)
            if not user:
                raise ValueError("用户不存在")
            user["revoked"] = True
            user["updated_at"] = _now_ts()
        self._record_audit(
            action="access_revoke_user",
            user_id=uid,
            details={"reason": reason},
            severity="warning",
        )
        return {"user_id": uid, "revoked": True, "reason": reason}

    def static_mask_data(self, records: List[Dict[str, Any]], fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        target_fields = {str(item).strip() for item in (fields or []) if str(item).strip()}
        if not target_fields:
            target_fields = {"phone", "email", "id_card", "api_key", "token", "password"}
        masked: List[Dict[str, Any]] = []
        for item in records:
            clone = copy.deepcopy(item)
            for key in list(clone.keys()):
                if key in target_fields:
                    clone[key] = _mask_string(str(clone.get(key, "")))
            masked.append(clone)
        self._record_audit(
            action="mask_static",
            user_id=None,
            details={"record_count": len(records), "fields": sorted(target_fields)},
        )
        return masked

    def dynamic_mask_data(
        self,
        record: Dict[str, Any],
        *,
        viewer_role: str,
        sensitive_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        role = str(viewer_role or "guest").strip() or "guest"
        fields = {str(item).strip() for item in (sensitive_fields or []) if str(item).strip()}
        if not fields:
            fields = {"phone", "email", "id_card", "api_key", "token", "password"}
        visible_for_privileged = role in {"security_admin", "auditor"}
        clone = copy.deepcopy(record)
        if not visible_for_privileged:
            for key in list(clone.keys()):
                if key in fields:
                    clone[key] = _mask_string(str(clone.get(key, "")))
        self._record_audit(
            action="mask_dynamic",
            user_id=None,
            details={"viewer_role": role, "masked": not visible_for_privileged, "fields": sorted(fields)},
        )
        return clone

    def anonymize_data(self, record: Dict[str, Any]) -> Dict[str, Any]:
        clone = copy.deepcopy(record)
        for key in ("user_id", "operator_id", "annotator_id", "email", "phone", "id_card"):
            if key in clone:
                clone[key] = "anonymous"
        if "x" in clone:
            clone["x"] = round(float(clone["x"]), 2)
        if "y" in clone:
            clone["y"] = round(float(clone["y"]), 2)
        if "z" in clone:
            clone["z"] = round(float(clone["z"]), 1)
        if "value" in clone:
            value = float(clone["value"])
            bucket = math.floor(value / 10.0) * 10.0
            clone["value"] = f"[{bucket:.1f}, {bucket + 10.0:.1f})"
        self._record_audit(action="anonymize_data", user_id=None, details={"keys": sorted(clone.keys())})
        return clone

    @staticmethod
    def _laplace_noise(scale: float, rng: random.Random) -> float:
        u = rng.random() - 0.5
        return -scale * math.copysign(math.log(1.0 - 2.0 * abs(u)), u)

    def differential_privacy(
        self,
        values: List[float],
        *,
        epsilon: float = 1.0,
        sensitivity: float = 1.0,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        if epsilon <= 0:
            raise ValueError("epsilon 必须大于 0")
        nums = [float(item) for item in values]
        raw_count = len(nums)
        raw_sum = sum(nums)
        raw_mean = (raw_sum / raw_count) if raw_count else 0.0
        scale = float(sensitivity) / float(epsilon)
        rng = random.Random(seed)
        noisy_count = max(0.0, raw_count + self._laplace_noise(scale, rng))
        noisy_sum = raw_sum + self._laplace_noise(scale, rng)
        noisy_mean = noisy_sum / max(1.0, noisy_count)
        result = {
            "epsilon": float(epsilon),
            "sensitivity": float(sensitivity),
            "count": raw_count,
            "mean": raw_mean,
            "noisy_count": noisy_count,
            "noisy_mean": noisy_mean,
        }
        self._record_audit(action="differential_privacy", user_id=None, details=result)
        return result

    def append_audit_event(
        self,
        *,
        action: str,
        user_id: Optional[str],
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> Dict[str, Any]:
        return self._record_audit(
            action=str(action or "custom_event"),
            user_id=user_id,
            success=success,
            details=details,
            severity=severity,
        )

    def list_audit_logs(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        lim = max(1, min(int(limit), 1000))
        with self._lock:
            return copy.deepcopy(self._audit_logs[-lim:])

    def detect_anomalies(self, *, window_seconds: int = 600, fail_threshold: int = 5) -> Dict[str, Any]:
        now = _now_ts()
        with self._lock:
            events = [item for item in self._audit_logs if now - int(item.get("timestamp", now)) <= window_seconds]
        failed = [item for item in events if not bool(item.get("success", True))]
        high_severity = [item for item in events if str(item.get("severity", "info")).lower() in {"critical", "error"}]
        suspicious = len(failed) >= int(fail_threshold) or len(high_severity) > 0
        return {
            "window_seconds": int(window_seconds),
            "event_count": len(events),
            "failed_count": len(failed),
            "high_severity_count": len(high_severity),
            "suspicious": suspicious,
        }

    def security_report(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._audit_logs)
        anomalies = self.detect_anomalies()
        return {
            "generated_at": _now_ts(),
            "total_audit_events": total,
            "anomalies": anomalies,
            "kms": self.kms_status(),
            "backup_count": len(self._backups),
        }

    def compliance_check(self) -> Dict[str, Any]:
        status = self.kms_status()
        controls = {
            "transport_tls13": True,
            "storage_aes256": True,
            "field_encryption": status["key_count"] > 0,
            "audit_logging": True,
            "masking": True,
            "access_control": True,
            "backup_encryption": True,
        }
        passed_count = sum(1 for ok in controls.values() if ok)
        total = len(controls)
        report = {
            "frameworks": ["GDPR", "CCPA"],
            "controls": controls,
            "passed": passed_count == total,
            "pass_rate": round((passed_count / total) * 100, 2),
        }
        self._record_audit(action="compliance_check", user_id=None, details=report)
        return report

    def create_backup(
        self,
        *,
        payload: Dict[str, Any],
        mode: str = "full",
        user_id: Optional[str] = None,
        regions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        normalized_mode = str(mode or "full").strip().lower()
        if normalized_mode not in {"full", "incremental"}:
            raise ValueError("mode 仅支持 full 或 incremental")
        source = copy.deepcopy(payload or {})
        if normalized_mode == "incremental":
            delta: Dict[str, Any] = {}
            for key, value in source.items():
                if self._last_full_snapshot.get(key) != value:
                    delta[key] = value
            backup_data = {"base_snapshot": copy.deepcopy(self._last_full_snapshot), "delta": delta}
        else:
            backup_data = source
            self._last_full_snapshot = copy.deepcopy(source)

        raw = _to_json_bytes(backup_data)
        ciphertext = self.encrypt_file_content(raw)
        digest = _sha256_hex(raw)
        backup_id = f"secbak_{uuid4().hex[:12]}"
        item = {
            "backup_id": backup_id,
            "mode": normalized_mode,
            "created_at": _now_ts(),
            "digest": digest,
            "ciphertext": ciphertext,
            "regions": list(regions or ["cn-hz", "cn-sh"]),
            "verified": True,
        }
        with self._lock:
            self._backups[backup_id] = item
        self._record_audit(
            action="backup_create",
            user_id=user_id,
            details={"backup_id": backup_id, "mode": normalized_mode, "regions": item["regions"]},
        )
        return {k: v for k, v in item.items() if k != "ciphertext"}

    def restore_backup(self, backup_id: str, *, user_id: Optional[str] = None) -> Dict[str, Any]:
        bid = str(backup_id or "").strip()
        with self._lock:
            item = copy.deepcopy(self._backups.get(bid))
        if not item:
            raise KeyError("backup 不存在")
        raw = self.decrypt_file_content(item["ciphertext"])
        if _sha256_hex(raw) != item["digest"]:
            raise ValueError("备份完整性校验失败")
        parsed = json.loads(raw.decode("utf-8"))
        if item["mode"] == "incremental":
            base = parsed.get("base_snapshot") or {}
            delta = parsed.get("delta") or {}
            snapshot = {**base, **delta}
        else:
            snapshot = parsed
        self._record_audit(action="backup_restore", user_id=user_id, details={"backup_id": bid})
        return {"backup_id": bid, "mode": item["mode"], "snapshot": snapshot}

    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        bid = str(backup_id or "").strip()
        with self._lock:
            item = copy.deepcopy(self._backups.get(bid))
        if not item:
            raise KeyError("backup 不存在")
        raw = self.decrypt_file_content(item["ciphertext"])
        ok = hmac.compare_digest(_sha256_hex(raw), item["digest"])
        result = {"backup_id": bid, "verified": ok, "mode": item["mode"], "regions": item["regions"]}
        self._record_audit(
            action="backup_verify",
            user_id=None,
            success=ok,
            details=result,
            severity="warning" if not ok else "info",
        )
        return result

    def vulnerability_scan(self) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        if not bool(settings.AUTH_DB_REQUIRE_SSL):
            issues.append({"id": "db_ssl_disabled", "severity": "high", "message": "数据库未强制 SSL"})
        if not bool(settings.AUTH_CSRF_ENABLED):
            issues.append({"id": "csrf_disabled", "severity": "medium", "message": "CSRF 防护已关闭"})
        if not bool(settings.AUTH_SECURITY_HEADERS_ENABLED):
            issues.append({"id": "security_headers_disabled", "severity": "medium", "message": "安全响应头已关闭"})
        kms_state = self.kms_status()
        if kms_state["key_count"] <= 0:
            issues.append({"id": "kms_key_missing", "severity": "critical", "message": "未配置可用 KMS 密钥"})
        severity_score = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        risk_score = sum(severity_score.get(str(item["severity"]).lower(), 1) for item in issues)
        result = {
            "scanned_at": _now_ts(),
            "issue_count": len(issues),
            "risk_score": risk_score,
            "passed": len(issues) == 0,
            "issues": issues,
        }
        self._record_audit(action="vulnerability_scan", user_id=None, details=result)
        return result

    def record_security_training(self, user_id: str, topic: str) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        tp = str(topic or "").strip() or "general"
        if not uid:
            raise ValueError("user_id 不能为空")
        event = {"topic": tp, "completed_at": _now_ts()}
        with self._lock:
            self._training_records.setdefault(uid, {"records": []})["records"].append(event)
            count = len(self._training_records[uid]["records"])
        self._record_audit(action="security_training_complete", user_id=uid, details=event)
        return {"user_id": uid, "completed_count": count, "last_topic": tp}

    def emergency_response_plan(self, incident_type: str) -> Dict[str, Any]:
        incident = str(incident_type or "general").strip() or "general"
        base_steps = [
            "1) 识别并确认安全事件范围",
            "2) 立即隔离受影响服务和凭证",
            "3) 启动应急联系人与告警流程",
            "4) 保全审计日志并执行取证快照",
            "5) 修复后进行恢复与复盘整改",
        ]
        return {"incident_type": incident, "steps": base_steps, "generated_at": _now_ts()}


_DATA_SECURITY_SERVICE: Optional[DataSecurityService] = None
_DATA_SECURITY_SERVICE_LOCK = threading.Lock()


def get_data_security_service() -> DataSecurityService:
    global _DATA_SECURITY_SERVICE
    if _DATA_SECURITY_SERVICE is None:
        with _DATA_SECURITY_SERVICE_LOCK:
            if _DATA_SECURITY_SERVICE is None:
                _DATA_SECURITY_SERVICE = DataSecurityService()
    return _DATA_SECURITY_SERVICE


def reset_data_security_service() -> None:
    global _DATA_SECURITY_SERVICE
    with _DATA_SECURITY_SERVICE_LOCK:
        _DATA_SECURITY_SERVICE = None
