# GAN 异常检测模型文档

## 1. 模型概述

### 1.1 简介

GAN (Generative Adversarial Network, 生成对抗网络) 异常检测器是一种基于生成对抗思想的异常检测方法。该模型通过训练生成器和判别器，学习正常数据的分布，然后通过判别器评分和重建误差来识别异常样本。

### 1.2 工作原理

GAN 异常检测器包含两个核心组件：

1. **生成器 (Generator)**：
   - 输入：噪声 + 坐标条件
   - 输出：生成的值
   - 功能：学习正常数据的条件分布

2. **判别器 (Discriminator)**：
   - 输入：坐标 + 值
   - 输出：异常分数
   - 功能：区分正常样本和异常样本

3. **对抗训练**：
   - 生成器尝试生成逼真的正常样本
   - 判别器尝试区分真假样本
   - 达到纳什均衡时，判别器可以识别异常

4. **异常检测**：
   - 判别器分数：判别器认为样本异常的程度
   - 重建误差：真实值与生成值的差异
   - 梯度分数：真实值和生成值的空间梯度差异
   - 综合分数：三者的加权组合

### 1.3 网络架构

```
训练阶段:
输入: 坐标 + 值
  ↓
[生成器]: 噪声 + 坐标 → 生成值
  ↓
[判别器]: 坐标 + (真实值 | 生成值) → 分数
  ↓
损失: 
  - 生成器损失: |生成值 - 真实值| + 梯度惩罚
  - 判别器损失: 生成器分数 - 真实分数
  ↓
对抗训练 (max_epochs=60)

推理阶段:
输入: 新坐标 + 新值
  ↓
[生成器]: 生成值 (噪声=0)
  ↓
[判别器]: 坐标 + 新值 → 判别分数
  ↓
[计算]:
  - 判别器分数
  - 重建误差 = |新值 - 生成值|
  - 梯度分数 = |梯度(新值) - 梯度(生成值)|
  ↓
综合分数 = 0.5×判别 + 0.35×重建 + 0.15×梯度
```

### 1.4 损失函数

**生成器损失**：
```
L_G = |G(z, c) - v| + λ_GP × GP
```
- G(z, c): 生成器输出
- v: 真实值
- GP: 梯度惩罚

**判别器损失**：
```
L_D = D(c, G(z, c)) - D(c, v) + λ_GP × GP
```
- D(c, v): 判别器对真实样本的分数
- D(c, G(z, c)): 判别器对生成样本的分数

**梯度惩罚**：
```
GP = (||∇_x D(c, x)||_2 - 1)²
```
用于约束判别器的梯度，稳定训练。

### 1.5 适用场景

- 适合检测分布外异常
- 适合检测生成困难的异常
- 适合需要高判别力的场景
- 适合正常样本分布清晰的情况
- 不适合训练数据本身包含异常的情况

---

## 2. LIME 解释指南

### 2.1 概述

对于 GAN 模型，LIME 解释关注判别器决策的特征重要性。

### 2.2 关键特征

GAN 模型使用以下特征：

- **空间特征**：coord_x, coord_y, radius, angle
- **值特征**：value
- **判别器分数**：disc_score
- **重建分数**：recon_score
- **梯度分数**：grad_score
- **噪声水平**：noise_level

### 2.3 实现步骤

```python
from deep_learning.models.anomaly_detection import GANAnomalyDetector
import numpy as np

# 1. 训练模型
detector = GANAnomalyDetector()
detector.fit(coords, values)

# 2. 预处理数据
preprocessed = detector.preprocess_gan_data(
    coords, values,
    batch_size=64,
    use_training_stats=True,
    noise_scale=0.05
)

features = preprocessed["processed_features"]
feature_names = preprocessed["feature_names"]

# 3. 定义预测函数
def predict_fn(X):
    """LIME 使用的预测函数"""
    sample_coords = X[:, :2]
    sample_values = X[:, 4]  # value 列
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["combined"]

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

- **value**：值本身偏离正常范围
- **coord_x/coord_y**：坐标位置异常
- **disc_score**：判别器认为异常
- **recon_score**：生成器难以重建
- **grad_score**：空间梯度异常

---

## 3. SHAP 解释指南

### 3.1 概述

SHAP 分析 GAN 模型中各特征对综合异常分数的贡献。

### 3.2 实现步骤

```python
import shap
from deep_learning.models.anomaly_detection import GANAnomalyDetector

