# 可解释性面板 API 对接与故障排查

## 1. 前端依赖接口
- `createSpatiotemporalExplainTask(payload)`
- `getSpatiotemporalExplainTask(taskId)`
- `cancelSpatiotemporalExplainTask(taskId)`
- `deleteSpatiotemporalExplainTask(taskId)`
- `getSpatiotemporalExplainMonitor()`
- `verifySpatiotemporalExplainBackend()`

## 2. 关键请求参数
- `model_type`：模型类型
- `coords`：坐标数组，至少 2 个点
- `series`：三维序列，节点数需与 `coords` 一致
- `pred_horizon`：1~48
- `top_k`：1~20
- `batch_size`：16~4096
- `priority`：0~9
- `max_retries`：0~3

## 3. 常见问题
- 提交失败（`不是合法 JSON`）：检查 `coords/series` 输入。
- 提交失败（`series 与 coords 节点数量必须一致`）：检查维度。
- 无法校验后端：确认消息队列/Redis 后端可达。
- 结果不可用：任务状态不是 `completed` 或结果字段为空。

## 4. 性能建议
- 大量任务时优先使用列表滚动增量渲染。
- 高频调整 SHAP 参数时依赖内置防抖更新，避免连续重绘。
- 建议开启自动刷新并保留合理轮询间隔（默认 4 秒）。
