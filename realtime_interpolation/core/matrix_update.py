"""
矩阵更新模块
Matrix Update Module

实现Sherman-Morrison和Woodbury矩阵更新公式
"""

import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ShermanMorrisonUpdater:
    """Sherman-Morrison矩阵更新器"""

    def __init__(self, epsilon: float = 1e-10):
        """
        初始化Sherman-Morrison更新器

        Args:
            epsilon: 数值稳定性阈值
        """
        self.epsilon = epsilon

    def update(
        self,
        A_inv: np.ndarray,
        u: np.ndarray,
        v: np.ndarray
    ) -> np.ndarray:
        """
        Sherman-Morrison矩阵更新

        公式: (A + uv^T)^(-1) = A^(-1) - (A^(-1) * u * v^T * A^(-1)) / (1 + v^T * A^(-1) * u)

        Args:
            A_inv: 原矩阵的逆矩阵 (n x n)
            u: 更新向量 (n x 1)
            v: 更新向量 (n x 1)

        Returns:
            更新后的逆矩阵 (n x n)

        Raises:
            ValueError: 矩阵奇异，无法更新
        """
        # 确保向量是列向量
        if u.ndim == 1:
            u = u.reshape(-1, 1)
        if v.ndim == 1:
            v = v.reshape(-1, 1)

        # 1. 计算 A^(-1) * u
        Au = A_inv @ u

        # 2. 计算 v^T * A^(-1) * u
        vAu = np.dot(v.T, Au)

        # 3. 检查分母是否接近0
        denominator = 1 + vAu
        if abs(denominator) < self.epsilon:
            logger.warning(f"矩阵奇异，分母接近0: {denominator}")
            # 尝试使用伪逆
            A_new_inv = np.linalg.pinv(A_inv)
            return A_new_inv

        # 4. 计算 (A^(-1) * u) * (v^T * A^(-1))
        Au_vA = np.outer(Au, v.T @ A_inv)

        # 5. 计算更新后的逆矩阵
        A_new_inv = A_inv - Au_vA / denominator

        return A_new_inv

    def add_row_col(
        self,
        K_inv: np.ndarray,
        k_new: np.ndarray,
        c_new: float
    ) -> np.ndarray:
        """
        使用Sherman-Morrison公式添加新的行和列

        原矩阵: K (n x n)
        新矩阵: K_new = | K     k_new |
                         | k_new^T c_new |
        (n+1) x (n+1)

        Args:
            K_inv: 原协方差矩阵的逆 (n x n)
            k_new: 新列向量 (n x 1)
            c_new: 新元素 (1 x 1)

        Returns:
            更新后的逆矩阵 ((n+1) x (n+1))
        """
        n = K_inv.shape[0]

        # 确保k_new是列向量
        if k_new.ndim == 1:
            k_new = k_new.reshape(-1, 1)

        # 1. 计算 A^(-1) * u
        Au = np.zeros((n + 1, 1))
        Au[:n, 0] = K_inv @ k_new
        Au[n, 0] = c_new

        # 2. 构造v
        v = np.zeros((n + 1, 1))
        v[:n, 0] = -K_inv @ k_new
        v[n, 0] = 1.0

        # 3. 扩展原逆矩阵
        A_inv = np.zeros((n + 1, n + 1))
        A_inv[:n, :n] = K_inv

        # 4. 应用Sherman-Morrison公式
        K_new_inv = self.update(A_inv, Au, v)

        return K_new_inv