# 1. 训练模型
detector = GANAnomalyDetector()
detector.fit(coords, values)

# 2. 准备背景数据
preprocessed = detector.preprocess_gan_data(
    coords, values,
    batch_size=64,
    use_training_stats=True
)
background = preprocessed["processed_features"][:100]
feature_names = preprocessed["feature_names"]

# 3. 定义预测函数
def model_predict(X):
    sample_coords = X[:, :2]
    sample_values = X[:, 4]
    scores = detector.anomaly_scores(sample_coords, sample_values)
    return scores["combined"].reshape(-1, 1)

# 4. 创建解释器
explainer = shap.KernelExplainer(model_predict, background)

# 5. 计算解释
instance = preprocessed["processed_features"][idx]
shap_values = explainer.shap_values(instance)

# 6. 可视化
# shap.waterfall_plot(shap_values[0], feature_names=feature_names)
```

### 3.3 生成器分析

也可以分析生成器的行为：

```python
# 分析生成器生成值与真实值的差异
generated = np.array(preprocessed["generated_values"])
true = preprocessed["values"]

diff = np.abs(generated - true)
print(f"平均差异: {np.mean(diff):.4f}")
print(f"最大差异: {np.max(diff):.4f}")

# 可视化差异
import matplotlib.pyplot as plt
plt.scatter(preprocessed["coords"][:, 0], 
            preprocessed["coords"][:, 1],
            c=diff, cmap='hot', s=50)
plt.colorbar(label='生成差异')
plt.title('生成器生成误差')
plt.show()
```

---

## 4. 异常分数解释说明

### 4.1 分数组成

GAN 模型提供四层异常分数：

```
综合分数 = 0.5 × 判别器分数 + 0.35 × 重建误差 + 0.15 × 梯度分数
```

### 4.2 分数详解

#### 4.2.1 判别器分数

**定义**：判别器认为样本异常的程度

**计算**：
```python
disc_score = 0.7 × 归一化(|值 - 均值| / 标准差) 
           + 0.3 × 归一化(|空间梯度 - 梯度均值| / 梯度标准差)
```

**组成**：
- **值分数**：样本值偏离正常分布的程度
- **梯度分数**：空间梯度偏离正常模式的程度

**意义**：
- 高值：判别器认为样本明显异常
- 低值：判别器认为样本可能是正常的

**典型范围**：0 ~ 1

**特点**：
- 判别器在对抗训练中学习区分真假
- 对分布外样本敏感

#### 4.2.2 重建误差

**定义**：真实值与生成器生成值的差异

**计算**：
```python
recon_score = 归一化(|真实值 - 生成器值|)
```

**意义**：
- 高值：生成器无法生成该样本，说明样本异常
- 低值：生成器可以很好地生成该样本

**典型范围**：0 ~ 1

**特点**：
- 生成器学习正常数据的条件分布
- 异常样本的生成误差通常较大

#### 4.2.3 梯度分数

**定义**：真实值的空间梯度与生成值的空间梯度的差异

**计算**：
```python
梯度_real = 空间梯度(真实值)
梯度_fake = 空间梯度(生成值)
gradient_score = 归一化(|梯度_real - 梯度_fake|)
```

**空间梯度计算**：
```python
梯度 = |值_i - 值_j| / ||坐标_i - 坐标_j||
```

**意义**：
- 高值：样本的空间变化模式异常
- 低值：样本的空间变化模式正常

**典型范围**：0 ~ 1

**特点**：
- 捕捉空间连续性异常
- 对局部突变敏感

#### 4.2.4 综合分数

**定义**：三个分数的加权组合

**计算**：
```python
combined = 0.5 × disc_score + 0.35 × recon_score + 0.15 × gradient_score
```

**意义**：
- 结合判别器的判别能力
- 结合生成器的生成能力
- 结合空间连续性信息
- 更全面的异常评估

**典型范围**：0 ~ 1

**权重说明**：
- 判别器权重最大 (0.5)：主要依据判别器
- 重建误差次之 (0.35)：辅助判断
- 梯度分数最小 (0.15)：补充信息

### 4.3 阈值确定

支持多种阈值方法（与 VAE 相同）：

1. **百分位数法**：默认 percentile=95.0
2. **标准差法**：k=2.5
3. **IQR 法**

### 4.4 分数解读指南

| 判别器分数 | 重建误差 | 梯度分数 | 可能情况 | 建议操作 |
|-----------|---------|---------|---------|---------|
| 高 | 高 | 高 | 各方面都异常 | 优先处理 |
| 高 | 低 | 低 | 判别器认为异常但生成器能生成 | 检查判别器 |
| 低 | 高 | 高 | 判别器认为正常但生成器无法生成 | 检查生成器 |
| 低 | 低 | 低 | 正常样本 | 无需处理 |

### 4.5 训练诊断

GAN 训练可能遇到以下问题：

#### 4.5.1 模式崩溃 (Mode Collapse)

**现象**：生成器只生成少数几种模式

**检测**：
```python
mode_collapse = any(item["mode_collapse"] > 0 for item in detector.history)
print(f"是否检测到模式崩溃: {mode_collapse}")
```

**解决**：
- 增加 `max_epochs`
- 调整 `gp_weight`
- 使用更多的训练数据

#### 4.5.2 训练不稳定

**现象**：损失震荡严重

**检测**：
```python
gen_losses = [item["generator_loss"] for item in detector.history]
disc_losses = [item["discriminator_loss"] for item in detector.history]

