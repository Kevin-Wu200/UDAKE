"""强化学习采样智能体：PPO / DQN / A2C(A3C)。"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np


def _softmax(logits: np.ndarray) -> np.ndarray:
    x = np.asarray(logits, dtype=float)
    x = x - np.max(x)
    exp = np.exp(x)
    return exp / (np.sum(exp) + 1e-12)


def _softmax_batch(logits: np.ndarray) -> np.ndarray:
    x = np.asarray(logits, dtype=float)
    if x.ndim == 1:
        return _softmax(x).reshape(1, -1)
    x = x - np.max(x, axis=1, keepdims=True)
    exp = np.exp(x)
    return exp / (np.sum(exp, axis=1, keepdims=True) + 1e-12)


def _array_digest(arr: np.ndarray) -> str:
    x = np.ascontiguousarray(np.asarray(arr, dtype=float))
    h = hashlib.sha256()
    h.update(str(tuple(int(v) for v in x.shape)).encode("utf-8"))
    h.update(x.tobytes())
    return h.hexdigest()


def flatten_observation(obs: dict[str, np.ndarray]) -> np.ndarray:
    order = ["sampling_distribution", "uncertainty_map", "sampled_values", "spatial_features", "boundary_info"]
    parts = [np.asarray(obs.get(k, np.array([])), dtype=float).reshape(-1) for k in order]
    vec = np.concatenate(parts, axis=0)
    if vec.size == 0:
        return np.zeros((1,), dtype=float)
    return vec


@dataclass
class PPOConfig:
    learning_rate: float = 0.02
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_ratio: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    grad_clip: float = 1.0
    update_epochs: int = 4


class PPOAgent:
    """轻量 PPO：线性 Actor-Critic + GAE + Clipped Surrogate。"""

    def __init__(self, action_dim: int, config: PPOConfig | None = None, seed: int = 42) -> None:
        self.config = config or PPOConfig()
        self.action_dim = int(max(2, action_dim))
        self.rng = np.random.default_rng(seed)

        self.actor_w: np.ndarray | None = None
        self.actor_b: np.ndarray | None = None
        self.critic_w: np.ndarray | None = None
        self.critic_b = 0.0

        self.trajectory: list[dict[str, Any]] = []
        self.preprocess_mean: np.ndarray | None = None
        self.preprocess_std: np.ndarray | None = None
        self._inference_cache: dict[str, dict[str, Any]] = {}
        self._inference_cache_size = 16

    def _invalidate_inference_cache(self) -> None:
        self._inference_cache.clear()

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        found = self._inference_cache.get(key)
        if found is None:
            return None
        # LRU refresh
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = found
        return found

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = value
        if len(self._inference_cache) > int(self._inference_cache_size):
            oldest = next(iter(self._inference_cache.keys()))
            self._inference_cache.pop(oldest, None)

    def _ensure_params(self, state_dim: int) -> None:
        if self.actor_w is None:
            scale = 1.0 / np.sqrt(max(1, state_dim))
            self.actor_w = self.rng.normal(0.0, scale, size=(state_dim, self.action_dim))
            self.actor_b = np.zeros((self.action_dim,), dtype=float)
            self.critic_w = self.rng.normal(0.0, scale, size=(state_dim,),)
            self.critic_b = 0.0
            self._invalidate_inference_cache()

    def _policy(self, state_vec: np.ndarray) -> np.ndarray:
        logits = state_vec @ self.actor_w + self.actor_b  # type: ignore[operator]
        return _softmax(logits)

    def value(self, observation: dict[str, np.ndarray]) -> float:
        state = flatten_observation(observation)
        self._ensure_params(len(state))
        return float(state @ self.critic_w + self.critic_b)  # type: ignore[operator]

    def select_action(self, observation: dict[str, np.ndarray], deterministic: bool = False) -> tuple[int, float, float]:
        state = flatten_observation(observation)
        self._ensure_params(len(state))
        probs = self._policy(state)
        if deterministic:
            action = int(np.argmax(probs))
        else:
            action = int(self.rng.choice(np.arange(self.action_dim), p=probs))
        log_prob = float(np.log(probs[action] + 1e-12))
        value = float(state @ self.critic_w + self.critic_b)  # type: ignore[operator]
        return action, log_prob, value

    def store_transition(
        self,
        observation: dict[str, np.ndarray],
        action: int,
        reward: float,
        done: bool,
        log_prob: float,
        value: float,
    ) -> None:
        self.trajectory.append(
            {
                "state": flatten_observation(observation),
                "action": int(action),
                "reward": float(reward),
                "done": bool(done),
                "log_prob": float(log_prob),
                "value": float(value),
            }
        )

    def _gae(self, last_value: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        rewards = np.asarray([x["reward"] for x in self.trajectory], dtype=float)
        values = np.asarray([x["value"] for x in self.trajectory] + [last_value], dtype=float)
        dones = np.asarray([x["done"] for x in self.trajectory], dtype=float)

        advantages = np.zeros_like(rewards)
        gae = 0.0
        for t in reversed(range(len(rewards))):
            delta = rewards[t] + self.config.gamma * values[t + 1] * (1.0 - dones[t]) - values[t]
            gae = delta + self.config.gamma * self.config.gae_lambda * (1.0 - dones[t]) * gae
            advantages[t] = gae
        returns = advantages + values[:-1]
        return advantages, returns

    def update(self, last_value: float = 0.0) -> dict[str, float]:
        if not self.trajectory:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        states = np.stack([x["state"] for x in self.trajectory], axis=0)
        actions = np.asarray([x["action"] for x in self.trajectory], dtype=int)
        old_log_probs = np.asarray([x["log_prob"] for x in self.trajectory], dtype=float)

        advantages, returns = self._gae(last_value=last_value)
        adv_std = np.std(advantages) + 1e-8
        advantages = (advantages - np.mean(advantages)) / adv_std

        policy_loss_value = 0.0
        value_loss_value = 0.0
        entropy_value = 0.0

        for _ in range(self.config.update_epochs):
            logits = states @ self.actor_w + self.actor_b  # type: ignore[operator]
            logits -= np.max(logits, axis=1, keepdims=True)
            probs = np.exp(logits)
            probs /= np.sum(probs, axis=1, keepdims=True) + 1e-12

            chosen_probs = probs[np.arange(len(actions)), actions]
            new_log_probs = np.log(chosen_probs + 1e-12)
            ratio = np.exp(new_log_probs - old_log_probs)
            ratio_clipped = np.clip(ratio, 1.0 - self.config.clip_ratio, 1.0 + self.config.clip_ratio)

            surrogate_1 = ratio * advantages
            surrogate_2 = ratio_clipped * advantages
            surrogate = np.minimum(surrogate_1, surrogate_2)
            policy_loss = -float(np.mean(surrogate))

            entropy = -float(np.mean(np.sum(probs * np.log(probs + 1e-12), axis=1)))

            values_pred = states @ self.critic_w + self.critic_b  # type: ignore[operator]
            td_error = values_pred - returns
            value_loss = float(np.mean(td_error ** 2))

            # Actor gradient（线性 softmax 近似）
            grad_logits = probs.copy()
            grad_logits[np.arange(len(actions)), actions] -= 1.0
            weight = -(ratio_clipped * advantages)
            grad_logits *= weight[:, None] / len(actions)

            grad_actor_w = states.T @ grad_logits
            grad_actor_b = np.sum(grad_logits, axis=0)

            # Critic gradient
            grad_critic_w = states.T @ td_error / len(actions)
            grad_critic_b = float(np.mean(td_error))

            # 梯度裁剪
            actor_norm = float(np.linalg.norm(grad_actor_w)) + 1e-8
            critic_norm = float(np.linalg.norm(grad_critic_w)) + 1e-8
            actor_scale = min(1.0, self.config.grad_clip / actor_norm)
            critic_scale = min(1.0, self.config.grad_clip / critic_norm)

            self.actor_w -= self.config.learning_rate * actor_scale * grad_actor_w
            self.actor_b -= self.config.learning_rate * actor_scale * grad_actor_b

            self.critic_w -= self.config.learning_rate * self.config.value_coef * critic_scale * grad_critic_w
            self.critic_b -= self.config.learning_rate * self.config.value_coef * critic_scale * grad_critic_b

            # 熵奖励（鼓励探索）
            self.actor_b += self.config.learning_rate * self.config.entropy_coef * np.mean(probs - 1.0 / self.action_dim, axis=0)

            policy_loss_value = policy_loss
            value_loss_value = value_loss
            entropy_value = entropy

        self.trajectory.clear()
        self._invalidate_inference_cache()
        return {
            "policy_loss": float(policy_loss_value),
            "value_loss": float(value_loss_value),
            "entropy": float(entropy_value),
        }

    def save(self, path: str) -> None:
        if self.actor_w is None or self.actor_b is None or self.critic_w is None:
            raise ValueError("模型尚未初始化")
        np.savez(
            path,
            actor_w=self.actor_w,
            actor_b=self.actor_b,
            critic_w=self.critic_w,
            critic_b=np.array([self.critic_b], dtype=float),
            preprocess_mean=np.asarray(self.preprocess_mean if self.preprocess_mean is not None else np.array([], dtype=float), dtype=float),
            preprocess_std=np.asarray(self.preprocess_std if self.preprocess_std is not None else np.array([], dtype=float), dtype=float),
        )

    def load(self, path: str) -> None:
        data = np.load(path)
        self.actor_w = np.asarray(data["actor_w"], dtype=float)
        self.actor_b = np.asarray(data["actor_b"], dtype=float)
        self.critic_w = np.asarray(data["critic_w"], dtype=float)
        self.critic_b = float(np.asarray(data["critic_b"], dtype=float).reshape(-1)[0])
        if "preprocess_mean" in data and "preprocess_std" in data:
            loaded_mean = np.asarray(data["preprocess_mean"], dtype=float).reshape(-1)
            loaded_std = np.asarray(data["preprocess_std"], dtype=float).reshape(-1)
            if loaded_mean.size > 0 and loaded_std.size > 0 and loaded_mean.shape == loaded_std.shape:
                self.preprocess_mean = loaded_mean
                self.preprocess_std = np.where(loaded_std < 1e-8, 1.0, loaded_std)
        self._invalidate_inference_cache()

    def preprocess_ppo_data(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        if isinstance(observations, np.ndarray):
            raw = np.asarray(observations, dtype=float)
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)
        else:
            if not observations:
                raise ValueError("observations 不能为空")
            rows = [flatten_observation(obs).astype(float).reshape(-1) for obs in observations]
            dim = int(rows[0].shape[0])
            for i, row in enumerate(rows[1:], start=1):
                if int(row.shape[0]) != dim:
                    raise ValueError(f"第{i}条观测维度不一致: {int(row.shape[0])} != {dim}")
            raw = np.stack(rows, axis=0)

        if raw.ndim != 2 or raw.shape[0] == 0 or raw.shape[1] == 0:
            raise ValueError("observations 必须可转换为二维特征矩阵")

        mean_runtime = np.mean(raw, axis=0)
        std_runtime = np.std(raw, axis=0)
        std_runtime = np.where(std_runtime < 1e-8, 1.0, std_runtime)

        scaler_source = "runtime"
        mean = mean_runtime
        std = std_runtime
        if use_training_stats and self.preprocess_mean is not None and self.preprocess_std is not None:
            if self.preprocess_mean.shape == mean_runtime.shape and self.preprocess_std.shape == std_runtime.shape:
                mean = self.preprocess_mean
                std = np.where(self.preprocess_std < 1e-8, 1.0, self.preprocess_std)
                scaler_source = "trained"
            else:
                scaler_source = "runtime_fallback"
        elif use_training_stats and (self.preprocess_mean is not None or self.preprocess_std is not None):
            scaler_source = "runtime_fallback"

        if self.preprocess_mean is None or self.preprocess_std is None:
            self.preprocess_mean = mean_runtime
            self.preprocess_std = std_runtime

        scaled = (raw - mean) / std
        feature_names = [f"state_feature_{i}" for i in range(raw.shape[1])]
        return {
            "raw_features": raw,
            "processed_features": scaled,
            "feature_names": feature_names,
            "scaler": {
                "source": scaler_source,
                "mean": mean.tolist(),
                "std": std.tolist(),
            },
            "validation": {
                "is_valid": True,
                "n_samples": int(raw.shape[0]),
                "feature_dim": int(raw.shape[1]),
                "zero_variance_feature_indices": np.where(np.std(raw, axis=0) < 1e-8)[0].astype(int).tolist(),
            },
        }

    def predict_ppo(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        pre = self.preprocess_ppo_data(observations, use_training_stats=True)
        raw = np.asarray(pre["raw_features"], dtype=float)
        self._ensure_params(int(raw.shape[1]))
        cache_key = ""
        if deterministic:
            cache_key = f"ppo_predict:{_array_digest(raw)}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                out = dict(cached)
                perf = dict(out.get("performance", {}))
                perf["cache_hit"] = True
                perf["latency_ms"] = float((time.perf_counter() - start) * 1000.0)
                out["performance"] = perf
                return out

        policy_start = time.perf_counter()
        logits = raw @ self.actor_w + self.actor_b  # type: ignore[operator]
        probs_matrix = _softmax_batch(logits)
        policy_inference_ms = float((time.perf_counter() - policy_start) * 1000.0)

        if deterministic:
            actions_arr = np.argmax(probs_matrix, axis=1).astype(int)
        else:
            actions_arr = np.asarray(
                [int(self.rng.choice(np.arange(self.action_dim), p=p)) for p in probs_matrix],
                dtype=int,
            )

        value_start = time.perf_counter()
        values_arr = raw @ self.critic_w + self.critic_b  # type: ignore[operator]
        value_inference_ms = float((time.perf_counter() - value_start) * 1000.0)

        selected_probs = probs_matrix[np.arange(probs_matrix.shape[0]), actions_arr]
        entropy_arr = -np.sum(probs_matrix * np.log(probs_matrix + 1e-12), axis=1)

        actions = [int(x) for x in actions_arr.tolist()]
        action_probs = [float(x) for x in selected_probs.tolist()]
        values = [float(x) for x in np.asarray(values_arr, dtype=float).reshape(-1).tolist()]
        entropies = [float(x) for x in np.asarray(entropy_arr, dtype=float).reshape(-1).tolist()]
        policy_matrix = [[float(v) for v in row] for row in probs_matrix.tolist()]

        result = {
            "action_indices": actions,
            "selected_action_probabilities": action_probs,
            "state_values": values,
            "policy_entropy": entropies,
            "action_probabilities": policy_matrix,
            "prediction": {
                "action_indices": actions,
                "selected_action_probabilities": action_probs,
                "state_values": values,
            },
            "preprocess": {
                "scaler": pre["scaler"],
                "validation": pre["validation"],
                "feature_names": pre["feature_names"],
            },
            "performance": {
                "cache_hit": False,
                "policy_inference_ms": policy_inference_ms,
                "value_inference_ms": value_inference_ms,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
            },
        }
        if deterministic and cache_key:
            self._cache_set(cache_key, result)
        return result


class PrioritizedReplayBuffer:
    """优先经验回放（PER）循环缓冲区。"""

    def __init__(self, capacity: int = 2000, alpha: float = 0.6, seed: int = 42) -> None:
        self.capacity = int(max(1, capacity))
        self.alpha = float(np.clip(alpha, 0.0, 1.0))
        self.rng = np.random.default_rng(seed)
        self.data: list[dict[str, Any]] = []
        self.priorities: list[float] = []
        self.ptr = 0

    def __len__(self) -> int:
        return len(self.data)

    def add(self, transition: dict[str, Any], priority: float | None = None) -> None:
        p = float(max(priority or 1.0, 1e-6))
        if len(self.data) < self.capacity:
            self.data.append(transition)
            self.priorities.append(p)
        else:
            self.data[self.ptr] = transition
            self.priorities[self.ptr] = p
            self.ptr = (self.ptr + 1) % self.capacity

    def sample(self, batch_size: int, beta: float = 0.4) -> tuple[list[dict[str, Any]], np.ndarray, np.ndarray]:
        if not self.data:
            return [], np.array([], dtype=int), np.array([], dtype=float)

        probs = np.asarray(self.priorities, dtype=float) ** self.alpha
        probs = probs / (np.sum(probs) + 1e-12)

        size = min(int(max(1, batch_size)), len(self.data))
        idx = self.rng.choice(np.arange(len(self.data)), size=size, replace=False, p=probs)

        samples = [self.data[int(i)] for i in idx]
        weights = (len(self.data) * probs[idx]) ** (-beta)
        weights = weights / (np.max(weights) + 1e-12)
        return samples, idx.astype(int), weights.astype(float)

    def update_priorities(self, indices: np.ndarray, priorities: np.ndarray) -> None:
        for i, p in zip(indices, priorities):
            self.priorities[int(i)] = float(max(float(p), 1e-6))


@dataclass
class DQNConfig:
    learning_rate: float = 0.02
    gamma: float = 0.98
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay: float = 0.995
    batch_size: int = 32
    target_update_interval: int = 30
    soft_tau: float = 0.05
    exploration: Literal["epsilon_greedy", "boltzmann", "ucb"] = "epsilon_greedy"
    network_type: Literal["dqn", "graph", "dueling"] = "dueling"


class DQNAgent:
    """DQN / 图卷积Q近似 / Dueling DQN（线性轻量实现）。"""

    def __init__(self, action_dim: int, config: DQNConfig | None = None, seed: int = 42) -> None:
        self.config = config or DQNConfig()
        self.action_dim = int(max(2, action_dim))
        self.rng = np.random.default_rng(seed)
        self.buffer = PrioritizedReplayBuffer(capacity=3000, seed=seed)

        self.w: np.ndarray | None = None
        self.b: np.ndarray | None = None
        self.target_w: np.ndarray | None = None
        self.target_b: np.ndarray | None = None

        self.v_w: np.ndarray | None = None
        self.v_b: float = 0.0
        self.target_v_w: np.ndarray | None = None
        self.target_v_b: float = 0.0

        self.epsilon = float(self.config.epsilon_start)
        self.step_counter = 0
        self.action_visit = np.zeros((self.action_dim,), dtype=float)
        self.preprocess_mean: np.ndarray | None = None
        self.preprocess_std: np.ndarray | None = None
        self._inference_cache: dict[str, dict[str, Any]] = {}
        self._inference_cache_size = 16

    def _invalidate_inference_cache(self) -> None:
        self._inference_cache.clear()

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        found = self._inference_cache.get(key)
        if found is None:
            return None
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = found
        return found

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = value
        if len(self._inference_cache) > int(self._inference_cache_size):
            oldest = next(iter(self._inference_cache.keys()))
            self._inference_cache.pop(oldest, None)

    def _ensure_params(self, state_dim: int) -> None:
        if self.w is not None:
            return
        scale = 1.0 / np.sqrt(max(1, state_dim))
        self.w = self.rng.normal(0.0, scale, size=(state_dim, self.action_dim))
        self.b = np.zeros((self.action_dim,), dtype=float)
        self.target_w = self.w.copy()
        self.target_b = self.b.copy()

        self.v_w = self.rng.normal(0.0, scale, size=(state_dim,))
        self.target_v_w = self.v_w.copy()
        self.v_b = 0.0
        self.target_v_b = 0.0
        self._invalidate_inference_cache()

    def _q_values(self, state: np.ndarray, target: bool = False) -> np.ndarray:
        if target:
            w = self.target_w
            b = self.target_b
            vw = self.target_v_w
            vb = self.target_v_b
        else:
            w = self.w
            b = self.b
            vw = self.v_w
            vb = self.v_b

        adv = state @ w + b
        if self.config.network_type == "dueling":
            v = float(state @ vw + vb)
            return v + (adv - np.mean(adv))
        return adv

    def select_action(self, observation: dict[str, np.ndarray], deterministic: bool = False) -> int:
        state = flatten_observation(observation)
        self._ensure_params(len(state))
        q = self._q_values(state, target=False)

        if deterministic:
            action = int(np.argmax(q))
        else:
            if self.config.exploration == "epsilon_greedy":
                if self.rng.random() < self.epsilon:
                    action = int(self.rng.integers(0, self.action_dim))
                else:
                    action = int(np.argmax(q))
            elif self.config.exploration == "boltzmann":
                temp = max(0.1, self.epsilon)
                probs = _softmax(q / temp)
                action = int(self.rng.choice(np.arange(self.action_dim), p=probs))
            else:  # ucb
                total = np.sum(self.action_visit) + 1.0
                bonus = np.sqrt(np.log(total + 1.0) / (self.action_visit + 1.0))
                action = int(np.argmax(q + 0.4 * bonus))

        self.action_visit[action] += 1.0
        return action

    def store_transition(
        self,
        observation: dict[str, np.ndarray],
        action: int,
        reward: float,
        next_observation: dict[str, np.ndarray],
        done: bool,
    ) -> None:
        tr = {
            "state": flatten_observation(observation),
            "action": int(action),
            "reward": float(reward),
            "next_state": flatten_observation(next_observation),
            "done": bool(done),
        }
        self.buffer.add(tr, priority=1.0)

    def train_step(self, beta: float = 0.4) -> dict[str, float]:
        if len(self.buffer) < 4:
            return {"loss": 0.0, "td_error": 0.0, "epsilon": float(self.epsilon)}

        samples, idx, weights = self.buffer.sample(self.config.batch_size, beta=beta)
        if not samples:
            return {"loss": 0.0, "td_error": 0.0, "epsilon": float(self.epsilon)}

        states = np.stack([s["state"] for s in samples], axis=0)
        actions = np.asarray([s["action"] for s in samples], dtype=int)
        rewards = np.asarray([s["reward"] for s in samples], dtype=float)
        next_states = np.stack([s["next_state"] for s in samples], axis=0)
        dones = np.asarray([s["done"] for s in samples], dtype=float)

        self._ensure_params(states.shape[1])

        q_now = states @ self.w + self.b
        if self.config.network_type == "dueling":
            v_now = states @ self.v_w + self.v_b
            q_now = v_now[:, None] + (q_now - np.mean(q_now, axis=1, keepdims=True))

        q_next_t = next_states @ self.target_w + self.target_b
        if self.config.network_type == "dueling":
            v_next_t = next_states @ self.target_v_w + self.target_v_b
            q_next_t = v_next_t[:, None] + (q_next_t - np.mean(q_next_t, axis=1, keepdims=True))

        target = rewards + self.config.gamma * (1.0 - dones) * np.max(q_next_t, axis=1)
        q_sa = q_now[np.arange(len(actions)), actions]
        td = q_sa - target

        loss_vec = 0.5 * (td ** 2) * weights
        loss = float(np.mean(loss_vec))

        grad = td * weights / len(actions)
        grad_w = np.zeros_like(self.w)
        grad_b = np.zeros_like(self.b)
        for i, a in enumerate(actions):
            grad_w[:, a] += states[i] * grad[i]
            grad_b[a] += grad[i]

        self.w -= self.config.learning_rate * grad_w
        self.b -= self.config.learning_rate * grad_b

        if self.config.network_type == "dueling":
            grad_v = grad
            grad_v_w = states.T @ grad_v
            grad_v_b = float(np.sum(grad_v))
            self.v_w -= self.config.learning_rate * grad_v_w
            self.v_b -= self.config.learning_rate * grad_v_b

        self.buffer.update_priorities(idx, np.abs(td) + 1e-4)

        self.step_counter += 1
        if self.step_counter % self.config.target_update_interval == 0:
            self.target_w = self.w.copy()
            self.target_b = self.b.copy()
            self.target_v_w = self.v_w.copy()
            self.target_v_b = self.v_b
        else:
            tau = self.config.soft_tau
            self.target_w = (1.0 - tau) * self.target_w + tau * self.w
            self.target_b = (1.0 - tau) * self.target_b + tau * self.b
            self.target_v_w = (1.0 - tau) * self.target_v_w + tau * self.v_w
            self.target_v_b = (1.0 - tau) * self.target_v_b + tau * self.v_b

        self.epsilon = max(self.config.epsilon_end, self.epsilon * self.config.epsilon_decay)
        self._invalidate_inference_cache()

        return {
            "loss": loss,
            "td_error": float(np.mean(np.abs(td))),
            "epsilon": float(self.epsilon),
        }

    def save(self, path: str) -> None:
        if self.w is None or self.b is None:
            raise ValueError("模型尚未初始化")
        np.savez(
            path,
            w=self.w,
            b=self.b,
            target_w=self.target_w,
            target_b=self.target_b,
            v_w=self.v_w,
            v_b=np.array([self.v_b], dtype=float),
            target_v_w=self.target_v_w,
            target_v_b=np.array([self.target_v_b], dtype=float),
            epsilon=np.array([self.epsilon], dtype=float),
            preprocess_mean=np.asarray(self.preprocess_mean if self.preprocess_mean is not None else np.array([], dtype=float), dtype=float),
            preprocess_std=np.asarray(self.preprocess_std if self.preprocess_std is not None else np.array([], dtype=float), dtype=float),
        )

    def load(self, path: str) -> None:
        data = np.load(path)
        self.w = np.asarray(data["w"], dtype=float)
        self.b = np.asarray(data["b"], dtype=float)
        self.target_w = np.asarray(data["target_w"], dtype=float)
        self.target_b = np.asarray(data["target_b"], dtype=float)
        self.v_w = np.asarray(data["v_w"], dtype=float)
        self.v_b = float(np.asarray(data["v_b"], dtype=float).reshape(-1)[0])
        self.target_v_w = np.asarray(data["target_v_w"], dtype=float)
        self.target_v_b = float(np.asarray(data["target_v_b"], dtype=float).reshape(-1)[0])
        self.epsilon = float(np.asarray(data["epsilon"], dtype=float).reshape(-1)[0])
        if "preprocess_mean" in data and "preprocess_std" in data:
            loaded_mean = np.asarray(data["preprocess_mean"], dtype=float).reshape(-1)
            loaded_std = np.asarray(data["preprocess_std"], dtype=float).reshape(-1)
            if loaded_mean.size > 0 and loaded_std.size > 0 and loaded_mean.shape == loaded_std.shape:
                self.preprocess_mean = loaded_mean
                self.preprocess_std = np.where(loaded_std < 1e-8, 1.0, loaded_std)
        self._invalidate_inference_cache()

    def preprocess_dqn_data(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        if isinstance(observations, np.ndarray):
            raw = np.asarray(observations, dtype=float)
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)
        else:
            if not observations:
                raise ValueError("observations 不能为空")
            rows = [flatten_observation(obs).astype(float).reshape(-1) for obs in observations]
            dim = int(rows[0].shape[0])
            for i, row in enumerate(rows[1:], start=1):
                if int(row.shape[0]) != dim:
                    raise ValueError(f"第{i}条观测维度不一致: {int(row.shape[0])} != {dim}")
            raw = np.stack(rows, axis=0)

        if raw.ndim != 2 or raw.shape[0] == 0 or raw.shape[1] == 0:
            raise ValueError("observations 必须可转换为二维特征矩阵")

        mean_runtime = np.mean(raw, axis=0)
        std_runtime = np.std(raw, axis=0)
        std_runtime = np.where(std_runtime < 1e-8, 1.0, std_runtime)

        scaler_source = "runtime"
        mean = mean_runtime
        std = std_runtime
        if use_training_stats and self.preprocess_mean is not None and self.preprocess_std is not None:
            if self.preprocess_mean.shape == mean_runtime.shape and self.preprocess_std.shape == std_runtime.shape:
                mean = self.preprocess_mean
                std = np.where(self.preprocess_std < 1e-8, 1.0, self.preprocess_std)
                scaler_source = "trained"
            else:
                scaler_source = "runtime_fallback"
        elif use_training_stats and (self.preprocess_mean is not None or self.preprocess_std is not None):
            scaler_source = "runtime_fallback"

        if self.preprocess_mean is None or self.preprocess_std is None:
            self.preprocess_mean = mean_runtime
            self.preprocess_std = std_runtime

        scaled = (raw - mean) / std
        feature_names = [f"state_feature_{i}" for i in range(raw.shape[1])]
        return {
            "raw_features": raw,
            "processed_features": scaled,
            "feature_names": feature_names,
            "scaler": {
                "source": scaler_source,
                "mean": mean.tolist(),
                "std": std.tolist(),
            },
            "validation": {
                "is_valid": True,
                "n_samples": int(raw.shape[0]),
                "feature_dim": int(raw.shape[1]),
                "zero_variance_feature_indices": np.where(np.std(raw, axis=0) < 1e-8)[0].astype(int).tolist(),
            },
        }

    def predict_dqn(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        pre = self.preprocess_dqn_data(observations, use_training_stats=True)
        raw = np.asarray(pre["raw_features"], dtype=float)
        self._ensure_params(int(raw.shape[1]))
        cache_key = ""
        if deterministic:
            cache_key = f"dqn_predict:{self.config.network_type}:{_array_digest(raw)}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                out = dict(cached)
                perf = dict(out.get("performance", {}))
                perf["cache_hit"] = True
                perf["latency_ms"] = float((time.perf_counter() - start) * 1000.0)
                out["performance"] = perf
                return out

        policy_start = time.perf_counter()
        q = raw @ self.w + self.b  # type: ignore[operator]
        if self.config.network_type == "dueling":
            v = (raw @ self.v_w + self.v_b).reshape(-1, 1)  # type: ignore[operator]
            q = v + (q - np.mean(q, axis=1, keepdims=True))
        policy_inference_ms = float((time.perf_counter() - policy_start) * 1000.0)

        temp = max(0.1, float(self.epsilon))
        probs_matrix = _softmax_batch(q / temp)
        if deterministic:
            actions_arr = np.argmax(q, axis=1).astype(int)
        else:
            actions_arr = np.asarray(
                [int(self.rng.choice(np.arange(self.action_dim), p=p)) for p in probs_matrix],
                dtype=int,
            )

        value_start = time.perf_counter()
        selected_q_arr = q[np.arange(q.shape[0]), actions_arr]
        max_q_arr = np.max(q, axis=1)
        value_inference_ms = float((time.perf_counter() - value_start) * 1000.0)

        actions = [int(x) for x in actions_arr.tolist()]
        selected_q_values = [float(x) for x in selected_q_arr.tolist()]
        max_q_values = [float(x) for x in max_q_arr.tolist()]
        q_matrix = [[float(v) for v in row] for row in q.tolist()]
        action_probabilities = [[float(v) for v in row] for row in probs_matrix.tolist()]

        result = {
            "action_indices": actions,
            "selected_q_values": selected_q_values,
            "max_q_values": max_q_values,
            "q_values": q_matrix,
            "action_probabilities": action_probabilities,
            "prediction": {
                "action_indices": actions,
                "selected_q_values": selected_q_values,
                "max_q_values": max_q_values,
            },
            "preprocess": {
                "scaler": pre["scaler"],
                "validation": pre["validation"],
                "feature_names": pre["feature_names"],
            },
            "performance": {
                "cache_hit": False,
                "policy_inference_ms": policy_inference_ms,
                "value_inference_ms": value_inference_ms,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
            },
        }
        if deterministic and cache_key:
            self._cache_set(cache_key, result)
        return result


@dataclass
class A2CConfig:
    learning_rate_actor: float = 0.02
    learning_rate_critic: float = 0.02
    gamma: float = 0.98
    entropy_coef: float = 0.01
    grad_clip: float = 1.0
    async_workers: int = 2


class ActorCriticAgent:
    """A2C/A3C 统一实现。"""

    def __init__(self, action_dim: int, config: A2CConfig | None = None, seed: int = 42) -> None:
        self.config = config or A2CConfig()
        self.action_dim = int(max(2, action_dim))
        self.rng = np.random.default_rng(seed)

        self.actor_w: np.ndarray | None = None
        self.actor_b: np.ndarray | None = None
        self.critic_w: np.ndarray | None = None
        self.critic_b = 0.0

        self.buffer: list[dict[str, Any]] = []
        self.preprocess_mean: np.ndarray | None = None
        self.preprocess_std: np.ndarray | None = None
        self._inference_cache: dict[str, dict[str, Any]] = {}
        self._inference_cache_size = 16

    def _invalidate_inference_cache(self) -> None:
        self._inference_cache.clear()

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        found = self._inference_cache.get(key)
        if found is None:
            return None
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = found
        return found

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        self._inference_cache.pop(key, None)
        self._inference_cache[key] = value
        if len(self._inference_cache) > int(self._inference_cache_size):
            oldest = next(iter(self._inference_cache.keys()))
            self._inference_cache.pop(oldest, None)

    def _ensure_params(self, state_dim: int) -> None:
        if self.actor_w is not None:
            return
        scale = 1.0 / np.sqrt(max(1, state_dim))
        self.actor_w = self.rng.normal(0.0, scale, size=(state_dim, self.action_dim))
        self.actor_b = np.zeros((self.action_dim,), dtype=float)
        self.critic_w = self.rng.normal(0.0, scale, size=(state_dim,))
        self.critic_b = 0.0
        self._invalidate_inference_cache()

    def select_action(self, observation: dict[str, np.ndarray], deterministic: bool = False) -> tuple[int, float]:
        state = flatten_observation(observation)
        self._ensure_params(len(state))

        probs = _softmax(state @ self.actor_w + self.actor_b)
        action = int(np.argmax(probs)) if deterministic else int(self.rng.choice(np.arange(self.action_dim), p=probs))
        value = float(state @ self.critic_w + self.critic_b)
        return action, value

    def store_transition(self, observation: dict[str, np.ndarray], action: int, reward: float, done: bool, value: float) -> None:
        self.buffer.append(
            {
                "state": flatten_observation(observation),
                "action": int(action),
                "reward": float(reward),
                "done": bool(done),
                "value": float(value),
            }
        )

    def _returns_advantages(self) -> tuple[np.ndarray, np.ndarray]:
        rewards = np.asarray([x["reward"] for x in self.buffer], dtype=float)
        values = np.asarray([x["value"] for x in self.buffer], dtype=float)
        dones = np.asarray([x["done"] for x in self.buffer], dtype=float)

        returns = np.zeros_like(rewards)
        ret = 0.0
        for t in reversed(range(len(rewards))):
            ret = rewards[t] + self.config.gamma * ret * (1.0 - dones[t])
            returns[t] = ret
        adv = returns - values
        return returns, adv

    def train_sync(self) -> dict[str, float]:
        if not self.buffer:
            return {"actor_loss": 0.0, "critic_loss": 0.0, "entropy": 0.0}

        states = np.stack([x["state"] for x in self.buffer], axis=0)
        actions = np.asarray([x["action"] for x in self.buffer], dtype=int)
        returns, advantages = self._returns_advantages()

        adv_std = np.std(advantages) + 1e-8
        advantages = (advantages - np.mean(advantages)) / adv_std

        logits = states @ self.actor_w + self.actor_b
        logits -= np.max(logits, axis=1, keepdims=True)
        probs = np.exp(logits)
        probs /= np.sum(probs, axis=1, keepdims=True) + 1e-12

        selected = probs[np.arange(len(actions)), actions]
        actor_loss = -float(np.mean(np.log(selected + 1e-12) * advantages))
        entropy = -float(np.mean(np.sum(probs * np.log(probs + 1e-12), axis=1)))

        values_pred = states @ self.critic_w + self.critic_b
        td = values_pred - returns
        critic_loss = float(np.mean(td ** 2))

        grad_logits = probs.copy()
        grad_logits[np.arange(len(actions)), actions] -= 1.0
        grad_logits *= -advantages[:, None] / len(actions)

        grad_actor_w = states.T @ grad_logits
        grad_actor_b = np.sum(grad_logits, axis=0)
        grad_critic_w = states.T @ td / len(actions)
        grad_critic_b = float(np.mean(td))

        actor_norm = float(np.linalg.norm(grad_actor_w)) + 1e-8
        critic_norm = float(np.linalg.norm(grad_critic_w)) + 1e-8
        actor_scale = min(1.0, self.config.grad_clip / actor_norm)
        critic_scale = min(1.0, self.config.grad_clip / critic_norm)

        self.actor_w -= self.config.learning_rate_actor * actor_scale * grad_actor_w
        self.actor_b -= self.config.learning_rate_actor * actor_scale * grad_actor_b
        self.actor_b += self.config.learning_rate_actor * self.config.entropy_coef * np.mean(probs - 1.0 / self.action_dim, axis=0)

        self.critic_w -= self.config.learning_rate_critic * critic_scale * grad_critic_w
        self.critic_b -= self.config.learning_rate_critic * critic_scale * grad_critic_b

        self.buffer.clear()
        self._invalidate_inference_cache()
        return {
            "actor_loss": actor_loss,
            "critic_loss": critic_loss,
            "entropy": entropy,
        }

    def train_async(self, episodes_results: list[list[dict[str, Any]]]) -> dict[str, float]:
        """A3C 风格：接收多个 worker 轨迹后同步更新全局参数。"""
        merged: list[dict[str, Any]] = []
        for trace in episodes_results:
            merged.extend(trace)
        self.buffer = merged
        out = self.train_sync()
        self._invalidate_inference_cache()
        return out

    def preprocess_a2c_data(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        if isinstance(observations, np.ndarray):
            raw = np.asarray(observations, dtype=float)
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)
        else:
            if not observations:
                raise ValueError("observations 不能为空")
            rows = [flatten_observation(obs).astype(float).reshape(-1) for obs in observations]
            dim = int(rows[0].shape[0])
            for i, row in enumerate(rows[1:], start=1):
                if int(row.shape[0]) != dim:
                    raise ValueError(f"第{i}条观测维度不一致: {int(row.shape[0])} != {dim}")
            raw = np.stack(rows, axis=0)

        if raw.ndim != 2 or raw.shape[0] == 0 or raw.shape[1] == 0:
            raise ValueError("observations 必须可转换为二维特征矩阵")

        mean_runtime = np.mean(raw, axis=0)
        std_runtime = np.std(raw, axis=0)
        std_runtime = np.where(std_runtime < 1e-8, 1.0, std_runtime)

        scaler_source = "runtime"
        mean = mean_runtime
        std = std_runtime
        if use_training_stats and self.preprocess_mean is not None and self.preprocess_std is not None:
            if self.preprocess_mean.shape == mean_runtime.shape and self.preprocess_std.shape == std_runtime.shape:
                mean = self.preprocess_mean
                std = np.where(self.preprocess_std < 1e-8, 1.0, self.preprocess_std)
                scaler_source = "trained"
            else:
                scaler_source = "runtime_fallback"
        elif use_training_stats and (self.preprocess_mean is not None or self.preprocess_std is not None):
            scaler_source = "runtime_fallback"

        if self.preprocess_mean is None or self.preprocess_std is None:
            self.preprocess_mean = mean_runtime
            self.preprocess_std = std_runtime

        scaled = (raw - mean) / std
        feature_names = [f"state_feature_{i}" for i in range(raw.shape[1])]
        return {
            "raw_features": raw,
            "processed_features": scaled,
            "feature_names": feature_names,
            "scaler": {
                "source": scaler_source,
                "mean": mean.tolist(),
                "std": std.tolist(),
            },
            "validation": {
                "is_valid": True,
                "n_samples": int(raw.shape[0]),
                "feature_dim": int(raw.shape[1]),
                "zero_variance_feature_indices": np.where(np.std(raw, axis=0) < 1e-8)[0].astype(int).tolist(),
            },
        }

    def predict_a2c(
        self,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        *,
        deterministic: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        pre = self.preprocess_a2c_data(observations, use_training_stats=True)
        raw = np.asarray(pre["raw_features"], dtype=float)
        self._ensure_params(int(raw.shape[1]))
        cache_key = ""
        if deterministic:
            cache_key = f"a2c_predict:{_array_digest(raw)}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                out = dict(cached)
                perf = dict(out.get("performance", {}))
                perf["cache_hit"] = True
                perf["latency_ms"] = float((time.perf_counter() - start) * 1000.0)
                out["performance"] = perf
                return out

        policy_start = time.perf_counter()
        logits = raw @ self.actor_w + self.actor_b  # type: ignore[operator]
        probs_matrix = _softmax_batch(logits)
        policy_inference_ms = float((time.perf_counter() - policy_start) * 1000.0)

        if deterministic:
            actions_arr = np.argmax(probs_matrix, axis=1).astype(int)
        else:
            actions_arr = np.asarray(
                [int(self.rng.choice(np.arange(self.action_dim), p=p)) for p in probs_matrix],
                dtype=int,
            )

        value_start = time.perf_counter()
        values_arr = raw @ self.critic_w + self.critic_b  # type: ignore[operator]
        value_inference_ms = float((time.perf_counter() - value_start) * 1000.0)

        selected_probs = probs_matrix[np.arange(probs_matrix.shape[0]), actions_arr]
        entropy_arr = -np.sum(probs_matrix * np.log(probs_matrix + 1e-12), axis=1)

        actions = [int(x) for x in actions_arr.tolist()]
        action_probs = [float(x) for x in selected_probs.tolist()]
        values = [float(x) for x in np.asarray(values_arr, dtype=float).reshape(-1).tolist()]
        entropies = [float(x) for x in np.asarray(entropy_arr, dtype=float).reshape(-1).tolist()]
        policy_matrix = [[float(v) for v in row] for row in probs_matrix.tolist()]

        result = {
            "action_indices": actions,
            "selected_action_probabilities": action_probs,
            "state_values": values,
            "policy_entropy": entropies,
            "action_probabilities": policy_matrix,
            "prediction": {
                "action_indices": actions,
                "selected_action_probabilities": action_probs,
                "state_values": values,
            },
            "preprocess": {
                "scaler": pre["scaler"],
                "validation": pre["validation"],
                "feature_names": pre["feature_names"],
            },
            "performance": {
                "cache_hit": False,
                "policy_inference_ms": policy_inference_ms,
                "value_inference_ms": value_inference_ms,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
            },
        }
        if deterministic and cache_key:
            self._cache_set(cache_key, result)
        return result

    def save(self, path: str) -> None:
        if self.actor_w is None or self.actor_b is None or self.critic_w is None:
            raise ValueError("模型尚未初始化")
        np.savez(
            path,
            actor_w=self.actor_w,
            actor_b=self.actor_b,
            critic_w=self.critic_w,
            critic_b=np.array([self.critic_b], dtype=float),
            preprocess_mean=np.asarray(self.preprocess_mean if self.preprocess_mean is not None else np.array([], dtype=float), dtype=float),
            preprocess_std=np.asarray(self.preprocess_std if self.preprocess_std is not None else np.array([], dtype=float), dtype=float),
        )

    def load(self, path: str) -> None:
        data = np.load(path)
        self.actor_w = np.asarray(data["actor_w"], dtype=float)
        self.actor_b = np.asarray(data["actor_b"], dtype=float)
        self.critic_w = np.asarray(data["critic_w"], dtype=float)
        self.critic_b = float(np.asarray(data["critic_b"], dtype=float).reshape(-1)[0])
        if "preprocess_mean" in data and "preprocess_std" in data:
            loaded_mean = np.asarray(data["preprocess_mean"], dtype=float).reshape(-1)
            loaded_std = np.asarray(data["preprocess_std"], dtype=float).reshape(-1)
            if loaded_mean.size > 0 and loaded_std.size > 0 and loaded_mean.shape == loaded_std.shape:
                self.preprocess_mean = loaded_mean
                self.preprocess_std = np.where(loaded_std < 1e-8, 1.0, loaded_std)
        self._invalidate_inference_cache()


def save_agent(agent: Any, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    agent.save(path)


def load_agent(agent: Any, path: str) -> Any:
    agent.load(path)
    return agent
