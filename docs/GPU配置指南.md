# GPU配置指南

## 1. 配置项
- `enable_gpu`：全局 GPU 开关。
- `auto_switch`：启用后根据任务规模自动选择 CPU/GPU。
- `min_size_for_gpu`：任务规模阈值。

## 2. 推荐策略
- 小规模任务（低于阈值）走 CPU，减少传输开销。
- 大规模任务走 GPU，提升吞吐。

## 3. 故障处理
- GPU 不可用时系统自动回退 CPU。
- 可通过 `GET /api/gpu/status` 检查后端与设备状态。