plt.plot(gen_losses, label="生成器")
plt.plot(disc_losses, label="判别器")
plt.legend()
plt.show()
```

**解决**：
- 调整 `gp_weight`
- 调整学习率（当前实现固定）
- 使用更小的 `max_epochs`

---

## 5. 生成器分析说明

### 5.1 生成器结构

**设计矩阵**：
```python
design = [1, x, y, radius, angle]
```

**生成过程**：
```python
生成值 = design @ coef + bias + 0.1 × noise
```

**特点**：
- 线性模型（简化实现）
- 条件生成（基于坐标）
- 可解释性强

### 5.2 生成器能力分析

#### 5.2.1 生成质量

```python
# 生成正常样本
noise = np.zeros_like(values)
generated = detector.generator(noise, coords)

# 计算生成误差
errors = np.abs(values - generated)

print(f"平均误差: {np.mean(errors):.4f}")
print(f"中位数误差: {np.median(errors):.4f}")
print(f"最大误差: {np.max(errors):.4f}")
```

#### 5.2.2 生成分布

```python
# 比较真实值和生成值的分布
import matplotlib.pyplot as plt

plt.hist(values, bins=30, alpha=0.5, label='真实值')
plt.hist(generated, bins=30, alpha=0.5, label='生成值')
plt.legend()
plt.xlabel('值')
plt.ylabel('频数')
plt.title('真实值 vs 生成值分布')
plt.show()
```

#### 5.2.3 空间生成质量

```python
# 可视化生成误差的空间分布
plt.scatter(coords[:, 0], coords[:, 1], c=errors, 
            cmap='hot', s=50)
plt.colorbar(label='生成误差')
plt.title('生成误差空间分布')
plt.show()
```

### 5.3 判别器分析说明

### 5.3.1 判别器结构

判别器计算两个分数：

1. **值分数**：
```python
value_score = |值 - 均值| / 标准差
```

2. **梯度分数**：
```python
梯度 = |值_i - 值_j| / ||坐标_i - 坐标_j||
spatial_score = |梯度 - 梯度均值| / 梯度标准差
```

3. **判别器分数**：
```python
disc_score = 0.7 × 归一化(value_score) + 0.3 × 归一化(spatial_score)
```

### 5.3.2 判别器能力

```python
# 判别器对真实样本的分数
real_disc = detector.discriminator(coords, values)

# 判别器对生成样本的分数
noise = np.zeros_like(values)
fake = detector.generator(noise, coords)
fake_disc = detector.discriminator(coords, fake)

print(f"真实样本平均判别分数: {np.mean(real_disc):.4f}")
print(f"生成样本平均判别分数: {np.mean(fake_disc):.4f}")

