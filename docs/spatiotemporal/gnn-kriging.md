# GNN-Kriging 模型文档

## 概述

GNN-Kriging（Graph Neural Network Kriging）是一种结合了图神经网络和传统克里金插值的空间插值模型。该模型利用图结构捕获空间数据中的局部和全局空间依赖关系，通过残差学习改进克里金先验的预测结果。

## 核心思想

GNN-Kriging 采用**图神经网络先验融合**策略，在克里金插值的基础上构建残差学习网络：

1. **克里金先验**：使用通用克里金方法作为基线预测器，提供初始的均值和方差估计
2. **空间图构建**：根据查询点的空间位置和预测值构建空间图
3. **图神经网络**：使用多种图卷积层（GCN、GAT、EdgeConv）提取空间特征
4. **残差学习**：学习克里金先验的残差，最终预测为 `预测 = 克里金先验 + 残差`

## 模型架构

### 1. 特征提取

模型为每个查询点构建多维特征向量，包括：

- **空间特征**（4维）：坐标极坐标表示（半径、角度）和坐标值
- **协方差特征**（2维）：局部均值和局部方差
- **趋势特征**（2维）：全局趋势的偏差项和x方向系数
- **正弦位置编码**（12维）：基于坐标的正弦位置编码
- **可学习位置编码**（8维）：通过学习得到的位置表示
- **先验特征**（2维）：克里金先验的均值和方差

总特征维度：30维

### 2. 图构建

使用 `SpatialGraphBuilder` 构建空间图，支持多种策略：

- **knn**：k近邻图（默认 k=8）
- **radius**：半径图（默认半径=0.25）
- **voronoi**：Voronoi图
- **delaunay**：Delaunay三角剖分图

权重模式：混合权重（hybrid），结合距离和值相似度

### 3. 图神经网络层

模型使用三种不同的图卷积层捕获空间依赖：

- **GCN（Graph Convolutional Network）**：基于邻接矩阵的图卷积
- **GAT（Graph Attention Network）**：多头注意力机制（4个头）
- **EdgeConv（Edge Convolution）**：基于边的卷积操作

三种层的输出通过投影层融合后，再通过多头注意力机制进一步处理。

### 4. 预测头

使用 `MultiTaskHead` 生成最终预测：

- **均值预测**：残差值，用于修正克里金先验
- **方差预测**：预测不确定性
- **辅助任务**：可选的辅助输出用于正则化

## 参数说明

### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `hidden_dim` | int | 16 | 隐藏层维度（最小值为4） |
| `graph_strategy` | str | "knn" | 图构建策略：knn/radius/voronoi/delaunay |
| `seed` | int | 42 | 随机种子，确保结果可复现 |

### 关键子模块参数

- **SpatialGraphBuilder**：
  - `default_k`: 8（k近邻数量）
  - `default_radius`: 0.25（半径阈值）

- **CovarianceFeatureExtractor**：
  - `bandwidth`: 0.2（协方差核带宽）

- **LearnablePositionEncoding**：
  - `dim`: 8（编码维度）

- **GCNLayer**：
  - `hidden_dim`: 16（隐藏维度）
  - `seed`: 42（随机种子）

- **GATLayer**：
  - `hidden_dim`: 16（隐藏维度）
  - `heads`: 4（注意力头数）
  - `seed`: 43（随机种子）

- **EdgeConvLayer**：
  - `hidden_dim`: 16（隐藏维度）
  - `seed`: 44（随机种子）

- **MultiScaleAttention**：
  - `dim`: 16（注意力维度）
  - `heads`: 4（注意力头数）
  - `seed`: 45（随机种子）

### 可训练参数

- `proj`: 投影矩阵（hidden_dim * 3, hidden_dim）
- `bias`: 偏置项
- `residual_gain`: 残差增益系数

## 使用方法

### 基本预测

```python
from deep_learning.models.spatial_interpolation.gnn_kriging import GNNKrigingModel

# 初始化模型
model = GNNKrigingModel(hidden_dim=16, graph_strategy="knn")

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
print(f"置信区间: {result['confidence_interval']}")
```

### 数据预处理

```python
# 预处理数据用于进一步分析
preprocessed = model.preprocess_gnn_kriging_data(
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
| coord_x | 1 | x坐标 |
| coord_y | 1 | y坐标 |
| radius | 1 | 极坐标半径 |
| angle | 1 | 极坐标角度 |
| local_mean | 1 | k近邻局部均值 |
| local_var | 1 | k近邻局部方差 |
| trend_bias | 1 | 趋势偏置 |
| trend_x | 1 | x方向趋势系数 |
| sin_pos_0~11 | 12 | 正弦位置编码 |
| learn_pos_0~7 | 8 | 可学习位置编码 |
| prior_mean | 1 | 克里金先验均值 |
| prior_var | 1 | 克里金先验方差 |

## 输出说明

### GNNKrigingOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `mean` | np.ndarray | 最终预测均值 |
| `variance` | np.ndarray | 预测方差 |
| `residual` | np.ndarray | 残差值（预测 - 克里金先验） |
| `adjacency` | np.ndarray | 图的邻接矩阵 |

### predict_standard 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `prediction` | list | 预测值列表 |
| `variance` | list | 方差列表 |
| `residual` | list | 残差列表 |
| `uncertainty` | list | 不确定性（标准差）列表 |
| `confidence_interval` | dict | 置信区间（lower, upper, z_score） |
| `details` | dict | 详细信息（图策略、样本数等） |
| `preprocess` | dict | 预处理信息（特征名、批次切片等） |

## 适用场景

GNN-Kriging 适用于以下场景：

1. **数据具有明显空间结构**：采样点之间存在空间相关性
2. **需要捕获局部和全局依赖**：既要考虑近邻影响，又要考虑全局模式
3. **预测结果需要不确定性估计**：提供方差和置信区间
4. **中等规模数据集**：样本点数量适中（几十到几千）

## 优势与局限

### 优势

- 结合了克里金的理论保证和神经网络的表达能力
- 通过图结构显式建模空间依赖
- 提供不确定性估计
- 支持多种图构建策略

### 局限

- 计算复杂度较高，特别是图构建和GNN推理
- 需要足够的数据来学习有效模式
- 超参数较多，需要调优

## 性能优化建议

1. **图策略选择**：
   - 小数据集：使用 knn 策略
   - 大数据集：使用 radius 策略减少边数
   - 规则采样：使用 delaunay 策略

2. **隐藏维度**：
   - 简单任务：使用较小的 hidden_dim（8-12）
   - 复杂任务：使用较大的 hidden_dim（16-24）

3. **批次处理**：
   - 大规模预测：使用 batch_size 参数分批处理

## 参考文献

1. Kipf, T. N., & Welling, M. (2017). Semi-supervised classification with graph convolutional networks.
2. Veličković, P., et al. (2018). Graph attention networks.
3. Wang, Y., et al. (2019). Dynamic graph CNN for learning on point clouds.