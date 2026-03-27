"""IP whitelist/blacklist and auto-ban logic for auth workflows."""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from .cache import AuthCacheManager


@dataclass(frozen=True)
class IPCheckResult:
    allowed: bool
    reason: str = "allowed"
    whitelisted: bool = False
    blacklisted: bool = False


class IPAccessController:
    def __init__(
        self,
        cache: AuthCacheManager,
        *,
        whitelist: Iterable[str] = (),
        blacklist: Iterable[str] = (),
        auto_ban_threshold: int = 10,
        auto_ban_window_seconds: int = 3600,
        auto_ban_seconds: int = 1800,
    ) -> None:
        self.cache = cache
        self.whitelist = {item.strip() for item in whitelist if item and item.strip()}
        self.blacklist = {item.strip() for item in blacklist if item and item.strip()}
        self.auto_ban_threshold = max(1, int(auto_ban_threshold))
        self.auto_ban_window_seconds = max(60, int(auto_ban_window_seconds))
        self.auto_ban_seconds = max(60, int(auto_ban_seconds))

    @staticmethod
    def _normalize_ip(ip_address: Optional[str]) -> str:
        return str(ip_address or "").strip()

    @staticmethod
    def _match_ip_rule(ip_address: str, rule: str) -> bool:
        try:
            if "/" in rule:
                return ipaddress.ip_address(ip_address) in ipaddress.ip_network(rule, strict=False)
            return ipaddress.ip_address(ip_address) == ipaddress.ip_address(rule)
        except ValueError:
            return ip_address == rule

    def is_whitelisted(self, ip_address: Optional[str]) -> bool:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text:
            return False
        return any(self._match_ip_rule(ip_text, rule) for rule in self.whitelist)

    def _blacklist_key(self, ip_address: str) -> str:
        return f"auth:ip:blacklist:{ip_address}"

    def _failed_key(self, ip_address: str) -> str:
        return f"auth:ip:failed:{ip_address}"

    def is_blacklisted(self, ip_address: Optional[str]) -> bool:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text:
            return False
        if any(self._match_ip_rule(ip_text, rule) for rule in self.blacklist):
            return True
        return self.cache.exists(self._blacklist_key(ip_text))

    def check(self, ip_address: Optional[str]) -> IPCheckResult:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text:
            return IPCheckResult(allowed=True, reason="ip_missing")
        if self.is_whitelisted(ip_text):
            return IPCheckResult(allowed=True, reason="whitelist", whitelisted=True)
        if self.is_blacklisted(ip_text):
            return IPCheckResult(allowed=False, reason="blacklist", blacklisted=True)
        return IPCheckResult(allowed=True, reason="allowed")

    def ban_ip(self, ip_address: Optional[str], *, seconds: Optional[int] = None, reason: str = "manual") -> None:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text or self.is_whitelisted(ip_text):
            return
        ttl = max(60, int(seconds or self.auto_ban_seconds))
        self.cache.set(
            self._blacklist_key(ip_text),
            {"reason": reason, "banned_at": int(time.time()), "ip": ip_text},
            ttl=ttl,
        )

    def clear_failed_attempts(self, ip_address: Optional[str]) -> None:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text:
            return
        self.cache.delete(self._failed_key(ip_text))

    def record_failed_attempt(self, ip_address: Optional[str]) -> bool:
        ip_text = self._normalize_ip(ip_address)
        if not ip_text or self.is_whitelisted(ip_text):
            return False
        key = self._failed_key(ip_text)
        payload = self.cache.get(key) or {"count": 0}
        count = int(payload.get("count", 0)) + 1
        self.cache.set(key, {"count": count, "updated_at": int(time.time())}, ttl=self.auto_ban_window_seconds)
        if count >= self.auto_ban_threshold:
            self.ban_ip(ip_text, seconds=self.auto_ban_seconds, reason="brute_force")
            self.cache.delete(key)
            return True
        return False