# 好的判别器应该：真实分数低，生成分数高
```

### 5.3.3 判别器可视化

```python
# 可视化判别器分数
plt.scatter(coords[:, 0], coords[:, 1], c=real_disc,
            cmap='hot', s=50)
plt.colorbar(label='判别器分数')
plt.title('判别器分数空间分布')
plt.show()
```

### 5.4 对抗训练分析

#### 5.4.1 训练历史

```python
# 查看训练历史
for epoch_info in detector.history[::10]:  # 每10个epoch显示一次
    print(f"Epoch {int(epoch_info['epoch']):2d}: "
          f"G={epoch_info['generator_loss']:.4f}, "
          f"D={epoch_info['discriminator_loss']:.4f}, "
          f"GP={epoch_info['gradient_penalty']:.4f}")
```

#### 5.4.2 损失曲线

```python
# 绘制训练曲线
epochs = [item["epoch"] for item in detector.history]
gen_losses = [item["generator_loss"] for item in detector.history]
disc_losses = [item["discriminator_loss"] for item in detector.history]
gp_losses = [item["gradient_penalty"] for item in detector.history]

fig, axes = plt.subplots(3, 1, figsize=(10, 12))

axes[0].plot(epochs, gen_losses)
axes[0].set_ylabel('生成器损失')
axes[0].set_title('生成器训练曲线')

axes[1].plot(epochs, disc_losses)
axes[1].set_ylabel('判别器损失')
axes[1].set_title('判别器训练曲线')

axes[2].plot(epochs, gp_losses)
axes[2].set_xlabel('Epoch')
axes[2].set_ylabel('梯度惩罚')
axes[2].set_title('梯度惩罚曲线')

plt.tight_layout()
plt.show()
```

#### 5.4.3 收敛判断

```python
# 判断是否收敛
def is_converged(history, window=10, threshold=0.01):
    """检查最后window个epoch的损失变化"""
    if len(history) < window:
        return False
    recent = history[-window:]
    losses = [item["generator_loss"] for item in recent]
    return np.std(losses) < threshold

print(f"是否收敛: {is_converged(detector.history)}")
```

---

## 6. 使用示例

### 6.1 基础使用

```python
import numpy as np
from deep_learning.models.anomaly_detection import GANAnomalyDetector

# 准备数据
coords = np.random.rand(100, 2)
values = np.random.rand(100)

# 训练模型
detector = GANAnomalyDetector()
training_result = detector.fit(coords, values)

print(f"训练完成:")
print(f"  最终生成器损失: {training_result['final_generator_loss']:.4f}")
print(f"  最终判别器损失: {training_result['final_discriminator_loss']:.4f}")
print(f"  模式崩溃: {training_result['mode_collapse_detected']}")
print(f"  训练轮数: {training_result['epochs']}")

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

print("判别器分数:", score_bundle["discriminator"][:5])
print("重建误差:", score_bundle["reconstruction"][:5])
print("梯度分数:", score_bundle["gradient"][:5])
print("综合分数:", score_bundle["combined"][:5])
```

### 6.3 数据预处理

```python
# 预处理数据以获取详细特征
preprocessed = detector.preprocess_gan_data(
    coords, values,
    batch_size=32,
    use_training_stats=True,
    noise_scale=0.05
)

print("特征名称:", preprocessed["feature_names"])
print("特征形状:", preprocessed["processed_features"].shape)
print("生成值:", preprocessed["generated_values"][:5])
print("潜在投影:", preprocessed["latent_projection"][:5])
```

### 6.4 调整参数

```python
from deep_learning.models.anomaly_detection import GANConfig

# 自定义配置
config = GANConfig(
    latent_dim=8,              # 潜在维度
    max_epochs=80,             # 训练轮数
    gp_weight=15.0,            # 梯度惩罚权重
    random_state=123           # 随机种子
)

detector = GANAnomalyDetector(config=config)
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

### 6.6 生成器生成

```python
# 生成新的样本
new_coords = np.random.rand(20, 2)
noise = np.zeros(20)  # 不添加噪声
generated_values = detector.generator(noise, new_coords)

print("生成的值:", generated_values)

# 可视化生成
import matplotlib.pyplot as plt
plt.scatter(coords[:, 0], coords[:, 1], c=values, 
            cmap='viridis', s=50, label='训练数据')
plt.scatter(new_coords[:, 0], new_coords[:, 1], c=generated_values,
            cmap='viridis', marker='x', s=100, label='生成数据')
plt.legend()
plt.colorbar()
plt.title('生成器生成结果')
plt.show()
```

