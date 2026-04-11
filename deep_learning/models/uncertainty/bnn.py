"""贝叶斯神经网络（BNN）不确定性量化实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence, Union

import numpy as np

from .common import (
    PredictiveMoments,
    confidence_interval,
    decompose_uncertainty,
    ensure_1d,
    ensure_2d,
    gaussian_nll,
    kl_diag_gaussian,
    sigmoid,
    softplus,
    temperature_scale_variance,
)


@dataclass
class GaussianPrior:
    sigma: float = 1.0


@dataclass
class GaussianMixturePrior:
    sigmas: tuple[float, float] = (1.0, 0.1)
    weights: tuple[float, float] = (0.5, 0.5)


PriorType = Union[GaussianPrior, GaussianMixturePrior]


def _effective_prior_sigma(prior: PriorType) -> float:
    if isinstance(prior, GaussianPrior):
        return float(max(prior.sigma, 1e-6))
    w = np.asarray(prior.weights, dtype=float)
    s = np.asarray(prior.sigmas, dtype=float)
    w = np.maximum(w, 1e-8)
    w = w / np.sum(w)
    return float(np.sqrt(np.sum(w * (s ** 2)) + 1e-8))


class BayesianParameter:
    def __init__(self, shape: tuple[int, ...], rng: np.random.Generator) -> None:
        self.mu = rng.normal(0.0, 0.08, size=shape)
        self.rho = np.full(shape, -2.0, dtype=float)

    @property
    def sigma(self) -> np.ndarray:
        return softplus(self.rho) + 1e-6

    def sample(self, rng: np.random.Generator, temperature: float = 1.0) -> np.ndarray:
        eps = rng.normal(0.0, 1.0, size=self.mu.shape)
        return self.mu + float(max(temperature, 1e-4)) * self.sigma * eps

    def kl(self, prior: PriorType) -> float:
        return kl_diag_gaussian(self.mu, self.sigma, prior_sigma=_effective_prior_sigma(prior))

    def kl_grad_mu(self, prior: PriorType) -> np.ndarray:
        p2 = _effective_prior_sigma(prior) ** 2
        return self.mu / p2

    def kl_grad_rho(self, prior: PriorType) -> np.ndarray:
        sigma = self.sigma
        p2 = _effective_prior_sigma(prior) ** 2
        dkl_dsigma = -1.0 / sigma + sigma / p2
        dsigma_drho = sigmoid(self.rho)
        return dkl_dsigma * dsigma_drho


class BayesianDenseLayer:
    """贝叶斯全连接层。"""

    def __init__(self, in_dim: int, out_dim: int, prior: PriorType, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.weight = BayesianParameter((in_dim, out_dim), rng)
        self.bias = BayesianParameter((out_dim,), rng)
        self.prior = prior

    def forward(self, x: np.ndarray, sample: bool = True, rng: np.random.Generator | None = None) -> np.ndarray:
        w = self.weight.mu
        b = self.bias.mu
        if sample:
            if rng is None:
                rng = np.random.default_rng(42)
            w = self.weight.sample(rng)
            b = self.bias.sample(rng)
        return x @ w + b

    def kl(self) -> float:
        return self.weight.kl(self.prior) + self.bias.kl(self.prior)


class BayesianConvLayer:
    """贝叶斯一维卷积层（轻量实现）。"""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, prior: PriorType, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.kernel_size = int(max(1, kernel_size))
        self.weight = BayesianParameter((out_channels, in_channels, self.kernel_size), rng)
        self.bias = BayesianParameter((out_channels,), rng)
        self.prior = prior

    def forward(self, x: np.ndarray, sample: bool = True, rng: np.random.Generator | None = None) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        if arr.ndim != 3:
            raise ValueError("输入需为 [batch, length, channels]")
        batch, length, in_channels = arr.shape
        out_channels = self.weight.mu.shape[0]
        if in_channels != self.weight.mu.shape[1]:
            raise ValueError("输入通道数与卷积层不匹配")

        w = self.weight.mu
        b = self.bias.mu
        if sample:
            rng = rng or np.random.default_rng(42)
            w = self.weight.sample(rng)
            b = self.bias.sample(rng)

        pad = self.kernel_size // 2
        padded = np.pad(arr, ((0, 0), (pad, pad), (0, 0)), mode="edge")
        output = np.zeros((batch, length, out_channels), dtype=float)

        for t in range(length):
            window = padded[:, t : t + self.kernel_size, :]  # [B, K, C]
            window = np.transpose(window, (0, 2, 1))  # [B, C, K]
            for oc in range(out_channels):
                output[:, t, oc] = np.sum(window * w[oc][None, :, :], axis=(1, 2)) + b[oc]

        return output

    def kl(self) -> float:
        return self.weight.kl(self.prior) + self.bias.kl(self.prior)


class ELBOLoss:
    """ELBO 损失 = NLL + KL。"""

    def __call__(
        self,
        y_true: np.ndarray,
        pred_mean: np.ndarray,
        pred_var: np.ndarray,
        kl_value: float,
        kl_weight: float,
    ) -> dict[str, float]:
        nll = gaussian_nll(y_true, pred_mean, pred_var)
        total = float(nll + kl_weight * kl_value)
        return {
            "total": total,
            "nll": float(nll),
            "kl": float(kl_value),
            "kl_weight": float(kl_weight),
        }


class BayesianNeuralRegressor:
    """两层 BNN 回归器，输出均值与异方差。"""

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int = 32,
        prior: PriorType | None = None,
        seed: int = 42,
    ) -> None:
        self.in_dim = int(in_dim)
        self.hidden_dim = int(max(4, hidden_dim))
        self.prior = prior or GaussianPrior(1.0)
        self.rng = np.random.default_rng(seed)

        self.hidden = BayesianDenseLayer(self.in_dim, self.hidden_dim, prior=self.prior, seed=seed)
        self.mean_head = BayesianDenseLayer(self.hidden_dim, 1, prior=self.prior, seed=seed + 1)
        self.logvar_head = BayesianDenseLayer(self.hidden_dim, 1, prior=self.prior, seed=seed + 2)
        self.elbo = ELBOLoss()

        self.history: list[dict[str, float]] = []
        self.feature_names: list[str] = [f"feature_{i}" for i in range(self.in_dim)]
        self._runtime_feature_mean = np.zeros(self.in_dim, dtype=float)
        self._runtime_feature_std = np.ones(self.in_dim, dtype=float)
        self._has_runtime_stats = False

    def _forward_mean(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        z1 = self.hidden.forward(x, sample=False)
        h = np.tanh(z1)
        mean = self.mean_head.forward(h, sample=False).reshape(-1)
        logvar = np.clip(self.logvar_head.forward(h, sample=False).reshape(-1), -8.0, 5.0)
        return h, mean, logvar

    def _forward_sample(self, x: np.ndarray, temperature: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
        z1 = self.hidden.forward(x, sample=True, rng=self.rng)
        h = np.tanh(z1)
        mean = self.mean_head.forward(h, sample=True, rng=self.rng).reshape(-1)
        logvar = self.logvar_head.forward(h, sample=True, rng=self.rng).reshape(-1)
        var = temperature_scale_variance(np.exp(np.clip(logvar, -8.0, 5.0)), temperature=temperature)
        return mean, var

    def _kl_total(self) -> float:
        return float(self.hidden.kl() + self.mean_head.kl() + self.logvar_head.kl())

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        epochs: int = 220,
        lr: float = 8e-3,
        kl_anneal_epochs: int = 100,
        temperature: float = 1.0,
    ) -> dict[str, Any]:
        features = ensure_2d(x)
        target = ensure_1d(y)
        if len(features) != len(target):
            raise ValueError("x 与 y 长度不一致")
        if features.shape[1] != self.in_dim:
            raise ValueError("输入维度与模型不匹配")

        n = float(len(target))
        lr = float(max(lr, 1e-5))
        epochs = int(max(1, epochs))

        for epoch in range(epochs):
            h, mean, logvar = self._forward_mean(features)
            var = np.exp(logvar) + 1e-6
            error = mean - target

            d_mean = error / var / n
            d_logvar = 0.5 * (1.0 - (error ** 2) / var) / n

            grad_w_mean = h.T @ d_mean[:, None]
            grad_b_mean = np.sum(d_mean)
            grad_w_logvar = h.T @ d_logvar[:, None]
            grad_b_logvar = np.sum(d_logvar)

            dh = d_mean[:, None] @ self.mean_head.weight.mu.T + d_logvar[:, None] @ self.logvar_head.weight.mu.T
            dz1 = dh * (1.0 - h ** 2)

            grad_w_hidden = features.T @ dz1
            grad_b_hidden = np.sum(dz1, axis=0)

            kl_weight = min(1.0, (epoch + 1) / float(max(1, kl_anneal_epochs)))

            self.mean_head.weight.mu -= lr * (grad_w_mean + kl_weight * self.mean_head.weight.kl_grad_mu(self.prior) / n)
            self.mean_head.bias.mu -= lr * (
                grad_b_mean + kl_weight * self.mean_head.bias.kl_grad_mu(self.prior) / n
            )

            self.logvar_head.weight.mu -= lr * (
                grad_w_logvar + kl_weight * self.logvar_head.weight.kl_grad_mu(self.prior) / n
            )
            self.logvar_head.bias.mu -= lr * (
                grad_b_logvar + kl_weight * self.logvar_head.bias.kl_grad_mu(self.prior) / n
            )

            self.hidden.weight.mu -= lr * (grad_w_hidden + kl_weight * self.hidden.weight.kl_grad_mu(self.prior) / n)
            self.hidden.bias.mu -= lr * (grad_b_hidden + kl_weight * self.hidden.bias.kl_grad_mu(self.prior) / n)

            # 方差参数按 KL 梯度更新（重参数化后验）
            for layer in [self.hidden, self.mean_head, self.logvar_head]:
                layer.weight.rho -= lr * kl_weight * layer.weight.kl_grad_rho(self.prior) / n
                layer.bias.rho -= lr * kl_weight * layer.bias.kl_grad_rho(self.prior) / n

            kl_value = self._kl_total() / n
            losses = self.elbo(target, mean, var, kl_value=kl_value, kl_weight=kl_weight)
            losses["epoch"] = float(epoch + 1)
            losses["temperature"] = float(max(temperature, 1e-4))
            self.history.append(losses)

        return {
            "epochs": epochs,
            "final_loss": float(self.history[-1]["total"]),
            "final_nll": float(self.history[-1]["nll"]),
            "final_kl": float(self.history[-1]["kl"]),
            "best_total_loss": float(min(r["total"] for r in self.history)),
        }

    def sample_predict(
        self,
        x: np.ndarray,
        num_samples: int = 50,
        temperature: float = 1.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        features = ensure_2d(x)
        t = int(max(2, num_samples))
        sampled_means = np.zeros((t, len(features)), dtype=float)
        sampled_vars = np.zeros((t, len(features)), dtype=float)
        for i in range(t):
            mean_i, var_i = self._forward_sample(features, temperature=temperature)
            sampled_means[i] = mean_i
            sampled_vars[i] = var_i
        return sampled_means, sampled_vars

    def predict(
        self,
        x: np.ndarray,
        num_samples: int = 80,
        confidence: float = 0.95,
        temperature: float = 1.0,
    ) -> dict[str, Any]:
        sampled_means, sampled_vars = self.sample_predict(x, num_samples=num_samples, temperature=temperature)
        moments: PredictiveMoments = decompose_uncertainty(sampled_means, sampled_vars)
        lower, upper = confidence_interval(moments.mean, moments.variance, confidence=confidence)
        return {
            "mean": moments.mean,
            "variance": moments.variance,
            "aleatoric": moments.aleatoric,
            "epistemic": moments.epistemic,
            "lower": lower,
            "upper": upper,
            "confidence": float(confidence),
            "num_samples": int(max(2, num_samples)),
        }

    def preprocess_bnn_data(
        self,
        features: np.ndarray | list[list[float]],
        *,
        feature_names: list[str] | None = None,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        x_raw = ensure_2d(np.asarray(features, dtype=float))
        if x_raw.shape[1] != self.in_dim:
            raise ValueError(f"输入维度不匹配：期望 {self.in_dim}，实际 {x_raw.shape[1]}")

        names = list(feature_names) if feature_names is not None else [f"feature_{i}" for i in range(x_raw.shape[1])]
        if len(names) != x_raw.shape[1]:
            raise ValueError("feature_names 长度与特征维度不一致")

        if use_training_stats and self._has_runtime_stats:
            mean = np.asarray(self._runtime_feature_mean, dtype=float)
            std = np.asarray(self._runtime_feature_std, dtype=float)
            stats_source = "runtime"
        else:
            mean = np.mean(x_raw, axis=0)
            std = np.std(x_raw, axis=0)
            std = np.where(std > 1e-8, std, 1.0)
            self._runtime_feature_mean = mean.astype(float)
            self._runtime_feature_std = std.astype(float)
            self._has_runtime_stats = True
            stats_source = "batch"

        x_scaled = (x_raw - mean.reshape(1, -1)) / std.reshape(1, -1)
        self.feature_names = list(names)
        return {
            "raw_features": x_raw,
            "processed_features": x_scaled,
            "feature_names": list(names),
            "scaler": {
                "mean": [float(v) for v in mean.tolist()],
                "std": [float(v) for v in std.tolist()],
                "source": stats_source,
            },
            "validation": {
                "is_valid": True,
                "sample_count": int(x_raw.shape[0]),
                "feature_dim": int(x_raw.shape[1]),
                "stats_source": stats_source,
            },
        }

    def predict_bnn(
        self,
        features: np.ndarray | list[list[float]],
        *,
        num_samples: int = 80,
        confidence: float = 0.95,
        temperature: float = 1.0,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_bnn_data(features, use_training_stats=use_training_stats)
        pred = self.predict(
            np.asarray(pre["processed_features"], dtype=float),
            num_samples=num_samples,
            confidence=confidence,
            temperature=temperature,
        )
        pred["preprocess"] = {
            "scaler": dict(pre["scaler"]),
            "validation": dict(pre["validation"]),
            "feature_names": list(pre["feature_names"]),
        }
        return pred

    def _named_parameters(self) -> list[tuple[str, BayesianParameter]]:
        return [
            ("hidden.weight", self.hidden.weight),
            ("hidden.bias", self.hidden.bias),
            ("mean_head.weight", self.mean_head.weight),
            ("mean_head.bias", self.mean_head.bias),
            ("logvar_head.weight", self.logvar_head.weight),
            ("logvar_head.bias", self.logvar_head.bias),
        ]

    def explain_bayesian_weights(self, top_k: int = 8) -> dict[str, Any]:
        """输出贝叶斯权重解释（后验均值/方差与全局重要参数）。"""
        named_params = self._named_parameters()
        summaries: list[dict[str, Any]] = []
        uncertain_pool: list[tuple[float, str, int, float, float, float]] = []
        confident_pool: list[tuple[float, str, int, float, float, float]] = []

        for name, param in named_params:
            mu = np.asarray(param.mu, dtype=float).reshape(-1)
            sigma = np.asarray(param.sigma, dtype=float).reshape(-1)
            snr = np.abs(mu) / (sigma + 1e-8)
            summaries.append(
                {
                    "parameter": name,
                    "count": int(mu.size),
                    "posterior_mean": {
                        "mean": float(np.mean(mu)),
                        "std": float(np.std(mu)),
                        "abs_mean": float(np.mean(np.abs(mu))),
                    },
                    "posterior_std": {
                        "mean": float(np.mean(sigma)),
                        "std": float(np.std(sigma)),
                        "min": float(np.min(sigma)),
                        "max": float(np.max(sigma)),
                    },
                    "signal_noise_ratio": {
                        "mean": float(np.mean(snr)),
                        "p50": float(np.quantile(snr, 0.5)),
                        "p90": float(np.quantile(snr, 0.9)),
                    },
                }
            )
            for idx in range(mu.size):
                uncertain_pool.append((float(sigma[idx]), name, int(idx), float(mu[idx]), float(sigma[idx]), float(snr[idx])))
                confident_pool.append((float(snr[idx]), name, int(idx), float(mu[idx]), float(sigma[idx]), float(snr[idx])))

        k = max(1, int(top_k))
        uncertain_pool.sort(key=lambda item: item[0], reverse=True)
        confident_pool.sort(key=lambda item: item[0], reverse=True)
        top_uncertain = [
            {
                "parameter": str(name),
                "flat_index": int(idx),
                "mu": float(mu),
                "sigma": float(sig),
                "signal_noise_ratio": float(snr),
            }
            for _, name, idx, mu, sig, snr in uncertain_pool[:k]
        ]
        top_confident = [
            {
                "parameter": str(name),
                "flat_index": int(idx),
                "mu": float(mu),
                "sigma": float(sig),
                "signal_noise_ratio": float(snr),
            }
            for _, name, idx, mu, sig, snr in confident_pool[:k]
        ]

        return {
            "summary": {
                "parameter_groups": int(len(named_params)),
                "total_parameter_count": int(sum(item["count"] for item in summaries)),
                "prior_type": type(self.prior).__name__,
            },
            "parameter_summaries": summaries,
            "top_uncertain_parameters": top_uncertain,
            "top_confident_parameters": top_confident,
        }

    def analyze_posterior_distributions(
        self,
        quantiles: Sequence[float] = (0.1, 0.25, 0.5, 0.75, 0.9),
    ) -> dict[str, Any]:
        """输出各层后验分布统计，用于后验分布分析。"""
        q = np.asarray(list(quantiles), dtype=float)
        q = np.clip(q, 0.0, 1.0)
        if q.size == 0:
            q = np.asarray([0.5], dtype=float)

        layers: list[dict[str, Any]] = []
        all_mu: list[np.ndarray] = []
        all_sigma: list[np.ndarray] = []
        low_snr_ratios: list[float] = []
        for name, param in self._named_parameters():
            mu = np.asarray(param.mu, dtype=float).reshape(-1)
            sigma = np.asarray(param.sigma, dtype=float).reshape(-1)
            snr = np.abs(mu) / (sigma + 1e-8)
            low_snr_ratio = float(np.mean(snr < 1.0))
            low_snr_ratios.append(low_snr_ratio)
            all_mu.append(mu)
            all_sigma.append(sigma)
            layers.append(
                {
                    "parameter": name,
                    "count": int(mu.size),
                    "mu_quantiles": {f"q{int(v * 100):02d}": float(np.quantile(mu, v)) for v in q.tolist()},
                    "sigma_quantiles": {f"q{int(v * 100):02d}": float(np.quantile(sigma, v)) for v in q.tolist()},
                    "sigma_mean": float(np.mean(sigma)),
                    "sigma_std": float(np.std(sigma)),
                    "low_snr_ratio": low_snr_ratio,
                }
            )

        mu_all = np.concatenate(all_mu) if all_mu else np.zeros((0,), dtype=float)
        sigma_all = np.concatenate(all_sigma) if all_sigma else np.zeros((0,), dtype=float)
        return {
            "summary": {
                "parameter_groups": int(len(layers)),
                "global_mu_mean": float(np.mean(mu_all)) if mu_all.size else 0.0,
                "global_mu_std": float(np.std(mu_all)) if mu_all.size else 0.0,
                "global_sigma_mean": float(np.mean(sigma_all)) if sigma_all.size else 0.0,
                "global_sigma_std": float(np.std(sigma_all)) if sigma_all.size else 0.0,
                "mean_low_snr_ratio": float(np.mean(low_snr_ratios)) if low_snr_ratios else 0.0,
            },
            "layers": layers,
            "quantiles": [float(v) for v in q.tolist()],
        }

    def analyze_epistemic_uncertainty(
        self,
        features: np.ndarray | list[list[float]],
        *,
        num_samples: int = 80,
        top_k: int = 8,
        temperature: float = 1.0,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        """输出认知不确定性分析。"""
        pre = self.preprocess_bnn_data(features, use_training_stats=use_training_stats)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        sampled_means, sampled_vars = self.sample_predict(x_scaled, num_samples=max(2, int(num_samples)), temperature=temperature)

        epistemic = np.var(sampled_means, axis=0)
        aleatoric = np.mean(sampled_vars, axis=0)
        total = np.maximum(epistemic + aleatoric, 1e-8)
        ratio = np.clip(epistemic / total, 0.0, 1.0)
        pred_mean = np.mean(sampled_means, axis=0)

        n = int(epistemic.size)
        k = min(max(1, int(top_k)), max(1, n))
        top_idx = np.argsort(epistemic)[::-1][:k] if n > 0 else np.asarray([], dtype=int)
        corr = float(np.corrcoef(epistemic, total)[0, 1]) if n >= 2 else 0.0
        if not np.isfinite(corr):
            corr = 0.0

        return {
            "summary": {
                "sample_count": int(n),
                "monte_carlo_samples": int(max(2, int(num_samples))),
                "mean_epistemic": float(np.mean(epistemic)) if n > 0 else 0.0,
                "mean_aleatoric": float(np.mean(aleatoric)) if n > 0 else 0.0,
                "mean_epistemic_ratio": float(np.mean(ratio)) if n > 0 else 0.0,
                "p90_epistemic": float(np.quantile(epistemic, 0.9)) if n > 0 else 0.0,
                "corr_epistemic_total": corr,
            },
            "top_epistemic_samples": [
                {
                    "sample_index": int(i),
                    "prediction_mean": float(pred_mean[int(i)]),
                    "epistemic": float(epistemic[int(i)]),
                    "aleatoric": float(aleatoric[int(i)]),
                    "total_variance": float(total[int(i)]),
                    "epistemic_ratio": float(ratio[int(i)]),
                }
                for i in top_idx.tolist()
            ],
            "distribution": {
                "epistemic": [float(v) for v in epistemic.tolist()],
                "aleatoric": [float(v) for v in aleatoric.tolist()],
                "epistemic_ratio": [float(v) for v in ratio.tolist()],
            },
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }
