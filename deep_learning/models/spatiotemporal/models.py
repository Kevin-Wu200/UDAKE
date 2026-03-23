"""Core model implementations for stage-6 spatiotemporal forecasting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from .attention import (
    AttentionOutput,
    attention_pooling,
    multi_head_attention,
    spatial_multi_head_attention,
    spatiotemporal_multi_head_attention,
    temporal_multi_head_attention,
)
from .graph import build_knn_graph
from .losses import combined_spatiotemporal_loss
from .position_encoding import (
    sinusoidal_spatial_position_encoding,
    sinusoidal_temporal_position_encoding,
)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _softplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)


def _normalize_adjacency(adjacency: np.ndarray) -> np.ndarray:
    adj = np.asarray(adjacency, dtype=float)
    if adj.ndim != 2 or adj.shape[0] != adj.shape[1]:
        raise ValueError("adjacency must be [n_nodes, n_nodes]")
    a = adj + np.eye(adj.shape[0], dtype=float)
    degree = np.sum(a, axis=1)
    d_inv_sqrt = 1.0 / np.sqrt(np.maximum(degree, 1e-8))
    return (d_inv_sqrt[:, None] * a) * d_inv_sqrt[None, :]


@dataclass
class SpatialEncodingOutput:
    features: np.ndarray
    gcn_features: np.ndarray
    gat_features: np.ndarray
    transformer_features: np.ndarray
    attention_weights: np.ndarray


class SpatialEncoder:
    """Spatial encoder with GCN + GAT-like + transformer attention + position encoding."""

    def __init__(self, dim: int = 32, num_heads: int = 4, seed: int = 42) -> None:
        self.dim = int(dim)
        self.num_heads = int(max(1, num_heads))
        rng = np.random.default_rng(seed)
        self.w_gcn = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_gat = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_proj = rng.normal(0.0, 0.08, size=(self.dim * 3, self.dim))

    def forward(self, node_features: np.ndarray, coords: np.ndarray, adjacency: np.ndarray) -> SpatialEncodingOutput:
        x = np.asarray(node_features, dtype=float)
        c = np.asarray(coords, dtype=float)
        adj = _normalize_adjacency(adjacency)

        pos = sinusoidal_spatial_position_encoding(c, dim=self.dim)
        x_pos = x + pos

        gcn = np.tanh(adj @ x_pos @ self.w_gcn)

        # GAT-like: score from similarity, then masked by adjacency.
        sim = x_pos @ x_pos.T
        mask = (adj > 0).astype(float)
        logits = sim / np.sqrt(max(1.0, x_pos.shape[1]))
        logits = np.where(mask > 0, logits, -1e9)
        alpha = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        alpha = alpha / np.maximum(np.sum(alpha, axis=1, keepdims=True), 1e-8)
        gat = np.tanh(alpha @ x_pos @ self.w_gat)

        attn = spatial_multi_head_attention(x_pos, num_heads=self.num_heads)
        transformer = np.tanh(attn.context)

        merged = np.concatenate([gcn, gat, transformer], axis=1)
        fused = np.tanh(merged @ self.w_proj)
        return SpatialEncodingOutput(
            features=fused,
            gcn_features=gcn,
            gat_features=gat,
            transformer_features=transformer,
            attention_weights=attn.weights,
        )


@dataclass
class TemporalEncodingOutput:
    tokens: np.ndarray
    summary: np.ndarray
    recurrent_tokens: np.ndarray
    transformer_tokens: np.ndarray
    attention_weights: np.ndarray


class TemporalEncoder:
    """Temporal encoder with GRU-like recurrence + transformer + temporal attention."""

    def __init__(self, dim: int = 32, num_heads: int = 4, seed: int = 42) -> None:
        self.dim = int(dim)
        self.num_heads = int(max(1, num_heads))
        rng = np.random.default_rng(seed)
        self.wz = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.uz = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.wh = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.uh = rng.normal(0.0, 0.08, size=(self.dim, self.dim))

    def _gru_like(self, x: np.ndarray) -> np.ndarray:
        n, t, d = x.shape
        h = np.zeros((n, d), dtype=float)
        out = np.zeros_like(x)

        for i in range(t):
            xt = x[:, i, :]
            z = _sigmoid(xt @ self.wz + h @ self.uz)
            h_tilde = np.tanh(xt @ self.wh + (z * h) @ self.uh)
            h = (1.0 - z) * h + z * h_tilde
            out[:, i, :] = h
        return out

    def forward(self, sequence_features: np.ndarray) -> TemporalEncodingOutput:
        x = np.asarray(sequence_features, dtype=float)
        n, t, d = x.shape
        if d != self.dim:
            raise ValueError("sequence feature dim mismatch with encoder dim")

        t_pos = sinusoidal_temporal_position_encoding(t, dim=self.dim)
        x_pos = x + t_pos[None, :, :]

        recurrent = self._gru_like(x_pos)
        attn_out = temporal_multi_head_attention(x_pos, num_heads=self.num_heads)
        transformer = np.tanh(attn_out.context)

        tokens = 0.5 * recurrent + 0.5 * transformer
        pooled, _ = attention_pooling(tokens, axis=1)
        return TemporalEncodingOutput(
            tokens=tokens,
            summary=pooled,
            recurrent_tokens=recurrent,
            transformer_tokens=transformer,
            attention_weights=attn_out.weights,
        )


@dataclass
class FusionOutput:
    tokens: np.ndarray
    pooled: np.ndarray
    st_attention_weights: np.ndarray
    cross_attention_weights: np.ndarray


class SpatioTemporalFusionBlock:
    """ST-Attention + Cross-Attention + Concat/Add/Gating + Residual."""

    def __init__(self, dim: int = 32, num_heads: int = 4, seed: int = 42) -> None:
        self.dim = int(dim)
        self.num_heads = int(max(1, num_heads))
        rng = np.random.default_rng(seed)
        self.w_concat = rng.normal(0.0, 0.08, size=(self.dim * 2, self.dim))

    def forward(
        self,
        spatial_features: np.ndarray,
        temporal_tokens: np.ndarray,
        strategy: Literal["concat", "add", "gating"] = "gating",
    ) -> FusionOutput:
        s = np.asarray(spatial_features, dtype=float)
        t = np.asarray(temporal_tokens, dtype=float)
        n, seq_len, d = t.shape
        if s.shape != (n, d):
            raise ValueError("spatial features shape mismatch")

        s_expand = np.repeat(s[:, None, :], seq_len, axis=1)

        st_out = spatiotemporal_multi_head_attention(t + s_expand, num_heads=self.num_heads)

        cross = multi_head_attention(
            query=t,
            key=s_expand,
            value=s_expand,
            num_heads=self.num_heads,
        )

        if strategy == "concat":
            merged = np.concatenate([st_out.context, cross.context], axis=-1)
            fused = np.tanh(merged @ self.w_concat)
        elif strategy == "add":
            fused = st_out.context + cross.context + s_expand
        else:
            gate = _sigmoid(st_out.context * s_expand)
            fused = gate * st_out.context + (1.0 - gate) * cross.context

        # Residual connection.
        fused = fused + t
        pooled, _ = attention_pooling(fused, axis=1)

        return FusionOutput(
            tokens=fused,
            pooled=pooled,
            st_attention_weights=st_out.weights,
            cross_attention_weights=cross.weights,
        )


@dataclass
class SpatioTemporalOutput:
    mean: np.ndarray
    variance: np.ndarray
    attention: dict[str, np.ndarray] = field(default_factory=dict)
    extras: dict[str, np.ndarray] = field(default_factory=dict)


class MultiStepPredictionHead:
    def __init__(self, dim: int, pred_horizon: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.dim = int(dim)
        self.pred_horizon = int(max(1, pred_horizon))
        self.w_mean = rng.normal(0.0, 0.08, size=(self.dim, self.pred_horizon))
        self.w_var = rng.normal(0.0, 0.08, size=(self.dim, self.pred_horizon))
        self.bias = np.zeros((self.pred_horizon,), dtype=float)
        self.var_bias = np.zeros((self.pred_horizon,), dtype=float)

    def predict(self, pooled_features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        f = np.asarray(pooled_features, dtype=float)
        mean = f @ self.w_mean + self.bias[None, :]
        var = _softplus(f @ self.w_var + self.var_bias[None, :]) + 1e-6
        return mean, var

    def update_bias(self, grad: np.ndarray, lr: float) -> None:
        g = np.asarray(grad, dtype=float).reshape(-1)
        if len(g) != self.pred_horizon:
            g = np.full((self.pred_horizon,), float(np.mean(g)))
        self.bias -= lr * g
        self.var_bias -= 0.1 * lr * np.sign(g)


class BaseSpatioTemporalModel:
    model_name: str = "base_st"

    def forward(self, coords: np.ndarray, series: np.ndarray, adjacency: np.ndarray | None = None, **kwargs: Any) -> SpatioTemporalOutput:
        raise NotImplementedError

    def _iter_batch(self, batch: list[dict[str, np.ndarray]]) -> list[dict[str, np.ndarray]]:
        return batch

    def train_step(self, batch: list[dict[str, np.ndarray]], lr: float = 0.01, mixed_precision: bool = False) -> float:
        del mixed_precision
        losses: list[float] = []
        grads: list[np.ndarray] = []
        for sample in self._iter_batch(batch):
            pred = self.forward(
                coords=sample["coords"],
                series=sample["series"],
                adjacency=sample.get("adjacency"),
            )
            loss = combined_spatiotemporal_loss(
                y_pred=pred.mean,
                y_true=sample["targets"],
                y_var=pred.variance,
                adjacency=sample["adjacency"],
            )
            losses.append(float(loss["total"]))
            grads.append(np.mean(pred.mean - sample["targets"], axis=0))

        if hasattr(self, "head") and grads:
            grad = np.mean(np.stack(grads, axis=0), axis=0)
            self.head.update_bias(grad=grad, lr=float(lr))
        return float(np.mean(losses)) if losses else 0.0

    def val_step(self, batch: list[dict[str, np.ndarray]]) -> float:
        losses: list[float] = []
        for sample in self._iter_batch(batch):
            pred = self.forward(sample["coords"], sample["series"], sample.get("adjacency"))
            loss = combined_spatiotemporal_loss(pred.mean, sample["targets"], pred.variance, sample["adjacency"])
            losses.append(float(loss["total"]))
        return float(np.mean(losses)) if losses else 0.0

    def get_state(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def load_state(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)


class SpatioTemporalTransformer(BaseSpatioTemporalModel):
    model_name = "st_transformer"

    def __init__(self, dim: int = 32, num_heads: int = 4, pred_horizon: int = 6, seed: int = 42) -> None:
        self.dim = int(dim)
        self.num_heads = int(max(1, num_heads))
        self.pred_horizon = int(max(1, pred_horizon))
        self.seed = seed

        self.spatial_encoder = SpatialEncoder(dim=self.dim, num_heads=self.num_heads, seed=seed)
        self.temporal_encoder = TemporalEncoder(dim=self.dim, num_heads=self.num_heads, seed=seed + 1)
        self.fusion = SpatioTemporalFusionBlock(dim=self.dim, num_heads=self.num_heads, seed=seed + 2)
        self.head = MultiStepPredictionHead(dim=self.dim, pred_horizon=self.pred_horizon, seed=seed + 3)

        self.input_proj: np.ndarray | None = None

    def _ensure_input_proj(self, in_features: int) -> None:
        if self.input_proj is not None and self.input_proj.shape[0] == in_features:
            return
        rng = np.random.default_rng(self.seed + 11)
        self.input_proj = rng.normal(0.0, 0.08, size=(in_features, self.dim))

    def _prepare_adjacency(self, coords: np.ndarray, adjacency: np.ndarray | None) -> np.ndarray:
        if adjacency is not None:
            return np.asarray(adjacency, dtype=float)
        return build_knn_graph(coords, k=min(6, max(1, len(coords) - 1))).adjacency

    def forward(
        self,
        coords: np.ndarray,
        series: np.ndarray,
        adjacency: np.ndarray | None = None,
        fusion_strategy: Literal["concat", "add", "gating"] = "gating",
        **_: Any,
    ) -> SpatioTemporalOutput:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        n, seq_len, in_dim = s.shape

        self._ensure_input_proj(in_dim)
        assert self.input_proj is not None
        seq_emb = np.tanh(np.einsum("ntf,fd->ntd", s, self.input_proj))

        adj = self._prepare_adjacency(c, adjacency)
        spatial_input = np.mean(seq_emb, axis=1)
        spatial = self.spatial_encoder.forward(spatial_input, c, adj)
        temporal = self.temporal_encoder.forward(seq_emb)
        fused = self.fusion.forward(spatial.features, temporal.tokens, strategy=fusion_strategy)

        mean, variance = self.head.predict(fused.pooled)
        return SpatioTemporalOutput(
            mean=mean,
            variance=variance,
            attention={
                "spatial": spatial.attention_weights,
                "temporal": temporal.attention_weights,
                "st": fused.st_attention_weights,
                "cross": fused.cross_attention_weights,
            },
            extras={
                "spatial_features": spatial.features,
                "temporal_summary": temporal.summary,
                "fused_tokens": fused.tokens,
            },
        )


class GCNLSTMModel(BaseSpatioTemporalModel):
    model_name = "gcn_lstm"

    def __init__(self, dim: int = 28, layers: int = 2, bidirectional: bool = True, pred_horizon: int = 6, seed: int = 42) -> None:
        self.dim = int(dim)
        self.layers = int(max(1, layers))
        self.bidirectional = bool(bidirectional)
        self.pred_horizon = int(max(1, pred_horizon))
        self.seed = seed

        rng = np.random.default_rng(seed)
        self.w_gcn = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_lstm = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_gate = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.head = MultiStepPredictionHead(dim=self.dim, pred_horizon=self.pred_horizon, seed=seed + 1)
        self.input_proj: np.ndarray | None = None

    def _ensure_input_proj(self, in_features: int) -> None:
        if self.input_proj is not None and self.input_proj.shape[0] == in_features:
            return
        rng = np.random.default_rng(self.seed + 7)
        self.input_proj = rng.normal(0.0, 0.08, size=(in_features, self.dim))

    def _lstm_pass(self, seq: np.ndarray) -> np.ndarray:
        n, t, d = seq.shape
        h = np.zeros((n, d), dtype=float)
        c = np.zeros((n, d), dtype=float)
        outs = np.zeros_like(seq)

        for i in range(t):
            x = seq[:, i, :]
            gate = _sigmoid(x @ self.w_gate + h)
            c = gate * c + (1.0 - gate) * np.tanh(x @ self.w_lstm)
            h = np.tanh(c)
            outs[:, i, :] = h
        return outs

    def forward(self, coords: np.ndarray, series: np.ndarray, adjacency: np.ndarray | None = None, **_: Any) -> SpatioTemporalOutput:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        n, seq_len, in_dim = s.shape
        self._ensure_input_proj(in_dim)
        assert self.input_proj is not None

        adj = adjacency if adjacency is not None else build_knn_graph(c, k=min(6, max(1, n - 1))).adjacency
        adj_norm = _normalize_adjacency(adj)

        x = np.tanh(np.einsum("ntf,fd->ntd", s, self.input_proj))

        # Spatial extraction at each time step.
        spatial_seq = np.zeros_like(x)
        for i in range(seq_len):
            spatial_seq[:, i, :] = np.tanh(adj_norm @ x[:, i, :] @ self.w_gcn)

        # Temporal extraction with stacked LSTM and optional BiLSTM.
        hidden = spatial_seq
        for _ in range(self.layers):
            fw = self._lstm_pass(hidden)
            if self.bidirectional:
                bw = self._lstm_pass(hidden[:, ::-1, :])[:, ::-1, :]
                hidden = 0.5 * (fw + bw)
            else:
                hidden = fw

        # Skip + gate coupling.
        gate = _sigmoid(hidden @ self.w_gate)
        coupled = gate * hidden + (1.0 - gate) * spatial_seq
        pooled = np.mean(coupled, axis=1)

        mean, variance = self.head.predict(pooled)
        return SpatioTemporalOutput(
            mean=mean,
            variance=variance,
            attention={
                "temporal_gate": gate,
            },
            extras={
                "coupled_tokens": coupled,
            },
        )


class ConvLSTMModel(BaseSpatioTemporalModel):
    model_name = "convlstm"

    def __init__(self, dim: int = 24, pred_horizon: int = 6, seed: int = 42) -> None:
        self.dim = int(dim)
        self.pred_horizon = int(max(1, pred_horizon))
        self.seed = seed
        rng = np.random.default_rng(seed)

        self.w_conv_local = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_conv_global = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_rec = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_attn = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.head = MultiStepPredictionHead(dim=self.dim, pred_horizon=self.pred_horizon, seed=seed + 1)
        self.input_proj: np.ndarray | None = None

    def _ensure_input_proj(self, in_features: int) -> None:
        if self.input_proj is not None and self.input_proj.shape[0] == in_features:
            return
        rng = np.random.default_rng(self.seed + 13)
        self.input_proj = rng.normal(0.0, 0.08, size=(in_features, self.dim))

    def forward(self, coords: np.ndarray, series: np.ndarray, adjacency: np.ndarray | None = None, **_: Any) -> SpatioTemporalOutput:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        n, seq_len, in_dim = s.shape
        self._ensure_input_proj(in_dim)
        assert self.input_proj is not None

        adj = adjacency if adjacency is not None else build_knn_graph(c, k=min(6, max(1, n - 1))).adjacency
        adj_norm = _normalize_adjacency(adj)
        adj_global = _normalize_adjacency(np.where(adj > np.percentile(adj, 60), adj, 0.0))

        x = np.tanh(np.einsum("ntf,fd->ntd", s, self.input_proj))
        h = np.zeros((n, self.dim), dtype=float)
        outputs = np.zeros((n, seq_len, self.dim), dtype=float)
        spatial_attn = np.zeros((n, seq_len), dtype=float)

        for t in range(seq_len):
            xt = x[:, t, :]
            local = np.tanh(adj_norm @ xt @ self.w_conv_local)
            global_ = np.tanh(adj_global @ xt @ self.w_conv_global)
            multi_scale = 0.6 * local + 0.4 * global_

            # ConvLSTM recurrence.
            h = np.tanh(multi_scale + h @ self.w_rec)

            # Spatial attention.
            score = np.sum(h * (xt @ self.w_attn), axis=1)
            attn = np.exp(score - np.max(score))
            attn = attn / np.maximum(np.sum(attn), 1e-8)
            spatial_attn[:, t] = attn
            outputs[:, t, :] = h * attn[:, None]

        # Temporal attention.
        pooled, temporal_attn = attention_pooling(outputs, axis=1)
        mean, variance = self.head.predict(pooled)
        return SpatioTemporalOutput(
            mean=mean,
            variance=variance,
            attention={
                "spatial": spatial_attn,
                "temporal": temporal_attn,
            },
            extras={
                "multi_scale_tokens": outputs,
            },
        )


class STGCNModel(BaseSpatioTemporalModel):
    model_name = "stgcn"

    def __init__(self, dim: int = 24, n_blocks: int = 3, pred_horizon: int = 6, seed: int = 42) -> None:
        self.dim = int(dim)
        self.n_blocks = int(max(1, n_blocks))
        self.pred_horizon = int(max(1, pred_horizon))
        self.seed = seed

        rng = np.random.default_rng(seed)
        self.w_spatial = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_temporal = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.w_dilated = rng.normal(0.0, 0.08, size=(self.dim, self.dim))
        self.head = MultiStepPredictionHead(dim=self.dim, pred_horizon=self.pred_horizon, seed=seed + 1)
        self.input_proj: np.ndarray | None = None

    def _ensure_input_proj(self, in_features: int) -> None:
        if self.input_proj is not None and self.input_proj.shape[0] == in_features:
            return
        rng = np.random.default_rng(self.seed + 19)
        self.input_proj = rng.normal(0.0, 0.08, size=(in_features, self.dim))

    def _temporal_conv(self, x: np.ndarray, dilation: int = 1) -> np.ndarray:
        """1D temporal conv with dilation over seq axis."""
        n, t, d = x.shape
        out = np.zeros_like(x)
        for i in range(t):
            prev = max(0, i - dilation)
            nxt = min(t - 1, i + dilation)
            out[:, i, :] = 0.5 * x[:, prev, :] + 0.5 * x[:, nxt, :]
        return np.tanh(out @ self.w_temporal)

    def forward(self, coords: np.ndarray, series: np.ndarray, adjacency: np.ndarray | None = None, **_: Any) -> SpatioTemporalOutput:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        n, seq_len, in_dim = s.shape
        self._ensure_input_proj(in_dim)
        assert self.input_proj is not None

        adj = adjacency if adjacency is not None else build_knn_graph(c, k=min(6, max(1, n - 1))).adjacency
        adj_norm = _normalize_adjacency(adj)

        x = np.tanh(np.einsum("ntf,fd->ntd", s, self.input_proj))
        hidden = x

        for b in range(self.n_blocks):
            spatial = np.zeros_like(hidden)
            for i in range(seq_len):
                spatial[:, i, :] = np.tanh(adj_norm @ hidden[:, i, :] @ self.w_spatial)

            temporal = self._temporal_conv(spatial, dilation=2 ** min(b, 2))
            dilated = self._temporal_conv(spatial, dilation=2 ** min(b + 1, 3)) @ self.w_dilated

            # ST-Block with residual.
            hidden = np.tanh(0.5 * temporal + 0.5 * dilated) + hidden

        pooled = np.mean(hidden, axis=1)
        mean, variance = self.head.predict(pooled)
        return SpatioTemporalOutput(
            mean=mean,
            variance=variance,
            attention={
                "st_block_depth": np.array([self.n_blocks], dtype=float),
            },
            extras={
                "hidden_tokens": hidden,
            },
        )
