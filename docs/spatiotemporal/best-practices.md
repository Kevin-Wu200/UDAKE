# 空间插值模型最佳实践指南

## 概述

本指南提供了使用UDAKE空间插值模型的最佳实践，涵盖模型选择、数据准备、性能优化和常见问题解决。

## 模型选择指南

### ResidualKrigingModel

**适用场景**：
- 中小规模数据集（< 10000样本点）
- 需要快速推理的场景
- 数据分布相对均匀的区域
- 计算资源有限的部署环境

**优势**：
- 推理速度快，内存占用低
- 对噪声数据具有鲁棒性
- 支持多种架构选择（mlp/cnn/hybrid）

**不适用场景**：
- 极度非平稳数据
- 大规模稀疏数据
- 需要精确不确定性估计的场景

### AttentionKrigingModel

**适用场景**：
- 复杂非平稳空间数据
- 需要捕捉长距离依赖关系
- 中等规模数据集（1000-50000样本点）
- 需要可解释注意力权重的应用

**优势**：
- 强大的非线性建模能力
- 注意力权重提供可解释性
- 动态权重适应空间异质性

**不适用场景**：
- 极大规模数据（> 50000样本点）
- 实时性要求极高的应用
- 计算资源受限的环境

### GNNKrigingModel

**适用场景**：
- 网络化空间数据（如交通、传感器网络）
- 需要建模空间拓扑结构
- 大规模密集数据集
- 多模态空间数据融合

**优势**：
- 有效建模空间邻域关系
- 支持多种图构建策略
- 可处理复杂空间拓扑

**不适用场景**：
- 稀疏数据集
- 简单均匀分布数据
- 计算资源严格受限

## 数据准备最佳实践

### 数据质量检查

**最小数据要求**：
- 样本点数量：至少10个点（推荐> 50个）
- 空间范围：覆盖目标预测区域
- 时间间隔：均匀分布（对于时空数据）

**数据清洗步骤**：
```python
# 1. 移除重复坐标
coords, values = remove_duplicates(sample_coords, sample_values)

# 2. 处理异常值
values = clip_outliers(values, lower=np.percentile(values, 1), upper=np.percentile(values, 99))

# 3. 验证空间分布
check_spatial_coverage(sample_coords, query_coords)

# 4. 确保数据有限
assert np.all(np.isfinite(coords)) and np.all(np.isfinite(values))
```

### 数据格式规范

**坐标格式**：
```python
# 二维坐标：[[x1, y1], [x2, y2], ...]
sample_coords = np.array([[120.1, 30.1], [120.2, 30.2], [120.3, 30.3]])

# 值向量：[value1, value2, ...]
sample_values = np.array([80.0, 82.5, 84.2])
```

**注意事项**：
- 坐标应使用相同单位（度、米等）
- 值应为数值类型，避免缺失值
- 坐标和值的维度必须匹配

### 空间分布优化

**采样密度建议**：
- 均匀分布：推荐
- 聚类分布：在重要区域增加密度
- 边界增强：在区域边界增加采样点

**覆盖范围**：
- 样本点应覆盖目标预测区域
- 在预测边界外至少保留20%缓冲区
- 避免采样点集中在单一子区域

## 性能优化建议

### 批处理策略

**批量大小选择**：
- 小数据集（< 1000）：批量处理全部数据
- 中等数据（1000-10000）：批量大小256-1024
- 大数据集（> 10000）：批量大小512-2048

**批处理示例**：
```python
model = ResidualKrigingModel(architecture="hybrid")
result = model.predict_standard(
    sample_coords=train_coords,
    sample_values=train_values,
    query_coords=test_coords,
    batch_size=512  # 优化批量大小
)
```

### 内存管理

**大规模数据处理**：
```python
# 分块处理大型查询集
chunk_size = 10000
predictions = []
for i in range(0, len(query_coords), chunk_size):
    chunk = query_coords[i:i+chunk_size]
    result = model.predict_standard(
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=chunk
    )
    predictions.extend(result["prediction"])
```

