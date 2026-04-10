# GCAE 异常检测模型文档

## 1. 模型概述

### 1.1 简介

GCAE (Graph Convolutional Autoencoder, 图卷积自编码器) 异常检测器是一种基于图神经网络的异常检测方法，特别适合处理具有空间拓扑结构的数据。该模型通过图卷积、图注意力、边卷积等操作捕捉空间依赖关系，从而识别异常。

### 1.2 工作原理

GCAE 异常检测器采用图编码-解码结构：

1. **图构建**：
   - 使用 k 近邻 (k-NN) 构建邻接矩阵
   - 默认 k=8，表示每个节点连接最近的 8 个邻居

2. **图编码器**：
   - **GCN 层**：标准化邻接矩阵聚合邻居信息
   - **GAT 层**：注意力机制动态分配邻居权重
   - **EdgeConv 层**：捕捉边特征的相对变化
   - 合并多层特征后进行 SVD 降维

3. **潜在表示**：
   - 通过投影矩阵得到潜在嵌入
   - 保留图结构的拓扑信息

4. **图解码器**：
   - 从潜在表示重建节点特征
   - 同时重建图的邻接结构

5. **异常检测**：
   - 节点重建误差
   - 节点潜在距离
   - 边结构误差
   - 子图异常分数

### 1.3 网络架构

```
输入：坐标 + 值
  ↓
节点特征构建 (coord_x, coord_y, radius, value)
  ↓
图构建 (k-NN, k=8)
  ↓
GCN 层 (邻接矩阵聚合)
  ↓
GAT 层 (注意力机制)
  ↓
EdgeConv 层 (边特征)
  ↓
特征融合 + SVD 降维
  ↓
潜在表示 z (latent_dim=4)
  ↓
解码重建 (特征 + 邻接矩阵)
  ↓
输出：节点分数 + 边分数 + 子图分数
```

### 1.4 损失函数

```
总损失 = α × 特征重建损失 + β × 结构损失

特征重建损失 = MSE(融合特征, 重建特征)
结构损失 = MSE(真实邻接矩阵, 重建邻接矩阵)
```

默认权重：α=0.6 (特征), β=0.4 (结构)

### 1.5 适用场景

- 适合检测空间结构异常（孤立的异常点）
- 适合检测图拓扑异常（连接异常）
- 适合需要考虑空间上下文的场景
- 适合具有明确空间关系的数据
- 不适合完全随机分布的数据

---

## 2. LIME 解释指南

### 2.1 概述

对于 GCAE 模型，LIME 解释关注图结构特征对异常分数的贡献。

### 2.2 关键特征

GCAE 模型使用以下特征：

- **空间特征**：coord_x, coord_y, radius
- **值特征**：value
- **图响应特征**：gcn_response, gat_response, edgeconv_response
- **结构特征**：node_degree, adj_density
- **局部统计特征**：local_mean_k5, local_std_k5

### 2.3 实现步骤

```python
from deep_learning.models.anomaly_detection import GCAEAnomalyDetector
import numpy as np

# 1. 训练模型
detector = GCAEAnomalyDetector()
detector.fit(coords, values)

# 2. 预处理数据获取特征
preprocessed = detector.preprocess_graph_data(coords, values)
features = preprocessed["processed_features"]
feature_names = preprocessed["feature_names"]

# 3. 定义预测函数
def predict_fn(X):
    """LIME 使用的预测函数"""
    # 需要从特征重建 coords 和 values
    sample_coords = X[:, :2]
    sample_values = X[:, 3]  # value 列
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["node"]

# 4. 应用 LIME（伪代码）
# lime_explainer = lime.lime_tabular.LimeTabularExplainer(
#     training_data=features,
#     feature_names=feature_names,
#     mode='regression'
# )
# explanation = lime_explainer.explain_instance(
#     features[idx], predict_fn, num_features=8
# )
```

### 2.4 解释结果解读

