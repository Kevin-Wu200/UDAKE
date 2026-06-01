"""IP reputation tracking for product-key validation.

支持异步持久化：得分跨越阈值时同步写入数据库，支持定期批量同步。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class IPReputationDecision:
    allowed: bool
    score: int
    reason: str = ""


class IPReputationService:
    _SYNC_THRESHOLD_STEP = 10  # 信誉分每变化10分触发一次数据库同步

    def __init__(
        self,
        cache_backend: Any,
        *,
        default_score: int = 60,
        blacklist_threshold: int = 15,
        whitelist_threshold: int = 90,
        db_session_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._cache = cache_backend
        self._default_score = max(0, min(100, int(default_score)))
        self._blacklist_threshold = max(0, int(blacklist_threshold))
        self._whitelist_threshold = min(100, max(0, int(whitelist_threshold)))
        self._ttl = 7 * 24 * 60 * 60
        self._ban_ttl = 60 * 60
        self._db_session_factory = db_session_factory
        self._last_synced_scores: Dict[str, int] = {}  # 记录上次同步时的得分
        self._dirty: Dict[str, bool] = {}  # 标记需要同步的 IP
        self._lock = threading.Lock()

    @staticmethod
    def _profile_key(ip_address: str) -> str:
        return f"ip_reputation:profile:{ip_address}"

    @staticmethod
    def _blacklist_key(ip_address: str) -> str:
        return f"ip_reputation:blacklist:{ip_address}"

    @staticmethod
    def _whitelist_key(ip_address: str) -> str:
        return f"ip_reputation:whitelist:{ip_address}"

    def _load_profile(self, ip_address: str) -> Dict[str, Any]:
        payload = self._cache.get(self._profile_key(ip_address))
        if isinstance(payload, dict):
            payload.setdefault("score", self._default_score)
            return payload
        return {
            "score": self._default_score,
            "success_count": 0,
            "failed_count": 0,
            "rate_limited_count": 0,
            "updated_at": int(time.time()),
        }

    def _save_profile(self, ip_address: str, profile: Dict[str, Any]) -> None:
        profile["score"] = max(0, min(100, int(profile.get("score", self._default_score))))
        profile["updated_at"] = int(time.time())
        self._cache.set(self._profile_key(ip_address), profile, ttl=self._ttl)
        score = int(profile["score"])
        if score <= self._blacklist_threshold:
            self._cache.set(self._blacklist_key(ip_address), {"score": score}, ttl=self._ban_ttl)
        elif score >= self._whitelist_threshold:
            self._cache.set(self._whitelist_key(ip_address), {"score": score}, ttl=self._ttl)

        # 检查是否需要异步同步到数据库
        self._mark_dirty_if_threshold_crossed(ip_address, score)

    def _mark_dirty_if_threshold_crossed(self, ip_address: str, score: int) -> None:
        """得分跨越阈值台阶时标记为需要同步到数据库。"""
        with self._lock:
            last_synced = self._last_synced_scores.get(ip_address)
            if last_synced is None:
                # 首次，同步
                self._dirty[ip_address] = True
                self._last_synced_scores[ip_address] = score
            elif abs(score - last_synced) >= self._SYNC_THRESHOLD_STEP:
                self._dirty[ip_address] = True
                self._last_synced_scores[ip_address] = score

    def _sync_profile_to_db(self, ip_address: str) -> None:
        """将单个 IP 的信誉度 Profile 同步到数据库。"""
        if self._db_session_factory is None:
            return
        try:
            profile = self._load_profile(ip_address)
            db = self._db_session_factory()
            try:
                from ..auth_db.models import IPReputation

                record = (
                    db.query(IPReputation)
                    .filter(IPReputation.ip_address == ip_address)
                    .one_or_none()
                )
                now_utc = datetime.now(timezone.utc)
                if record:
                    record.score = int(profile.get("score", self._default_score))
                    record.success_count = int(profile.get("success_count", 0))
                    record.failed_count = int(profile.get("failed_count", 0))
                    record.rate_limited_count = int(profile.get("rate_limited_count", 0))
                else:
                    record = IPReputation(
                        ip_address=ip_address,
                        score=int(profile.get("score", self._default_score)),
                        success_count=int(profile.get("success_count", 0)),
                        failed_count=int(profile.get("failed_count", 0)),
                        rate_limited_count=int(profile.get("rate_limited_count", 0)),
                    )
                    db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("同步 IP 信誉度到数据库失败 ip=%s: %s", ip_address, exc)

    def flush_dirty_to_db(self) -> int:
        """将所有标记为脏的 IP 信誉度同步到数据库。返回同步数量。"""
        with self._lock:
            dirty_ips = [ip for ip, dirty in self._dirty.items() if dirty]
            self._dirty.clear()

        count = 0
        for ip_addr in dirty_ips:
            self._sync_profile_to_db(ip_addr)
            count += 1
        if count > 0:
            logger.info("批量同步 %d 个 IP 信誉度到数据库", count)
        return count

    def check(self, ip_address: str) -> IPReputationDecision:
        if self._cache.get(self._whitelist_key(ip_address)):
            profile = self._load_profile(ip_address)
            return IPReputationDecision(allowed=True, score=int(profile.get("score", self._default_score)), reason="whitelisted")
        if self._cache.get(self._blacklist_key(ip_address)):
            profile = self._load_profile(ip_address)
            return IPReputationDecision(allowed=False, score=int(profile.get("score", self._default_score)), reason="blacklisted")
        profile = self._load_profile(ip_address)
        score = int(profile.get("score", self._default_score))
        return IPReputationDecision(allowed=score > self._blacklist_threshold, score=score)

    def record_success(self, ip_address: str) -> int:
        profile = self._load_profile(ip_address)
        profile["success_count"] = int(profile.get("success_count", 0)) + 1
        profile["score"] = int(profile.get("score", self._default_score)) + 2
        self._save_profile(ip_address, profile)
        return int(profile["score"])

    def record_failed(self, ip_address: str) -> int:
        profile = self._load_profile(ip_address)
        profile["failed_count"] = int(profile.get("failed_count", 0)) + 1
        profile["score"] = int(profile.get("score", self._default_score)) - 4
        self._save_profile(ip_address, profile)
        return int(profile["score"])

    def record_rate_limited(self, ip_address: str) -> int:
        profile = self._load_profile(ip_address)
        profile["rate_limited_count"] = int(profile.get("rate_limited_count", 0)) + 1
        profile["score"] = int(profile.get("score", self._default_score)) - 8
        self._save_profile(ip_address, profile)
        return int(profile["score"])
