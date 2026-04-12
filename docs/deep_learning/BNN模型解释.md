# 贝叶斯神经网络（BNN）模型解释

## 1. 概述

贝叶斯神经网络（Bayesian Neural Network，简称BNN）是一种将贝叶斯概率理论与神经网络相结合的不确定性量化模型。与传统的确定性神经网络不同，BNN通过为网络参数赋予概率分布来表征模型的不确定性，能够同时量化认知不确定性（epistemic uncertainty）和偶然不确定性（aleatoric uncertainty）。

## 2. 核心原理

### 2.1 贝叶斯推断

传统神经网络学习固定的参数值，而BNN学习参数的后验分布。给定训练数据D，后验分布通过贝叶斯定理计算：

```
p(θ|D) = p(D|θ) * p(θ) / p(D)
```

其中：
- θ：网络参数
- p(θ)：先验分布
- p(D|θ)：似然函数
- p(D)：证据（归一化常数）

### 2.2 变分推断

由于后验分布难以精确计算，BNN采用变分推断方法，通过优化变分分布q(θ|φ)来近似真实后验：

```
min KL(q(θ|φ) || p(θ|D))
```

等价于最大化证据下界（ELBO）：
```
ELBO = E_q[log p(D|θ)] - KL(q(θ|φ) || p(θ))
```

### 2.3 重参数化技巧

通过重参数化技巧实现梯度的反向传播：
```
θ = μ + σ ⊙ ε
```

其中ε服从标准正态分布N(0, I)。

## 3. 模型架构

### 3.1 网络结构

本实现的BNN采用两层全连接架构：

```
输入层 → 隐藏层（贝叶斯全连接） → 输出层（均值和方差分支）
```

- 隐藏层：贝叶斯全连接层 + Tanh激活函数
- 输出层：两个独立分支
  - 均值分支：预测输出均值
  - 方差分支：预测对数方差（确保方差为正）

### 3.2 贝叶斯层实现

#### BayesianParameter类
每个网络参数由均值μ和标准差σ参数化：

```python
class BayesianParameter:
    mu: np.ndarray      # 均值参数
    rho: np.ndarray     # 标准差参数（通过softplus转换）
```

标准差通过softplus函数计算：
```
σ = softplus(ρ) + ε
```

#### BayesianDenseLayer类
贝叶斯全连接层实现权重和偏置的概率分布：

- 权重：Weight ~ N(μ_w, σ_w²)
- 偏置：Bias ~ N(μ_b, σ_b²)

### 3.3 先验分布

支持两种先验分布：

#### GaussianPrior
```
N(0, σ²)
```

#### GaussianMixturePrior
混合高斯先验，适用于复杂参数分布：
```
π₁ * N(0, σ₁²) + π₂ * N(0, σ₂²)
```

## 4. 训练过程

### 4.1 损失函数

使用ELBO损失函数：

```
L = NLL + λ * KL
```

- NLL（负对数似然）：衡量预测分布与真实值的拟合程度
- KL散度：衡量后验分布与先验分布的差异
- λ：KL权重（支持退火策略）

### 4.2 梯度更新

通过反向传播计算梯度：

1. 前向传播：采样参数并计算预测
2. 计算NLL梯度：∂L_NLL/∂μ, ∂L_NLL/∂ρ
3. 计算KL梯度：∂L_KL/∂μ, ∂L_KL/∂ρ
4. 参数更新：
   - μ更新：μ ← μ - lr * (∂L_NLL/∂μ + λ * ∂L_KL/∂μ)
   - ρ更新：ρ ← ρ - lr * λ * ∂L_KL/∂ρ

### 4.3 KL退火

在训练初期逐渐增加KL权重，避免模型过早收敛到先验：

```
λ(t) = min(1, t / T_anneal)
```

其中T_anneal为退火周期。

## 5. 预测过程

### 5.1 采样预测

通过蒙特卡洛采样获得预测分布：

```
对于t = 1, 2, ..., T:
    采样网络参数 θ^(t) ~ q(θ|φ)
    计算预测 μ^(t), σ²^(t)
```

最终预测统计量：
- 均值：E[y] = (1/T) * Σ μ^(t)
- 方差：Var[y] = E[σ²] + Var[μ]

### 5.2 不确定性分解

总不确定性分解为：

#### 偶然不确定性（Aleatoric）
源于数据本身噪声，无法通过更多数据消除：
```
σ_aleatoric² = E[σ²]
```

#### 认知不确定性（Epistemic）
源于模型参数不确定性，可通过更多数据减少：
```
σ_epistemic² = Var[μ]
```

#### 总不确定性
```
σ_total² = σ_aleatoric² + σ_epistemic²
```

## 6. 关键特性

### 6.1 温度缩放

支持温度参数调节预测分布的分散程度：

```
σ'² = T * σ²
```