LIME 返回的特征重要性：

- **node_degree**：节点度数异常
- **gcn_response**：图卷积响应异常
- **edgeconv_response**：边特征异常
- **adj_density**：邻接密度异常
- **local_mean_k5**：局部统计异常

---

## 3. SHAP 解释指南

### 3.1 概述

SHAP 分析 GCAE 模型中各特征对节点异常分数的贡献。

### 3.2 实现步骤

```python
import shap
from deep_learning.models.anomaly_detection import GCAEAnomalyDetector

# 1. 训练模型
detector = GCAEAnomalyDetector()
detector.fit(coords, values)

# 2. 准备背景数据
preprocessed = detector.preprocess_graph_data(coords, values)
background = preprocessed["processed_features"][:100]
feature_names = preprocessed["feature_names"]

# 3. 定义预测函数
def model_predict(X):
    sample_coords = X[:, :2]
    sample_values = X[:, 3]
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["node"].reshape(-1, 1)

# 4. 创建解释器
explainer = shap.KernelExplainer(model_predict, background)

# 5. 计算解释
instance = preprocessed["processed_features"][idx]  # 要解释的样本
shap_values = explainer.shap_values(instance)

# 6. 可视化
# shap.waterfall_plot(shap_values[0], feature_names=feature_names)
```

### 3.3 图级解释

GCAE 支持子图级别的解释：

```python
# 获取子图分数
result = detector.predict(coords, values)
subgraph_scores = result["subgraph_scores"]

# 可以使用 SHAP 分析整个图的异常分数
def graph_predict(X):
    """预测整个图的异常分数"""
    # 需要构建图的表示
    return ...

# 然后使用 SHAP 分析图特征的重要性
```

---

## 4. 异常分数解释说明

### 4.1 分数类型

GCAE 提供三个层次的异常分数：

1. **节点分数** (Node Score)
2. **边分数** (Edge Score)
3. **子图分数** (Subgraph Score)

### 4.2 分数详解

#### 4.2.1 节点分数

**定义**：
```
节点分数 = 0.7 × 归一化(节点重建误差) + 0.3 × 归一化(潜在距离)
```

**组成**：
- **节点重建误差**：节点特征的重建能力
- **潜在距离**：节点在潜在空间偏离中心的程度

**意义**：
- 高值：该节点特征或位置异常
- 低值：该节点符合正常模式

**典型范围**：0 ~ 1

#### 4.2.2 边分数

**定义**：
```
边分数 = |真实邻接矩阵 - 重建邻接矩阵|
```

**计算**：
- 比较真实图的边连接和潜在空间重建的边连接
- 基于潜在表示的内积重建邻接矩阵

**意义**：
- 高值：该边连接异常（应该连接却没连接，或不应连接却连接）
- 低值：该边连接符合正常拓扑

**典型范围**：0 ~ 1

**矩阵形式**：N × N 矩阵，N 为节点数

#### 4.2.3 子图分数

**定义**：
```
子图分数[i] = (节点分数[i] + 邻居节点分数的平均) / 2
```

**意义**：
- 高值：该节点及其邻居都异常
- 低值：该节点或其邻居至少有一个正常
- 捕捉局部区域的异常聚集

**典型范围**：0 ~ 1

### 4.3 综合异常判断

GCAE 的 predict 方法主要使用节点分数：

```python
# 主要使用节点分数进行异常检测
node_scores = score_bundle["node"]
threshold = compute_threshold(node_scores, ...)
```

但边分数和子图分数可用于更精细的分析。

### 4.4 阈值确定

支持多种阈值方法（与 VAE 相同）：

1. **百分位数法**：默认 percentile=95.0
2. **标准差法**：k=2.5
3. **IQR 法**

### 4.5 分数解读指南

