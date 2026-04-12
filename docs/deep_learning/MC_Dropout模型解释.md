# MC Dropout（蒙特卡洛Dropout）模型解释

## 1. 概述

MC Dropout（Monte Carlo Dropout）是一种简单而有效的不确定性量化方法，通过在测试时保持Dropout激活并执行多次前向传播来估计预测的不确定性。该方法由Gal和Ghahramani于2016年提出，证明了Dropout可以被解释为近似贝叶斯推断。

## 2. 核心原理

### 2.1 Dropout作为贝叶斯近似

传统观点认为Dropout是一种正则化技术，而MC Dropout从贝叶斯角度重新解释了Dropout：

- 训练时：Dropout采样网络结构的子网络
- 测试时：保持Dropout激活，多次采样不同子网络
- 预测分布：由多次采样的预测值统计得到

### 2.2 数学基础

对于输入x，第t次前向传播的预测：

```
ŷ^(t) = f(x; θ^(t))
```

其中θ^(t)是第t次Dropout采样得到的网络参数。

最终预测统计量：
- 均值：E[y] = (1/T) * Σ ŷ^(t)
- 方差：Var[y] = (1/T) * Σ (ŷ^(t) - E[y])²

### 2.3 理论解释

MC Dropout可以视为变分推断的一种近似：

- 变分分布：q(θ) = ∫ p(θ|z) p(z) dz
- Dropout掩码：z ~ Bernoulli(p)
- 采样预测：E_q[f(x,θ)] ≈ (1/T) * Σ f(x,θ^(t))

## 3. 模型架构

### 3.1 网络结构

本实现采用两层全连接网络：

```
输入层 → 隐藏层 + Dropout → 输出层（均值和方差分支）
```

- 隐藏层：全连接层 + Tanh激活函数 + Dropout
- 输出层：两个独立分支
  - 均值分支：预测输出均值
  - 方差分支：预测对数方差

### 3.2 Dropout层实现

#### DropoutType
支持三种Dropout类型：

##### Standard（标准Dropout）
```python
mask = (U(0,1) < keep_prob) / keep_prob
```

##### Spatial（空间Dropout）
在特征维度上共享Dropout掩码：
```python
mask = repeat((U(0,1) < keep_prob) / keep_prob, axis=0)
```

##### Variational（变分Dropout）
训练时固定Dropout掩码，推理时保持不变：
```python
if mask is None:
    mask = (U(0,1) < keep_prob) / keep_prob
```

### 3.3 MCDropoutRegressor类

主要组件：

- 网络参数：w1, b1（隐藏层），w_mean, b_mean（均值），w_logvar, b_logvar（方差）
- Dropout层：控制神经元激活概率
- 历史记录：存储训练过程中的损失值

## 4. 训练过程

### 4.1 损失函数

使用混合损失函数：

```
L = (1 - w) * MSE + w * NLL
```

- MSE：均方误差，衡量预测均值与真实值的差异
- NLL：负对数似然，考虑预测方差
- w：NLL权重，平衡MSE和NLL的贡献

### 4.2 梯度计算

#### 均值梯度
```
∂L/∂μ = [(1-w) * 2 * error + w * error / σ²] / n
```

#### 方差梯度
```
∂L/∂logσ = w * 0.5 * (1 - error² / σ²) / n
```

其中error = ŷ - y，n为样本数。

### 4.3 Dropout反向传播

通过Dropout层的梯度需要除以保持概率：

```python
d_h = d_h_drop * keep_prob
```

确保梯度量的正确缩放。

## 5. 预测过程

### 5.1 蒙特卡洛采样

通过T次前向传播获得预测分布：

```python
for t in range(T):
    随机生成Dropout掩码
    计算预测 μ^(t), σ²^(t)
```

### 5.2 不确定性分解

#### 偶然不确定性（Aleatoric）
源于数据噪声，反映模型输出的固有方差：
```
σ_aleatoric² = E[σ²]
```

#### 认知不确定性（Epistemic）
源于模型不确定性，反映多次预测的方差：
```
σ_epistemic² = Var[μ]
```

