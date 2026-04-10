# VAE 异常检测模型文档

## 1. 模型概述

### 1.1 简介

VAE (Variational Autoencoder, 变分自编码器) 异常检测器是一种基于深度学习的无监督异常检测方法，通过学习数据的潜在分布来识别异常样本。该模型适用于空间插值数据中的异常检测任务。

### 1.2 工作原理

VAE 异常检测器采用编码器-解码器结构：

1. **编码器**：将输入的坐标和值映射到潜在空间
   - 使用空间特征编码器提取坐标和值的特征
   - 通过 SVD 降维获得潜在表示
   - 计算潜在空间的均值和方差

2. **重参数化**：从潜在分布中采样
   - 使用重参数化技巧实现端到端训练
   - 噪声调度从 1.0 递减到 0.05

3. **解码器**：从潜在表示重建原始特征
   - 通过转置投影矩阵重建特征
   - 计算重建误差作为异常信号

4. **异常检测**：
   - 重建误差：衡量输入与重建的差异
   - 潜在距离：衡量样本在潜在空间偏离中心的程度
   - 综合分数：70% 重建误差 + 30% 潜在距离

### 1.3 特征工程

模型自动构建以下特征：

- **坐标特征**：原始坐标 (x, y)
- **半径特征**：距离原点的欧氏距离
- **角度特征**：坐标的极角
- **值特征**：原始值、中心化值、平方值
- **多尺度特征**：不同邻域尺度下的局部统计量
- **残差连接**：保留原始坐标和值，增强重建稳定性

### 1.4 损失函数

```
总损失 = 重建损失 + β × KL散度损失

重建损失 = MSE(输入, 重建)
KL散度 = -0.5 × Σ(1 + log_var - μ² - exp(log_var))
```

其中 β = 0.1，用于平衡重建质量和潜在空间的正则化。

### 1.5 适用场景

- 适合检测偏离正常空间分布的异常点
- 适合检测重建困难的异常模式
- 适合需要可视化潜在空间的应用
- 不适合检测与正常样本相似但语义不同的异常

---

## 2. LIME 解释指南

### 2.1 概述

LIME (Local Interpretable Model-agnostic Explanations) 是一种局部解释方法，可以为每个异常样本生成特征重要性分析。

### 2.2 应用到 VAE 模型

对于 VAE 异常检测器，LIME 解释关注：

1. **预测函数**：异常分数（综合分数）
2. **解释目标**：哪些特征贡献了高异常分数
3. **局部范围**：异常样本周围的邻域

### 2.3 实现步骤

```python
from deep_learning.models.anomaly_detection import VAEAnomalyDetector
import numpy as np

# 1. 训练 VAE 模型
detector = VAEAnomalyDetector()
detector.fit(coords, values)

# 2. 预测异常
result = detector.predict(coords, values)

# 3. 定义预测函数供 LIME 使用
def predict_fn(samples):
    """LIME 使用的预测函数"""
    sample_coords = samples[:, :2]
    sample_values = samples[:, 2]
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["combined"]

# 4. 应用 LIME 解释（伪代码）
# lime_explainer = lime.lime_tabular.LimeTabularExplainer(
#     training_data=features,
#     feature_names=feature_names,
#     mode='regression'
# )
# explanation = lime_explainer.explain_instance(
#     instance, predict_fn, num_features=5
# )
```

### 2.4 解释结果解读

LIME 返回的特征重要性：

- **正值**：特征值增加时异常分数上升
- **负值**：特征值增加时异常分数下降
- **绝对值大小**：表示特征贡献的程度

典型重要特征：
- `coord_x`, `coord_y`：坐标偏离程度
- `radius`：距离中心点的远近
- `value`：数值偏离正常范围
- `local_mean_k5`：局部平均值差异
- `local_std_k5`：局部变异性差异

---

## 3. SHAP 解释指南

### 3.1 概述

SHAP (SHapley Additive exPlanations) 是一种基于博弈论的解释方法，提供一致且局部的特征归因。

### 3.2 应用到 VAE 模型

对于 VAE 异常检测器，SHAP 分析：

1. **基础模型**：异常分数预测函数
2. **背景数据**：正常样本的特征分布
3. **输出解释**：每个特征对异常分数的贡献

### 3.3 实现步骤

