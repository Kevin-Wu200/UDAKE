# 空间特征工程指南

## 概述

空间特征工程是提升空间插值模型性能的关键环节。本指南详细介绍空间特征的类型、提取方法、优化策略以及在不同模型中的应用。

## 空间特征分类

### 1. 基础坐标特征

**原始坐标**：
```python
# 二维坐标
features = [
    "coord_x",  # x坐标
    "coord_y"   # y坐标
]

# 三维坐标（扩展）
features.extend([
    "coord_z"   # z坐标（高程、深度等）
])
```

**特征特点**：
- 最基础的空间位置信息
- 直接影响预测结果
- 需要标准化处理

### 2. 距离和方向特征

**距离特征**：
```python
# 计算到邻近点的距离
distances = compute_knn_distances(query_coords, sample_coords, k=8)

features = [
    "mean_neighbor_distance",    # 平均邻域距离
    "std_neighbor_distance",     # 邻域距离标准差
    "min_neighbor_distance",     # 最小邻域距离
    "max_neighbor_distance"      # 最大邻域距离
]
```

**方向特征**：
```python
# 计算邻近点相对于查询点的方向
directions = compute_neighbor_directions(query_coords, sample_coords, k=8)

features.extend([
    "direction_x",  # x方向平均分量
    "direction_y",  # y方向平均分量
    "direction_angle"  # 主方向角度
])
```

### 3. 统计特征

**邻域值统计**：
```python
# k近邻点的值统计
neighbor_values = get_knn_values(sample_coords, sample_values, query_coords, k=8)

features = [
    "local_mean",      # 局部均值
    "local_std",       # 局部标准差
    "local_min",       # 局部最小值
    "local_max",       # 局部最大值
    "local_median",    # 局部中位数
    "local_skewness",  # 局部偏度
    "local_kurtosis"   # 局部峰度
]
```

**归一化统计特征**：
```python
# 标准化的高阶统计量
z_scores = (neighbor_values - local_mean) / local_std

features.extend([
    "value_skewness",  # 值偏度
    "value_kurtosis",  # 值峰度
    "value_cv"         # 变异系数
])
```

### 4. 密度特征

**采样密度**：
```python
# 计算局部采样密度
density = k / (np.pi * max_distance ** 2)

features = [
    "local_density",           # 局部密度
    "global_density",          # 全局密度
    "density_ratio",           # 密度比率
    "inverse_density"          # 密度倒数
]
```

**空间分布特征**：
```python
# 使用Voronoi图分析
areas = compute_voronoi_areas(sample_coords)
features.extend([
    "voronoi_area_mean",       # Voronoi区域平均面积
    "voronoi_area_std",        # Voronoi区域面积标准差
    "area_cv"                  # 面积变异系数
])
```

### 5. 位置编码特征

**正弦位置编码**：
```python
def sinusoidal_position_encoding(coords, dim):
    """生成正弦位置编码"""
    encoding = np.zeros((len(coords), dim))
    for i in range(dim // 2):
        encoding[:, 2*i] = np.sin(coords[:, 0] / (10000 ** (2*i/dim)))
        encoding[:, 2*i+1] = np.cos(coords[:, 0] / (10000 ** (2*i/dim)))
    return encoding

features.extend([
    f"sin_pos_{i}" for i in range(dim)
])
```

**可学习位置编码**：
```python
class LearnablePositionEncoding:
    """可学习的位置编码"""
    def __init__(self, dim, seed=42):
        rng = np.random.default_rng(seed)
        self.weights = rng.normal(0, 0.02, size=(dim,))
    
    def encode(self, coords):
        return coords @ self.weights

features.extend([
    f"learn_pos_{i}" for i in range(dim)
])
```

### 6. 协方差特征

**局部协方差**：
```python
# 计算局部协方差特征
covariance_features = compute_local_covariance(
    query_coords, sample_coords, sample_values
)

features.extend([
    "local_mean",      # 局部均值
    "local_var",       # 局部方差
    "local_cov",       # 局部协方差
    "local_correlation" # 局部相关系数
])
```

