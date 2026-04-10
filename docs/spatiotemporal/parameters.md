# 空间插值模型参数说明文档

## 概述

本文档提供了UDAKE空间插值扩展模型（GNN-Kriging、Attention-Kriging、Residual-Kriging）的完整参数说明，包括构造参数、训练参数和预测参数。

## 模型对比

| 特性 | GNN-Kriging | Attention-Kriging | Residual-Kriging |
|------|-------------|-------------------|------------------|
| 核心架构 | 图神经网络 | Transformer | 多分支残差网络 |
| 空间建模 | 图结构 | 注意力机制 | 特征工程 |
| 计算复杂度 | O(n × k) | O(n²) | O(n × k) |
| 适用规模 | 中等 | 小到中等 | 大 |
| 可解释性 | 中 | 高（注意力） | 高（特征） |
| 训练难度 | 中 | 中 | 低 |

## GNN-Kriging 参数

### 构造函数参数

```python
GNNKrigingModel(hidden_dim=16, graph_strategy="knn", seed=42)
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `hidden_dim` | int | 16 | 4~32 | 隐藏层维度，控制模型容量 |
| `graph_strategy` | str | "knn" | "knn"/"radius"/"voronoi"/"delaunay" | 图构建策略 |
| `seed` | int | 42 | 任意整数 | 随机种子，确保可复现 |

### 子模块参数

#### SpatialGraphBuilder

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_k` | int | 8 | k近邻数量 |
| `default_radius` | float | 0.25 | 半径阈值 |

#### CovarianceFeatureExtractor

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `bandwidth` | float | 0.2 | 协方差核带宽，控制局部范围 |

#### LearnablePositionEncoding

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 8 | 编码维度 |

#### GCNLayer

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `hidden_dim` | int | 16 | 隐藏维度 |
| `seed` | int | 42 | 随机种子 |

#### GATLayer

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `hidden_dim` | int | 16 | 隐藏维度 |
| `heads` | int | 4 | 注意力头数 |
| `seed` | int | 43 | 随机种子 |

#### EdgeConvLayer

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `hidden_dim` | int | 16 | 隐藏维度 |
| `seed` | int | 44 | 随机种子 |

#### MultiScaleAttention

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 16 | 注意力维度 |
| `heads` | int | 4 | 注意力头数 |
| `seed` | int | 45 | 随机种子 |

### 训练参数

#### train_step 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch` | list | 必需 | 批次数据，每个元素包含coords、values、targets |
| `lr` | float | 1e-2 | 学习率 |
| `mixed_precision` | bool | False | 是否使用混合精度（当前未实现） |

### 预测参数

#### predict_standard 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标，形状(n, 2) |
| `sample_values` | np.ndarray | 必需 | 采样点值，形状(n,) |
| `query_coords` | np.ndarray | None | 查询点坐标，形状(m, 2)，默认为采样点 |
| `confidence_z` | float | 1.96 | 置信区间z分数（1.96对应95%置信度） |

#### preprocess_gnn_kriging_data 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标 |
| `sample_values` | np.ndarray | 必需 | 采样点值 |
| `query_coords` | np.ndarray | None | 查询点坐标 |
| `batch_size` | int | None | 批次大小，默认为查询点数 |
| `use_runtime_stats` | bool | True | 是否使用运行时统计进行归一化 |

## Attention-Kriging 参数

### 构造函数参数

```python
AttentionKrigingModel(dim=24, heads=4, seed=42)
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `dim` | int | 24 | 8~64 | 模型维度，控制模型容量 |
| `heads` | int | 4 | 1~8 | 注意力头数 |
| `seed` | int | 42 | 任意整数 | 随机种子 |

### 子模块参数

#### LearnablePositionEncoding

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 12 | 编码维度（dim // 2） |

#### TransformerEncoderBlock

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 24 | 模型维度 |
| `heads` | int | 4 | 注意力头数 |
| `seed` | int | 43 | 随机种子 |

#### MultiHeadSpatialAttention

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 24 | 注意力维度 |
| `heads` | int | 4 | 注意力头数 |
| `seed` | int | 44~46 | 不同层的随机种子 |

### 训练参数

#### train_step 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch` | list | 必需 | 批次数据 |
| `lr` | float | 1e-2 | 学习率 |
| `mixed_precision` | bool | False | 是否使用混合精度（当前未实现） |

