"""Validation config loader for product-key optimization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class ValidationRuntimeConfig:
    ip_limit_per_minute: int = 10
    key_limit_per_hour: int = 20
    user_limit_per_hour: int = 30
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    enable_ip_reputation: bool = True
    enable_audit_log: bool = True
    enable_data_masking: bool = True


_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "configs" / "validation_config.yaml"


def _dig(data: Dict[str, Any], *keys: str, default: Any) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def load_validation_runtime_config(config_path: str | None = None) -> ValidationRuntimeConfig:
    path = Path(config_path).expanduser().resolve() if config_path else _DEFAULT_PATH
    if not path.exists():
        return ValidationRuntimeConfig()
    if yaml is None:
        return ValidationRuntimeConfig()
    with path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}

    return ValidationRuntimeConfig(
        ip_limit_per_minute=int(_dig(payload, "product_key_validation", "rate_limit", "ip_limit_per_minute", default=10)),
        key_limit_per_hour=int(_dig(payload, "product_key_validation", "rate_limit", "key_limit_per_hour", default=20)),
        user_limit_per_hour=int(_dig(payload, "product_key_validation", "rate_limit", "user_limit_per_hour", default=30)),
        cache_enabled=bool(_dig(payload, "product_key_validation", "cache", "enabled", default=True)),
        cache_ttl_seconds=int(_dig(payload, "product_key_validation", "cache", "ttl_seconds", default=300)),
        enable_ip_reputation=bool(_dig(payload, "product_key_validation", "security", "enable_ip_reputation", default=True)),
        enable_audit_log=bool(_dig(payload, "product_key_validation", "security", "enable_audit_log", default=True)),
        enable_data_masking=bool(_dig(payload, "product_key_validation", "security", "enable_data_masking", default=True)),
    )