### 7. 趋势特征

**空间趋势**：
```python
# 拟合空间趋势
trend_features = compute_spatial_trend(
    sample_coords, sample_values, query_coords
)

features.extend([
    "trend_bias",      # 趋势截距
    "trend_x",         # x方向趋势
    "trend_y",         # y方向趋势
    "trend_xy"         # 交互趋势
])
```

**曲率特征**：
```python
# 计算空间曲率
curvature = compute_spatial_curvature(sample_coords, sample_values)
features.extend([
    "mean_curvature",   # 平均曲率
    "gaussian_curvature", # 高斯曲率
    "principal_curvature_1", # 主曲率1
    "principal_curvature_2"  # 主曲率2
])
```

### 8. 图结构特征

**邻接矩阵特征**：
```python
# 基于图的拓扑特征
adjacency = build_adjacency_matrix(coords, strategy="knn")

features.extend([
    "node_degree",           # 节点度
    "clustering_coefficient", # 聚类系数
    "betweenness_centrality", # 介数中心性
    "closeness_centrality"   # 接近中心性
])
```

**边特征**：
```python
# 边权重特征
edge_features = compute_edge_features(adjacency, values)

features.extend([
    "edge_weight_mean",      # 边权重均值
    "edge_weight_std",       # 边权重标准差
    "edge_count",            # 边数量
    "edge_density"           # 边密度
])
```

### 9. 不确定性特征

**克里金方差**：
```python
# 基础克里金方差
prior_mean, prior_var = baseline_kriging.predict(query_coords)

features.extend([
    "prior_mean",        # 先验均值
    "prior_var",         # 先验方差
    "prior_std",         # 先验标准差
    "prior_cv"           # 先验变异系数
])
```

**不确定性度量**：
```python
# 多种不确定性度量
uncertainty_metrics = compute_uncertainty_metrics(
    predictions, sample_values
)

features.extend([
    "prediction_uncertainty",  # 预测不确定性
    "entropy",                 # 熵
    "confidence_score",        # 置信度
    "reliability_index"        # 可靠性指数
])
```

### 10. 注意力特征

**注意力权重**：
```python
# 注意力权重统计
attention_weights = model.get_attention_weights()

features.extend([
    "attn_weight_mean",   # 注意力权重均值
    "attn_weight_max",    # 注意力权重最大值
    "attn_weight_std",    # 注意力权重标准差
    "attn_weight_entropy" # 注意力权重熵
])
```

## 特征提取实现

### ResidualKrigingModel特征提取

```python
def extract_residual_kriging_features(
    sample_coords, 
    sample_values, 
    query_coords, 
    prior_mean, 
    k=8
):
    """ResidualKrigingModel的特征工程"""
    # 1. 构建空间索引
    index = SpatialIndex(sample_coords)
    
    # 2. 查询k近邻
    knn = index.query_knn(query_coords, k=k)
    ids = knn.indices
    local_dist = knn.distances
    local_vals = sample_values[ids]
    
    # 3. 计算距离特征
    mean_dist = np.mean(local_dist, axis=1)
    std_dist = np.std(local_dist, axis=1)
    
    # 4. 计算方向特征
    local_diff = sample_coords[ids] - query_coords[:, None, :]
    direction = np.mean(local_diff / (local_dist[:, :, None] + 1e-12), axis=1)
    
    # 5. 计算密度特征
    local_max_dist = np.maximum(np.max(local_dist, axis=1), 1e-6)
    density = k / (np.pi * (local_max_dist ** 2))
    
    # 6. 计算统计特征
    local_mean = np.mean(local_vals, axis=1, keepdims=True)
    centered = local_vals - local_mean
    local_std = np.std(local_vals, axis=1, keepdims=True) + 1e-12
    z = centered / local_std
    skew = np.mean(z ** 3, axis=1)
    kurt = np.mean(z ** 4, axis=1)
    
    # 7. 组合特征
    features = np.stack([
        mean_dist,
        std_dist,
        direction[:, 0],
        direction[:, 1],
        density,
        skew,
        kurt,
        prior_mean
    ], axis=1)
    
    feature_names = [
        "mean_neighbor_distance",
        "std_neighbor_distance",
        "direction_x",
        "direction_y",
        "local_density",
        "value_skewness",
        "value_kurtosis",
        "prior_mean"
    ]
    
    return features, feature_names
```