| 节点分数 | 边分数 | 可能情况 | 建议操作 |
|---------|-------|---------|---------|
| 高 | 高 | 节点和连接都异常 | 优先处理 |
| 高 | 低 | 节点异常但连接正常 | 检查节点属性 |
| 低 | 高 | 节点正常但连接异常 | 检查网络拓扑 |
| 低 | 低 | 正常样本 | 无需处理 |

---

## 5. 图结构特征分析说明

### 5.1 图拓扑指标

GCAE 自动计算以下图指标：

#### 5.1.1 节点度数 (Node Degree)

**定义**：节点的邻居数量

**计算**：
```python
node_degree = adj.sum(axis=1)
```

**异常模式**：
- **极高度数**：可能是集线器异常或连接错误
- **极低度数**：可能是孤立节点异常

#### 5.1.2 图密度 (Graph Density)

**定义**：实际边数 / 可能边数

**计算**：
```python
density = adj.sum() / (n_nodes * n_nodes)
```

**异常模式**：
- 过密：可能存在过度连接
- 过疏：可能存在网络断裂

#### 5.1.3 局部聚类系数

（当前简化实现未包含，可在未来扩展）

### 5.2 空间邻域分析

#### 5.2.1 k 近邻图

GCAE 使用 k-NN 构建邻接矩阵：

```python
adj = knn_graph(coords, k=8)
```

**特点**：
- 只连接最近的 k 个邻居
- 自动适应空间分布
- 保持图的稀疏性

#### 5.2.2 局部统计特征

计算 k 近邻内的统计量：

```python
local = multiscale_value_features(coords, values, scales=(5,))
# 返回局部均值和标准差
```

### 5.3 图神经网络响应

#### 5.3.1 GCN 响应

```python
gcn = adj_norm @ features
```

**意义**：聚合邻居特征的加权平均

#### 5.3.2 GAT 响应

```python
# 注意力权重基于特征相似度
logits = features @ features.T
weights = softmax(logits + mask)
gat = weights @ features
```

**意义**：动态分配邻居权重

#### 5.3.3 EdgeConv 响应

```python
# 边特征 = 邻居特征 - 中心特征
edge_feat = features[neighbors] - features[center]
edgeconv = center + edge_feat.mean()
```

**意义**：捕捉局部相对变化

### 5.4 图结构异常类型

#### 5.4.1 孤立异常

**特征**：
- 节点度高，边分数高
- 节点与周围邻居不相似

**检测**：
- 高节点分数
- 高边分数
- 子图分数可能不高（邻居正常）

#### 5.4.2 集群异常

**特征**：
- 一组节点都异常
- 它们之间的连接正常，但与外部异常

**检测**：
- 高节点分数
- 高子图分数
- 集群内边分数可能低

#### 5.4.3 桥梁异常

**特征**：
- 连接两个不同区域的节点异常
- 影响网络连通性

**检测**：
- 节点分数中等
- 相关边的分数高

### 5.5 可视化工具

#### 5.5.1 图结构可视化

```python
import networkx as nx
import matplotlib.pyplot as plt

# 转换为 NetworkX 图
G = nx.from_numpy_array(detector.adj_template)

# 可视化
pos = {i: coords[i] for i in range(len(coords))}
nx.draw(G, pos, node_color=values, with_labels=True,
        cmap='viridis', node_size=100)
plt.colorbar(label='值')
plt.title('图结构可视化')
plt.show()
```

#### 5.5.2 节点分数可视化

```python
# 节点大小表示异常分数
result = detector.predict(coords, values)
node_sizes = np.array(result['node_scores']) * 300

nx.draw(G, pos, node_color=values, node_size=node_sizes,
        cmap='viridis')
plt.title('节点异常分数可视化')
plt.show()
```

#### 5.5.3 边分数可视化

```python
# 边的粗细表示异常程度
result = detector.predict(coords, values)
edge_scores = np.array(result['edge_scores'])

# 绘制边
for i, j in G.edges():
    weight = edge_scores[i, j]
    nx.draw_networkx_edges(G, pos, edgelist=[(i, j)],
                           width=weight * 5, alpha=0.5)

plt.title('边异常分数可视化')
plt.show()
```