```python
import shap
from deep_learning.models.anomaly_detection import VAEAnomalyDetector

# 1. 训练模型
detector = VAEAnomalyDetector()
detector.fit(coords, values)

# 2. 准备背景数据（正常样本）
background = features[labels == 0][:100]  # 100个正常样本

# 3. 定义预测函数
def model_predict(X):
    sample_coords = X[:, :2]
    sample_values = X[:, 2]
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["combined"].reshape(-1, 1)

# 4. 创建 SHAP 解释器
explainer = shap.KernelExplainer(model_predict, background)

# 5. 计算解释
shap_values = explainer.shap_values(instance_to_explain)

# 6. 可视化
# shap.waterfall_plot(shap_values[0])
# shap.force_plot(explainer.expected_value[0], shap_values[0])
```

### 3.4 解释结果解读

SHAP 提供的可视化：

- **瀑布图**：显示从基准值到预测值的逐步贡献
- **力图**：交互式展示特征推拉预测值
- **蜂群图**：全局特征重要性分布
- **依赖图**：特征值与 SHAP 值的关系

---

## 4. 异常分数解释说明

### 4.1 分数组成

VAE 模型提供三层异常分数：

```
综合分数 = 0.7 × 重建误差 + 0.3 × 潜在距离
```

### 4.2 分数详解

#### 4.2.1 重建误差 (Reconstruction Error)

**定义**：输入特征与重建特征的均方误差

**计算**：
```
重建误差 = MSE(标准化特征, 重建特征)
```

**意义**：
- 高值：样本难以从潜在空间重建，可能是异常
- 低值：样本可以被很好地重建，可能是正常样本

**典型范围**：0 ~ 1（归一化后）

#### 4.2.2 潜在距离 (Latent Distance)

**定义**：样本在潜在空间中与分布中心的欧氏距离

**计算**：
```
潜在距离 = ||z - μ_center||
```

**意义**：
- 高值：样本偏离正常分布的潜在表示
- 低值：样本位于潜在空间的正常区域

**典型范围**：0 ~ 1（归一化后）

#### 4.2.3 综合分数 (Combined Score)

**定义**：重建误差和潜在距离的加权组合

**计算**：
```
综合分数 = 0.7 × safe_minmax(重建误差) + 0.3 × safe_minmax(潜在距离)
```

**意义**：
- 结合重建质量和分布偏移
- 更全面的异常评估

**典型范围**：0 ~ 1

### 4.3 阈值确定

支持多种阈值方法：

1. **百分位数法**（默认）：
   - `percentile=95.0`：前 5% 高分样本为异常
   - 适合已知异常比例的情况

2. **标准差法**：
   - `k=2.5`：超过均值 2.5 倍标准差为异常
   - 适合正态分布的数据

3. **IQR 法**：
   - 超过 Q3 + 1.5×IQR 为异常
   - 适合偏态分布

### 4.4 分数解读指南

| 综合分数范围 | 异常可能性 | 建议操作 |
|------------|----------|---------|
| 0.0 ~ 0.3 | 极低 | 视为正常样本 |
| 0.3 ~ 0.6 | 低 | 可疑，需人工复核 |
| 0.6 ~ 0.8 | 中高 | 可能异常，需详细分析 |
| 0.8 ~ 1.0 | 极高 | 高度异常，需立即处理 |

---

## 5. 重建误差分析说明

### 5.1 误差来源

VAE 的重建误差来自多个方面：

1. **编码误差**：
   - 从输入到潜在空间的映射损失
   - 受限于潜在维度（latent_dim）

2. **解码误差**：
   - 从潜在空间重建的损失
   - 受限于解码器的表达能力

3. **噪声干扰**：
   - 训练时的噪声注入
   - 测试数据的噪声

### 5.2 误差分析工具

#### 5.2.1 误差分布分析

```python
import matplotlib.pyplot as plt
import numpy as np

# 获取重建误差
scores = detector.anomaly_scores(coords, values)
recon_errors = scores["reconstruction"]

# 绘制分布
plt.hist(recon_errors, bins=50, alpha=0.7)
plt.xlabel("重建误差")
plt.ylabel("频数")
plt.title("重建误差分布")
plt.show()

# 统计指标
print(f"均值: {np.mean(recon_errors):.4f}")
print(f"中位数: {np.median(recon_errors):.4f}")
print(f"标准差: {np.std(recon_errors):.4f}")
print(f"95分位数: {np.percentile(recon_errors, 95):.4f}")
```

#### 5.2.2 空间误差可视化

