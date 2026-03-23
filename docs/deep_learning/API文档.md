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