---

## 6. 使用示例

### 6.1 基础使用

```python
import numpy as np
from deep_learning.models.anomaly_detection import GCAEAnomalyDetector

# 准备数据
coords = np.random.rand(100, 2)
values = np.random.rand(100)

# 训练模型
detector = GCAEAnomalyDetector()
training_result = detector.fit(coords, values)

print(f"训练完成:")
print(f"  总损失: {training_result['total_loss']:.4f}")
print(f"  特征重建损失: {training_result['feature_recon_loss']:.4f}")
print(f"  结构损失: {training_result['structure_loss']:.4f}")
print(f"  图节点数: {training_result['graph_nodes']}")
print(f"  图密度: {training_result['graph_density']:.4f}")

# 预测异常
result = detector.predict(coords, values, percentile=95.0)

print(f"\n检测结果:")
print(f"  异常数: {result['anomaly_count']}")
print(f"  阈值: {result['threshold']:.4f}")
print(f"  异常索引: {result['anomaly_indices']}")
```

### 6.2 获取详细分数

```python
# 获取所有分数组件
score_bundle = detector.anomaly_scores(coords, values)

print("节点分数:", score_bundle["node"][:5])
print("边分数矩阵形状:", score_bundle["edge"].shape)
print("子图分数:", score_bundle["subgraph"][:5])
print("池化嵌入:", score_bundle["pooling"][:5])
```

### 6.3 数据预处理

```python
# 预处理数据以获取详细特征
preprocessed = detector.preprocess_graph_data(
    coords, values,
    batch_size=32,
    use_training_stats=True
)

print("特征名称:", preprocessed["feature_names"])
print("特征形状:", preprocessed["processed_features"].shape)
print("批次切片:", preprocessed["batch_slices"])
print("归一化器:", preprocessed["scaler"])
```

### 6.4 调整参数

```python
from deep_learning.models.anomaly_detection import GCAEConfig

# 自定义配置
config = GCAEConfig(
    latent_dim=6,              # 潜在维度
    knn_k=10,                  # k-NN 的 k 值
    structure_weight=0.5,      # 结构损失权重
    feature_weight=0.5,        # 特征损失权重
    random_state=123           # 随机种子
)

detector = GCAEAnomalyDetector(config=config)
detector.fit(coords, values)
```

### 6.5 标准预测

```python
# 使用标准接口预测
result = detector.predict_standard(
    coords, values,
    threshold_method="percentile",
    percentile=95.0
)

print(f"分数: {result['scores'][:5]}")
print(f"标签: {result['labels'][:5]}")
print(f"异常数: {result['anomaly_count']}")
```

### 6.6 图结构分析

```python
# 分析图的拓扑特性
import networkx as nx

# 获取邻接矩阵
preprocessed = detector.preprocess_graph_data(coords, values)
adj = preprocessed["adjacency_matrix"]

# 转换为图对象
G = nx.from_numpy_array(adj)

# 计算图指标
print(f"节点数: {G.number_of_nodes()}")
print(f"边数: {G.number_of_edges()}")
print(f"平均度数: {np.mean([d for n, d in G.degree()]):.2f}")
print(f"聚类系数: {nx.average_clustering(G):.4f}")
print(f"连通分量数: {nx.number_connected_components(G)}")
```

---

## 7. 参数说明

### 7.1 GCAEConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `latent_dim` | int | 4 | 潜在空间维度，建议 2-8 |
| `knn_k` | int | 8 | k-NN 的 k 值，建议 5-15 |
| `structure_weight` | float | 0.4 | 结构损失权重，范围 0-1 |
| `feature_weight` | float | 0.6 | 特征损失权重，范围 0-1 |
| `random_state` | int | 42 | 随机种子 |

### 7.2 预处理参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `batch_size` | int | None | 批处理大小，None 表示全部 |
| `use_training_stats` | bool | True | 是否使用训练时的归一化参数 |