```python
# 按位置绘制重建误差
plt.scatter(coords[:, 0], coords[:, 1], c=recon_errors, cmap='hot', s=50)
plt.colorbar(label='重建误差')
plt.xlabel('X坐标')
plt.ylabel('Y坐标')
plt.title('重建误差空间分布')
plt.show()
```

#### 5.2.3 特征级误差分析

```python
# 计算每个特征的重建误差
normalized, mu, recon = detector._encode_for_inference(coords, values)
feature_errors = np.abs(normalized - recon)

# 绘制特征误差热图
import seaborn as sns
sns.heatmap(feature_errors.T, cmap='hot', cbar_kws={'label': '误差'})
plt.xlabel('样本索引')
plt.ylabel('特征索引')
plt.title('特征级重建误差')
plt.show()
```

### 5.3 误差诊断

#### 5.3.1 高重建误差原因

1. **特征维度过高**：
   - 潜在维度不足以捕捉所有信息
   - 解决：增加 `latent_dim`

2. **数据分布复杂**：
   - 单一潜在空间难以表示多模态数据
   - 解决：使用混合模型或增加训练数据

3. **训练不充分**：
   - epoch 数量不足
   - 解决：增加 `max_epochs`

4. **噪声过大**：
   - 数据噪声影响模型学习
   - 解决：调整噪声调度参数

#### 5.3.2 误差与异常的关系

- **正常样本**：低重建误差，模型可以很好地重建
- **异常样本**：高重建误差，模型难以重建异常模式
- **边界样本**：中等重建误差，需要结合其他分数判断

### 5.4 误差优化建议

1. **调整潜在维度**：
   ```python
   config = VAETrainConfig(latent_dim=8)  # 增加维度
   ```

2. **调整噪声调度**：
   ```python
   config = VAETrainConfig(
       noise_schedule_start=0.8,  # 降低初始噪声
       noise_schedule_end=0.02    # 降低最终噪声
   )
   ```

3. **调整 KL 权重**：
   ```python
   config = VAETrainConfig(beta=0.05)  # 降低 KL 权重
   ```

4. **增加训练轮数**：
   ```python
   config = VAETrainConfig(max_epochs=80)  # 增加训练轮数
   ```

---

## 6. 使用示例

### 6.1 基础使用

```python
import numpy as np
from deep_learning.models.anomaly_detection import VAEAnomalyDetector

# 准备数据
coords = np.random.rand(100, 2)  # 100个样本的坐标
values = np.random.rand(100)     # 对应的值

# 训练模型
detector = VAEAnomalyDetector()
training_result = detector.fit(coords, values)

print(f"训练完成: 最终损失={training_result['final_total_loss']:.4f}")

# 预测异常
result = detector.predict(coords, values, percentile=95.0)

print(f"检测到 {result['anomaly_count']} 个异常")
print(f"阈值: {result['threshold']:.4f}")
print(f"异常索引: {result['anomaly_indices']}")
```

### 6.2 获取详细分数

```python
# 获取所有分数组件
scores = detector.anomaly_scores(coords, values)

print("重建误差:", scores["reconstruction"][:5])
print("潜在距离:", scores["latent_distance"][:5])
print("综合分数:", scores["combined"][:5])
```

### 6.3 潜在空间可视化

```python
import matplotlib.pyplot as plt

# 获取潜在表示
latent_points = detector.latent_visualization(coords, values)

# 绘制潜在空间
latent_array = np.array([[p['z1'], p['z2']] for p in latent_points])
plt.scatter(latent_array[:, 0], latent_array[:, 1], alpha=0.6)
plt.xlabel('潜在维度 1')
plt.ylabel('潜在维度 2')
plt.title('VAE 潜在空间可视化')
plt.show()
```

### 6.4 调整参数

```python
from deep_learning.models.anomaly_detection import VAETrainConfig

# 自定义配置
config = VAETrainConfig(
    latent_dim=6,              # 潜在维度
    beta=0.15,                 # KL 散度权重
    max_epochs=50,             # 训练轮数
    noise_schedule_start=0.8,  # 初始噪声
    noise_schedule_end=0.03,   # 最终噪声
    random_state=123           # 随机种子
)

detector = VAEAnomalyDetector(config=config)
detector.fit(coords, values)
```

### 6.5 批量预测