### 计算优化

**缓存策略**：
- 缓存空间索引结构
- 缓存预计算特征
- 使用运行时统计信息加速推理

**参数调优**：
```python
# ResidualKrigingModel参数优化
model = ResidualKrigingModel(
    architecture="hybrid",  # 最准确但较慢
    baseline="universal",   # 更适合非平稳数据
    seed=42
)

# AttentionKrigingModel参数优化
model = AttentionKrigingModel(
    dim=24,          # 较大维度提升精度但增加计算量
    heads=4,         # 注意力头数，4-8为推荐范围
    seed=42
)

# GNNKrigingModel参数优化
model = GNNKrigingModel(
    hidden_dim=16,       # 隐藏层维度
    graph_strategy="knn",  # knn/radius/voronoi/delaunay
    seed=42
)
```

## 模型训练最佳实践

### 训练数据准备

**交叉验证策略**：
```python
# 空间交叉验证
from sklearn.model_selection import KFold
kf = KFold(n_splits=5, shuffle=True, random_state=42)

for train_idx, val_idx in kf.split(sample_coords):
    train_coords = sample_coords[train_idx]
    train_values = sample_values[train_idx]
    val_coords = sample_coords[val_idx]
    val_values = sample_values[val_idx]
    
    # 训练和验证
    model = ResidualKrigingModel()
    # ... 训练过程 ...
```

**损失函数监控**：
- 监控训练损失和验证损失
- 防止过拟合：验证损失持续上升时停止
- 保存最佳模型状态

### 超参数调优

**关键超参数**：
1. **学习率**：1e-3到1e-2之间
2. **批量大小**：根据数据规模调整
3. **模型维度**：权衡精度和速度
4. **正则化权重**：防止过拟合

**调优策略**：
```python
learning_rates = [1e-3, 5e-3, 1e-2]
batch_sizes = [128, 256, 512]
dimensions = [16, 24, 32]

best_score = float('inf')
best_params = None

for lr in learning_rates:
    for bs in batch_sizes:
        for dim in dimensions:
            model = AttentionKrigingModel(dim=dim)
            # 训练和评估
            score = evaluate_model(model, validation_data)
            if score < best_score:
                best_score = score
                best_params = {'lr': lr, 'batch_size': bs, 'dim': dim}
```

## 不确定性量化最佳实践

### 置信区间使用

**置信水平选择**：
- 95%置信区间（z=1.96）：标准应用
- 90%置信区间（z=1.645）：快速评估
- 99%置信区间（z=2.576）：高风险应用

**不确定性解读**：
```python
result = model.predict_standard(
    sample_coords=train_coords,
    sample_values=train_values,
    query_coords=test_coords,
    confidence_z=1.96  # 95%置信区间
)

# 检查预测可靠性
for i, (pred, lower, upper) in enumerate(zip(
    result["prediction"],
    result["confidence_interval"]["lower"],
    result["confidence_interval"]["upper"]
)):
    uncertainty = upper - lower
    if uncertainty > threshold:
        print(f"点{i}的不确定性过高: {uncertainty:.2f}")
```

### 不确定性可视化

**不确定性热图**：
- 使用颜色深浅表示不确定性
- 高不确定性区域需要更多采样点
- 辅助决策和数据收集规划

## 常见问题和解决方案

### 问题1：预测结果异常

**症状**：
- 预测值超出合理范围
- 出现NaN或Inf值
- 空间不连续

**解决方案**：
```python
# 1. 检查输入数据质量
assert np.all(np.isfinite(sample_coords))
assert np.all(np.isfinite(sample_values))
assert np.all(np.isfinite(query_coords))

# 2. 验证样本点数量
if len(sample_coords) < 10:
    print("警告：样本点数量过少，建议增加采样点")

# 3. 检查空间覆盖范围
from scipy.spatial import ConvexHull
hull = ConvexHull(sample_coords)
# 预测点应在凸包内或附近
```