### 7.3 预测参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `coords` | np.ndarray | 必需 | 坐标数组，形状 (N, 2) |
| `values` | np.ndarray | 必需 | 值数组，形状 (N,) |
| `threshold_method` | str | "percentile" | 阈值方法 |
| `percentile` | float | 95.0 | 百分位数 |
| `k` | float | 2.5 | 标准差倍数 |

### 7.4 参数调优建议

#### 7.4.1 潜在维度 (latent_dim)

- **小维度 (2-3)**：
  - 快速，可解释性强
  - 可能欠拟合

- **中等维度 (4-6)**：
  - 推荐
  - 平衡性能和复杂度

- **大维度 (7-8+)**：
  - 表达能力强
  - 可能过拟合

#### 7.4.2 k-NN 的 k 值 (knn_k)

- **小 k (5-7)**：
  - 关注最近邻
  - 捕捉局部异常

- **中等 k (8-12)**：
  - 推荐
  - 平衡局部和全局

- **大 k (13-15+)**：
  - 关注大范围连接
  - 捕捉全局异常

#### 7.4.3 损失权重

**结构权重高** (structure_weight > 0.5)：
- 更关注图拓扑异常
- 适合检测连接异常

**特征权重高** (feature_weight > 0.5)：
- 更关注节点属性异常
- 适合检测值异常

**平衡配置** (structure_weight=0.4, feature_weight=0.6)：
- 推荐
- 同时考虑两方面

---

## 8. 常见问题解答

### 8.1 图构建相关

**Q: k-NN 的 k 值如何选择？**

A: 考虑因素：
1. 数据密度：稀疏数据用小 k，密集数据用大 k
2. 空间范围：小范围用小 k，大范围用大 k
3. 计算效率：k 越大越慢
4. 推荐经验值：
   - 小数据 (< 100): k=5-8
   - 中等数据 (100-500): k=8-12
   - 大数据 (> 500): k=10-15

**Q: 图太密集或太稀疏怎么办？**

A: 调整方法：
1. 调整 `knn_k` 值
2. 使用距离阈值剪枝
3. 考虑其他图构建方法（如 radius graph）

**Q: 如何处理非连通图？**

A: 当前实现支持非连通图：
- 每个连通分量独立处理
- 子图分数会反映连通性
- 非连通节点可能被标记为异常

### 8.2 训练相关

**Q: 训练时图结构损失很高怎么办？**

A: 可能原因和解决：
1. k 值不合适：调整 `knn_k`
2. 数据分布复杂：增加 `latent_dim`
3. 结构权重过高：降低 `structure_weight`
4. 数据确实异常：这是正常现象

**Q: 训练很慢怎么办？**

A: 优化建议：
1. 降低 `latent_dim`
2. 降低 `knn_k`
3. 使用数据采样
4. 减少数据量

**Q: 模型不收敛怎么办？**

A: 检查：
1. 数据质量（是否有 NaN/Inf）
2. 数据量是否足够（至少 30 个点）
3. 调整损失权重
4. 检查图构建是否正确

### 8.3 预测相关

**Q: 节点分数和边分数不一致怎么办？**

A: 这是正常现象：
- 节点分数高但边分数低：节点属性异常，连接正常
- 节点分数低但边分数高：节点正常，连接异常
- 综合判断：看子图分数

**Q: 如何确定真正的异常？**

A: 多层次分析：
1. 查看节点分数
2. 查看边分数
3. 查看子图分数
4. 结合领域知识
5. 考虑模型集成

**Q: 边分数矩阵如何解读？**

A: 矩阵解读：
- `edge_scores[i, j]`：节点 i 和 j 之间的边异常程度
- 对称矩阵
- 对角线为 0（自环）
- 高值表示该边连接异常

### 8.4 性能相关

**Q: GCAE 比 VAE 慢很多？**

