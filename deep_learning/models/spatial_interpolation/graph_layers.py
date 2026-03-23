"""Numpy graph layers used by spatial interpolation models."""

from __future__ import annotations

import numpy as np


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    shifted = logits - logits.max(axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / (exp.sum(axis=axis, keepdims=True) + 1e-12)


class GCNLayer:
    """Basic graph convolution layer with symmetric normalization."""

    def __init__(self, in_dim: int, out_dim: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.weight = rng.normal(0.0, 0.15, size=(in_dim, out_dim))
        self.bias = np.zeros(out_dim, dtype=float)

    def forward(self, x: np.ndarray, adjacency: np.ndarray) -> np.ndarray:
        n = adjacency.shape[0]
        a_hat = adjacency + np.eye(n, dtype=float)
        degree = a_hat.sum(axis=1)
        degree_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(degree, 1e-12)))
        normalized = degree_inv_sqrt @ a_hat @ degree_inv_sqrt
        return _relu(normalized @ x @ self.weight + self.bias)


class GATLayer:
    """Simplified multi-head graph attention layer."""

    def __init__(self, in_dim: int, out_dim: int, heads: int = 2, seed: int = 42) -> None:
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.heads = max(1, int(heads))
        rng = np.random.default_rng(seed)
        self.weight = rng.normal(0.0, 0.12, size=(self.heads, in_dim, out_dim))
        self.attn_src = rng.normal(0.0, 0.12, size=(self.heads, out_dim))
        self.attn_dst = rng.normal(0.0, 0.12, size=(self.heads, out_dim))

    def forward(self, x: np.ndarray, edge_index: np.ndarray, n_nodes: int) -> np.ndarray:
        if edge_index.shape[1] == 0:
            return np.zeros((n_nodes, self.out_dim), dtype=float)

        src = edge_index[0]
        dst = edge_index[1]

        outputs: list[np.ndarray] = []
        for h in range(self.heads):
            projected = x @ self.weight[h]
            score = projected[src] @ self.attn_src[h] + projected[dst] @ self.attn_dst[h]
            score = np.tanh(score)

            attention = np.zeros_like(score)
            for node in range(n_nodes):
                mask = dst == node
                if np.any(mask):
                    attention[mask] = _softmax(score[mask], axis=0)

            agg = np.zeros((n_nodes, self.out_dim), dtype=float)
            for idx in range(len(src)):
                agg[int(dst[idx])] += attention[idx] * projected[int(src[idx])]
            outputs.append(agg)

        merged = np.mean(np.stack(outputs, axis=0), axis=0)
        return _relu(merged)


class EdgeConvLayer:
    """EdgeConv-like operator using neighborhood differences."""

    def __init__(self, in_dim: int, out_dim: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.weight_center = rng.normal(0.0, 0.1, size=(in_dim, out_dim))
        self.weight_delta = rng.normal(0.0, 0.1, size=(in_dim, out_dim))
        self.bias = np.zeros(out_dim, dtype=float)

    def forward(self, x: np.ndarray, edge_index: np.ndarray, n_nodes: int) -> np.ndarray:
        if edge_index.shape[1] == 0:
            return _relu(x @ self.weight_center + self.bias)

        src = edge_index[0]
        dst = edge_index[1]
        msg = np.zeros((n_nodes, self.bias.shape[0]), dtype=float)
        counts = np.zeros(n_nodes, dtype=float)

        for idx in range(len(src)):
            i = int(src[idx])
            j = int(dst[idx])
            edge_feature = x[i] @ self.weight_center + (x[j] - x[i]) @ self.weight_delta
            msg[j] += edge_feature
            counts[j] += 1.0

        counts = np.where(counts == 0.0, 1.0, counts)
        msg = msg / counts[:, None]
        return _relu(msg + self.bias)