#### 总不确定性
```
σ_total² = σ_aleatoric² + σ_epistemic²
```

### 5.3 置信区间

基于预测分布计算置信区间：

```
[μ - z * σ, μ + z * σ]
```

其中z为标准正态分布的分位数（如95%置信度对应z≈1.96）。

## 6. 关键特性

### 6.1 自适应采样次数

通过`adaptive_t()`方法自动确定最优采样次数：

```python
curve = [epistemic_uncertainty for t in range(2, max_t+1)]
best_t = find_stable_point(curve, tolerance)
```

原理：当认知不确定性趋于稳定时停止采样。

### 6.2 T敏感性分析

通过`t_sensitivity()`方法分析采样次数对不确定性的影响：

```python
for t in t_values:
    pred = predict(x, t=t)
    record(epistemic, total_variance)
```

帮助用户选择合适的采样次数。

### 6.3 批量预测

支持大规模数据的高效批量处理：

- 自动分批处理
- 内存优化选项
- 结果缓存机制

### 6.4 数据预处理

内置标准化预处理：

```
x_scaled = (x - μ_x) / σ_x
```

支持使用训练时统计量或当前批次统计量。

## 7. 可解释性分析

### 7.1 Dropout权重解释

通过`explain_dropout_weights()`方法分析权重特性：

- 权重统计：均值、标准差、绝对值均值
- Dropout效应：考虑保持概率的调整重要性
- 稀疏性：权重接近零的比例

#### 高重要性参数
考虑Dropout后重要性最高的参数：
```
adjusted_importance = |w| * keep_prob
```

#### 弱参数
重要性最低的参数，可能对应冗余特征。

### 7.2 多次前向传播分析

通过`analyze_multiple_forward_passes()`方法分析预测稳定性：

- 预测标准差：衡量预测的波动性
- 稳定性分数：1 / (1 + CV)，其中CV为变异系数
- 高不稳定样本：预测波动最大的样本

### 7.3 预测分布分析

通过`analyze_prediction_distribution()`方法分析预测分布的形态：

- 分位数：Q05, Q25, Q50, Q75, Q95
- 偏度：衡量分布的不对称性
- 峰度：衡量分布的尖锐程度
- 区间宽度：Q95 - Q05，衡量预测的不确定性范围

## 8. 性能优化

### 8.1 向量化采样

使用向量化操作加速多次前向传播：

```python
# 一次性生成T个Dropout掩码
masks = generate_dropout_masks(shape=(T, ...))
# 向量化前向传播
predictions = vectorized_forward(x, masks)
```

### 8.2 缓存机制

#### 预测缓存
缓存相同输入和采样次数的预测结果。

#### 批量缓存
缓存批量预测结果，支持大规模数据的高效处理。

### 8.3 内存优化

支持float32精度存储，减少内存占用：

```python
x_batch = np.asarray(x, dtype=np.float32)
```

## 9. 使用示例

### 9.1 基本使用

```python
from deep_learning.models.uncertainty.mc_dropout import (
    MCDropoutRegressor,
    MCDropoutConfig
)

# 创建模型
config = MCDropoutConfig(
    in_dim=10,
    hidden_dim=32,
    dropout_rate=0.2,
    dropout_type="standard",
    seed=42
)
model = MCDropoutRegressor(config)

# 训练
result = model.fit(x_train, y_train, epochs=180, lr=8e-3)

# 预测
pred = model.predict(x_test, t=50, confidence=0.95)

# 获取结果
print(f"预测均值: {pred['mean']}")
print(f"总不确定性: {pred['variance']}")
print(f"偶然不确定性: {pred['aleatoric']}")
print(f"认知不确定性: {pred['epistemic']}")
```

### 9.2 自适应采样

```python
# 自动确定最优采样次数
adaptive_result = model.adaptive_t(
    x_test,
    max_t=100,
    tolerance=0.02,
    min_t=10
)
print(f"最优采样次数: {adaptive_result['best_t']}")
```

### 9.3 解释性分析