A: 原因和优化：
1. 图构建开销：不可避免
2. 降低 `knn_k`
3. 降低 `latent_dim`
4. 使用近似算法

**Q: 检测准确率不如 VAE？**

A: 可能原因：
1. 数据没有明显的图结构
2. k 值选择不当
3. 损失权重不合适
4. 尝试调整参数或使用其他模型

**Q: 误报率高？**

A: 降低误报：
1. 提高 `percentile`
2. 调整损失权重
3. 使用模型集成
4. 添加后处理

### 8.5 解释相关

**Q: 如何解释节点异常？**

A: 分析步骤：
1. 查看节点分数
2. 查看该节点的特征值
3. 查看邻居节点的分数
4. 查看连接边的分数
5. 使用 LIME/SHAP 分析特征重要性

**Q: 如何解释边异常？**

A: 分析步骤：
1. 查看边分数
2. 查看两端节点的分数
3. 查看两个节点的特征差异
4. 查看空间距离
5. 判断是否应该连接

**Q: 如何解释子图异常？**

A: 分析步骤：
1. 查看子图分数高的节点
2. 查看这些节点的连接关系
3. 查看整个子图的属性
4. 判断是否是集群异常

### 8.6 可视化相关

**Q: 如何可视化图结构？**

A: 使用 NetworkX：
```python
import networkx as nx
import matplotlib.pyplot as plt

G = nx.from_numpy_array(adj)
pos = {i: coords[i] for i in range(len(coords))}

# 节点颜色表示值，大小表示异常分数
result = detector.predict(coords, values)
node_sizes = np.array(result['node_scores']) * 300

nx.draw(G, pos, node_color=values, node_size=node_sizes,
        cmap='viridis', with_labels=False)
plt.colorbar()
plt.show()
```

**Q: 如何可视化边异常？**

A: 使用边的粗细和颜色：
```python
# 边的粗细表示异常程度
edge_scores = result['edge_scores']
for i, j in G.edges():
    weight = edge_scores[i, j]
    nx.draw_networkx_edges(G, pos, edgelist=[(i, j)],
                           width=weight * 5,
                           edge_color='red' if weight > 0.5 else 'blue')
```

### 8.7 集成相关

**Q: 如何与其他模型集成？**

A: 参考以下代码：
```python
from deep_learning.models.anomaly_detection import (
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
    AnomalyEnsembleIntegrator
)

# 训练多个模型
gcae = GCAEAnomalyDetector()
vae = VAEAnomalyDetector()
gcae.fit(coords, values)
vae.fit(coords, values)

# 创建集成
detectors = {"gcae": gcae, "vae": vae}
ensemble = AnomalyEnsembleIntegrator(detectors)

# 集成预测
result = ensemble.detect(coords, values)
```

### 8.8 其他

**Q: GCAE 适合什么类型的数据？**

A: 适用数据：
- 具有明确空间关系的数据
- 传感器网络数据
- 地理空间数据
- 社交网络数据
- 网络流量数据

**Q: GCAE 不适合什么数据？**

A: 不适用数据：
- 完全随机分布的数据
- 没有空间关系的数据
- 维度极高的数据
- 时间序列数据（除非有空间维度）

**Q: 模型支持动态图吗？**

A: 当前限制：
- 静态图结构
- 每次预测重新构建图
- 未来版本可能支持增量更新

---

## 9. 最佳实践

### 9.1 数据准备

