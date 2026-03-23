"""贝叶斯神经网络（BNN）不确定性量化实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

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
