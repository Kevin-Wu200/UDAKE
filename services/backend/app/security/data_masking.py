"""Data masking helpers for product key validation security."""

from __future__ import annotations


def mask_product_key(product_key: str, *, visible_prefix: int = 3, visible_suffix: int = 4) -> str:
    text = str(product_key or "").strip().upper()
    if not text:
        return "***"
    compact = text.replace("-", "")
    if len(compact) <= visible_prefix + visible_suffix:
        return "*" * max(3, len(compact))
    middle = "*" * (len(compact) - visible_prefix - visible_suffix)
    return f"{compact[:visible_prefix]}{middle}{compact[-visible_suffix:]}"


def mask_ip(ip_address: str | None) -> str:
    if not ip_address:
        return "unknown"
    text = ip_address.strip()
    if ":" in text:
        parts = text.split(":")
        if len(parts) <= 2:
            return "****"
        return ":".join(parts[:2] + ["****"])
    parts = text.split(".")
    if len(parts) != 4:
        return "***.***.***.***"
    return f"{parts[0]}.{parts[1]}.***.***"