```python
import numpy as np
from deep_learning.models.anomaly_detection import GCAEAnomalyDetector

# 1. 数据质量检查
coords = ...  # 你的坐标数据
values = ...  # 你的值数据

assert coords.shape[1] == 2, "坐标必须是二维"
assert len(coords) == len(values), "坐标和值数量必须一致"
assert len(coords) >= 30, "至少需要30个样本"
assert np.isfinite(coords).all(), "坐标不能包含NaN或Inf"
assert np.isfinite(values).all(), "值不能包含NaN或Inf"

# 2. 空间分布分析
print(f"坐标范围: X[{coords[:, 0].min():.2f}, {coords[:, 0].max():.2f}]")
print(f"          Y[{coords[:, 1].min():.2f}, {coords[:, 1].max():.2f}]")
print(f"空间范围: {coords.max(axis=0) - coords.min(axis=0)}")

# 3. 密度分析
from scipy.spatial.distance import pdist, squareform
distances = pdist(coords)
print(f"平均距离: {np.mean(distances):.4f}")
print(f"中位数距离: {np.median(distances):.4f}")

# 4. 建议的 k 值
suggested_k = max(5, min(12, int(len(coords) / 10)))
print(f"建议的 k 值: {suggested_k}")
```

### 9.2 参数调优

```python
from deep_learning.models.anomaly_detection import GCAEConfig
from sklearn.model_selection import ParameterGrid

# 参数网格
param_grid = {
    'latent_dim': [4, 6, 8],
    'knn_k': [6, 8, 10],
    'structure_weight': [0.3, 0.4, 0.5],
    'feature_weight': [0.5, 0.6, 0.7]
}

# 网格搜索
best_score = float('inf')
best_config = None

for params in ParameterGrid(param_grid):
    config = GCAEConfig(**params)
    detector = GCAEAnomalyDetector(config=config)
    result = detector.fit(coords, values)
    
    # 使用验证集评估（如果有）
    score = result['total_loss']
    
    if score < best_score:
        best_score = score
        best_config = params

print(f"最佳配置: {best_config}")
print(f"最佳损失: {best_score:.4f}")
```

### 9.3 异常分析流程

```python
import matplotlib.pyplot as plt
import networkx as nx

# 1. 训练模型
detector = GCAEAnomalyDetector()
detector.fit(coords, values)

# 2. 预测异常
result = detector.predict(coords, values)

# 3. 获取图结构
preprocessed = detector.preprocess_graph_data(coords, values)
adj = preprocessed["adjacency_matrix"]
G = nx.from_numpy_array(adj)
pos = {i: coords[i] for i in range(len(coords))}

# 4. 可视化
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# (a) 原始数据
axes[0].scatter(coords[:, 0], coords[:, 1], c=values, cmap='viridis', s=50)
axes[0].set_title('原始数据')
plt.colorbar(axes[0].collections[0], ax=axes[0], label='值')

# (b) 节点异常分数
node_sizes = np.array(result['node_scores']) * 300
nx.draw(G, pos, node_color=values, node_size=node_sizes,
        cmap='viridis', ax=axes[1])
axes[1].set_title('节点异常分数')

# (c) 异常检测结果
colors = ['red' if label == 1 else 'blue' for label in result['anomaly_labels']]
nx.draw(G, pos, node_color=colors, node_size=100, ax=axes[2])
axes[2].set_title('异常检测结果')

plt.tight_layout()
plt.show()
```

### 9.4 性能评估

```python
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, precision_recall_curve
)

# 假设有真实标签
true_labels = ...  # 0: 正常, 1: 异常

# 预测
result = detector.predict(coords, values)
predicted_labels = result['anomaly_labels']
scores = result['node_scores']

# 计算指标
metrics = {
    'accuracy': accuracy_score(true_labels, predicted_labels),
    'precision': precision_score(true_labels, predicted_labels),
    'recall': recall_score(true_labels, predicted_labels),
    'f1': f1_score(true_labels, predicted_labels),
    'auc': roc_auc_score(true_labels, scores)
}

for name, value in metrics.items():
    print(f"{name}: {value:.4f}")

# 绘制 PR 曲线
precisions, recalls, thresholds = precision_recall_curve(true_labels, scores)
plt.plot(recalls, precisions)
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.title('Precision-Recall Curve')
plt.show()
```

### 9.5 模型对比