```python
# Dropout权重解释
weight_exp = model.explain_dropout_weights(top_k=8)
print("高重要性参数:", weight_exp['top_important_parameters'])

# 多次前向传播分析
forward_exp = model.analyze_multiple_forward_passes(x_test, t=80)
print("高不稳定样本:", forward_exp['top_unstable_samples'])

# 预测分布分析
dist_exp = model.analyze_prediction_distribution(x_test, t=80)
print("宽区间样本:", dist_exp['top_wide_interval_samples'])
```

## 10. 适用场景

### 10.1 优势场景

- **快速原型开发**：实现简单，无需修改网络架构
- **现有模型改进**：可轻松添加到已有Dropout网络
- **实时应用**：计算开销相对较小
- **中等数据集**：在数据量适中的情况下效果良好

### 10.2 注意事项

- **采样次数选择**：需要平衡精度和计算成本
- **Dropout率调节**：过高的Dropout率可能影响性能
- **训练稳定性**：需要仔细调节超参数
- **理论近似**：只是贝叶斯方法的近似，精度有限

## 11. 与其他模型对比

| 特性 | MC Dropout | BNN | Deep Ensemble | EDL |
|------|------------|-----|---------------|-----|
| 实现复杂度 | 低 | 高 | 中 | 低 |
| 计算复杂度 | 中 | 高 | 高 | 低 |
| 理论基础 | 近似贝叶斯 | 精确贝叶斯 | 频率学派 | 证据理论 |
| 训练次数 | 1次 | 1次 | N次 | 1次 |
| 推理速度 | 中 | 慢 | 慢 | 快 |
| 不确定性质量 | 中 | 高 | 高 | 高 |

## 12. 技术细节

### 12.1 数值稳定性

- 方差裁剪：logvar ∈ [-8, 5]，避免数值溢出
- 最小方差：σ² ≥ 1e-6，确保正定性
- 梯度裁剪：防止梯度爆炸

### 12.2 随机种子控制

```python
self.rng = np.random.default_rng(seed)
```

确保结果可复现。

### 12.3 线程安全

使用线程锁保护缓存操作：

```python
with self._predict_cache_lock:
    # 缓存操作
```

### 12.4 Dropout掩码生成

```python
def _make_mask(self, x):
    keep = 1.0 - self.rate
    if self.kind == "spatial":
        # 空间Dropout
        base = (rng.uniform(0, 1, size=(1, dim)) < keep) / keep
        return np.repeat(base, x.shape[0], axis=0)
    elif self.kind == "variational":
        # 变分Dropout
        if self._variational_mask is None:
            self._variational_mask = (rng.uniform(0, 1, size=x.shape) < keep) / keep
        return self._variational_mask
    else:
        # 标准Dropout
        return (rng.uniform(0, 1, size=x.shape) < keep) / keep
```

## 13. 最佳实践

### 13.1 超参数选择

#### Dropout率
- 推荐范围：0.1 - 0.5
- 过高：可能欠拟合
- 过低：正则化效果有限

#### 采样次数T
- 快速测试：T = 20-30
- 标准使用：T = 50-100
- 高精度需求：T ≥ 100

#### 隐藏层维度
- 简单任务：hidden_dim = 16-32
- 复杂任务：hidden_dim = 64-128

### 13.2 训练技巧

1. **逐步增加采样次数**：训练初期使用较少采样，后期增加
2. **监控损失曲线**：避免训练不收敛
3. **验证集评估**：定期在验证集上评估不确定性质量

### 13.3 部署建议

1. **缓存预测结果**：相同输入可重用预测结果
2. **批量处理**：利用批量预测提高效率
3. **自适应采样**：根据应用场景动态调整采样次数

## 14. 参考资料

- Gal, Y., & Ghahramani, Z. (2016). "Dropout as a Bayesian Approximation: Representing Model Uncertainty in Deep Learning"
- Srivastava, N., et al. (2014). "Dropout: A Simple Way to Prevent Neural Networks from Overfitting"
- Kendall, A., & Gal, Y. (2017). "What Uncertainties Do We Need in Bayesian Deep Learning?"

## 15. 文件位置

- 实现代码：`deep_learning/models/uncertainty/mc_dropout.py`
- 文档：`docs/deep_learning/MC_Dropout模型解释.md`