### 问题2：训练收敛困难

**症状**：
- 训练损失不下降
- 损失震荡严重
- 过拟合

**解决方案**：
```python
# 1. 调整学习率
lr_schedule = [1e-2, 5e-3, 1e-3, 5e-4]  # 学习率衰减

# 2. 增加正则化
reg_weight = 1e-3  # L2正则化权重

# 3. 早停策略
patience = 10  # 验证损失不下降的容忍轮数
```

### 问题3：内存不足

**症状**：
- OOM错误
- 系统变慢
- 推理超时

**解决方案**：
```python
# 1. 减小批量大小
batch_size = 128  # 从256或512减小

# 2. 分块处理
chunk_size = 5000
for i in range(0, len(query_coords), chunk_size):
    # 处理每个块

# 3. 使用简化模型
# 从attention_kriging或gnn_kriging切换到residual_kriging
```

### 问题4：精度不达标

**症状**：
- RMSE过高
- MAE超出预期
- 空间细节丢失

**解决方案**：
```python
# 1. 增加模型复杂度
model = AttentionKrigingModel(dim=32, heads=8)  # 增加维度和头数

# 2. 改用更强大的模型
# 从residual_kriging升级到attention_kriging或gnn_kriging

# 3. 增加训练数据
# 收集更多样本点，特别是在高变化区域

# 4. 特征工程
# 添加额外的空间特征或协变量
```

## 使用场景推荐

### 环境监测

**推荐模型**：ResidualKrigingModel或GNNKrigingModel

**特点**：
- 传感器网络数据
- 需要实时更新
- 关注异常检测

**配置建议**：
```python
model = ResidualKrigingModel(
    architecture="hybrid",
    baseline="universal"
)
```

### 气象预报

**推荐模型**：AttentionKrigingModel

**特点**：
- 大气数据具有长距离依赖
- 需要高精度预测
- 不确定性量化重要

**配置建议**：
```python
model = AttentionKrigingModel(
    dim=32,
    heads=8,
    seed=42
)
```

### 地质勘探

**推荐模型**：GNNKrigingModel

**特点**：
- 钻孔数据呈现网络结构
- 需要建模地质构造
- 多变量空间插值

**配置建议**：
```python
model = GNNKrigingModel(
    hidden_dim=24,
    graph_strategy="radius",  # 基于距离构建图
    seed=42
)
```

### 城市规划

**推荐模型**：ResidualKrigingModel

**特点**：
- 人口密度、房价等数据
- 快速决策支持
- 计算资源有限

**配置建议**：
```python
model = ResidualKrigingModel(
    architecture="mlp",  # 最快推理速度
    baseline="ordinary"
)
```

## 部署建议

### 生产环境部署

**模型服务化**：
```python
from fastapi import FastAPI
import uvicorn

app = FastAPI()
model = ResidualKrigingModel()
# 预加载模型

@app.post("/predict")
async def predict(request):
    result = model.predict_standard(
        sample_coords=request.sample_coords,
        sample_values=request.sample_values,
        query_coords=request.query_coords
    )
    return result
```

**监控和日志**：
- 记录预测延迟
- 监控资源使用
- 跟踪预测精度

### 移动端部署

**轻量化模型**：
```python
# 使用ResidualKrigingModel的mlp架构
model = ResidualKrigingModel(
    architecture="mlp",
    baseline="ordinary"
)

# 减小模型维度
# 通过特征选择减少输入维度
```

**性能优化**：
- 量化模型权重
- 优化推理流程
- 使用移动端推理框架

## 总结

选择合适的空间插值模型需要综合考虑：
1. **数据特性**：规模、分布、平稳性
2. **应用需求**：精度、速度、可解释性
3. **资源约束**：计算能力、内存、存储
4. **部署环境**：本地、云端、移动端

遵循本指南的最佳实践，可以确保空间插值模型的稳定运行和最优性能。