```python
from deep_learning.models.anomaly_detection import (
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
    GANAnomalyDetector,
    ContrastiveAnomalyDetector
)

# 训练所有模型
models = {
    'GCAE': GCAEAnomalyDetector(),
    'VAE': VAEAnomalyDetector(),
    'GAN': GANAnomalyDetector(),
    'Contrastive': ContrastiveAnomalyDetector()
}

results = {}
for name, model in models.items():
    if name == 'Contrastive':
        model.fit(coords, values, epochs=20)
    else:
        model.fit(coords, values)
    
    result = model.predict(coords, values)
    results[name] = result

# 对比结果
for name, result in results.items():
    print(f"{name:12s}: {result['anomaly_count']} 个异常, "
          f"阈值={result['threshold']:.4f}")

# 可视化对比
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.ravel()

for ax, (name, result) in zip(axes, results.items()):
    scores = result['scores']
    ax.hist(scores, bins=30, alpha=0.7)
    ax.axvline(result['threshold'], color='red', linestyle='--')
    ax.set_title(f'{name} 分数分布')
    ax.set_xlabel('异常分数')
    ax.set_ylabel('频数')

plt.tight_layout()
plt.show()
```

---

## 10. 参考资源

### 10.1 相关文档

- [VAE 异常检测模型](./VAE异常检测模型.md)
- [GAN 异常检测模型](./GAN异常检测模型.md)
- [对比学习异常检测模型](./对比学习异常检测模型.md)
- [LIME 集成指南](./LIME集成指南.md)
- [SHAP 集成指南](./SHAP集成指南.md)

### 10.2 学术论文

1. Kipf & Welling (2016). "Semi-Supervised Classification with Graph Convolutional Networks"
2. Veličković et al. (2017). "Graph Attention Networks"
3. Wang et al. (2019). "Dynamic Graph CNN for Learning on Point Clouds"

### 10.3 代码示例

- 模型实现：`deep_learning/models/anomaly_detection/gcae_anomaly.py`
- 训练示例：`deep_learning/examples/anomaly_training_demo.py`
- 推理示例：`deep_learning/examples/anomaly_inference_demo.py`

### 10.4 相关库

- NetworkX: 图操作和可视化
- PyTorch Geometric: 图神经网络（如需扩展）
- igraph: 高效图算法

---

## 附录：完整 API 参考

### GCAEAnomalyDetector 类

#### 初始化
```python
GCAEAnomalyDetector(config: GCAEConfig | None = None)
```

#### 方法

**fit**
```python
fit(coords: np.ndarray, values: np.ndarray) -> dict[str, float]
```
训练模型。

**predict**
```python
predict(
    coords: np.ndarray,
    values: np.ndarray,
    threshold_method: ThresholdMethod = "percentile",
    percentile: float = 95.0,
    k: float = 2.5
) -> dict[str, object]
```
预测异常。

**predict_standard**
```python
predict_standard(
    coords: np.ndarray,
    values: np.ndarray,
    *,
    threshold_method: ThresholdMethod = "percentile",
    percentile: float = 95.0,
    k: float = 2.5
) -> dict[str, object]
```
标准接口预测。

**anomaly_scores**
```python
anomaly_scores(coords: np.ndarray, values: np.ndarray) -> dict[str, object]
```
计算所有异常分数。

**preprocess_graph_data**
```python
preprocess_graph_data(
    coords: np.ndarray,
    values: np.ndarray,
    *,
    batch_size: int | None = None,
    use_training_stats: bool = True
) -> dict[str, object]
```
预处理图数据。

**is_trained**
```python
is_trained() -> bool
```
检查模型是否已训练。

### GCAEConfig 类

#### 参数
- `latent_dim`: int = 4
- `knn_k`: int = 8
- `structure_weight`: float = 0.4
- `feature_weight`: float = 0.6
- `random_state`: int = 42

---

**文档版本**: 1.0  
**最后更新**: 2026-04-10  
**维护者**: UDAKE 开发团队