### AttentionKrigingModel特征提取

```python
def extract_attention_kriging_features(
    query_coords, 
    prior_mean, 
    prior_var, 
    rel_bias
):
    """AttentionKrigingModel的特征工程"""
    # 1. 位置编码
    sin_pos = sinusoidal_position_encoding(query_coords, dim=12)
    learn_pos = learnable_position_encoding(query_coords)
    
    # 2. 注意力权重统计
    rel = np.asarray(rel_bias, dtype=float)
    rel_norm = rel / (np.sum(rel, axis=1, keepdims=True) + 1e-12)
    rel_entropy = -np.sum(rel_norm * np.log(rel_norm + 1e-12), axis=1)
    
    # 3. 注意力统计特征
    rel_stats = np.stack([
        np.mean(rel, axis=1),
        np.max(rel, axis=1),
        np.std(rel, axis=1),
        rel_entropy
    ], axis=1)
    
    # 4. 先验特征
    prior_feat = np.stack([
        np.asarray(prior_mean, dtype=float),
        np.asarray(prior_var, dtype=float)
    ], axis=1)
    
    # 5. 组合特征
    features = np.concatenate([
        query_coords,
        sin_pos,
        learn_pos,
        prior_feat,
        rel_stats
    ], axis=1)
    
    feature_names = [
        "coord_x", "coord_y"
    ]
    feature_names.extend([f"sin_pos_{i}" for i in range(12)])
    feature_names.extend([f"learn_pos_{i}" for i in range(8)])
    feature_names.extend(["prior_mean", "prior_var"])
    feature_names.extend([
        "attn_weight_mean",
        "attn_weight_max",
        "attn_weight_std",
        "attn_weight_entropy"
    ])
    
    return features, feature_names
```

### GNNKrigingModel特征提取

```python
def extract_gnn_kriging_features(
    query_coords,
    sample_coords,
    sample_values,
    prior_mean,
    prior_var
):
    """GNNKrigingModel的特征工程"""
    # 1. 空间特征
    spatial = extract_spatial_features(query_coords)
    
    # 2. 协方差特征
    cov_feat = compute_local_covariance(
        query_coords, sample_coords, sample_values
    )
    
    # 3. 趋势特征
    trend = extract_trend_features(
        sample_coords, sample_values, query_coords
    )
    
    # 4. 位置编码
    sin_pos = sinusoidal_position_encoding(query_coords, dim=12)
    learn_pos = learnable_position_encoding(query_coords)
    
    # 5. 先验特征
    prior_feat = np.stack([
        np.asarray(prior_mean, dtype=float),
        np.asarray(prior_var, dtype=float)
    ], axis=1)
    
    # 6. 组合特征
    features = np.concatenate([
        spatial,
        cov_feat,
        trend,
        sin_pos,
        learn_pos,
        prior_feat
    ], axis=1)
    
    feature_names = [
        "coord_x", "coord_y",
        "radius", "angle",
        "local_mean", "local_var",
        "trend_bias", "trend_x"
    ]
    feature_names.extend([f"sin_pos_{i}" for i in range(12)])
    feature_names.extend([f"learn_pos_{i}" for i in range(8)])
    feature_names.extend(["prior_mean", "prior_var"])
    
    return features, feature_names
```

## 特征标准化和归一化

### 运行时标准化

```python
def runtime_standardization(features):
    """运行时标准化"""
    mean = features.mean(axis=0, keepdims=True)
    std = features.std(axis=0, keepdims=True) + 1e-6
    standardized = (features - mean) / std
    
    scaler = {
        "mean": mean.reshape(-1).tolist(),
        "std": std.reshape(-1).tolist(),
        "source": "runtime"
    }
    
    return standardized, scaler
```

### 预定义标准化