---

## 7. 参数说明

### 7.1 GANConfig 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `latent_dim` | int | 6 | 潜在噪声维度，建议 4-8 |
| `max_epochs` | int | 60 | 最大训练轮数，建议 40-100 |
| `gp_weight` | float | 10.0 | 梯度惩罚权重，建议 5-20 |
| `random_state` | int | 42 | 随机种子 |

### 7.2 预处理参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `batch_size` | int | None | 批处理大小 |
| `use_training_stats` | bool | True | 是否使用训练时的归一化参数 |
| `noise_scale` | float | 0.05 | 噪声标准差 |

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

- **小维度 (4-5)**：
  - 生成器更简单
  - 可能欠拟合

- **中等维度 (6-8)**：
  - 推荐
  - 平衡表达能力和复杂度

- **大维度 (9-10+)**：
  - 表达能力强
  - 可能不稳定

#### 7.4.2 训练轮数 (max_epochs)

- **快速训练 (40-50)**：
  - 快速验证
  - 可能未收敛

- **标准训练 (60-80)**：
  - 推荐
  - 通常能收敛

- **深度训练 (90-100+)**：
  - 更充分训练
  - 可能过拟合

#### 7.4.3 梯度惩罚权重 (gp_weight)

- **小权重 (5-8)**：
  - 约束弱
  - 训练可能不稳定

- **中等权重 (10-15)**：
  - 推荐
  - 平衡稳定性和灵活性

- **大权重 (16-20+)**：
  - 强约束
  - 训练稳定但可能限制表达能力

#### 7.4.4 综合分数权重

在 `anomaly_scores` 中固定为：
- 判别器: 0.5
- 重建误差: 0.35
- 梯度分数: 0.15

如需调整，需要修改源代码。

---

## 8. 常见问题解答

### 8.1 训练相关

**Q: 训练不收敛怎么办？**

A: 检查以下几点：
1. 增加 `gp_weight` 到 15-20
2. 减少 `max_epochs` 到 40-50
3. 检查数据质量
4. 尝试不同的 `random_state`

**Q: 生成器和判别器损失都很大？**

A: 可能原因：
1. 数据分布复杂
2. 生成器太简单（线性模型）
3. 需要更多训练轮数
4. 考虑使用更复杂的模型

**Q: 出现模式崩溃怎么办？**

A: 解决方法：
1. 增加 `max_epochs`
2. 调整 `gp_weight`
3. 使用更多训练数据
4. 检查 `mode_collapse` 标志

**Q: 训练很慢怎么办？**

A: 优化建议：
1. 减少 `max_epochs`
2. 减少 `latent_dim`
3. 使用数据采样
4. 当前实现基于 numpy，已经比较高效

### 8.2 预测相关

**Q: 判别器分数都很高？**

A: 可能原因：
1. 判别器过于敏感
2. 数据本身异常多
3. 训练不充分
4. 解决：重新训练或调整阈值

**Q: 重建误差都很小？**

A: 可能原因：
1. 生成器过拟合
2. 数据模式简单
3. 异常不明显
4. 解决：检查生成器行为

**Q: 梯度分数不稳定？**

A: 可能原因：
1. 数据空间分布不均匀
2. 噪声较大
3. 梯度计算对距离敏感
4. 解决：平滑数据或调整权重

**Q: 综合分数与单个分数不一致？**

A: 这是正常的：
- 综合分数是加权组合
- 不同分数可能给出不同判断
- 需要综合分析

### 8.3 生成器相关

**Q: 生成器生成的值都一样？**

A: 模式崩溃：
1. 检查训练历史中的 `mode_collapse`
2. 增加 `max_epochs`
3. 调整 `gp_weight`
4. 使用更多数据

**Q: 生成器无法生成高值或低值？**

A: 原因：
1. 线性生成器的局限性
2. 数据范围未正确处理
3. 训练不充分
4. 解决：检查数据归一化

