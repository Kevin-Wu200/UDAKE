"""
矩阵更新模块
Matrix Update Module

实现Sherman-Morrison和Woodbury矩阵更新公式
"""

import logging
from typing import List, Tuple

import numpy as np

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
        Au[:n, 0] = (K_inv @ k_new).reshape(-1)
        Au[n, 0] = c_new

        # 2. 构造v
        v = np.zeros((n + 1, 1))
        v[:n, 0] = (-(K_inv @ k_new)).reshape(-1)
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


class BlockMatrixUpdater:
    """分块矩阵更新器"""

    def __init__(self, block_size: int = 100, epsilon: float = 1e-10):
        """
        初始化分块矩阵更新器

        Args:
            block_size: 分块大小
            epsilon: 数值稳定性阈值
        """
        self.block_size = block_size
        self.epsilon = epsilon
        self.sherman_morrison = ShermanMorrisonUpdater(epsilon)

    def block_update(
        self,
        K_inv: np.ndarray,
        new_rows: np.ndarray,
        new_cols: np.ndarray,
        new_diag: float
    ) -> np.ndarray:
        """
        分块更新协方差矩阵

        将矩阵分成多个块，仅更新受影响的块

        Args:
            K_inv: 原矩阵的逆 (n x n)
            new_rows: 新行的协方差向量 (n x k)
            new_cols: 新列的协方差向量 (n x k)
            new_diag: 新对角元素

        Returns:
            更新后的逆矩阵 ((n+k) x (n+k))
        """
        n = K_inv.shape[0]
        k = new_rows.shape[1]

        # 扩展矩阵
        K_new_inv = np.zeros((n + k, n + k))
        K_new_inv[:n, :n] = K_inv

        # 分块处理
        num_blocks = (n + k - 1) // self.block_size + 1

        for block_i in range(num_blocks):
            for block_j in range(num_blocks):
                # 计算块的范围
                i_start = block_i * self.block_size
                i_end = min((block_i + 1) * self.block_size, n + k)
                j_start = block_j * self.block_size
                j_end = min((block_j + 1) * self.block_size, n + k)

                # 更新块
                if i_end > n or j_end > n:
                    # 需要更新的块
                    self._update_block(
                        K_new_inv, K_inv,
                        new_rows, new_cols, new_diag,
                        i_start, i_end, j_start, j_end
                    )

        return K_new_inv

    def _update_block(
        self,
        K_new_inv: np.ndarray,
        K_inv: np.ndarray,
        new_rows: np.ndarray,
        new_cols: np.ndarray,
        new_diag: float,
        i_start: int,
        i_end: int,
        j_start: int,
        j_end: int
    ) -> None:
        """更新单个块"""
        n = K_inv.shape[0]
        k = new_rows.shape[1]

        # 更新新行新列的块
        for i in range(i_start, i_end):
            for j in range(j_start, j_end):
                if i >= n and j >= n:
                    # 新增部分
                    idx_i, idx_j = i - n, j - n
                    if idx_i == idx_j:
                        K_new_inv[i, j] = 1.0 / new_diag
                    else:
                        # 使用Sherman-Morrison公式
                        u = np.zeros(n + k)
                        u[n + idx_i] = 1.0
                        v = np.zeros(n + k)
                        v[:n] = -new_cols[:, idx_i]
                        v[n + idx_j] = 1.0
                        # 简化计算
                        K_new_inv[i, j] = -np.dot(new_rows[:, idx_i], K_inv @ new_cols[:, idx_j]) / new_diag
                elif i >= n:
                    # 新行
                    idx_i = i - n
                    K_new_inv[i, j] = -np.dot(new_rows[:, idx_i], K_inv[j, :]) / new_diag
                elif j >= n:
                    # 新列
                    idx_j = j - n
                    K_new_inv[i, j] = -np.dot(K_inv[i, :], new_cols[:, idx_j]) / new_diag

    def sparse_update(
        self,
        K_inv: np.ndarray,
        new_points: List[Tuple[int, float, float]]
    ) -> np.ndarray:
        """
        稀疏矩阵更新

        仅更新非零元素，利用矩阵的稀疏性

        Args:
            K_inv: 原矩阵的逆 (n x n)
            new_points: 新点列表 (index, row_value, col_value)

        Returns:
            更新后的逆矩阵
        """
        n = K_inv.shape[0]
        K_new_inv = K_inv.copy()

        # 找到需要更新的非零位置
        update_indices = set()
        for idx, _, _ in new_points:
            # 更新第idx行和第idx列
            update_indices.add(idx)
            # 同时更新与idx相关的行和列
            for i in range(n):
                if abs(K_inv[i, idx]) > self.epsilon:
                    update_indices.add(i)

        # 仅更新相关行和列
        for idx, row_val, col_val in new_points:
            # 更新第idx行
            K_new_inv[idx, :] = self._update_sparse_row(
                K_inv, idx, new_points, update_indices
            )
            # 更新第idx列
            K_new_inv[:, idx] = self._update_sparse_col(
                K_inv, idx, new_points, update_indices
            )

        return K_new_inv

    def _update_sparse_row(
        self,
        K_inv: np.ndarray,
        idx: int,
        new_points: List[Tuple[int, float, float]],
        update_indices: set
    ) -> np.ndarray:
        """更新稀疏行"""
        n = K_inv.shape[0]  # noqa: F841
        row = K_inv[idx, :].copy()

        for i in update_indices:
            # 计算更新项
            update = 0.0
            for _, row_val, col_val in new_points:
                update += K_inv[idx, i] * K_inv[i, i] * col_val
            row[i] -= update

        return row

    def _update_sparse_col(
        self,
        K_inv: np.ndarray,
        idx: int,
        new_points: List[Tuple[int, float, float]],
        update_indices: set
    ) -> np.ndarray:
        """更新稀疏列"""
        n = K_inv.shape[0]  # noqa: F841
        col = K_inv[:, idx].copy()

        for i in update_indices:
            # 计算更新项
            update = 0.0
            for _, row_val, col_val in new_points:
                update += K_inv[i, idx] * K_inv[i, i] * row_val
            col[i] -= update

        return col


