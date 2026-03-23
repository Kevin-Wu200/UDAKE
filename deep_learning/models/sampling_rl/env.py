"""强化学习采样环境（SamplingEnv）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .features import SamplingFeatureEngineer
from .rewards import (
    RewardComposer,
    RewardDebugger,
    RewardNormalizer,
    RewardWeights,
    boundary_constraint_penalty,
    budget_constraint_penalty,
    distance_constraint_penalty,
)

ActionMode = Literal["discrete", "continuous", "hybrid"]


@dataclass
class ActionSpace:
    mode: ActionMode
    grid_size: int
    boundary: tuple[float, float, float, float]
    max_sample_count: int = 3


class BaseEnv(ABC):
    """环境基类。"""

    @abstractmethod
    def reset(self) -> dict[str, np.ndarray]:
        raise NotImplementedError

    @abstractmethod
    def step(self, action: Any) -> tuple[dict[str, np.ndarray], float, bool, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def render(self) -> dict[str, Any]:
        raise NotImplementedError


class SamplingEnv(BaseEnv):
    """采样环境：支持离散/连续/混合动作，内置综合奖励函数。"""

    def __init__(
        self,
        uncertainty_map: np.ndarray,
        value_map: np.ndarray | None = None,
        boundary: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0),
        action_mode: ActionMode = "discrete",
        budget: int = 20,
        target_uncertainty: float = 0.15,
        max_steps: int = 40,
        sampling_cost: float = 0.03,
        min_distance: float = 0.05,
        reward_weights: RewardWeights | None = None,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.default_rng(seed)
        self.feature_engineer = SamplingFeatureEngineer()

        self.base_uncertainty = np.asarray(uncertainty_map, dtype=float)
        if self.base_uncertainty.ndim != 2:
            raise ValueError("uncertainty_map 必须为二维")

        self.h, self.w = self.base_uncertainty.shape
        self.boundary = boundary
        self.action_mode = action_mode
        self.action_space = ActionSpace(
            mode=action_mode,
            grid_size=int(self.h * self.w),
            boundary=boundary,
            max_sample_count=3,
        )

        self.budget = int(max(1, budget))
        self.target_uncertainty = float(np.clip(target_uncertainty, 1e-6, 1.0))
        self.max_steps = int(max(1, max_steps))
        self.sampling_cost = float(max(1e-8, sampling_cost))
        self.min_distance = float(max(0.0, min_distance))

        self.reward_composer = RewardComposer(
            weights=reward_weights or RewardWeights(),
            normalizer=RewardNormalizer(momentum=0.98),
        )
        self.reward_debugger = RewardDebugger()

        self.value_map = self._prepare_value_map(value_map)
        self.xx, self.yy = self._coordinate_mesh()

        self.current_uncertainty = self.base_uncertainty.copy()
        self.sampled_mask = np.zeros((self.h, self.w), dtype=bool)
        self.sampled_values = np.zeros((self.h, self.w), dtype=float)
        self.sampled_points: list[tuple[float, float]] = []
        self.sampled_indices: list[tuple[int, int]] = []
        self.reward_curve: list[float] = []
        self.step_count = 0
        self.last_info: dict[str, Any] = {}

    def _prepare_value_map(self, value_map: np.ndarray | None) -> np.ndarray:
        if value_map is not None:
            arr = np.asarray(value_map, dtype=float)
            if arr.shape != self.base_uncertainty.shape:
                raise ValueError("value_map 与 uncertainty_map 形状不一致")
            return arr

        x = np.linspace(0.0, 1.0, self.w)
        y = np.linspace(0.0, 1.0, self.h)
        xx, yy = np.meshgrid(x, y)
        smooth = 1.2 * np.sin(xx * 3.0) + 0.8 * np.cos(yy * 2.5)
        noise = self.rng.normal(0.0, 0.05, size=smooth.shape)
        return smooth + noise

    def _coordinate_mesh(self) -> tuple[np.ndarray, np.ndarray]:
        min_x, max_x, min_y, max_y = self.boundary
        x = np.linspace(min_x, max_x, self.w)
        y = np.linspace(min_y, max_y, self.h)
        return np.meshgrid(x, y)

    def _observation(self) -> dict[str, np.ndarray]:
        sampled_values_norm = np.where(self.sampled_mask, self.sampled_values, 0.0)
        spatial_feat = np.stack(
            [
                (self.xx - self.xx.min()) / (self.xx.max() - self.xx.min() + 1e-8),
                (self.yy - self.yy.min()) / (self.yy.max() - self.yy.min() + 1e-8),
                self.current_uncertainty,
                self.sampled_mask.astype(float),
            ],
            axis=0,
        )
        boundary_info = np.array(
            [
                self.boundary[0],
                self.boundary[1],
                self.boundary[2],
                self.boundary[3],
                max(0.0, (self.budget - len(self.sampled_points)) / self.budget),
                min(1.0, self.step_count / self.max_steps),
            ],
            dtype=float,
        )

        return {
            "sampling_distribution": self.sampled_mask.astype(float),
            "uncertainty_map": self.current_uncertainty.copy(),
            "sampled_values": sampled_values_norm,
            "spatial_features": spatial_feat,
            "boundary_info": boundary_info,
        }

    def _index_to_xy(self, row: int, col: int) -> tuple[float, float]:
        return float(self.xx[row, col]), float(self.yy[row, col])

    def _xy_to_index(self, x: float, y: float) -> tuple[int, int, bool]:
        min_x, max_x, min_y, max_y = self.boundary
        outside = bool((x < min_x) or (x > max_x) or (y < min_y) or (y > max_y))
        x = float(np.clip(x, min_x, max_x))
        y = float(np.clip(y, min_y, max_y))

        col = int(np.clip(round((x - min_x) / max(max_x - min_x, 1e-8) * (self.w - 1)), 0, self.w - 1))
        row = int(np.clip(round((y - min_y) / max(max_y - min_y, 1e-8) * (self.h - 1)), 0, self.h - 1))
        return row, col, outside

    def _decode_action(self, action: Any) -> tuple[list[tuple[int, int]], float, float]:
        """返回采样索引列表、边界惩罚、距离惩罚。"""
        points: list[tuple[int, int]] = []
        boundary_pen = 0.0
        distance_pen = 0.0

        if self.action_mode == "discrete":
            idx = int(action)
            idx = int(np.clip(idx, 0, self.h * self.w - 1))
            row, col = divmod(idx, self.w)
            points.append((row, col))

        elif self.action_mode == "continuous":
            if not isinstance(action, (list, tuple, np.ndarray)) or len(action) < 2:
                raise ValueError("continuous 动作格式必须为 [x, y]")
            row, col, outside = self._xy_to_index(float(action[0]), float(action[1]))
            boundary_pen += boundary_constraint_penalty(outside, magnitude=1.0)
            points.append((row, col))

        elif self.action_mode == "hybrid":
            if not isinstance(action, dict):
                raise ValueError("hybrid 动作格式必须为 {'position': ..., 'sample_count': ...}")
            sample_count = int(np.clip(int(action.get("sample_count", 1)), 1, self.action_space.max_sample_count))
            pos = action.get("position", 0)

            if isinstance(pos, (int, np.integer)):
                row, col = divmod(int(np.clip(int(pos), 0, self.h * self.w - 1)), self.w)
            elif isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                row, col, outside = self._xy_to_index(float(pos[0]), float(pos[1]))
                boundary_pen += boundary_constraint_penalty(outside, magnitude=1.0)
            else:
                row, col = 0, 0
                boundary_pen += 1.0

            points.append((row, col))
            if sample_count > 1:
                # 额外采样点在邻域内按不确定性贪心选择。
                radius = int(np.ceil(sample_count))
                candidates: list[tuple[float, int, int]] = []
                for rr in range(max(0, row - radius), min(self.h, row + radius + 1)):
                    for cc in range(max(0, col - radius), min(self.w, col + radius + 1)):
                        score = float(self.current_uncertainty[rr, cc])
                        candidates.append((score, rr, cc))
                candidates.sort(key=lambda x: x[0], reverse=True)
                for _, rr, cc in candidates[: sample_count - 1]:
                    points.append((rr, cc))

        else:
            raise ValueError(f"不支持的动作模式: {self.action_mode}")

        unique_points: list[tuple[int, int]] = []
        for item in points:
            if item not in unique_points:
                unique_points.append(item)

        for row, col in unique_points:
            if self.sampled_points:
                x, y = self._index_to_xy(row, col)
                dist = min(np.hypot(x - sx, y - sy) for sx, sy in self.sampled_points)
                ok = dist >= self.min_distance
                distance_pen += distance_constraint_penalty(ok, magnitude=(1.0 - dist / max(self.min_distance, 1e-8)) if not ok else 0.0)

        return unique_points, float(boundary_pen), float(distance_pen)

    def _estimate_error_before(self, row: int, col: int) -> float:
        true_v = float(self.value_map[row, col])
        if not self.sampled_indices:
            pred_v = float(np.mean(self.value_map))
        else:
            sampled_vals = np.array([self.sampled_values[r, c] for r, c in self.sampled_indices], dtype=float)
            pred_v = float(np.mean(sampled_vals))
        return abs(pred_v - true_v)

    def _apply_sampling(self, points: list[tuple[int, int]]) -> tuple[float, float, float]:
        """执行状态转移并返回：不确定性减少、精度提升、覆盖提升。"""
        if not points:
            return 0.0, 0.0, 0.0

        pre_uncertainty = float(np.mean(self.current_uncertainty))
        pre_coverage = float(np.count_nonzero(self.sampled_mask) / (self.h * self.w))

        accuracy_gain = 0.0
        for row, col in points:
            before_err = self._estimate_error_before(row, col)

            x, y = self._index_to_xy(row, col)
            measured = float(self.value_map[row, col])
            self.sampled_mask[row, col] = True
            self.sampled_values[row, col] = measured

            if (row, col) not in self.sampled_indices:
                self.sampled_indices.append((row, col))
                self.sampled_points.append((x, y))

            after_err = abs(measured - float(self.value_map[row, col]))
            accuracy_gain += max(0.0, before_err - after_err)

            # 更新不确定性：局部高斯衰减
            rr, cc = np.indices(self.current_uncertainty.shape)
            sigma = max(1.0, min(self.h, self.w) / 10.0)
            influence = np.exp(-((rr - row) ** 2 + (cc - col) ** 2) / (2.0 * sigma ** 2))
            self.current_uncertainty = np.maximum(
                0.0,
                self.current_uncertainty - 0.25 * influence * self.current_uncertainty[row, col],
            )

        post_uncertainty = float(np.mean(self.current_uncertainty))
        post_coverage = float(np.count_nonzero(self.sampled_mask) / (self.h * self.w))

        uncertainty_reduction = max(0.0, pre_uncertainty - post_uncertainty)
        coverage_gain = max(0.0, post_coverage - pre_coverage)
        return float(uncertainty_reduction), float(accuracy_gain), float(coverage_gain)

    def _termination_reason(self) -> tuple[bool, str]:
        if len(self.sampled_points) >= self.budget:
            return True, "budget_limit"
        if float(np.mean(self.current_uncertainty)) <= self.target_uncertainty:
            return True, "target_accuracy"
        if self.step_count >= self.max_steps:
            return True, "max_steps"
        return False, "running"

    def reset(self) -> dict[str, np.ndarray]:
        self.current_uncertainty = self.base_uncertainty.copy()
        self.sampled_mask[:] = False
        self.sampled_values[:] = 0.0
        self.sampled_points = []
        self.sampled_indices = []
        self.reward_curve = []
        self.step_count = 0
        self.last_info = {}
        return self._observation()

    def step(self, action: Any) -> tuple[dict[str, np.ndarray], float, bool, dict[str, Any]]:
        self.step_count += 1

        points, boundary_pen, distance_pen = self._decode_action(action)

        remaining_budget = self.budget - len(self.sampled_points)
        budget_pen = budget_constraint_penalty(remaining_budget, required_budget=len(points))
        valid_points = points[: max(0, remaining_budget)]

        uncertainty_red, accuracy_gain, coverage_gain = self._apply_sampling(valid_points)

        sampling_cost_penalty = float(self.sampling_cost * max(1, len(valid_points)) + budget_pen)

        components = self.reward_composer.compose(
            uncertainty_reduction=uncertainty_red,
            accuracy_improvement=accuracy_gain,
            spatial_coverage=coverage_gain,
            sampling_cost_penalty=sampling_cost_penalty,
            boundary_penalty=boundary_pen,
            distance_penalty=distance_pen,
        )
        self.reward_debugger.log(components)

        done, reason = self._termination_reason()
        reward = float(components["total_reward"])
        self.reward_curve.append(reward)

        info = {
            "reward_breakdown": components,
            "termination_reason": reason,
            "step": int(self.step_count),
            "remaining_budget": int(self.budget - len(self.sampled_points)),
            "mean_uncertainty": float(np.mean(self.current_uncertainty)),
            "sampled_count": int(len(self.sampled_points)),
        }
        self.last_info = info
        return self._observation(), reward, done, info

    def sample_random_action(self) -> Any:
        if self.action_mode == "discrete":
            return int(self.rng.integers(0, self.h * self.w))
        if self.action_mode == "continuous":
            min_x, max_x, min_y, max_y = self.boundary
            return [
                float(self.rng.uniform(min_x, max_x)),
                float(self.rng.uniform(min_y, max_y)),
            ]
        # hybrid
        min_x, max_x, min_y, max_y = self.boundary
        return {
            "position": [float(self.rng.uniform(min_x, max_x)), float(self.rng.uniform(min_y, max_y))],
            "sample_count": int(self.rng.integers(1, self.action_space.max_sample_count + 1)),
        }

    def render(self) -> dict[str, Any]:
        return {
            "sample_points": [{"x": float(x), "y": float(y)} for x, y in self.sampled_points],
            "uncertainty_map": self.current_uncertainty.copy(),
            "reward_curve": list(self.reward_curve),
            "debug_summary": self.reward_debugger.summary(),
            "last_info": dict(self.last_info),
        }


def register_to_gymnasium(env_id: str = "UDAKE/SamplingEnv-v0") -> bool:
    """注册到 Gymnasium。"""
    try:
        import gymnasium as gym  # type: ignore
    except Exception:
        return False

    try:
        if env_id in gym.registry:
            return True
    except Exception:
        pass

    try:
        gym.register(
            id=env_id,
            entry_point="deep_learning.models.sampling_rl.env:SamplingEnv",
        )
        return True
    except Exception:
        return False