### 预测参数

#### predict_standard 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标，形状(n, 2) |
| `sample_values` | np.ndarray | 必需 | 采样点值，形状(n,) |
| `query_coords` | np.ndarray | 必需 | 查询点坐标，形状(m, 2) |
| `confidence_z` | float | 1.96 | 置信区间z分数 |

#### preprocess_attention_kriging_data 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标 |
| `sample_values` | np.ndarray | 必需 | 采样点值 |
| `query_coords` | np.ndarray | None | 查询点坐标 |
| `batch_size` | int | None | 批次大小 |
| `use_runtime_stats` | bool | True | 是否使用运行时统计进行归一化 |

## Residual-Kriging 参数

### 构造函数参数

```python
ResidualKrigingModel(architecture="hybrid", baseline="universal", seed=42)
```

| 参数 | 类型 | 默认值 | 范围 | 说明 |
|------|------|--------|------|------|
| `architecture` | str | "hybrid" | "mlp"/"cnn"/"hybrid" | 网络架构类型 |
| `baseline` | str | "universal" | "ordinary"/"universal" | 克里金基线类型 |
| `seed` | int | 42 | 任意整数 | 随机种子 |

### 子模块参数

#### MLP分支

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `mlp_w1` | np.ndarray | N(0, 0.08²) | 第一层权重，形状(8, 12) |
| `mlp_w2` | np.ndarray | N(0, 0.08²) | 第二层权重，形状(12, 1) |

#### 空间索引

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 自动构建 | - | - | 基于坐标哈希检测变化 |

### 训练参数

#### train_step 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `batch` | list | 必需 | 批次数据 |
| `lr` | float | 1e-2 | 学习率 |
| `mixed_precision` | bool | False | 是否使用混合精度（当前未实现） |

### 预测参数

#### predict_standard 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标，形状(n, 2) |
| `sample_values` | np.ndarray | 必需 | 采样点值，形状(n,) |
| `query_coords` | np.ndarray | 必需 | 查询点坐标，形状(m, 2) |
| `confidence_z` | float | 1.96 | 置信区间z分数 |

#### preprocess_residual_kriging_data 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sample_coords` | np.ndarray | 必需 | 采样点坐标 |
| `sample_values` | np.ndarray | 必需 | 采样点值 |
| `query_coords` | np.ndarray | None | 查询点坐标 |
| `batch_size` | int | None | 批次大小 |
| `use_runtime_stats` | bool | True | 是否使用运行时统计进行归一化 |

## 通用参数说明

### 输入验证

所有模型共享相同的输入验证逻辑：

| 约束 | 说明 |
|------|------|
| `sample_coords.shape` | (n, 2)，n ≥ 2 |
| `sample_values.shape` | (n,) |
| `query_coords.shape` | (m, 2) |
| 数值范围 | 必须为有限值（finite） |

### 置信区间参数

| z分数 | 置信度 |
|-------|--------|
| 1.0 | ~68% |
| 1.64 | ~90% |
| 1.96 | ~95% |
| 2.58 | ~99% |
| 3.0 | ~99.7% |

### 学习率建议

| 场景 | 学习率 |
|------|--------|
| 标准训练 | 1e-2 |
| 稳定训练 | 5e-3 |
| 微调 | 1e-3 |
| 高噪声数据 | 5e-4 |

## 参数调优指南

### GNN-Kriging

1. **hidden_dim**：
   - 简单任务：8-12
   - 中等任务：16（默认）
   - 复杂任务：20-24

