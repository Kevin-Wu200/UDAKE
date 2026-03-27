"""Input sanitization and validation helpers for auth endpoints."""

from __future__ import annotations

import html
import re
from typing import Any

SCRIPT_TAG_RE = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", flags=re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
JS_PROTOCOL_RE = re.compile(r"javascript\s*:", flags=re.IGNORECASE)
EVENT_HANDLER_RE = re.compile(r"\bon\w+\s*=", flags=re.IGNORECASE)
SUSPICIOUS_SQL_RE = re.compile(
    r"(?:\bunion\b\s+\bselect\b|\bdrop\b\s+\btable\b|\binsert\b\s+\binto\b|\bdelete\b\s+\bfrom\b|--|/\*)",
    flags=re.IGNORECASE,
)


def sanitize_text(value: str, *, max_len: int = 2048) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        raise ValueError(f"输入长度超过限制({max_len})")
    text = SCRIPT_TAG_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    text = JS_PROTOCOL_RE.sub("", text)
    text = EVENT_HANDLER_RE.sub("", text)
    return html.escape(text, quote=True)


def contains_suspicious_sql(value: str) -> bool:
    return bool(SUSPICIOUS_SQL_RE.search(str(value or "")))


def ensure_safe_text(value: str, *, max_len: int = 2048, reject_sql: bool = False) -> str:
    cleaned = sanitize_text(value, max_len=max_len)
    if reject_sql and contains_suspicious_sql(cleaned):
        raise ValueError("输入包含非法字符")
    return cleaned


def sanitize_payload(value: Any, *, max_len: int = 2048) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, max_len=max_len)
    if isinstance(value, list):
        return [sanitize_payload(item, max_len=max_len) for item in value]
    if isinstance(value, dict):
        return {str(k): sanitize_payload(v, max_len=max_len) for k, v in value.items()}
    return value