**Q: 如何评估生成器质量？**

A: 评估方法：
1. 比较真实值和生成值的分布
2. 计算生成误差
3. 可视化生成结果
4. 使用判别器评估

### 8.4 判别器相关

**Q: 判别器无法区分真假？**

A: 原因：
1. 训练不充分
2. 判别器太简单
3. 数据特征不明显
4. 解决：增加训练轮数

**Q: 判别器对所有样本都给高分数？**

A: 原因：
1. 判别器过于保守
2. 训练数据包含异常
3. 判别器权重设置不当
4. 解决：调整判别器结构或参数

**Q: 判别器分数与实际异常不一致？**

A: 可能原因：
1. 异常定义不同
2. 判别器学习的是生成器能生成的样本
3. 需要领域知识辅助判断
4. 解决：结合其他分数分析

### 8.5 性能相关

**Q: GAN 比 VAE 慢很多？**

A: 原因：
1. GAN 需要对抗训练
2. 每个epoch需要生成和判别
3. 梯度惩罚计算开销
4. 解决：减少 `max_epochs` 或 `latent_dim`

**Q: 检测准确率不如其他模型？**

A: 可能原因：
1. 数据类型不适合 GAN
2. 训练参数不合适
3. 生成器太简单
4. 解决：调整参数或尝试其他模型

**Q: 误报率高？**

A: 降低误报：
1. 提高 `percentile`
2. 调整综合分数权重
3. 使用模型集成
4. 检查判别器是否过于敏感

### 8.6 解释相关

**Q: 如何解释判别器的决策？**

A: 分析步骤：
1. 查看值分数和梯度分数
2. 使用 LIME/SHAP 分析特征重要性
3. 比较正常样本和异常样本的特征
4. 理解判别器关注的特征

**Q: 如何解释生成器的行为？**

A: 分析步骤：
1. 查看生成器系数
2. 分析生成误差的空间分布
3. 比较生成值和真实值的分布
4. 理解生成器学到的模式

**Q: 综合分数如何解释？**

A: 分解方法：
1. 查看三个组成部分
2. 理解每个部分的贡献
3. 分析哪些部分驱动了高分
4. 结合领域知识判断

### 8.7 集成相关

**Q: 如何与其他模型集成？**

A: 参考代码：
```python
from deep_learning.models.anomaly_detection import (
    GANAnomalyDetector,
    VAEAnomalyDetector,
    AnomalyEnsembleIntegrator
)

# 训练多个模型
gan = GANAnomalyDetector()
vae = VAEAnomalyDetector()
gan.fit(coords, values)
vae.fit(coords, values)

# 创建集成
detectors = {"gan": gan, "vae": vae}
ensemble = AnomalyEnsembleIntegrator(detectors)

# 集成预测
result = ensemble.detect(coords, values)
```

### 8.8 其他

**Q: GAN 适合什么类型的数据？**

A: 适用数据：
- 分布清晰的正常数据
- 需要高判别力的场景
- 可以生成的数据
- 条件生成的场景

**Q: GAN 不适合什么数据？**

A: 不适用数据：
- 训练数据包含大量异常
- 数据分布极其复杂
- 需要精确重建的场景
- 小数据集（< 50 样本）

**Q: 模型可以增量训练吗？**

A: 当前限制：
- 不支持增量训练
- 需要重新训练
- 未来版本可能支持

**Q: 如何保存和加载模型？**

A: 模型持久化：
```python
import pickle

# 保存
with open('gan_model.pkl', 'wb') as f:
    pickle.dump(detector, f)

# 加载
with open('gan_model.pkl', 'rb') as f:
    detector = pickle.load(f)
```

---

## 9. 最佳实践

### 9.1 数据准备