```python
def predefined_standardization(features, scaler):
    """使用预定义的标准化参数"""
    mean = np.array(scaler["mean"])
    std = np.array(scaler["std"])
    standardized = (features - mean) / std
    return standardized
```

### Min-Max归一化

```python
def minmax_normalization(features):
    """Min-Max归一化到[0,1]"""
    min_val = features.min(axis=0, keepdims=True)
    max_val = features.max(axis=0, keepdims=True)
    normalized = (features - min_val) / (max_val - min_val + 1e-6)
    
    scaler = {
        "min": min_val.reshape(-1).tolist(),
        "max": max_val.reshape(-1).tolist(),
        "source": "minmax"
    }
    
    return normalized, scaler
```

### Robust标准化

```python
def robust_standardization(features):
    """Robust标准化（使用中位数和IQR）"""
    median = np.median(features, axis=0, keepdims=True)
    q75 = np.percentile(features, 75, axis=0, keepdims=True)
    q25 = np.percentile(features, 25, axis=0, keepdims=True)
    iqr = q75 - q25 + 1e-6
    standardized = (features - median) / iqr
    
    scaler = {
        "median": median.reshape(-1).tolist(),
        "iqr": iqr.reshape(-1).tolist(),
        "source": "robust"
    }
    
    return standardized, scaler
```

## 特征选择方法

### 方差阈值

```python
def variance_threshold_selection(features, threshold=0.01):
    """基于方差阈值的特征选择"""
    variances = np.var(features, axis=0)
    selected_indices = np.where(variances > threshold)[0]
    return selected_indices
```

### 相关系数筛选

```python
def correlation_selection(features, target, threshold=0.1):
    """基于相关系数的特征选择"""
    correlations = np.corrcoef(features.T, target)[-1, :-1]
    selected_indices = np.where(np.abs(correlations) > threshold)[0]
    return selected_indices
```

### 互信息筛选

```python
from sklearn.feature_selection import mutual_info_regression

def mutual_info_selection(features, target, k=10):
    """基于互信息的特征选择"""
    mi_scores = mutual_info_regression(features, target)
    selected_indices = np.argsort(mi_scores)[-k:]
    return selected_indices
```

### 递归特征消除

```python
from sklearn.feature_selection import RFE
from sklearn.linear_model import Ridge

def rfe_selection(features, target, n_features_to_select=15):
    """递归特征消除"""
    estimator = Ridge()
    selector = RFE(estimator, n_features_to_select=n_features_to_select)
    selector.fit(features, target)
    return np.where(selector.support_)[0]
```

## 特征降维

### PCA降维

```python
from sklearn.decomposition import PCA

def pca_reduction(features, n_components=10):
    """PCA降维"""
    pca = PCA(n_components=n_components)
    reduced_features = pca.fit_transform(features)
    
    return reduced_features, {
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "cumulative_variance": np.cumsum(pca.explained_variance_ratio_).tolist()
    }
```

### t-SNE可视化

```python
from sklearn.manifold import TSNE

def tsne_visualization(features, n_components=2):
    """t-SNE降维用于可视化"""
    tsne = TSNE(n_components=n_components, random_state=42)
    reduced = tsne.fit_transform(features)
    return reduced
```

### UMAP降维

```python
import umap

def umap_reduction(features, n_components=10):
    """UMAP降维"""
    reducer = umap.UMAP(n_components=n_components, random_state=42)
    reduced_features = reducer.fit_transform(features)
    return reduced_features
```

## 特征工程最佳实践

### 1. 特征工程流程

