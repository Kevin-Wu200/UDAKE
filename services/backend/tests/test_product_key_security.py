"""Security tests for product key generation."""

from __future__ import annotations

import math

from app.auth.product_key_service import ProductKeyRegistry


def test_key_predictability_uniqueness_and_distribution():
    registry = ProductKeyRegistry()
    keys = []
    for _ in range(200):
        key, _ = registry.generate_enterprise_key(
            company_name="测试企业",
            company_id=123,
            key_type="enterprise_standard",
        )
        keys.append(key)

    assert len(set(keys)) == 200

    char_freq = {}
    total = 0
    for key in keys:
        for ch in key.replace("-", ""):
            char_freq[ch] = char_freq.get(ch, 0) + 1
            total += 1

    for freq in char_freq.values():
        ratio = freq / total
        assert 0.005 < ratio < 0.2


def test_key_collision_rate_is_low():
    registry = ProductKeyRegistry()
    keys = set()
    collisions = 0

    total = 5000
    for idx in range(total):
        key, _ = registry.generate_personal_key(user_id=idx, key_type="personal_standard")
        if key in keys:
            collisions += 1
        keys.add(key)

    collision_rate = collisions / total
    assert collision_rate < 0.0001


def test_key_entropy_is_high_enough():
    registry = ProductKeyRegistry()
    keys = []
    for _ in range(500):
        key, _ = registry.generate_enterprise_key(
            company_name="测试企业",
            company_id=123,
            key_type="enterprise_standard",
        )
        keys.append(key.replace("-", ""))

    char_freq = {}
    total_chars = 0
    for key in keys:
        for ch in key:
            char_freq[ch] = char_freq.get(ch, 0) + 1
            total_chars += 1

    entropy = 0.0
    for freq in char_freq.values():
        p = freq / total_chars
        entropy -= p * math.log2(p)

    assert entropy > 4.0


def test_generation_seed_not_leaked_in_product_key():
    registry = ProductKeyRegistry()
    key, seed = registry.generate_enterprise_key(
        company_name="测试企业",
        company_id=123,
        key_type="enterprise_standard",
    )

    raw = key.replace("-", "")
    assert seed not in key
    assert seed not in raw