其中T为温度参数，T > 1增加不确定性，T < 1减少不确定性。

### 6.2 批量预测

支持大规模数据的批量处理：

- 自动分批处理
- 内存优化选项
- 结果缓存机制

### 6.3 数据预处理

内置标准化预处理：

```
x_scaled = (x - μ_x) / σ_x
```

支持使用训练时统计量或当前批次统计量。

## 7. 可解释性分析

### 7.1 贝叶斯权重解释

通过`explain_bayesian_weights()`方法分析参数后验分布：

- 后验均值：参数的中心估计
- 后验标准差：参数的不确定性
- 信噪比：|μ|/σ，衡量参数的确定性程度

#### 高不确定性参数
标准差最大的参数，表明模型对这些参数不够确定。

#### 高确定性参数
信噪比最高的参数，表明模型对这些参数有强置信。

### 7.2 后验分布分析

通过`analyze_posterior_distributions()`方法分析后验分布的统计特性：

- 分位数：Q10, Q25, Q50, Q75, Q90
- 标准差分布：衡量参数不确定性的分布
- 低信噪比比例：σ > |μ|的参数比例

### 7.3 认知不确定性分析

通过`analyze_epistemic_uncertainty()`方法分析认知不确定性：

- 高认知不确定性样本：模型预测方差大的样本
- 认知不确定性比例：σ_epistemic / σ_total
- 与总不确定性的相关性

## 8. 性能优化

### 8.1 向量化采样

使用向量化操作加速蒙特卡洛采样：

```python
# 一次性生成T个参数样本
weights = μ + σ * ε,  ε ~ N(0, I)
```

### 8.2 缓存机制

#### 预测缓存
缓存相同输入的预测结果，避免重复计算。

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
from deep_learning.models.uncertainty.bnn import (
    BayesianNeuralRegressor,
    GaussianPrior
)

# 创建模型
model = BayesianNeuralRegressor(
    in_dim=10,
    hidden_dim=32,
    prior=GaussianPrior(sigma=1.0),
    seed=42
)

# 训练
result = model.fit(x_train, y_train, epochs=220, lr=8e-3)

# 预测
pred = model.predict(x_test, num_samples=80, confidence=0.95)

# 获取结果
print(f"预测均值: {pred['mean']}")
print(f"总不确定性: {pred['variance']}")
print(f"偶然不确定性: {pred['aleatoric']}")
print(f"认知不确定性: {pred['epistemic']}")
```

### 9.2 解释性分析

```python
# 贝叶斯权重解释
weight_exp = model.explain_bayesian_weights(top_k=8)
print("高不确定性参数:", weight_exp['top_uncertain_parameters'])

# 后验分布分析
posterior_exp = model.analyze_posterior_distributions()
print("全局参数统计:", posterior_exp['summary'])

# 认知不确定性分析
epistemic_exp = model.analyze_epistemic_uncertainty(x_test)
print("高认知不确定性样本:", epistemic_exp['top_epistemic_samples'])
```

## 10. 适用场景

### 10.1 优势场景

- **数据稀缺场景**：小样本学习，通过先验知识提供正则化
- **高风险决策**：需要量化不确定性的场景（医疗、金融）
- **异常检测**：高认知不确定性可能表示异常样本
- **主动学习**：根据认知不确定性选择最有价值的样本

### 10.2 注意事项

- **计算开销**：比确定性网络计算成本高（需多次采样）
- **训练难度**：需要调节KL权重和超参数
- **过拟合风险**：小数据集上可能过拟合到先验

## 11. 与其他模型对比

| 特性 | BNN | MC Dropout | Deep Ensemble | EDL |
|------|-----|------------|---------------|-----|
| 理论基础 | 贝叶斯推断 | 近似贝叶斯 | 频率学派 | 证据理论 |
| 不确定性类型 | 认知+偶然 | 认知+偶然 | 认知+偶然 | 数据+知识 |
| 计算复杂度 | 高 | 中 | 高 | 低 |
| 训练次数 | 1次 | 1次 | N次 | 1次 |
| 内存占用 | 中 | 低 | 高 | 低 |

## 12. 技术细节

### 12.1 数值稳定性

- 方差裁剪：logvar ∈ [-8, 5]，避免数值溢出
- 最小方差：σ² ≥ 1e-6，确保正定性
- KL正则化：限制权重范围，防止过拟合

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

## 13. 参考资料

- Blundell, C., et al. (2015). "Weight Uncertainty in Neural Networks"
- Gal, Y., & Ghahramani, Z. (2016). "Dropout as a Bayesian Approximation"
- Kendall, A., & Gal, Y. (2017). "What Uncertainties Do We Need in Bayesian Deep Learning?"

## 14. 文件位置

- 实现代码：`deep_learning/models/uncertainty/bnn.py`
- 文档：`docs/deep_learning/BNN模型解释.md`