```python
import numpy as np
from deep_learning.models.anomaly_detection import GANAnomalyDetector

# 1. 数据质量检查
coords = ...  # 你的坐标数据
values = ...  # 你的值数据

assert coords.shape[1] == 2, "坐标必须是二维"
assert len(coords) == len(values), "坐标和值数量必须一致"
assert len(coords) >= 50, "至少需要50个样本"
assert np.isfinite(coords).all(), "坐标不能包含NaN或Inf"
assert np.isfinite(values).all(), "值不能包含NaN或Inf"

# 2. 数据分布分析
print(f"坐标范围: X[{coords[:, 0].min():.2f}, {coords[:, 0].max():.2f}]")
print(f"          Y[{coords[:, 1].min():.2f}, {coords[:, 1].max():.2f}]")
print(f"值范围: [{values.min():.2f}, {values.max():.2f}]")
print(f"值均值: {values.mean():.2f}, 标准差: {values.std():.2f}")

# 3. 空间连续性检查
from scipy.spatial.distance import pdist
distances = pdist(coords)
print(f"平均空间距离: {np.mean(distances):.4f}")

# 4. 可视化数据分布
import matplotlib.pyplot as plt
plt.scatter(coords[:, 0], coords[:, 1], c=values, cmap='viridis', s=50)
plt.colorbar(label='值')
plt.xlabel('X')
plt.ylabel('Y')
plt.title('数据空间分布')
plt.show()
```

### 9.2 参数调优

```python
from deep_learning.models.anomaly_detection import GANConfig
from sklearn.model_selection import ParameterGrid

# 参数网格
param_grid = {
    'latent_dim': [4, 6, 8],
    'max_epochs': [50, 70, 90],
    'gp_weight': [8, 10, 12]
}

# 网格搜索
best_score = float('inf')
best_config = None

for params in ParameterGrid(param_grid):
    config = GANConfig(**params)
    detector = GANAnomalyDetector(config=config)
    result = detector.fit(coords, values)
    
    # 检查是否模式崩溃
    if result['mode_collapse_detected']:
        continue
    
    # 使用总损失评估
    score = result['final_generator_loss'] + result['final_discriminator_loss']
    
    if score < best_score:
        best_score = score
        best_config = params

print(f"最佳配置: {best_config}")
print(f"最佳损失: {best_score:.4f}")
```

### 9.3 训练监控

```python
import matplotlib.pyplot as plt

# 训练模型
detector = GANAnomalyDetector()
detector.fit(coords, values)

# 监控训练过程
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# (a) 损失曲线
epochs = [item["epoch"] for item in detector.history]
gen_losses = [item["generator_loss"] for item in detector.history]
disc_losses = [item["discriminator_loss"] for item in detector.history]

axes[0, 0].plot(epochs, gen_losses, label='生成器')
axes[0, 0].plot(epochs, disc_losses, label='判别器')
axes[0, 0].set_xlabel('Epoch')
axes[0, 0].set_ylabel('损失')
axes[0, 0].set_title('训练损失')
axes[0, 0].legend()

# (b) 梯度惩罚
gp_losses = [item["gradient_penalty"] for item in detector.history]
axes[0, 1].plot(epochs, gp_losses)
axes[0, 1].set_xlabel('Epoch')
axes[0, 1].set_ylabel('梯度惩罚')
axes[0, 1].set_title('梯度惩罚')

# (c) 模式崩溃检测
mode_collapse = [item["mode_collapse"] for item in detector.history]
axes[1, 0].plot(epochs, mode_collapse)
axes[1, 0].set_xlabel('Epoch')
axes[1, 0].set_ylabel('模式崩溃标志')
axes[1, 0].set_title('模式崩溃检测')

# (d) 损失差异
loss_diff = [abs(g - d) for g, d in zip(gen_losses, disc_losses)]
axes[1, 1].plot(epochs, loss_diff)
axes[1, 1].set_xlabel('Epoch')
axes[1, 1].set_ylabel('|G_loss - D_loss|')
axes[1, 1].set_title('生成器与判别器损失差异')

plt.tight_layout()
plt.show()
```

### 9.4 异常分析

