# 时空预测 LIME 集成指南

## 1. 功能概览

- 解释入口：`POST /api/dl/spatiotemporal/explain`，`method=lime` 或 `method=hybrid`
- 核心模块：`services/backend/app/dl_services/lime_explainer.py`
- 输出内容：
  - 特征重要性列表（按原始时序特征聚合）
  - 单/批量局部解释
  - 可视化数据（局部贡献、全局特征、摘要文本）
  - 解释置信度与局部拟合度

## 2. 参数说明

- `top_k`：每个样本返回前 `k` 个贡献特征
- `max_retries`：任务失败后的最大重试次数（`0-3`）
- `batch_size`：基础预测批处理大小

LIME 参数由解释器自动配置：
- `num_samples`：根据特征维度和节点数动态调整
- `num_features`：由请求的 `top_k` 与解释器配置共同约束

## 3. 结果结构

- `summary.top_features`：全局重要特征（可直接用于前端列表）
- `lime.batch_explanations`：批量局部解释，包含：
  - `node_index`
  - `confidence`
  - `fidelity`
  - `top_contributions`
- `lime.visualization`：
  - `feature_importance_list`
  - `local_explanations`
  - `feature_contributions`
  - `summary_text`

## 4. 性能设计

- 背景样本上下文缓存：复用标准化与代理模型
- 解释结果缓存：相同输入直接命中缓存
- 并行解释：多节点解释使用线程池并发
- 采样策略：按数据规模动态调整 `num_samples`

## 5. 异步任务集成

- 任务创建：沿用 `/spatiotemporal/explain`
- 状态流转：`queued -> running -> completed/failed/retrying/cancelled`
- 取消任务：`POST /api/dl/spatiotemporal/explain/{task_id}/cancel`
- 失败重试：由 `max_retries` 控制
