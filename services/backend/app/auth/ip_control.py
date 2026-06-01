"""IP whitelist/blacklist and auto-ban logic for auth workflows.

支持 Write-through 持久化：所有封禁操作同步写入数据库，启动时从数据库预加载活跃规则至缓存。
"""

from __future__ import annotations

import ipaddress
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from .cache import AuthCacheManager

logger = logging.getLogger(__name__)


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
        db_session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.cache = cache
        self.whitelist = {item.strip() for item in whitelist if item and item.strip()}
        self.blacklist = {item.strip() for item in blacklist if item and item.strip()}
        self.auto_ban_threshold = max(1, int(auto_ban_threshold))
        self.auto_ban_window_seconds = max(60, int(auto_ban_window_seconds))
        self.auto_ban_seconds = max(60, int(auto_ban_seconds))
        self._db_session_factory = db_session_factory
        self._preloaded = False

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
            blacklist_data = self.cache.get(self._blacklist_key(ip_text))
            if blacklist_data is None:
                # 缓存失效，尝试从数据库回填
                if self._try_refill_from_db(ip_text):
                    return IPCheckResult(allowed=False, reason="blacklist", blacklisted=True)
            return IPCheckResult(allowed=False, reason="blacklist", blacklisted=True)
        return IPCheckResult(allowed=True, reason="allowed")

    def _try_refill_from_db(self, ip_address: str) -> bool:
        """缓存失效时从数据库回填黑名单信息。"""
        if self._db_session_factory is None:
            return False
        try:
            db = self._db_session_factory()
            try:
                from ..auth_db.models import IPRule

                now_utc = datetime.now(timezone.utc)
                rule = (
                    db.query(IPRule)
                    .filter(
                        IPRule.ip_or_cidr == ip_address,
                        IPRule.rule_type == "blacklist",
                        IPRule.is_active,
                    )
                    .filter(
                        (IPRule.expires_at.is_(None)) | (IPRule.expires_at > now_utc)
                    )
                    .first()
                )
                if rule:
                    ttl = self.auto_ban_seconds
                    if rule.expires_at:
                        remaining = int((rule.expires_at - now_utc).total_seconds())
                        if remaining > 0:
                            ttl = remaining
                    self.cache.set(
                        self._blacklist_key(ip_address),
                        {"reason": rule.reason or "db_refill", "banned_at": int(time.time()), "ip": ip_address, "db_id": rule.id},
                        ttl=ttl,
                    )
                    return True
            finally:
                db.close()
        except Exception as exc:
            logger.warning("数据库回填黑名单缓存失败 ip=%s: %s", ip_address, exc)
        return False

    def preload_active_rules_from_db(self) -> None:
        """启动时从数据库预加载所有活跃规则至缓存。"""
        if self._db_session_factory is None:
            return
        if self._preloaded:
            return
        try:
            db = self._db_session_factory()
            try:
                from ..auth_db.models import IPRule

                now_utc = datetime.now(timezone.utc)
                active_rules = (
                    db.query(IPRule)
                    .filter(IPRule.is_active)
                    .filter(
                        (IPRule.expires_at.is_(None)) | (IPRule.expires_at > now_utc)
                    )
                    .all()
                )
                loaded_count = 0
                for rule in active_rules:
                    if rule.rule_type == "blacklist":
                        self.blacklist.add(rule.ip_or_cidr)
                        if "/" not in rule.ip_or_cidr:
                            ttl = self.auto_ban_seconds
                            if rule.expires_at:
                                remaining = int((rule.expires_at - now_utc).total_seconds())
                                if remaining > 0:
                                    ttl = remaining
                            self.cache.set(
                                self._blacklist_key(rule.ip_or_cidr),
                                {
                                    "reason": rule.reason or "db_preload",
                                    "banned_at": int(rule.created_at.timestamp()) if rule.created_at else int(time.time()),
                                    "ip": rule.ip_or_cidr,
                                    "db_id": rule.id,
                                },
                                ttl=ttl,
                            )
                            loaded_count += 1
                    elif rule.rule_type == "whitelist":
                        self.whitelist.add(rule.ip_or_cidr)
                        loaded_count += 1
                self._preloaded = True
                logger.info("从数据库预加载 %d 条活跃 IP 规则", loaded_count)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("从数据库预加载 IP 规则失败: %s", exc)

    def ban_ip(
        self,
        ip_address: Optional[str],
        *,
        seconds: Optional[int] = None,
        reason: str = "manual",
        persist_to_db: bool = True,
    ) -> Optional[int]:
        """封禁 IP，可选同步持久化到数据库。返回数据库记录 ID（如果持久化成功）。"""
        ip_text = self._normalize_ip(ip_address)
        if not ip_text or self.is_whitelisted(ip_text):
            return None
        ttl = max(60, int(seconds or self.auto_ban_seconds))
        self.cache.set(
            self._blacklist_key(ip_text),
            {"reason": reason, "banned_at": int(time.time()), "ip": ip_text},
            ttl=ttl,
        )

        db_id: Optional[int] = None
        if persist_to_db and self._db_session_factory is not None:
            try:
                db = self._db_session_factory()
                try:
                    from ..auth_db.models import IPRule

                    expires_at_value = None
                    if ttl > 0:
                        expires_at_value = datetime.now(timezone.utc).replace(microsecond=0)
                        expires_at_value = expires_at_value.replace(second=expires_at_value.second + ttl)
                    rule = IPRule(
                        ip_or_cidr=ip_text,
                        rule_type="blacklist",
                        reason=reason,
                        is_active=True,
                        expires_at=expires_at_value,
                    )
                    db.add(rule)
                    db.commit()
                    db.refresh(rule)
                    db_id = rule.id
                finally:
                    db.close()
            except Exception as exc:
                logger.warning("持久化封禁规则到数据库失败 ip=%s: %s", ip_text, exc)
        return db_id

    def unban_ip(self, ip_address: Optional[str], *, remove_from_db: bool = True) -> None:
        """解封 IP，同步从缓存和数据库移除。"""
        ip_text = self._normalize_ip(ip_address)
        if not ip_text:
            return
        self.blacklist.discard(ip_text)
        self.cache.delete(self._blacklist_key(ip_text))

        if remove_from_db and self._db_session_factory is not None:
            try:
                db = self._db_session_factory()
                try:
                    from ..auth_db.models import IPRule

                    db.query(IPRule).filter(
                        IPRule.ip_or_cidr == ip_text,
                        IPRule.rule_type == "blacklist",
                        IPRule.is_active,
                    ).update({"is_active": False})
                    db.commit()
                finally:
                    db.close()
            except Exception as exc:
                logger.warning("从数据库移除封禁规则失败 ip=%s: %s", ip_text, exc)

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