```python
def feature_engineering_pipeline(
    sample_coords,
    sample_values,
    query_coords,
    model_type="residual"
):
    """完整的特征工程流程"""
    
    # 1. 数据验证
    validate_inputs(sample_coords, sample_values, query_coords)
    
    # 2. 基础克里金预测
    baseline = UniversalKrigingBaseline()
    baseline.fit(sample_coords, sample_values)
    prior_mean, prior_var = baseline.predict(query_coords)
    
    # 3. 模型特定特征提取
    if model_type == "residual":
        features, feature_names = extract_residual_kriging_features(
            sample_coords, sample_values, query_coords, prior_mean
        )
    elif model_type == "attention":
        rel_bias = compute_attention_bias(query_coords, sample_coords)
        features, feature_names = extract_attention_kriging_features(
            query_coords, prior_mean, prior_var, rel_bias
        )
    elif model_type == "gnn":
        features, feature_names = extract_gnn_kriging_features(
            query_coords, sample_coords, sample_values, prior_mean, prior_var
        )
    
    # 4. 特征标准化
    processed_features, scaler = runtime_standardization(features)
    
    # 5. 特征选择（可选）
    selected_indices = variance_threshold_selection(processed_features, threshold=0.01)
    processed_features = processed_features[:, selected_indices]
    feature_names = [feature_names[i] for i in selected_indices]
    
    # 6. 特征降维（可选）
    # reduced_features, pca_info = pca_reduction(processed_features, n_components=10)
    
    return {
        "feature_matrix": features,
        "processed_features": processed_features,
        "feature_names": feature_names,
        "scaler": scaler,
        "prior_mean": prior_mean,
        "prior_var": prior_var
    }
```

### 2. 特征重要性分析

```python
def analyze_feature_importance(model, feature_names):
    """分析特征重要性"""
    # 对于ResidualKrigingModel
    if hasattr(model, 'mlp_w1'):
        # 基于权重的特征重要性
        importance = np.mean(np.abs(model.mlp_w1), axis=1)
    
    # 对于AttentionKrigingModel
    elif hasattr(model, 'attention_weights'):
        # 基于注意力权重
        importance = np.mean(model.attention_weights, axis=0)
    
    # 对于GNNKrigingModel
    elif hasattr(model, 'attention'):
        # 基于多头注意力
        importance = np.mean(model.attention.attention_weights, axis=0)
    
    # 排序特征
    sorted_indices = np.argsort(importance)[::-1]
    
    return {
        "feature_names": [feature_names[i] for i in sorted_indices],
        "importance": importance[sorted_indices].tolist()
    }
```

### 3. 特征相关性分析

```python
def feature_correlation_analysis(features, feature_names):
    """特征相关性分析"""
    correlation_matrix = np.corrcoef(features.T)
    
    # 找出高相关特征对
    high_corr_pairs = []
    for i in range(len(feature_names)):
        for j in range(i+1, len(feature_names)):
            if abs(correlation_matrix[i, j]) > 0.8:
                high_corr_pairs.append((
                    feature_names[i],
                    feature_names[j],
                    correlation_matrix[i, j]
                ))
    
    return {
        "correlation_matrix": correlation_matrix.tolist(),
        "high_correlation_pairs": high_corr_pairs
    }
```

### 4. 特征工程优化

```python
def optimize_feature_engineering(
    sample_coords,
    sample_values,
    query_coords,
    model_class,
    n_trials=50
):
    """优化特征工程参数"""
    import optuna
    
    def objective(trial):
        # 超参数搜索空间
        k_neighbors = trial.suggest_int('k_neighbors', 4, 16)
        feature_scale = trial.suggest_categorical('feature_scale', ['runtime', 'robust'])
        use_position_encoding = trial.suggest_categorical('use_position_encoding', [True, False])
        
        # 构建模型
        model = model_class()
        
        # 特征工程
        features, _ = extract_residual_kriging_features(
            sample_coords, sample_values, query_coords,
            prior_mean, k=k_neighbors
        )
        
        # 标准化
        if feature_scale == 'runtime':
            processed, _ = runtime_standardization(features)
        else:
            processed, _ = robust_standardization(features)
        
        # 评估
        predictions = model.predict(processed)
        score = compute_rmse(predictions, ground_truth)
        
        return score
    
    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=n_trials)
    
    return study.best_params
```

## 特征工程案例分析

### 案例1：环境监测数据

**数据特点**：
- 传感器网络数据
- 空间分布不均匀
- 存在异常值

