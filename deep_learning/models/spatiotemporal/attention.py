"""Attention blocks for spatiotemporal models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AttentionOutput:
    context: np.ndarray
    weights: np.ndarray


def _softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    x = np.asarray(logits, dtype=float)
    x = x - np.max(x, axis=axis, keepdims=True)
    exp = np.exp(x)
    return exp / np.maximum(np.sum(exp, axis=axis, keepdims=True), 1e-8)


def _split_heads(x: np.ndarray, num_heads: int) -> np.ndarray:
    n, l, d = x.shape
    if d % num_heads != 0:
        raise ValueError("feature dim must be divisible by num_heads")
    head_dim = d // num_heads
    return x.reshape(n, l, num_heads, head_dim).transpose(0, 2, 1, 3)


def _merge_heads(x: np.ndarray) -> np.ndarray:
    n, h, l, d = x.shape
    return x.transpose(0, 2, 1, 3).reshape(n, l, h * d)


def multi_head_attention(query: np.ndarray, key: np.ndarray, value: np.ndarray, num_heads: int = 4) -> AttentionOutput:
    """Scaled dot-product multi-head attention.

    Inputs are [batch, seq_len, dim].
    """
    q = np.asarray(query, dtype=float)
    k = np.asarray(key, dtype=float)
    v = np.asarray(value, dtype=float)
    if q.ndim != 3 or k.ndim != 3 or v.ndim != 3:
        raise ValueError("query/key/value must be [batch, seq, dim]")

    qh = _split_heads(q, num_heads)
    kh = _split_heads(k, num_heads)
    vh = _split_heads(v, num_heads)

    scale = np.sqrt(max(1.0, qh.shape[-1]))
    logits = np.matmul(qh, kh.transpose(0, 1, 3, 2)) / scale
    weights = _softmax(logits, axis=-1)
    context = np.matmul(weights, vh)

    return AttentionOutput(context=_merge_heads(context), weights=weights)


def spatial_multi_head_attention(features: np.ndarray, num_heads: int = 4) -> AttentionOutput:
    """Attention over spatial nodes.

    Input shape [n_nodes, dim].
    """
    f = np.asarray(features, dtype=float)
    if f.ndim != 2:
        raise ValueError("features must be [n_nodes, dim]")
    out = multi_head_attention(f[None, :, :], f[None, :, :], f[None, :, :], num_heads=num_heads)
    return AttentionOutput(context=out.context[0], weights=out.weights[0])


def temporal_multi_head_attention(sequence_features: np.ndarray, num_heads: int = 4) -> AttentionOutput:
    """Attention over temporal tokens.

    Input shape [n_nodes, seq_len, dim].
    """
    s = np.asarray(sequence_features, dtype=float)
    if s.ndim != 3:
        raise ValueError("sequence_features must be [n_nodes, seq_len, dim]")
    out = multi_head_attention(s, s, s, num_heads=num_heads)
    return out


def spatiotemporal_multi_head_attention(tokens: np.ndarray, num_heads: int = 4) -> AttentionOutput:
    """Attention over flattened spatiotemporal tokens.

    Input shape [n_nodes, seq_len, dim], flatten to [1, n_nodes*seq_len, dim].
    """
    t = np.asarray(tokens, dtype=float)
    if t.ndim != 3:
        raise ValueError("tokens must be [n_nodes, seq_len, dim]")
    n, s, d = t.shape
    flat = t.reshape(1, n * s, d)
    out = multi_head_attention(flat, flat, flat, num_heads=num_heads)
    return AttentionOutput(context=out.context.reshape(n, s, d), weights=out.weights)


def attention_pooling(sequence: np.ndarray, axis: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Learn-less attention pooling using norm-based scores."""
    x = np.asarray(sequence, dtype=float)
    scores = np.linalg.norm(x, axis=-1)
    w = _softmax(scores, axis=axis)
    pooled = np.sum(x * np.expand_dims(w, axis=-1), axis=axis)
    return pooled, w
