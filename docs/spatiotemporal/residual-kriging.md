# Residual-Kriging 模型文档

## 概述

Residual-Kriging 是一种基于特征工程和多分支残差网络的空间插值模型。该模型在克里金基线预测的基础上，通过精心设计的空间特征工程和多分支网络架构（MLP、CNN、Hybrid）学习残差，提升插值精度。

## 核心思想

Residual-Kriging 采用**特征工程 + 多分支残差网络**策略：

1. **克里金基线**：使用普通克里金或通用克里金作为基线预测器
2. **特征工程**：构建多维空间特征，捕获局部空间结构
3. **多分支网络**：通过三个互补的分支学习不同尺度的残差模式
4. **残差融合**：融合多分支输出，生成最终残差

## 模型架构

### 1. 基线选择

模型支持两种克里金基线：

- **OrdinaryKrigingBaseline**：普通克里金，假设均值为常数
- **UniversalKrigingBaseline**：通用克里金，考虑趋势项

### 2. 特征工程

模型为每个查询点构建8维特征向量：

- **mean_neighbor_distance**：k近邻平均距离
- **std_neighbor_distance**：k近邻距离标准差
- **direction_x**：x方向平均方向余弦
- **direction_y**：y方向平均方向余弦
- **local_density**：局部点密度（k / (π * r²)）
- **value_skewness**：局部值偏度（衡量分布不对称性）
- **value_kurtosis**：局部值峰度（衡量分布尖锐程度）
- **prior_mean**：克里金先验均值

### 3. 空间索引

使用 `SpatialIndex` 高效查询k近邻：

- 支持增量构建和缓存
- 自动检测坐标变化
- 优化大规模数据查询性能

### 4. 多分支网络

#### MLP分支

两层全连接网络：
- 输入：8维特征
- 隐藏层：12维，ReLU激活
- 输出：1维残差

特点：
- ResNet风格跳跃连接：`hidden = hidden + 0.01 * features[:, -1]`
- Dense风格混合：`dense_mix = 0.9 * hidden + 0.1 * hidden.mean`

#### CNN分支

网格风格局部平滑：
- 基于查询点之间的空间距离计算权重
- 使用高斯核进行局部平滑
- 捕获空间连续性

特点：
- 计算所有查询点对的距离矩阵
- 使用指数衰减核：`w = exp(-dist / 0.15)`
- 归一化后加权平均

#### 多尺度融合分支

结合两个尺度的特征：
- 小尺度：k=4（局部细节）
- 大尺度：k=12（全局模式）

融合策略：
```python
residual = 0.6 * mlp_small + 0.4 * mlp_large
```

### 5. 最终融合

根据架构类型选择融合策略：

- **MLP架构**：仅使用MLP分支
- **CNN架构**：仅使用CNN分支
- **Hybrid架构**（默认）：
  ```python
  residual = 0.45 * residual_mlp + 0.25 * residual_cnn + 0.30 * residual_multi_scale
  ```

## 参数说明

### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `architecture` | str | "hybrid" | 网络架构：mlp/cnn/hybrid |
| `baseline` | str | "universal" | 克里金基线：ordinary/universal |
| `seed` | int | 42 | 随机种子 |

### 关键子模块参数

- **MLP分支**：
  - `mlp_w1`: (8, 12) - 第一层权重
  - `mlp_w2`: (12, 1) - 第二层权重
  - 初始化：N(0, 0.08²)

- **空间索引**：
  - 自动构建和缓存
  - 基于坐标哈希检测变化

- **特征工程**：
  - k近邻数：默认8（多尺度分支使用4和12）
  - 核带宽：0.15（CNN分支）

### 可训练参数

- `mlp_w1`: MLP第一层权重矩阵
- `mlp_w2`: MLP第二层权重矩阵
- `res_scale`: 残差缩放系数
- `bias`: 偏置项

## 使用方法

### 基本预测

```python
from deep_learning.models.spatial_interpolation.residual_kriging import ResidualKrigingModel

# 初始化模型
model = ResidualKrigingModel(
    architecture="hybrid",
    baseline="universal"
)

# 准备数据
sample_coords = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
sample_values = np.array([1.0, 2.0, 1.5])
query_coords = np.array([[0.5, 0.5], [0.2, 0.8]])

# 执行预测
result = model.predict_standard(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords,
    confidence_z=1.96
)

print(f"预测值: {result['prediction']}")
print(f"方差: {result['variance']}")
print(f"残差: {result['residual']}")
print(f"架构: {result['details']['architecture']}")
```

### 数据预处理

```python
# 预处理数据
preprocessed = model.preprocess_residual_kriging_data(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords,
    batch_size=32,
    use_runtime_stats=True
)

print(f"特征矩阵形状: {preprocessed['feature_matrix'].shape}")
print(f"特征名称: {preprocessed['feature_names']}")
```

### 模型训练

```python
# 准备训练数据
train_batch = [
    {"coords": coords, "values": values, "targets": targets},
    # ...
]

# 训练步骤
loss = model.train_step(train_batch, lr=1e-2)

# 验证步骤
val_loss = model.val_step(val_batch)
```

### 状态保存与加载

```python
# 保存模型状态
state = model.get_state()

# 加载模型状态
model.load_state(state)
```

## 特征详解

