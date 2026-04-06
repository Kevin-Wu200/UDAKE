# 深度学习 API 文档

## 基础路径

`/api/dl`

## 接口

1. `GET /health`
- 功能：检查深度学习服务状态和设备能力。
- 返回：`status/device/cuda_available/mps_available/registered_models`

2. `POST /train-demo`
- 功能：使用示例模型验证训练链路。
- 请求：
```json
{
  "samples": [[0.2, 0.3, 1.0], [0.1, 0.7, 0.9]]
}
```
- 返回：训练摘要和告警信息。

3. `POST /predict`
- 功能：执行批处理预测。
- 请求：
```json
{
  "samples": [[1.0, 2.0], [3.0, 4.0]],
  "bias": 0.5
}
```
- 返回：`predictions` 与系统资源快照。

4. `POST /spatial/train`
- 功能：训练阶段2空间插值模型。
- 请求：
```json
{
  "model_type": "gnn",
  "samples": [[0.1, 0.2, 1.0], [0.4, 0.6, 0.7]],
  "epochs": 30
}
```
- 参数说明：
  - `model_type`: `gnn | attention | residual`
  - `samples`: `[[x, y, value], ...]`

5. `POST /spatial/predict`
- 功能：执行空间插值预测，并与增量克里金进行可选融合。
- 请求：
```json
{
  "model_type": "attention",
  "samples": [[0.1, 0.2, 1.0], [0.4, 0.6, 0.7]],
  "queries": [[0.2, 0.3], [0.5, 0.5]],
  "blend_ratio": 0.6
}
```
- 返回：
  - `prediction`: 预测值
  - `variance`: 不确定性
  - `source`: `neural_only` 或 `neural+incremental_kriging`

6. `POST /spatiotemporal/explain`
- 功能：创建时空预测可解释性任务（支持 `lime/shap/hybrid`）。
- 请求：
```json
{
  "model_type": "st_transformer",
  "coords": [[120.1, 30.2], [120.2, 30.3]],
  "series": [[[1.0], [1.1], [1.2], [1.3]], [[0.9], [1.0], [1.1], [1.2]]],
  "pred_horizon": 2,
  "method": "lime",
  "top_k": 3,
  "max_retries": 1
}
```

7. `GET /spatiotemporal/explain/{task_id}`
- 功能：查询解释任务状态与结果。
- 状态：`queued/running/retrying/completed/failed/cancelled`

8. `POST /spatiotemporal/explain/{task_id}/cancel`
- 功能：取消解释任务。

9. `DELETE /spatiotemporal/explain/{task_id}`
- 功能：删除任务状态与结果缓存。

## 阶段11：用户验证与模型自评估 API

基础路径：`/api`

- `POST /evaluation/realtime`：实时评估
- `GET /evaluation/performance`：性能指标
- `GET /evaluation/errors`：误差分析
- `GET /evaluation/uncertainty`：不确定性评估
- `POST /model-selection/select`：选择最佳模型
- `GET /model-selection/status`：模型状态
- `POST /model-selection/switch`：模型切换
- `POST /model-selection/rollback`：模型回滚
- `POST /optimization/trigger`：触发优化
- `GET /optimization/status`：优化状态
- `POST /optimization/cancel`：取消优化
- `GET /reports/performance`：性能报告
- `GET /reports/evaluation`：评估报告
- `GET /reports/optimization`：优化报告
- `POST /reports/generate`：生成报告