```python
# 预测异常
result = detector.predict(coords, values)

# 获取详细分数
score_bundle = detector.anomaly_scores(coords, values)

# 可视化异常
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# (a) 判别器分数
sc1 = axes[0, 0].scatter(coords[:, 0], coords[:, 1], 
                        c=score_bundle["discriminator"], 
                        cmap='hot', s=50)
plt.colorbar(sc1, ax=axes[0, 0])
axes[0, 0].set_title('判别器分数')

# (b) 重建误差
sc2 = axes[0, 1].scatter(coords[:, 0], coords[:, 1], 
                        c=score_bundle["reconstruction"], 
                        cmap='hot', s=50)
plt.colorbar(sc2, ax=axes[0, 1])
axes[0, 1].set_title('重建误差')

# (c) 梯度分数
sc3 = axes[1, 0].scatter(coords[:, 0], coords[:, 1], 
                        c=score_bundle["gradient"], 
                        cmap='hot', s=50)
plt.colorbar(sc3, ax=axes[1, 0])
axes[1, 0].set_title('梯度分数')

# (d) 综合分数
sc4 = axes[1, 1].scatter(coords[:, 0], coords[:, 1], 
                        c=score_bundle["combined"], 
                        cmap='hot', s=50)
plt.colorbar(sc4, ax=axes[1, 1])
axes[1, 1].set_title('综合分数')

plt.tight_layout()
plt.show()

# 标记异常
anomaly_coords = coords[result["anomaly_indices"]]
plt.figure(figsize=(8, 6))
plt.scatter(coords[:, 0], coords[:, 1], c='blue', 
            alpha=0.5, s=50, label='正常')
plt.scatter(anomaly_coords[:, 0], anomaly_coords[:, 1], 
            c='red', s=100, label='异常')
plt.legend()
plt.title('异常检测结果')
plt.show()
```

### 9.5 性能评估

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
scores = result['scores']

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

# 绘制 ROC 曲线
from sklearn.metrics import roc_curve
fpr, tpr, _ = roc_curve(true_labels, scores)
plt.plot(fpr, tpr)
plt.plot([0, 1], [0, 1], 'k--')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curve')
plt.show()

# 绘制 PR 曲线
precisions, recalls, thresholds = precision_recall_curve(true_labels, scores)
plt.plot(recalls, precisions)
plt.xlabel('Recall')
plt.ylabel('Precision')
plt.title('Precision-Recall Curve')
plt.show()
```

---

## 10. 参考资源

### 10.1 相关文档

- [VAE 异常检测模型](./VAE异常检测模型.md)
- [GCAE 异常检测模型](./GCAE异常检测模型.md)
- [对比学习异常检测模型](./对比学习异常检测模型.md)
- [LIME 集成指南](./LIME集成指南.md)
- [SHAP 集成指南](./SHAP集成指南.md)

### 10.2 学术论文

1. Goodfellow et al. (2014). "Generative Adversarial Nets"
2. Schlegl et al. (2017). "Unsupervised Anomaly Detection with Generative Adversarial Networks to Guide Marker Discovery"
3. Akcay et al. (2018). "GANomaly: Semi-Supervised Anomaly Detection via Adversarial Training"

### 10.3 代码示例

- 模型实现：`deep_learning/models/anomaly_detection/gan_anomaly.py`
- 训练示例：`deep_learning/examples/anomaly_training_demo.py`
- 推理示例：`deep_learning/examples/anomaly_inference_demo.py`

### 10.4 相关资源

- GAN Zoo: https://github.com/hindupuravinash/the-gan-zoo
- GAN Papers: https://github.com/zsxuanhao/gan-papers

---

## 附录：完整 API 参考

### GANAnomalyDetector 类

#### 初始化
```python
GANAnomalyDetector(config: GANConfig | None = None)
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
anomaly_scores(coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]
```
计算所有异常分数。

**preprocess_gan_data**
```python
preprocess_gan_data(
    coords: np.ndarray,
    values: np.ndarray,
    *,
    batch_size: int | None = None,
    use_training_stats: bool = True,
    noise_scale: float = 0.05
) -> dict[str, object]
```
预处理 GAN 数据。

**generator**
```python
generator(noise: np.ndarray, coords: np.ndarray) -> np.ndarray
```
生成器生成值。

**discriminator**
```python
discriminator(coords: np.ndarray, values: np.ndarray) -> np.ndarray
```
判别器计算分数。

**is_trained**
```python
is_trained() -> bool
```
检查模型是否已训练。

### GANConfig 类

#### 参数
- `latent_dim`: int = 6
- `max_epochs`: int = 60
- `gp_weight`: float = 10.0
- `random_state`: int = 42

---

**文档版本**: 1.0  
**最后更新**: 2026-04-10  
**维护者**: UDAKE 开发团队