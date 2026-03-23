"""Attention building blocks for spatial kriging models."""

from __future__ import annotations

import numpy as np


def _softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    shifted = logits - logits.max(axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / (exp.sum(axis=axis, keepdims=True) + 1e-12)


class MultiHeadSpatialAttention:
    """Scaled dot-product attention with multiple heads."""

    def __init__(self, dim: int, heads: int = 4, seed: int = 42) -> None:
        self.dim = max(1, int(dim))
        self.heads = max(1, int(heads))
        self.head_dim = max(1, self.dim // self.heads)
        rng = np.random.default_rng(seed)

        self.w_q = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_k = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_v = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_o = rng.normal(0.0, 0.08, size=(self.dim, self.dim))

    def forward(self, query: np.ndarray, key: np.ndarray, value: np.ndarray) -> np.ndarray:
        q = query @ self.w_q
        k = key @ self.w_k
        v = value @ self.w_v

        outputs: list[np.ndarray] = []
        scale = float(np.sqrt(self.head_dim))

        for h in range(self.heads):
            s = h * self.head_dim
            e = min((h + 1) * self.head_dim, self.dim)
            q_h = q[:, s:e]
            k_h = k[:, s:e]
            v_h = v[:, s:e]
            attn = _softmax((q_h @ k_h.T) / max(scale, 1e-6), axis=1)
            outputs.append(attn @ v_h)

        merged = np.concatenate(outputs, axis=1)
        if merged.shape[1] < self.dim:
            pad = np.zeros((merged.shape[0], self.dim - merged.shape[1]), dtype=float)
            merged = np.concatenate([merged, pad], axis=1)
        return merged @ self.w_o


class GlobalContextAttention:
    """Use global token to capture long-range trend."""

    def __init__(self, dim: int, seed: int = 42) -> None:
        self.inner = MultiHeadSpatialAttention(dim=dim, heads=1, seed=seed)

    def forward(self, features: np.ndarray) -> np.ndarray:
        global_token = features.mean(axis=0, keepdims=True)
        repeated = np.repeat(global_token, repeats=features.shape[0], axis=0)
        return self.inner.forward(repeated, features, features)


class MultiScaleAttention:
    """Combine local spatial attention and global context attention."""

    def __init__(self, dim: int, heads: int = 4, seed: int = 42) -> None:
        self.local_attn = MultiHeadSpatialAttention(dim=dim, heads=heads, seed=seed)
        self.global_attn = GlobalContextAttention(dim=dim, seed=seed + 7)

    def forward(self, features: np.ndarray) -> np.ndarray:
        local = self.local_attn.forward(features, features, features)
        global_ctx = self.global_attn.forward(features)
        return 0.6 * local + 0.4 * global_ctx
