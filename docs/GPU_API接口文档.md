# GPU API接口文档

## 基础接口
- `GET /api/gpu/health`
- `GET /api/gpu/status`
- `GET /api/gpu/devices`
- `PUT /api/gpu/config`
- `GET /api/gpu/metrics`
- `DELETE /api/gpu/metrics`
- `GET /api/gpu/tasks`
- `GET /api/gpu/tasks/{task_id}`

## 矩阵计算接口
- `POST /api/gpu/compute/matrix/multiply`
- `POST /api/gpu/compute/matrix/inverse`
- `POST /api/gpu/compute/matrix/eigenvalues`
- `POST /api/gpu/compute/matrix/cholesky`
- `POST /api/gpu/compute/matrix/lu`
- `POST /api/gpu/compute/linear/solve`

## 向量计算接口
- `POST /api/gpu/compute/vector/dot`
- `POST /api/gpu/compute/vector/norm`
- `POST /api/gpu/compute/vector/sort`

## 克里金接口
- `POST /api/gpu/kriging/semivariogram`
- `POST /api/gpu/kriging/predict`

## 错误码约定
- `400`：参数不合法。
- `404`：任务不存在。
- `500`：内部计算或系统异常。
