# 时空预测 SHAP 集成指南

## 1. 功能概览

- 解释入口：`POST /api/dl/spatiotemporal/explain`，`method=shap` 或 `method=hybrid`
- 核心模块：`services/backend/app/dl_services/shap_explainer.py`
- 输出内容：
  - SHAP 全局特征重要性（按原始时序特征聚合）
  - 单/批量局部解释
  - 可视化数据（瀑布图、蜂群图、依赖图、摘要统计）
  - 可选交互值（`compute_interactions=True`）

## 2. 解释器策略

- 当前默认策略：`KernelExplainer`（通过代理模型预测函数兼容各类时空模型）
- 当环境无 `shap` 包时自动降级为线性代理分解，确保接口可用
- 特征工程完全复用 LIME 模块，保证 `lime/shap/hybrid` 结果可对齐

## 3. 参数说明

- `top_k`：每个样本返回前 `k` 个贡献特征
- `max_retries`：任务失败后的最大重试次数（`0-3`）
- `batch_size`：基础预测批处理大小

SHAP 参数由解释器自动配置：
- `background_size`：背景数据集大小（默认 64）
- `nsamples`：Kernel SHAP 采样数（默认 120）
- `max_explain_nodes`：参与解释的关键节点上限（默认 8）

## 4. 结果结构

- `summary.top_features`：全局重要特征（可直接用于前端列表）
- `shap.batch_explanations`：批量局部解释，包含：
  - `node_index`
  - `confidence`
  - `expected_value`
  - `top_contributions`
- `shap.visualization`：
  - `waterfall_list`
  - `beeswarm_data`
  - `dependence_data`
  - `feature_ranking`
  - `summary_stats`

## 5. 性能设计

- 背景数据集抽样：按目标值分布均匀选点
- 解释结果缓存：相同输入直接命中缓存
- 批量解释：支持多节点一次性解释并聚合
- GPU 标识：在可用时透传 `gpu_enabled` 状态

## 6. 异步任务集成

- 任务创建：沿用 `/spatiotemporal/explain`
- 状态流转：`queued -> running -> completed/failed/retrying/cancelled`
- 取消任务：`POST /api/dl/spatiotemporal/explain/{task_id}/cancel`
- 失败重试：由 `max_retries` 控制