```python
# 准备测试数据
test_coords = np.random.rand(50, 2)
test_values = np.random.rand(50)

# 批量预测
test_result = detector.predict(test_coords, test_values)

print(f"测试集异常数: {test_result['anomaly_count']}")
print(f"测试集平均分数: {np.mean(test_result['scores']):.4f}")
```

### 6.6 阈值方法比较

```python
methods = ["percentile", "std", "iqr"]

for method in methods:
    result = detector.predict(coords, values, threshold_method=method)
    print(f"{method:12s}: 阈值={result['threshold']:.4f}, "
          f"异常数={result['anomaly_count']}")
```

---

## 7. 参数说明

### 7.1 VAETrainConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `latent_dim` | int | 4 | 潜在空间维度，建议范围 2-10 |
| `beta` | float | 0.1 | KL 散度权重，范围 0.01-1.0 |
| `max_epochs` | int | 40 | 最大训练轮数，建议 20-100 |
| `noise_schedule_start` | float | 1.0 | 初始噪声标准差，范围 0.5-2.0 |
| `noise_schedule_end` | float | 0.05 | 最终噪声标准差，范围 0.01-0.2 |
| `random_state` | int | 42 | 随机种子，用于可复现性 |

### 7.2 predict 方法参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `coords` | np.ndarray | 必需 | 坐标数组，形状 (N, 2) |
| `values` | np.ndarray | 必需 | 值数组，形状 (N,) |
| `threshold_method` | str | "percentile" | 阈值方法：percentile/std/iqr |
| `percentile` | float | 95.0 | 百分位数阈值，范围 0-100 |
| `k` | float | 2.5 | 标准差倍数，仅用于 std 方法 |

### 7.3 参数调优建议

#### 7.3.1 潜在维度 (latent_dim)

- **小维度 (2-4)**：
  - 优点：计算快，易于可视化
  - 缺点：可能欠拟合
  - 适用：简单模式，快速原型

- **中等维度 (5-8)**：
  - 平衡性能和复杂度
  - 适用：大多数场景

- **大维度 (9-10+)**：
  - 优点：表达能力更强
  - 缺点：计算慢，易过拟合
  - 适用：复杂数据分布

#### 7.3.2 KL 权重 (beta)

- **小权重 (0.01-0.05)**：
  - 更关注重建质量
  - 潜在空间可能不规整

- **中等权重 (0.1-0.3)**：
  - 平衡重建和正则化
  - 推荐

- **大权重 (0.5-1.0)**：
  - 强制潜在空间正态分布
  - 可能影响重建质量

#### 7.3.3 训练轮数 (max_epochs)

- **快速测试 (10-20)**：
  - 快速验证模型结构

- **标准训练 (30-50)**：
  - 大多数场景

- **深度训练 (60-100)**：
  - 复杂数据，需要充分训练

#### 7.3.4 噪声调度

- **噪声大** (start=1.0, end=0.1)：
  - 更强的正则化
  - 潜在空间更平滑

- **噪声小** (start=0.5, end=0.02)：
  - 更精确的重建
  - 可能过拟合

---

## 8. 常见问题解答

### 8.1 训练相关

**Q: 训练损失不收敛怎么办？**

A: 检查以下几点：
1. 数据是否归一化（模型内部会归一化，但输入数据应合理）
2. 调整 `beta` 参数，尝试降低到 0.05
3. 增加 `max_epochs` 到 60+
4. 检查数据量，确保至少有 50 个样本

**Q: 训练速度慢怎么办？**

A: 优化建议：
1. 降低 `latent_dim` 到 2-3
2. 减少 `max_epochs` 到 20-30
3. 使用数据采样训练
4. 考虑使用 GPU 加速（当前实现基于 numpy）

**Q: 模型过拟合怎么办？**

A: 防止过拟合：
1. 降低 `latent_dim`
2. 增加 `noise_schedule_start` 和 `noise_schedule_end`
3. 使用更小的 `beta`
4. 增加训练数据

### 8.2 预测相关

**Q: 所有样本都被标记为异常？**

A: 可能原因：
1. 数据量太少（< 30 样本）
2. 数据分布极不均匀
3. 阈值设置过高
4. 解决：增加数据，调整阈值方法

**Q: 没有检测到任何异常？**

A: 可能原因：
1. 数据确实没有异常
2. 阈值设置过高
3. 模型欠拟合
4. 解决：降低 `percentile` 到 90，检查训练

**Q: 异常分数都一样？**

