"""Attention-Kriging model with transformer-style encoder and cross-attention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .attention import MultiHeadSpatialAttention
from .baselines import UniversalKrigingBaseline
from .heads import MultiTaskHead
from .position_encoding import LearnablePositionEncoding, relative_position_encoding, sinusoidal_position_encoding


def _layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    mean = x.mean(axis=1, keepdims=True)
    var = x.var(axis=1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)


@dataclass
class AttentionKrigingOutput:
    mean: np.ndarray
    variance: np.ndarray
    attention_weights: np.ndarray


class TransformerEncoderBlock:
    """Minimal transformer encoder block with residual and FFN."""

    def __init__(self, dim: int, heads: int = 4, seed: int = 42) -> None:
        self.attn = MultiHeadSpatialAttention(dim=dim, heads=heads, seed=seed)
        rng = np.random.default_rng(seed + 1)
        self.ffn_w1 = rng.normal(0.0, 0.08, size=(dim, dim * 2))
        self.ffn_w2 = rng.normal(0.0, 0.08, size=(dim * 2, dim))

    def forward(self, x: np.ndarray) -> np.ndarray:
        attn_out = self.attn.forward(x, x, x)
        x = _layer_norm(x + attn_out)
        ffn = np.maximum(0.0, x @ self.ffn_w1) @ self.ffn_w2
        return _layer_norm(x + ffn)


class AttentionKrigingModel:
    """Attention-driven kriging model with bidirectional cross-attention."""

    def __init__(self, dim: int = 24, heads: int = 4, seed: int = 42) -> None:
        self.dim = max(8, int(dim))
        self.seed = seed

        self.pos_encoder = LearnablePositionEncoding(dim=self.dim // 2, seed=seed)
        self.encoder = TransformerEncoderBlock(dim=self.dim, heads=heads, seed=seed + 1)
        self.sample_to_query = MultiHeadSpatialAttention(dim=self.dim, heads=heads, seed=seed + 2)
        self.query_to_sample = MultiHeadSpatialAttention(dim=self.dim, heads=heads, seed=seed + 3)
        self.head = MultiTaskHead(in_dim=self.dim, with_aux=True, seed=seed + 4)

        self.baseline = UniversalKrigingBaseline()
        self.dynamic_weight = 1.0
        self.bias = 0.0

    def _encode_samples(self, sample_coords: np.ndarray, sample_values: np.ndarray) -> np.ndarray:
        coords = np.asarray(sample_coords, dtype=float)
        values = np.asarray(sample_values, dtype=float).reshape(-1, 1)
        sin_pos = sinusoidal_position_encoding(coords, dim=self.dim // 2)
        learn_pos = self.pos_encoder.encode(coords)

        uncertainty = np.full((len(coords), 1), np.std(values) + 1e-6)
        value_feat = np.concatenate([values, uncertainty], axis=1)

        if value_feat.shape[1] < self.dim - sin_pos.shape[1] - learn_pos.shape[1]:
            remain = self.dim - sin_pos.shape[1] - learn_pos.shape[1] - value_feat.shape[1]
            value_feat = np.concatenate([value_feat, np.zeros((len(coords), remain), dtype=float)], axis=1)

        feat = np.concatenate([sin_pos, learn_pos, value_feat], axis=1)
        return feat[:, : self.dim]

    def _encode_queries(self, query_coords: np.ndarray, sample_coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        q = np.asarray(query_coords, dtype=float)
        s = np.asarray(sample_coords, dtype=float)
        sin_pos = sinusoidal_position_encoding(q, dim=self.dim // 2)
        learn_pos = self.pos_encoder.encode(q)
        rel = relative_position_encoding(q, s)

        rel_dist = rel[:, :, 2]
        rel_bias = np.exp(-rel_dist / 0.2)

        coord_feat = np.concatenate([sin_pos, learn_pos], axis=1)
        if coord_feat.shape[1] < self.dim:
            coord_feat = np.concatenate([coord_feat, np.zeros((len(q), self.dim - coord_feat.shape[1]), dtype=float)], axis=1)
        return coord_feat[:, : self.dim], rel_bias

    def forward(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
    ) -> AttentionKrigingOutput:
        s_coords = np.asarray(sample_coords, dtype=float)
        s_vals = np.asarray(sample_values, dtype=float).reshape(-1)
        q_coords = np.asarray(query_coords, dtype=float)

        self.baseline.fit(s_coords, s_vals)
        prior_mean, prior_var = self.baseline.predict(q_coords)

        sample_tokens = self._encode_samples(s_coords, s_vals)
        sample_tokens = self.encoder.forward(sample_tokens)

        query_tokens, rel_bias = self._encode_queries(q_coords, s_coords)
        query_tokens = self.encoder.forward(query_tokens)

        attn_sq = self.sample_to_query.forward(query_tokens, sample_tokens, sample_tokens)
        attn_qs = self.query_to_sample.forward(sample_tokens, query_tokens, query_tokens)

        # Dynamic, distance-aware and variance-aware blending.
        distance_weight = rel_bias.mean(axis=1)
        variance_weight = 1.0 / (1.0 + prior_var)
        adaptive = np.clip(self.dynamic_weight * distance_weight * variance_weight, 0.0, 2.0).reshape(-1, 1)

        context = attn_sq + adaptive * attn_sq + 0.2 * attn_qs.mean(axis=0, keepdims=True)
        out = self.head.forward(context)

        residual = self.bias + out["mean"] * adaptive.reshape(-1)
        pred_mean = prior_mean + residual
        pred_var = np.maximum(prior_var + np.abs(out["variance"]), 1e-6)

        return AttentionKrigingOutput(mean=pred_mean, variance=pred_var, attention_weights=rel_bias)

    def train_step(self, batch: list[dict[str, Any]], lr: float = 1e-2, mixed_precision: bool = False) -> float:
        del mixed_precision
        losses: list[float] = []

        for sample in batch:
            coords = np.asarray(sample["coords"], dtype=float)
            values = np.asarray(sample["values"], dtype=float).reshape(-1)
            targets = np.asarray(sample.get("targets", values), dtype=float).reshape(-1)

            out = self.forward(coords, values, query_coords=coords)
            err = out.mean - targets
            losses.append(float(np.mean(err ** 2)))

            self.bias -= lr * float(np.mean(err))
            self.dynamic_weight -= lr * float(np.mean(err * out.mean))

        return float(np.mean(losses) if losses else 0.0)

    def val_step(self, batch: list[dict[str, Any]]) -> float:
        losses: list[float] = []
        for sample in batch:
            coords = np.asarray(sample["coords"], dtype=float)
            values = np.asarray(sample["values"], dtype=float).reshape(-1)
            targets = np.asarray(sample.get("targets", values), dtype=float).reshape(-1)
            out = self.forward(coords, values, query_coords=coords)
            losses.append(float(np.mean(np.abs(out.mean - targets))))
        return float(np.mean(losses) if losses else 0.0)

    def get_state(self) -> dict[str, float]:
        return {"bias": float(self.bias), "dynamic_weight": float(self.dynamic_weight)}

    def load_state(self, state: dict[str, Any]) -> None:
        self.bias = float(state.get("bias", 0.0))
        self.dynamic_weight = float(state.get("dynamic_weight", 1.0))