class WoodburyUpdater:
    """Woodbury矩阵更新器"""

    def __init__(self, epsilon: float = 1e-10):
        """
        初始化Woodbury更新器

        Args:
            epsilon: 数值稳定性阈值
        """
        self.epsilon = epsilon

    def update(
        self,
        A_inv: np.ndarray,
        U: np.ndarray,
        C: np.ndarray,
        V: np.ndarray
    ) -> np.ndarray:
        """
        Woodbury矩阵更新

        公式: (A + UCV^T)^(-1) = A^(-1) - A^(-1) * U * (C^(-1) + V^T * A^(-1) * U)^(-1) * V^T * A^(-1)

        Args:
            A_inv: 原矩阵的逆矩阵 (n x n)
            U: 更新矩阵 (n x k)
            C: 矩阵 (k x k)
            V: 更新矩阵 (n x k)

        Returns:
            更新后的逆矩阵 (n x n)

        Raises:
            ValueError: 矩阵不可逆
        """
        # 1. 计算 C^(-1)
        try:
            C_inv = np.linalg.inv(C)
        except np.linalg.LinAlgError as e:
            logger.error(f"矩阵C不可逆: {e}")
            raise ValueError("矩阵C不可逆") from e

        # 2. 计算 V^T * A^(-1)
        VA_inv = V.T @ A_inv

        # 3. 计算 V^T * A^(-1) * U
        VA_inv_U = VA_inv @ U

        # 4. 计算 C^(-1) + V^T * A^(-1) * U
        M = C_inv + VA_inv_U

        # 5. 计算 M^(-1)
        try:
            M_inv = np.linalg.inv(M)
        except np.linalg.LinAlgError as e:
            logger.warning(f"矩阵M不可逆，使用伪逆: {e}")
            M_inv = np.linalg.pinv(M)

        # 6. 计算 A^(-1) * U
        A_inv_U = A_inv @ U

        # 7. 计算更新项
        update_term = A_inv_U @ M_inv @ VA_inv

        # 8. 计算新的逆矩阵
        A_new_inv = A_inv - update_term

        return A_new_inv

    def batch_update(
        self,
        K_inv: np.ndarray,
        new_points_cov: np.ndarray,
        new_values_cov: np.ndarray
    ) -> np.ndarray:
        """
        批量更新协方差矩阵

        Args:
            K_inv: 原协方差矩阵的逆 (n x n)
            new_points_cov: 新点与已有点的协方差矩阵 (n x k)
            new_values_cov: 新点之间的协方差矩阵 (k x k)

        Returns:
            更新后的逆矩阵 ((n+k) x (n+k))
        """
        n = K_inv.shape[0]
        k = new_points_cov.shape[1]

        # 构造更新矩阵
        U = np.zeros((n + k, k))
        U[:n, :] = new_points_cov
        U[n:, :] = new_values_cov

        V = np.zeros((n + k, k))
        V[:n, :] = -new_points_cov
        V[n:, :] = np.eye(k)

        C = np.eye(k)

        # 扩展原逆矩阵
        A_inv = np.zeros((n + k, n + k))
        A_inv[:n, :n] = K_inv

        # 应用Woodbury公式
        K_new_inv = self.update(A_inv, U, C, V)

        return K_new_inv


def test_sherman_morrison():
    """测试Sherman-Morrison更新"""
    print("测试Sherman-Morrison更新...")

    # 创建一个测试矩阵
    n = 5
    A = np.random.randn(n, n)
    A = A.T @ A + np.eye(n)  # 确保正定

    # 计算逆矩阵
    A_inv = np.linalg.inv(A)

    # 创建更新向量
    u = np.random.randn(n, 1)
    v = np.random.randn(n, 1)

    # 更新矩阵
    A_updated = A + u @ v.T

    # 使用Sherman-Morrison更新
    updater = ShermanMorrisonUpdater()
    A_updated_inv = updater.update(A_inv, u, v)

    # 计算真实的逆矩阵
    A_updated_inv_true = np.linalg.inv(A_updated)

    # 比较结果
    error = np.linalg.norm(A_updated_inv - A_updated_inv_true)
    print(f"误差: {error:.10f}")
    assert error < 1e-8, f"误差过大: {error}"

    print("Sherman-Morrison更新测试通过！")


def test_woodbury():
    """测试Woodbury更新"""
    print("\n测试Woodbury更新...")

    # 创建一个测试矩阵
    n = 5
    k = 3
    A = np.random.randn(n, n)
    A = A.T @ A + np.eye(n)  # 确保正定

    # 计算逆矩阵
    A_inv = np.linalg.inv(A)

    # 创建更新矩阵
    U = np.random.randn(n, k)
    C = np.random.randn(k, k)
    C = C.T @ C + np.eye(k)  # 确保正定
    V = np.random.randn(n, k)

    # 更新矩阵
    A_updated = A + U @ C @ V.T

    # 使用Woodbury更新
    updater = WoodburyUpdater()
    A_updated_inv = updater.update(A_inv, U, C, V)

    # 计算真实的逆矩阵
    A_updated_inv_true = np.linalg.inv(A_updated)

    # 比较结果
    error = np.linalg.norm(A_updated_inv - A_updated_inv_true)
    print(f"误差: {error:.10f}")
    assert error < 1e-8, f"误差过大: {error}"

    print("Woodbury更新测试通过！")


if __name__ == "__main__":
    test_sherman_morrison()
    test_woodbury()
    print("\n所有测试通过！")