A: 可能原因：
1. 数据完全相同
2. 模型未训练
3. 特征工程失败
4. 解决：检查数据质量，重新训练

### 8.3 解释相关

**Q: LIME/SHAP 解释很慢？**

A: 优化建议：
1. 减少背景数据样本数（SHAP）
2. 降低 `num_samples`（LIME）
3. 使用采样数据解释
4. 考虑批量解释

**Q: 解释结果不稳定？**

A: 原因和解决：
1. 随机性：设置固定随机种子
2. 背景数据：使用有代表性的背景
3. 采样变化：增加采样次数

### 8.4 性能相关

**Q: 检测准确率低？**

A: 改进建议：
1. 检查标注是否正确
2. 调整阈值方法
3. 尝试其他模型（GCAE、GAN、对比学习）
4. 优化特征工程

**Q: 误报率高？**

A: 降低误报：
1. 提高 `percentile` 到 97-98
2. 调整综合分数权重
3. 使用模型集成
4. 添加后处理规则

**Q: 漏报率高？**

A: 降低漏报：
1. 降低 `percentile` 到 90-92
2. 使用更敏感的模型
3. 调整综合分数权重
4. 增加模型复杂度

### 8.5 集成相关

**Q: 如何与其他模型集成？**

A: 集成方法：
```python
from deep_learning.models.anomaly_detection import (
    VAEAnomalyDetector,
    GANAnomalyDetector,
    AnomalyEnsembleIntegrator
)

# 训练多个模型
vae = VAEAnomalyDetector()
gan = GANAnomalyDetector()
vae.fit(coords, values)
gan.fit(coords, values)

# 创建集成
detectors = {"vae": vae, "gan": gan}
ensemble = AnomalyEnsembleIntegrator(detectors)

# 集成预测
result = ensemble.detect(coords, values)
```

### 8.6 部署相关

**Q: 如何保存和加载模型？**

A: 模型持久化：
```python
import pickle

# 保存
with open('vae_model.pkl', 'wb') as f:
    pickle.dump(detector, f)

# 加载
with open('vae_model.pkl', 'rb') as f:
    detector = pickle.load(f)
```

**Q: 模型在生产环境如何更新？**

A: 在线更新策略：
1. 定期重新训练（如每周）
2. 增量训练（如每天）
3. 使用滑动窗口数据
4. 监控模型性能

### 8.7 调试相关

**Q: 如何诊断模型问题？**

A: 调试步骤：
1. 检查训练损失曲线
2. 分析重建误差分布
3. 可视化潜在空间
4. 检查特征重要性
5. 对比多个模型

**Q: 如何获取训练历史？**

A: 查看训练过程：
```python
# 训练历史
history = detector.history

for epoch_info in history:
    print(f"Epoch {epoch_info['epoch']}: "
          f"Loss={epoch_info['total_loss']:.4f}, "
          f"Recon={epoch_info['reconstruction_loss']:.4f}, "
          f"KL={epoch_info['kl_loss']:.4f}")
```

### 8.8 其他

**Q: 模型支持哪些数据类型？**

A: 支持的数据：
- 坐标：二维空间坐标 (x, y)
- 值：连续数值
- 数据量：建议 50+ 样本
- 数值类型：float32/float64

**Q: 可以处理缺失值吗？**

A: 当前限制：
- 不支持缺失值
- 需要预处理缺失值（插值、删除）
- 未来版本可能支持

**Q: 模型的计算复杂度如何？**

A: 复杂度分析：
- 训练：O(N × d² × epochs)
- 预测：O(N × d²)
- 其中 N 是样本数，d 是特征维度
- 对于 1000 样本，训练约 1-2 秒

---

## 9. 最佳实践

### 9.1 数据准备

```python
# 1. 数据质量检查
assert np.isfinite(coords).all(), "坐标包含非有限值"
assert np.isfinite(values).all(), "值包含非有限值"
assert len(coords) == len(values), "坐标和值数量不匹配"
assert len(coords) >= 50, "样本数太少，建议至少50个"

# 2. 数据分布分析
print(f"坐标范围: X[{coords[:, 0].min():.2f}, {coords[:, 0].max():.2f}]")
print(f"          Y[{coords[:, 1].min():.2f}, {coords[:, 1].max():.2f}]")
print(f"值范围: [{values.min():.2f}, {values.max():.2f}]")
print(f"值均值: {values.mean():.2f}, 标准差: {values.std():.2f}")

# 3. 空间分布可视化
import matplotlib.pyplot as plt
plt.scatter(coords[:, 0], coords[:, 1], c=values, cmap='viridis')
plt.colorbar(label='值')
plt.xlabel('X')
plt.ylabel('Y')
plt.title('数据空间分布')
plt.show()
```