| 特征名称 | 维度 | 说明 |
|---------|------|------|
| mean_neighbor_distance | 1 | k近邻平均距离，反映局部稀疏度 |
| std_neighbor_distance | 1 | k近邻距离标准差，反映分布均匀性 |
| direction_x | 1 | x方向平均方向余弦，反映主导方向 |
| direction_y | 1 | y方向平均方向余弦，反映主导方向 |
| local_density | 1 | 局部点密度，k / (π * r_max²) |
| value_skewness | 1 | 局部值偏度，衡量分布不对称性 |
| value_kurtosis | 1 | 局部值峰度，衡量分布尖锐程度 |
| prior_mean | 1 | 克里金先验均值 |

### 特征计算细节

**方向余弦**：
```python
diff = sample_coords[indices] - query_coord
direction = diff / (distance[:, None] + 1e-12)
direction_mean = np.mean(direction, axis=1)
```

**局部密度**：
```python
local_max_dist = np.max(local_dist, axis=1)
density = k / (np.pi * (local_max_dist ** 2))
```

**标准化值**（用于计算偏度和峰度）：
```python
local_mean = np.mean(local_vals, axis=1)
local_std = np.std(local_vals, axis=1) + 1e-12
z = (local_vals - local_mean) / local_std
skew = np.mean(z ** 3, axis=1)
kurt = np.mean(z ** 4, axis=1)
```

## 输出说明

### ResidualKrigingOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `mean` | np.ndarray | 最终预测均值 |
| `variance` | np.ndarray | 预测方差 |
| `residual` | np.ndarray | 残差值（预测 - 克里金先验） |

### predict_standard 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `prediction` | list | 预测值列表 |
| `variance` | list | 方差列表 |
| `residual` | list | 残差列表 |
| `uncertainty` | list | 不确定性（标准差）列表 |
| `confidence_interval` | dict | 置信区间（lower, upper, z_score） |
| `details` | dict | 详细信息（架构、样本数等） |
| `preprocess` | dict | 预处理信息 |

## 架构选择

### MLP架构

**适用场景**：
- 数据量较小
- 特征与目标关系相对简单
- 需要快速推理

**特点**：
- 参数量少，训练快速
- 通过跳跃连接和混合增强表达能力

### CNN架构

**适用场景**：
- 查询点分布较密集
- 空间连续性较强
- 需要平滑预测

**特点**：
- 基于空间距离的核方法
- 自然的平滑效果
- 对噪声鲁棒

### Hybrid架构（推荐）

**适用场景**：
- 复杂空间过程
- 需要同时捕获局部和全局模式
- 追求最佳精度

**特点**：
- 结合三种分支的优势
- 多尺度特征融合
- 最强的表达能力

## 训练细节

### 损失函数

```python
# 残差损失
residual_loss = mean((prediction - target) ** 2)

# 正则化损失
reg_loss = 1e-3 * (mean(mlp_w1 ** 2) + mean(mlp_w2 ** 2))

# 一致性损失（空间平滑）
consistency = mean((residual[1:] - residual[:-1]) ** 2)

# 总损失
total_loss = residual_loss + reg_loss + 0.1 * consistency
```

### 梯度更新

```python
# 偏置更新
bias -= lr * mean(error)

# 残差缩放更新
res_scale -= lr * mean(error * residual)
```

## 适用场景

Residual-Kriging 适用于以下场景：

1. **特征工程有效**：空间特征与目标值有明确关系
2. **需要多尺度建模**：同时考虑局部和全局模式
3. **计算资源有限**：相比GNN和Attention模型更轻量
4. **需要快速推理**：预测速度快

## 优势与局限

### 优势

- 计算效率高，适合大规模数据
- 特征工程提供可解释性
- 多分支架构提供多样性
- 训练稳定，收敛快

### 局限

- 依赖特征工程质量
- 对复杂非线性模式建模能力有限
- 需要手动设计特征

## 性能优化建议

1. **架构选择**：
   - 简单任务：MLP架构
   - 平滑空间过程：CNN架构
   - 复杂任务：Hybrid架构

2. **基线选择**：
   - 无明显趋势：OrdinaryKriging
   - 存在趋势：UniversalKriging

3. **特征工程**：
   - 根据领域知识调整特征
   - 考虑添加领域特定特征

4. **正则化**：
   - 小数据集：增加正则化系数
   - 大数据集：减少正则化系数

## 示例代码

### 比较不同架构

```python
# 测试不同架构
architectures = ["mlp", "cnn", "hybrid"]
results = {}

for arch in architectures:
    model = ResidualKrigingModel(architecture=arch)
    result = model.predict_standard(
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords
    )
    results[arch] = result
    print(f"{arch} 预测: {result['prediction']}")
```

### 特征分析

```python
# 获取特征矩阵
preprocessed = model.preprocess_residual_kriging_data(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords
)

features = preprocessed['feature_matrix']
feature_names = preprocessed['feature_names']

# 分析特征重要性
import pandas as pd
df = pd.DataFrame(features, columns=feature_names)
print(df.describe())
```

### 残差分析

```python
# 分析残差分布
result = model.predict_standard(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords
)

residuals = np.array(result['residual'])
print(f"残差均值: {np.mean(residuals)}")
print(f"残差标准差: {np.std(residuals)}")
print(f"残差范围: [{np.min(residuals)}, {np.max(residuals)}]")
```

## 参考文献

1. Cressie, N. (1993). Statistics for spatial data.
2. He, K., et al. (2016). Deep residual learning for image recognition.
3. LeCun, Y., et al. (1998). Gradient-based learning applied to document recognition.