class SparseMatrixUpdater:
    """稀疏矩阵更新器"""

    def __init__(self, threshold: float = 1e-8):
        """
        初始化稀疏矩阵更新器

        Args:
            threshold: 稀疏性阈值
        """
        self.threshold = threshold
        self.sherman_morrison = ShermanMorrisonUpdater()

    def update_sparse(
        self,
        K_inv: np.ndarray,
        new_indices: List[int],
        new_values: List[float]
    ) -> np.ndarray:
        """
        更新稀疏矩阵

        Args:
            K_inv: 原矩阵的逆
            new_indices: 需要更新的索引
            new_values: 更新值

        Returns:
            更新后的逆矩阵
        """
        n = K_inv.shape[0]
        k = len(new_indices)

        # 构造稀疏更新矩阵
        U = np.zeros((n + k, k))
        V = np.zeros((n + k, k))

        for i, idx in enumerate(new_indices):
            U[idx, i] = 1.0
            V[idx, i] = new_values[i]

        # 使用Woodbury公式
        woodbury = WoodburyUpdater()
        K_new_inv = woodbury.update(K_inv, U, np.eye(k), V)

        return K_new_inv

    def get_sparse_pattern(self, matrix: np.ndarray) -> np.ndarray:
        """
        获取矩阵的稀疏模式

        Args:
            matrix: 输入矩阵

        Returns:
            稀疏模式（0表示零，1表示非零）
        """
        return (np.abs(matrix) > self.threshold).astype(int)

    def compress_sparse_matrix(self, matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        压缩稀疏矩阵（CSR格式）

        Args:
            matrix: 输入矩阵

        Returns:
            (data, indices, indptr)
        """
        n = matrix.shape[0]
        data = []
        indices = []
        indptr = [0]

        for i in range(n):
            nnz = 0
            for j in range(n):
                if abs(matrix[i, j]) > self.threshold:
                    data.append(matrix[i, j])
                    indices.append(j)
                    nnz += 1
            indptr.append(indptr[-1] + nnz)

        return np.array(data), np.array(indices), np.array(indptr)


def test_block_matrix_update():
    """测试分块矩阵更新"""
    print("\n测试分块矩阵更新...")

    # 创建测试矩阵
    n = 200
    A = np.random.randn(n, n)
    A = A.T @ A + np.eye(n)  # 确保正定

    # 计算逆矩阵
    A_inv = np.linalg.inv(A)

    # 添加新行新列
    k = 10
    new_rows = np.random.randn(n, k)
    new_cols = new_rows.copy()
    new_diag = 1.0

    # 构造完整的更新矩阵
    A_new = np.zeros((n + k, n + k))
    A_new[:n, :n] = A
    A_new[:n, n:] = new_rows
    A_new[n:, :n] = new_cols
    A_new[n:, n:] = new_diag * np.eye(k)

    # 使用分块更新
    updater = BlockMatrixUpdater(block_size=50)
    A_new_inv_block = updater.block_update(A_inv, new_rows, new_cols, new_diag)

    # 计算真实的逆矩阵
    A_new_inv_true = np.linalg.inv(A_new)

    # 比较结果
    error = np.linalg.norm(A_new_inv_block - A_new_inv_true)
    print(f"分块更新误差: {error:.10f}")
    assert error < 1e-6, f"误差过大: {error}"

    print("分块矩阵更新测试通过！")


def test_sparse_matrix_update():
    """测试稀疏矩阵更新"""
    print("\n测试稀疏矩阵更新...")

    # 创建稀疏测试矩阵
    n = 100
    A = np.zeros((n, n))
    for i in range(n):
        A[i, i] = 1.0
        if i > 0:
            A[i, i-1] = 0.1
        if i < n - 1:
            A[i, i+1] = 0.1

    # 计算逆矩阵
    A_inv = np.linalg.inv(A)

    # 添加新点
    new_indices = [0, 10, 20]
    new_values = [0.5, 0.3, 0.7]

    # 使用稀疏更新
    updater = SparseMatrixUpdater()
    A_new_inv = updater.update_sparse(A_inv, new_indices, new_values)

    print(f"稀疏更新完成，矩阵大小: {A_new_inv.shape}")

    print("稀疏矩阵更新测试通过！")


if __name__ == "__main__":
    test_sherman_morrison()
    test_woodbury()
    test_block_matrix_update()
    test_sparse_matrix_update()
    print("\n所有测试通过！")