**特征工程策略**：
```python
# 1. 密度加权特征
density_weights = compute_density_weights(sample_coords)
weighted_features = features * density_weights

# 2. 异常值处理
robust_features, robust_scaler = robust_standardization(features)

# 3. 传感器网络特征
network_features = extract_network_features(
    sample_coords, connectivity_matrix
)
```

### 案例2：气象数据

**数据特点**：
- 大尺度空间变化
- 长距离相关性
- 时间维度

**特征工程策略**：
```python
# 1. 大尺度趋势特征
trend_features = compute_large_scale_trend(
    sample_coords, sample_values, scale=100
)

# 2. 位置编码增强
enhanced_pos_encoding = enhanced_position_encoding(
    query_coords, sample_coords, dim=24
)

# 3. 气象场特征
field_features = compute_field_features(
    sample_coords, sample_values, kernel_size=5
)
```

### 案例3：地质数据

**数据特点**：
- 钻孔数据稀疏
- 空间异质性强
- 多变量相关

**特征工程策略**：
```python
# 1. 图结构特征
graph_features = extract_geological_graph_features(
    sample_coords, stratigraphy_info
)

# 2. 方向性特征
directional_features = compute_directional_features(
    sample_coords, sample_values, n_directions=8
)

# 3. 多变量协方差
covariance_features = compute_multivariate_covariance(
    sample_coords, sample_values, auxiliary_variables
)
```

## 特征工程验证

### 交叉验证

```python
def feature_engineering_cross_validation(
    sample_coords,
    sample_values,
    n_splits=5
):
    """特征工程的交叉验证"""
    from sklearn.model_selection import KFold
    
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    scores = []
    
    for train_idx, val_idx in kf.split(sample_coords):
        train_coords = sample_coords[train_idx]
        train_values = sample_values[train_idx]
        val_coords = sample_coords[val_idx]
        val_values = sample_values[val_idx]
        
        # 特征工程
        train_features = feature_engineering_pipeline(
            train_coords, train_values, train_coords
        )
        val_features = feature_engineering_pipeline(
            train_coords, train_values, val_coords
        )
        
        # 模型训练和评估
        model = ResidualKrigingModel()
        model.fit(train_features)
        predictions = model.predict(val_features)
        
        score = compute_rmse(predictions, val_values)
        scores.append(score)
    
    return {
        "mean_score": np.mean(scores),
        "std_score": np.std(scores),
        "scores": scores
    }
```

### 特征工程诊断

```python
def diagnose_feature_engineering(features, feature_names):
    """诊断特征工程质量"""
    diagnostics = {}
    
    # 1. 检查缺失值
    diagnostics['missing_values'] = np.isnan(features).sum()
    
    # 2. 检查无穷值
    diagnostics['infinite_values'] = np.isinf(features).sum()
    
    # 3. 检查零方差特征
    variances = np.var(features, axis=0)
    diagnostics['zero_variance_features'] = [
        feature_names[i] for i, v in enumerate(variances) if v < 1e-10
    ]
    
    # 4. 检查高相关特征
    corr_matrix = np.corrcoef(features.T)
    high_corr = []
    for i in range(len(feature_names)):
        for j in range(i+1, len(feature_names)):
            if abs(corr_matrix[i, j]) > 0.95:
                high_corr.append((feature_names[i], feature_names[j]))
    diagnostics['high_correlation_pairs'] = high_corr
    
    # 5. 检查异常值
    z_scores = np.abs((features - features.mean(axis=0)) / features.std(axis=0))
    outliers = (z_scores > 3).sum(axis=0)
    diagnostics['outliers_per_feature'] = {
        feature_names[i]: outliers[i] for i in range(len(feature_names))
    }
    
    return diagnostics
```

## 总结

空间特征工程是提升空间插值模型性能的关键技术：

1. **特征多样性**：使用多种类型的空间特征
2. **特征质量**：确保特征的可靠性和稳定性
3. **特征选择**：选择最具预测能力的特征
4. **特征优化**：持续优化特征工程流程
5. **模型适配**：为不同模型设计专属特征

通过系统的特征工程，可以显著提升插值精度、计算效率和模型可解释性。