2. **graph_strategy**：
   - 小数据集（<100）：knn
   - 中数据集（100-1000）：knn或radius
   - 大数据集（>1000）：radius
   - 规则采样：delaunay

3. **default_k**：
   - 稀疏数据：12-16
   - 密集数据：4-8
   - 默认：8

### Attention-Kriging

1. **dim**：
   - 简单任务：16
   - 中等任务：24（默认）
   - 复杂任务：32-48

2. **heads**：
   - 小数据集：2-4
   - 中数据集：4（默认）
   - 大数据集：6-8

### Residual-Kriging

1. **architecture**：
   - 快速推理：mlp
   - 平滑预测：cnn
   - 最佳精度：hybrid（默认）

2. **baseline**：
   - 无趋势：ordinary
   - 有趋势：universal（默认）

## 性能参数

### 内存使用

| 模型 | 内存复杂度 | 说明 |
|------|-----------|------|
| GNN-Kriging | O(n × k + m × k) | n样本数，m查询数，k近邻数 |
| Attention-Kriging | O(n × m) | 注意力矩阵 |
| Residual-Kriging | O(n × k + m × k) | 与GNN类似 |

### 计算时间

| 模型 | 时间复杂度 | 相对速度 |
|------|-----------|---------|
| GNN-Kriging | O(n × k × d) | 中等 |
| Attention-Kriging | O(n × m × d) | 较慢 |
| Residual-Kriging | O(n × k × d) | 较快 |

## 参数保存与加载

所有模型支持状态保存和加载：

```python
# 保存状态
state = model.get_state()
# 保存到文件
import json
with open('model_state.json', 'w') as f:
    json.dump(state, f)

# 加载状态
with open('model_state.json', 'r') as f:
    state = json.load(f)
model.load_state(state)
```

## 常见问题

### Q: 如何选择合适的模型？

A: 根据数据特点和需求选择：
- 数据量大且需要快速预测：Residual-Kriging
- 需要捕获复杂空间依赖：GNN-Kriging
- 需要理解哪些点影响预测：Attention-Kriging

### Q: 如何处理大规模数据？

A: 使用批次处理：
```python
preprocessed = model.preprocess_data(
    ...,
    batch_size=1000
)
```

### Q: 如何提高预测精度？

A: 尝试以下方法：
1. 增加模型容量（hidden_dim、dim）
2. 调整图策略或注意力头数
3. 使用更多训练数据
4. 调整学习率和训练轮数

### Q: 如何设置随机种子？

A: 在初始化时设置：
```python
model = GNNKrigingModel(seed=123)
```

## 参数速查表

### GNN-Kriging

```python
# 推荐配置
model = GNNKrigingModel(
    hidden_dim=16,          # 模型容量
    graph_strategy="knn",   # 图构建
    seed=42                 # 可复现性
)

# 快速配置
model = GNNKrigingModel(
    hidden_dim=8,
    graph_strategy="knn"
)

# 高精度配置
model = GNNKrigingModel(
    hidden_dim=24,
    graph_strategy="delaunay"
)
```

### Attention-Kriging

```python
# 推荐配置
model = AttentionKrigingModel(
    dim=24,     # 模型维度
    heads=4,    # 注意力头
    seed=42
)

# 快速配置
model = AttentionKrigingModel(
    dim=16,
    heads=2
)

# 高精度配置
model = AttentionKrigingModel(
    dim=32,
    heads=8
)
```

### Residual-Kriging

```python
# 推荐配置
model = ResidualKrigingModel(
    architecture="hybrid",   # 混合架构
    baseline="universal",    # 通用克里金
    seed=42
)

# 快速配置
model = ResidualKrigingModel(
    architecture="mlp",
    baseline="ordinary"
)

# 高精度配置
model = ResidualKrigingModel(
    architecture="hybrid",
    baseline="universal"
)
```

## 版本信息

- 文档版本：1.0
- 最后更新：2026-04-10
- 适用代码版本：UDAKE main分支