### 9.2 模型选择

```python
# 场景 1: 快速原型
detector = VAEAnomalyDetector()
detector.fit(coords, values)

# 场景 2: 高精度要求
config = VAETrainConfig(latent_dim=8, max_epochs=60, beta=0.05)
detector = VAEAnomalyDetector(config=config)
detector.fit(coords, values)

# 场景 3: 需要可解释性
detector = VAEAnomalyDetector()
detector.fit(coords, values)
# 后续结合 LIME/SHAP
```

### 9.3 阈值优化

```python
# 使用验证集优化阈值
from sklearn.metrics import precision_recall_curve

# 假设有真实标签
true_labels = ...  # 0: 正常, 1: 异常
scores = detector.anomaly_scores(coords, values)["combined"]

# 计算不同阈值下的性能
precisions, recalls, thresholds = precision_recall_curve(
    true_labels, scores
)

# 选择最佳 F1 分数的阈值
f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-6)
best_idx = np.argmax(f1_scores)
best_threshold = thresholds[best_idx]

print(f"最佳阈值: {best_threshold:.4f}")
print(f"最佳 F1: {f1_scores[best_idx]:.4f}")
```

### 9.4 性能监控

```python
# 定期评估模型性能
def monitor_model(detector, coords, values, true_labels):
    result = detector.predict(coords, values)
    predicted_labels = (np.array(result['scores']) >= result['threshold']).astype(int)
    
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    
    metrics = {
        'accuracy': accuracy_score(true_labels, predicted_labels),
        'precision': precision_score(true_labels, predicted_labels),
        'recall': recall_score(true_labels, predicted_labels),
        'f1': f1_score(true_labels, predicted_labels),
        'threshold': result['threshold']
    }
    
    return metrics

# 使用
metrics = monitor_model(detector, test_coords, test_values, test_labels)
print(metrics)
```

### 9.5 模型对比

```python
# 对比多个模型
from deep_learning.models.anomaly_detection import (
    VAEAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    ContrastiveAnomalyDetector
)

models = {
    'VAE': VAEAnomalyDetector(),
    'GAN': GANAnomalyDetector(),
    'GCAE': GCAEAnomalyDetector(),
    'Contrastive': ContrastiveAnomalyDetector()
}

results = {}
for name, model in models.items():
    model.fit(coords, values)
    result = model.predict(coords, values)
    results[name] = result

# 比较异常检测数
for name, result in results.items():
    print(f"{name:12s}: {result['anomaly_count']} 个异常")
```

---

## 10. 参考资源

### 10.1 相关文档

- [LIME 集成指南](./LIME集成指南.md)
- [SHAP 集成指南](./SHAP集成指南.md)
- [API 文档](./API文档.md)
- [训练教程](./训练教程.md)

### 10.2 学术论文

1. Kingma & Welling (2013). "Auto-Encoding Variational Bayes"
2. An & Cho (2015). "Variational Autoencoder based Anomaly Detection"

### 10.3 代码示例

- [训练示例](../../deep_learning/examples/anomaly_training_demo.py)
- [推理示例](../../deep_learning/examples/anomaly_inference_demo.py)

### 10.4 实现细节

- 模型实现：`deep_learning/models/anomaly_detection/vae_anomaly.py`
- 公共工具：`deep_learning/models/anomaly_detection/common.py`
- 训练管道：`deep_learning/models/anomaly_detection/training_pipeline.py`

---

## 附录：完整 API 参考

### VAEAnomalyDetector 类

#### 初始化
```python
VAEAnomalyDetector(config: VAETrainConfig | None = None)
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
    k: float = 2.5,
    percentile: float = 95.0
) -> dict[str, object]
```
预测异常。

**anomaly_scores**
```python
anomaly_scores(coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]
```
计算异常分数。

**latent_visualization**
```python
latent_visualization(coords: np.ndarray, values: np.ndarray) -> list[dict[str, float]]
```
获取潜在空间表示。

---

**文档版本**: 1.0  
**最后更新**: 2026-04-10  
**维护者**: UDAKE 开发团队