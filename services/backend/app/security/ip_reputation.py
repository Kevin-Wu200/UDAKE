"""IP reputation tracking for product-key validation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class IPReputationDecision:
    allowed: bool
    score: int
    reason: str = ""


class IPReputationService:
    def __init__(self, cache_backend: Any, *, default_score: int = 60, blacklist_threshold: int = 15, whitelist_threshold: int = 90) -> None:
        self._cache = cache_backend
        self._default_score = max(0, min(100, int(default_score)))
        self._blacklist_threshold = max(0, int(blacklist_threshold))
        self._whitelist_threshold = min(100, max(0, int(whitelist_threshold)))
        self._ttl = 7 * 24 * 60 * 60
        self._ban_ttl = 60 * 60

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
