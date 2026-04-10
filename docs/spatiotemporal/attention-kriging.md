# Attention-Kriging 模型文档

## 概述

Attention-Kriging 是一种基于Transformer架构的空间插值模型，利用双向交叉注意力机制在采样点和查询点之间建立动态依赖关系。该模型通过多头空间注意力捕获长程空间依赖，并在克里金先验基础上进行残差学习。

## 核心思想

Attention-Kriging 采用**Transformer风格编码器 + 双向交叉注意力**策略：

1. **编码器**：使用Transformer编码器块对采样点和查询点进行独立编码
2. **双向交叉注意力**：
   - 采样点 → 查询点（Sample-to-Query）：学习查询点如何从采样点获取信息
   - 查询点 → 采样点（Query-to-Sample）：捕获全局上下文信息
3. **动态权重融合**：根据距离和方差自适应调整融合权重
4. **残差学习**：在克里金先验上学习残差

## 模型架构

### 1. 位置编码

模型使用两种位置编码组合：

- **正弦位置编码**（dim/2维）：固定位置编码，提供绝对位置信息
- **可学习位置编码**（dim/2维）：通过学习优化的位置表示

### 2. Transformer编码器块

每个编码器块包含：

- **多头空间注意力**：捕获自注意力模式
- **前馈神经网络**：两层MLP（dim → dim*2 → dim）
- **层归一化**：在残差连接后应用
- **残差连接**：保留原始信息

### 3. 双向交叉注意力

模型使用两个独立的注意力头：

- **sample_to_query**：查询点作为Query，采样点作为Key和Value
- **query_to_sample**：采样点作为Query，查询点作为Key和Value

### 4. 动态融合机制

融合权重由三部分组成：

- **距离权重**：基于相对距离的指数衰减
- **方差权重**：1/(1 + prior_var)，不确定性高的点权重低
- **自适应系数**：`adaptive = dynamic_weight * distance_weight * variance_weight`

最终上下文：
```
context = attn_sq + adaptive * attn_sq + 0.2 * attn_qs.mean(axis=0, keepdims=True)
```

## 参数说明

### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `dim` | int | 24 | 模型维度（最小值为8） |
| `heads` | int | 4 | 注意力头数 |
| `seed` | int | 42 | 随机种子 |

### 关键子模块参数

- **LearnablePositionEncoding**：
  - `dim`: dim // 2 = 12（编码维度）
  - `seed`: 42（随机种子）

- **TransformerEncoderBlock**：
  - `dim`: 24（模型维度）
  - `heads`: 4（注意力头数）
  - `seed`: 43（随机种子）

- **MultiHeadSpatialAttention**：
  - `dim`: 24（注意力维度）
  - `heads`: 4（注意力头数）
  - `seed`: 44~45（不同层的随机种子）

- **MultiTaskHead**：
  - `in_dim`: 24（输入维度）
  - `with_aux`: True（是否包含辅助任务）
  - `seed`: 46（随机种子）

### 可训练参数

- `dynamic_weight`: 动态权重系数
- `bias`: 偏置项
- 位置编码矩阵（learnable）
- 注意力权重矩阵
- FFN权重矩阵

## 使用方法

### 基本预测

```python
from deep_learning.models.spatial_interpolation.attention_kriging import AttentionKrigingModel

# 初始化模型
model = AttentionKrigingModel(dim=24, heads=4)

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
print(f"注意力权重摘要: {result['attention_summary']}")
```

### 数据预处理

