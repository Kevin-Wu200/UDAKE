# GPU快速入门指南

## 1. 启动后端
在项目根目录启动 FastAPI 服务。

## 2. 健康检查
- `GET /api/gpu/health`

## 3. 配置策略
- `PUT /api/gpu/config`
  - `enable_gpu`: 是否启用 GPU
  - `auto_switch`: 是否按规模自动切换
  - `min_size_for_gpu`: 触发 GPU 的规模阈值

## 4. 示例调用
- 矩阵乘法：`POST /api/gpu/compute/matrix/multiply`
- 向量范数：`POST /api/gpu/compute/vector/norm`
- 变异函数：`POST /api/gpu/kriging/semivariogram`

## 5. 指标查看
- `GET /api/gpu/metrics`
- `GET /api/gpu/tasks`
