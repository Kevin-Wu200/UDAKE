"""强化学习采样特征工程。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class TopologyFeatures:
    adjacency: np.ndarray
    degree: np.ndarray
    connected_components: int
    clustering: np.ndarray


@dataclass
class RewardDecomposition:
    total_reward: float
    positive_total: float
    penalty_total: float
    weighted_components: dict[str, float]
    contribution_ratio: dict[str, float]


@dataclass
class StateActionFeatureBundle:
    feature_vector: np.ndarray
    feature_names: list[str]
    state_feature_count: int
    action_feature_count: int
    interaction_feature_count: int


class SamplingFeatureEngineer:
    """提供空间、不确定性、采样、拓扑特征。"""

    STATE_FEATURE_NAMES = (
        "state.mean_uncertainty",
        "state.std_uncertainty",
        "state.max_uncertainty",
        "state.p90_uncertainty",
        "state.gradient_mean",
        "state.sampled_ratio",
        "state.sampled_value_mean",
        "state.budget_remaining_ratio",
        "state.step_progress_ratio",
        "state.boundary_area",
    )

    ACTION_FEATURE_NAMES = (
        "action.mode_id",
        "action.position_x_norm",
        "action.position_y_norm",
        "action.position_index_norm",
        "action.sample_count_norm",
        "action.new_point_ratio",
        "action.coverage_gain_potential",
    )

    REWARD_FEATURE_NAMES = (
        "reward.uncertainty_reduction",
        "reward.accuracy_improvement",
        "reward.spatial_coverage",
        "reward.sampling_cost_penalty",
        "reward.boundary_penalty",
        "reward.distance_penalty",
        "reward.weighted_positive",
        "reward.weighted_penalty",
        "reward.raw_total",
    )

    POLICY_FEATURE_NAMES = (
        "policy.mode_id",
        "policy.max_action_prob",
        "policy.selected_action_prob",
        "policy.policy_entropy",
        "policy.top2_gap",
        "policy.prob_mean",
        "policy.prob_std",
    )

    VALUE_FEATURE_NAMES = (
        "value.state_value",
        "value.next_state_value",
        "value.td_target",
        "value.td_error",
        "value.advantage_like",
    )

    STATE_ACTION_INTERACTION_NAMES = (
        "interaction.uncertainty_x_sampling",
        "interaction.coverage_gap_x_action_novelty",
        "interaction.step_progress_x_action_density",
    )

    def position_features(self, coords: np.ndarray, boundary: tuple[float, float, float, float]) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("coords 必须为 [N, 2]")

        min_x, max_x, min_y, max_y = boundary
        width = max(max_x - min_x, 1e-8)
        height = max(max_y - min_y, 1e-8)

        x_norm = (arr[:, 0] - min_x) / width
        y_norm = (arr[:, 1] - min_y) / height
        radius = np.sqrt((x_norm - 0.5) ** 2 + (y_norm - 0.5) ** 2)
        angle = np.arctan2(y_norm - 0.5, x_norm - 0.5)
        return np.stack([x_norm, y_norm, radius, angle], axis=1)

    def distance_features(self, coords: np.ndarray, reference_points: np.ndarray | None = None) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        ref = arr if reference_points is None else np.asarray(reference_points, dtype=float)
        if len(arr) == 0:
            return np.zeros((0, 2), dtype=float)
        if len(ref) == 0:
            return np.zeros((len(arr), 2), dtype=float)

        diff = arr[:, None, :] - ref[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        if reference_points is None:
            # 自身距离矩阵，排除对角线。
            dist = dist + np.eye(len(arr)) * 1e6

        min_dist = dist.min(axis=1)
        mean_dist = dist.mean(axis=1)
        return np.stack([min_dist, mean_dist], axis=1)

    def density_features(self, coords: np.ndarray, k: int = 5) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        if len(arr) == 0:
            return np.zeros((0, 1), dtype=float)

        diff = arr[:, None, :] - arr[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + np.eye(len(arr)) * 1e6
        kk = int(max(1, min(k, max(1, len(arr) - 1))))
        nearest = np.partition(dist, kk, axis=1)[:, :kk]
        density = 1.0 / (nearest.mean(axis=1) + 1e-8)
        return density.reshape(-1, 1)

    def spatial_features(self, coords: np.ndarray, boundary: tuple[float, float, float, float]) -> np.ndarray:
        pos = self.position_features(coords, boundary)
        dist = self.distance_features(coords)
        density = self.density_features(coords)
        return np.concatenate([pos, dist, density], axis=1)

    def uncertainty_features(self, uncertainty_map: np.ndarray) -> np.ndarray:
        umap = np.asarray(uncertainty_map, dtype=float)
        if umap.ndim != 2:
            raise ValueError("uncertainty_map 必须为二维")

        grad_y, grad_x = np.gradient(umap)
        local_grad = np.sqrt(grad_x ** 2 + grad_y ** 2)

        flat = umap.reshape(-1)
        mean = np.mean(flat)
        std = np.std(flat) + 1e-8
        z = (flat - mean) / std

        confidence_width = 1.96 * np.sqrt(np.maximum(flat, 1e-8))
        return np.stack([flat, z, local_grad.reshape(-1), confidence_width], axis=1)

    def sampling_features(
        self,
        sampled_points: np.ndarray,
        boundary: tuple[float, float, float, float],
        grid_shape: tuple[int, int],
    ) -> np.ndarray:
        points = np.asarray(sampled_points, dtype=float)
        h, w = int(grid_shape[0]), int(grid_shape[1])
        density_map = np.zeros((h, w), dtype=float)

        min_x, max_x, min_y, max_y = boundary
        width = max(max_x - min_x, 1e-8)
        height = max(max_y - min_y, 1e-8)

        for x, y in points:
            col = int(np.clip(round((x - min_x) / width * (w - 1)), 0, w - 1))
            row = int(np.clip(round((y - min_y) / height * (h - 1)), 0, h - 1))
            density_map[row, col] += 1.0

        total = float(np.sum(density_map))
        if total > 0:
            distribution = density_map / total
            entropy = -np.sum(distribution * np.log(distribution + 1e-8))
            entropy_norm = entropy / np.log(h * w + 1e-8)
        else:
            entropy_norm = 0.0

        sampled_ratio = float(np.count_nonzero(density_map) / (h * w))
        return np.array([sampled_ratio, float(total), float(entropy_norm)], dtype=float)

    def topology_features(self, coords: np.ndarray, k: int = 4) -> TopologyFeatures:
        points = np.asarray(coords, dtype=float)
        n = len(points)
        if n == 0:
            return TopologyFeatures(
                adjacency=np.zeros((0, 0), dtype=float),
                degree=np.zeros((0,), dtype=float),
                connected_components=0,
                clustering=np.zeros((0,), dtype=float),
            )

        diff = points[:, None, :] - points[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + np.eye(n) * 1e6
        kk = int(max(1, min(k, max(1, n - 1))))
        nn_idx = np.argpartition(dist, kk, axis=1)[:, :kk]

        adjacency = np.zeros((n, n), dtype=float)
        for i in range(n):
            adjacency[i, nn_idx[i]] = 1.0
        adjacency = np.maximum(adjacency, adjacency.T)
        np.fill_diagonal(adjacency, 0.0)

        degree = adjacency.sum(axis=1)
        components = self._count_components(adjacency)
        clustering = self._clustering_coeff(adjacency)

        return TopologyFeatures(
            adjacency=adjacency,
            degree=degree,
            connected_components=components,
            clustering=clustering,
        )

    def _count_components(self, adjacency: np.ndarray) -> int:
        n = len(adjacency)
        if n == 0:
            return 0

        visited = np.zeros(n, dtype=bool)
        components = 0
        for i in range(n):
            if visited[i]:
                continue
            components += 1
            stack = [i]
            visited[i] = True
            while stack:
                cur = stack.pop()
                neighbors = np.where(adjacency[cur] > 0)[0]
                for nb in neighbors:
                    if not visited[nb]:
                        visited[nb] = True
                        stack.append(nb)
        return int(components)

    def _clustering_coeff(self, adjacency: np.ndarray) -> np.ndarray:
        n = len(adjacency)
        coeff = np.zeros(n, dtype=float)
        for i in range(n):
            neighbors = np.where(adjacency[i] > 0)[0]
            if len(neighbors) < 2:
                coeff[i] = 0.0
                continue
            sub = adjacency[np.ix_(neighbors, neighbors)]
            links = np.sum(sub) / 2.0
            possible = len(neighbors) * (len(neighbors) - 1) / 2.0
            coeff[i] = float(links / max(possible, 1e-8))
        return coeff

    def state_space_features(self, observation: dict[str, np.ndarray]) -> np.ndarray:
        umap = np.asarray(observation.get("uncertainty_map", np.zeros((1, 1), dtype=float)), dtype=float)
        sampled = np.asarray(observation.get("sampling_distribution", np.zeros_like(umap)), dtype=float)
        sampled_values = np.asarray(observation.get("sampled_values", np.zeros_like(umap)), dtype=float)
        boundary_info = np.asarray(observation.get("boundary_info", np.zeros((6,), dtype=float)), dtype=float).reshape(-1)

        grad_y, grad_x = np.gradient(umap)
        gradient_mean = float(np.mean(np.sqrt(grad_x**2 + grad_y**2)))
        sampled_ratio = float(np.mean(sampled > 0))
        sampled_value_mean = float(np.mean(sampled_values[sampled > 0])) if np.any(sampled > 0) else 0.0
        budget_remaining_ratio = float(boundary_info[4]) if boundary_info.size >= 5 else 0.0
        step_progress_ratio = float(boundary_info[5]) if boundary_info.size >= 6 else 0.0

        if boundary_info.size >= 4:
            boundary_area = float(max(0.0, (boundary_info[1] - boundary_info[0]) * (boundary_info[3] - boundary_info[2])))
        else:
            boundary_area = 1.0

        return np.asarray(
            [
                float(np.mean(umap)),
                float(np.std(umap)),
                float(np.max(umap)),
                float(np.percentile(umap, 90)),
                gradient_mean,
                sampled_ratio,
                sampled_value_mean,
                budget_remaining_ratio,
                step_progress_ratio,
                boundary_area,
            ],
            dtype=float,
        )

    def action_space_features(self, action: Any, action_space: Any) -> np.ndarray:
        mode = getattr(action_space, "mode", "discrete")
        grid_size = max(1, int(getattr(action_space, "grid_size", 1)))
        max_sample_count = max(1, int(getattr(action_space, "max_sample_count", 1)))
        boundary = getattr(action_space, "boundary", (0.0, 1.0, 0.0, 1.0))
        min_x, max_x, min_y, max_y = boundary
        width = max(1e-8, float(max_x - min_x))
        height = max(1e-8, float(max_y - min_y))

        mode_id = {"discrete": 0.0, "continuous": 1.0, "hybrid": 2.0}.get(mode, -1.0)
        x_norm = 0.0
        y_norm = 0.0
        index_norm = 0.0
        sample_count_norm = 1.0 / max_sample_count
        new_point_ratio = 1.0
        coverage_gain_potential = 1.0 / np.sqrt(grid_size)

        if mode == "discrete":
            idx = int(np.clip(int(action), 0, grid_size - 1))
            index_norm = float(idx / max(1, grid_size - 1))
            side = int(np.ceil(np.sqrt(grid_size)))
            row, col = divmod(idx, side)
            x_norm = float(np.clip(col / max(1, side - 1), 0.0, 1.0))
            y_norm = float(np.clip(row / max(1, side - 1), 0.0, 1.0))
        elif mode == "continuous":
            if isinstance(action, (list, tuple, np.ndarray)) and len(action) >= 2:
                x = float(action[0])
                y = float(action[1])
                x_norm = float(np.clip((x - min_x) / width, 0.0, 1.0))
                y_norm = float(np.clip((y - min_y) / height, 0.0, 1.0))
                index_norm = float(np.clip(y_norm * np.sqrt(grid_size) + x_norm, 0.0, np.sqrt(grid_size) + 1.0))
        elif mode == "hybrid":
            sample_count = 1
            pos: Any = 0
            if isinstance(action, dict):
                sample_count = int(np.clip(int(action.get("sample_count", 1)), 1, max_sample_count))
                pos = action.get("position", 0)
            sample_count_norm = float(sample_count / max_sample_count)
            coverage_gain_potential = float(sample_count_norm / np.sqrt(grid_size))

            if isinstance(pos, (int, np.integer)):
                idx = int(np.clip(int(pos), 0, grid_size - 1))
                index_norm = float(idx / max(1, grid_size - 1))
                side = int(np.ceil(np.sqrt(grid_size)))
                row, col = divmod(idx, side)
                x_norm = float(np.clip(col / max(1, side - 1), 0.0, 1.0))
                y_norm = float(np.clip(row / max(1, side - 1), 0.0, 1.0))
            elif isinstance(pos, (list, tuple, np.ndarray)) and len(pos) >= 2:
                x = float(pos[0])
                y = float(pos[1])
                x_norm = float(np.clip((x - min_x) / width, 0.0, 1.0))
                y_norm = float(np.clip((y - min_y) / height, 0.0, 1.0))
                index_norm = float(np.clip(y_norm * np.sqrt(grid_size) + x_norm, 0.0, np.sqrt(grid_size) + 1.0))
            else:
                new_point_ratio = 0.0

        return np.asarray(
            [
                float(mode_id),
                float(x_norm),
                float(y_norm),
                float(index_norm),
                float(sample_count_norm),
                float(new_point_ratio),
                float(coverage_gain_potential),
            ],
            dtype=float,
        )

    def reward_function_features(self, reward_components: dict[str, float], reward_weights: Any | None = None) -> np.ndarray:
        comp = {k: float(v) for k, v in reward_components.items()}

        if reward_weights is None:
            w = {
                "uncertainty_reduction": 0.40,
                "accuracy_improvement": 0.25,
                "spatial_coverage": 0.20,
                "sampling_cost": 0.08,
                "boundary_constraint": 0.04,
                "distance_constraint": 0.03,
            }
        else:
            w = {
                "uncertainty_reduction": float(getattr(reward_weights, "uncertainty_reduction", 0.40)),
                "accuracy_improvement": float(getattr(reward_weights, "accuracy_improvement", 0.25)),
                "spatial_coverage": float(getattr(reward_weights, "spatial_coverage", 0.20)),
                "sampling_cost": float(getattr(reward_weights, "sampling_cost", 0.08)),
                "boundary_constraint": float(getattr(reward_weights, "boundary_constraint", 0.04)),
                "distance_constraint": float(getattr(reward_weights, "distance_constraint", 0.03)),
            }

        weighted_positive = (
            w["uncertainty_reduction"] * comp.get("uncertainty_reduction", 0.0)
            + w["accuracy_improvement"] * comp.get("accuracy_improvement", 0.0)
            + w["spatial_coverage"] * comp.get("spatial_coverage", 0.0)
        )
        weighted_penalty = (
            w["sampling_cost"] * comp.get("sampling_cost_penalty", 0.0)
            + w["boundary_constraint"] * comp.get("boundary_penalty", 0.0)
            + w["distance_constraint"] * comp.get("distance_penalty", 0.0)
        )
        raw_total = comp.get("raw_total_reward", weighted_positive - weighted_penalty)

        return np.asarray(
            [
                comp.get("uncertainty_reduction", 0.0),
                comp.get("accuracy_improvement", 0.0),
                comp.get("spatial_coverage", 0.0),
                comp.get("sampling_cost_penalty", 0.0),
                comp.get("boundary_penalty", 0.0),
                comp.get("distance_penalty", 0.0),
                float(weighted_positive),
                float(weighted_penalty),
                float(raw_total),
            ],
            dtype=float,
        )

    def policy_network_features(
        self,
        action_probs: np.ndarray | None = None,
        action_logits: np.ndarray | None = None,
        selected_action: int | None = None,
        policy_entropy: float | None = None,
        action_mode: str = "discrete",
    ) -> np.ndarray:
        mode_id = {"discrete": 0.0, "continuous": 1.0, "hybrid": 2.0}.get(action_mode, -1.0)

        probs = None
        if action_probs is not None:
            probs = np.asarray(action_probs, dtype=float).reshape(-1)
        elif action_logits is not None:
            logits = np.asarray(action_logits, dtype=float).reshape(-1)
            logits = logits - float(np.max(logits))
            exps = np.exp(logits)
            probs = exps / (np.sum(exps) + 1e-8)

        if probs is None or probs.size == 0:
            probs = np.asarray([1.0], dtype=float)

        probs = np.clip(probs, 1e-8, 1.0)
        probs = probs / np.sum(probs)

        max_prob = float(np.max(probs))
        entropy = float(-np.sum(probs * np.log(probs))) if policy_entropy is None else float(policy_entropy)
        idx = int(np.clip(int(selected_action if selected_action is not None else int(np.argmax(probs))), 0, probs.size - 1))
        selected_prob = float(probs[idx])
        sorted_prob = np.sort(probs)
        top2_gap = float(sorted_prob[-1] - sorted_prob[-2]) if probs.size >= 2 else float(sorted_prob[-1])

        return np.asarray(
            [
                mode_id,
                max_prob,
                selected_prob,
                entropy,
                top2_gap,
                float(np.mean(probs)),
                float(np.std(probs)),
            ],
            dtype=float,
        )

    def value_network_features(
        self,
        state_value: float,
        next_state_value: float | None = None,
        reward: float | None = None,
        gamma: float = 0.99,
    ) -> np.ndarray:
        v = float(state_value)
        nv = float(next_state_value) if next_state_value is not None else v
        r = float(reward) if reward is not None else 0.0
        td_target = r + float(gamma) * nv
        td_error = td_target - v
        return np.asarray([v, nv, td_target, td_error, td_error], dtype=float)

    def feature_name_mapping(self) -> dict[str, str]:
        return {
            "state.mean_uncertainty": "状态-平均不确定性",
            "state.std_uncertainty": "状态-不确定性标准差",
            "state.max_uncertainty": "状态-最大不确定性",
            "state.p90_uncertainty": "状态-90分位不确定性",
            "state.gradient_mean": "状态-不确定性梯度均值",
            "state.sampled_ratio": "状态-已采样覆盖率",
            "state.sampled_value_mean": "状态-采样值均值",
            "state.budget_remaining_ratio": "状态-预算剩余比例",
            "state.step_progress_ratio": "状态-步数进度比例",
            "state.boundary_area": "状态-边界面积",
            "action.mode_id": "动作-类型编码",
            "action.position_x_norm": "动作-X归一化位置",
            "action.position_y_norm": "动作-Y归一化位置",
            "action.position_index_norm": "动作-索引归一化",
            "action.sample_count_norm": "动作-采样数量归一化",
            "action.new_point_ratio": "动作-新点比例",
            "action.coverage_gain_potential": "动作-覆盖增益潜力",
            "reward.uncertainty_reduction": "奖励-不确定性降低",
            "reward.accuracy_improvement": "奖励-精度提升",
            "reward.spatial_coverage": "奖励-空间覆盖",
            "reward.sampling_cost_penalty": "奖励-采样成本惩罚",
            "reward.boundary_penalty": "奖励-边界惩罚",
            "reward.distance_penalty": "奖励-距离惩罚",
            "reward.weighted_positive": "奖励-加权正向收益",
            "reward.weighted_penalty": "奖励-加权惩罚成本",
            "reward.raw_total": "奖励-原始总奖励",
            "policy.mode_id": "策略-动作空间编码",
            "policy.max_action_prob": "策略-最大动作概率",
            "policy.selected_action_prob": "策略-选中动作概率",
            "policy.policy_entropy": "策略-策略熵",
            "policy.top2_gap": "策略-前二动作概率差",
            "policy.prob_mean": "策略-概率均值",
            "policy.prob_std": "策略-概率标准差",
            "value.state_value": "价值-当前状态价值",
            "value.next_state_value": "价值-下一状态价值",
            "value.td_target": "价值-TD目标",
            "value.td_error": "价值-TD误差",
            "value.advantage_like": "价值-优势近似项",
            "interaction.uncertainty_x_sampling": "交互-不确定性与采样强度",
            "interaction.coverage_gap_x_action_novelty": "交互-覆盖缺口与动作新颖度",
            "interaction.step_progress_x_action_density": "交互-进度与动作密度",
        }

    def extract_state_action_features(
        self,
        observation: dict[str, np.ndarray],
        action: Any,
        action_space: Any,
    ) -> StateActionFeatureBundle:
        state_feat = self.state_space_features(observation)
        action_feat = self.action_space_features(action, action_space)

        uncertainty_x_sampling = float(state_feat[0] * action_feat[4])
        coverage_gap = float(1.0 - np.clip(state_feat[5], 0.0, 1.0))
        coverage_gap_x_action_novelty = float(coverage_gap * action_feat[5])
        step_progress_x_action_density = float(np.clip(state_feat[8], 0.0, 1.0) * action_feat[6])

        interaction_feat = np.asarray(
            [
                uncertainty_x_sampling,
                coverage_gap_x_action_novelty,
                step_progress_x_action_density,
            ],
            dtype=float,
        )

        vector = np.concatenate([state_feat, action_feat, interaction_feat], axis=0)
        names = [
            *self.STATE_FEATURE_NAMES,
            *self.ACTION_FEATURE_NAMES,
            *self.STATE_ACTION_INTERACTION_NAMES,
        ]
        return StateActionFeatureBundle(
            feature_vector=vector,
            feature_names=names,
            state_feature_count=len(self.STATE_FEATURE_NAMES),
            action_feature_count=len(self.ACTION_FEATURE_NAMES),
            interaction_feature_count=len(self.STATE_ACTION_INTERACTION_NAMES),
        )

    def decompose_reward(
        self,
        reward_components: dict[str, float],
        reward_weights: Any | None = None,
    ) -> RewardDecomposition:
        feat = self.reward_function_features(reward_components, reward_weights=reward_weights)
        weighted = {
            "uncertainty_reduction": float(feat[0]),
            "accuracy_improvement": float(feat[1]),
            "spatial_coverage": float(feat[2]),
            "sampling_cost_penalty": float(feat[3]),
            "boundary_penalty": float(feat[4]),
            "distance_penalty": float(feat[5]),
            "weighted_positive": float(feat[6]),
            "weighted_penalty": float(feat[7]),
            "raw_total_reward": float(feat[8]),
        }

        abs_sum = sum(abs(v) for v in weighted.values()) + 1e-8
        ratio = {k: float(abs(v) / abs_sum) for k, v in weighted.items()}
        return RewardDecomposition(
            total_reward=weighted["raw_total_reward"],
            positive_total=weighted["weighted_positive"],
            penalty_total=weighted["weighted_penalty"],
            weighted_components=weighted,
            contribution_ratio=ratio,
        )