```python
# 预处理数据
preprocessed = model.preprocess_attention_kriging_data(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords,
    batch_size=32,
    use_runtime_stats=True
)

print(f"特征矩阵形状: {preprocessed['feature_matrix'].shape}")
print(f"特征名称: {preprocessed['feature_names']}")
print(f"注意力摘要: {preprocessed['attention_summary']}")
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
| sin_pos_0~11 | 12 | 正弦位置编码 |
| learn_pos_0~11 | 12 | 可学习位置编码 |
| prior_mean | 1 | 克里金先验均值 |
| prior_var | 1 | 克里金先验方差 |
| attn_weight_mean | 1 | 注意力权重均值 |
| attn_weight_max | 1 | 注意力权重最大值 |
| attn_weight_std | 1 | 注意力权重标准差 |
| attn_weight_entropy | 1 | 注意力权重熵（衡量注意力集中度） |

## 输出说明

### AttentionKrigingOutput

| 字段 | 类型 | 说明 |
|------|------|------|
| `mean` | np.ndarray | 最终预测均值 |
| `variance` | np.ndarray | 预测方差 |
| `attention_weights` | np.ndarray | 注意力权重矩阵（查询点 × 采样点） |

### predict_standard 返回值

| 字段 | 类型 | 说明 |
|------|------|------|
| `prediction` | list | 预测值列表 |
| `variance` | list | 方差列表 |
| `uncertainty` | list | 不确定性（标准差）列表 |
| `attention_summary` | dict | 注意力权重摘要（mean_weight, max_weight） |
| `confidence_interval` | dict | 置信区间（lower, upper, z_score） |
| `details` | dict | 详细信息（样本数、查询点数） |
| `preprocess` | dict | 预处理信息 |

## 注意力机制详解

### 相对位置编码

相对位置编码捕获查询点与采样点之间的空间关系：

- **dx**: x方向相对距离
- **dy**: y方向相对距离
- **distance**: 欧氏距离

### 双向注意力

**Sample-to-Query (attn_sq)**:
- Query: 查询点token
- Key/Value: 采样点token
- 作用：让每个查询点从相关采样点聚合信息

**Query-to-Sample (attn_qs)**:
- Query: 采样点token
- Key/Value: 查询点token
- 作用：捕获全局上下文，用于正则化

### 动态权重

```python
distance_weight = exp(-distance / 0.2)
variance_weight = 1.0 / (1.0 + prior_var)
adaptive = clip(dynamic_weight * distance_weight * variance_weight, 0.0, 2.0)
```

- 距离近的点权重高
- 不确定性低的点权重高
- 通过 `dynamic_weight` 全局调节

## 适用场景

Attention-Kriging 适用于以下场景：

1. **长程空间依赖**：采样点和查询点之间的距离较大
2. **非平稳空间过程**：空间关系随位置变化
3. **需要可解释的注意力**：需要理解哪些采样点对预测贡献最大
4. **不规则采样**：采样点分布不均匀

## 优势与局限

### 优势

- 强大的长程依赖建模能力
- 注意力机制提供可解释性
- 动态权重自适应调整
- 适合非平稳空间过程

### 局限

- 计算复杂度为O(n²)，n为查询点数
- 需要较大的数据集才能发挥优势
- 超参数较多，需要调优

## 性能优化建议

1. **模型维度**：
   - 简单任务：dim=16, heads=2
   - 复杂任务：dim=24~32, heads=4~8

2. **批次处理**：
   - 大规模预测：使用 batch_size 参数分批处理

3. **注意力优化**：
   - 对于大规模数据，考虑稀疏注意力
   - 使用位置编码增强空间感知

## 注意力可视化

注意力权重矩阵可以用于：

1. **识别关键采样点**：权重高的采样点对预测贡献大
2. **检测异常**：异常采样点的注意力模式会不同
3. **空间依赖分析**：理解空间相关性的范围和方向

## 示例代码

### 提取注意力权重

```python
# 直接调用forward获取注意力权重
output = model.forward(
    sample_coords=sample_coords,
    sample_values=sample_values,
    query_coords=query_coords
)

# 注意力权重矩阵 (n_queries × n_samples)
attention_weights = output.attention_weights

# 可视化
import matplotlib.pyplot as plt
plt.imshow(attention_weights, cmap='hot', aspect='auto')
plt.xlabel('Sample Points')
plt.ylabel('Query Points')
plt.colorbar(label='Attention Weight')
plt.show()
```

### 分析注意力熵

```python
# 计算注意力熵（衡量注意力集中度）
attention_norm = attention_weights / attention_weights.sum(axis=1, keepdims=True)
entropy = -np.sum(attention_norm * np.log(attention_norm + 1e-12), axis=1)

# 熵越高，注意力越分散
# 熵越低，注意力越集中
print(f"注意力熵: {entropy}")
```

## 参考文献

1. Vaswani, A., et al. (2017). Attention is all you need.
2. Dosovitskiy, A., et al. (2020). An image is worth 16x16 words: Transformers for image recognition at scale.
3. Liu, Y., et al. (2021). Swin Transformer: Hierarchical vision transformer using shifted windows.