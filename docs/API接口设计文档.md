# API接口设计文档

## 基础信息

- 基础URL: `http://localhost:8000/api`
- 数据格式: JSON
- 字符编码: UTF-8

## 接口列表

### 1. 数据上传

**接口**: `POST /upload-data`

**描述**: 上传空间采样点数据

**请求**:
- Content-Type: multipart/form-data
- Body: file (GeoJSON文件)

**响应**:
```json
{
  "data_id": "uuid",
  "point_count": 100,
  "bounds": {
    "min_x": 116.0,
    "min_y": 39.0,
    "max_x": 117.0,
    "max_y": 40.0
  },
  "message": "数据上传成功"
}
```

### 2. 启动克里金任务

**接口**: `POST /start-kriging`

**描述**: 启动克里金插值任务

**请求**:
```json
{
  "data_id": "uuid",
  "method": "ordinary",
  "variogram_model": "spherical",
  "grid_resolution": 100,
  "nlags": 6,
  "enable_cross_validation": true,
  "n_folds": 5
}
```

**响应**:
```json
{
  "task_id": "uuid",
  "status": "pending",
  "message": "克里金任务已启动"
}
```

### 3. 查询任务状态

**接口**: `GET /task-status/{task_id}`

**描述**: 查询任务执行状态

**响应**:
```json
{
  "task_id": "uuid",
  "status": "running",
  "progress": 45.5,
  "message": "正在执行插值",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:01:00",
  "error": null
}
```

### 4. 获取预测结果

**接口**: `GET /result/prediction/{task_id}`

**描述**: 获取预测栅格结果

**响应**:
```json
{
  "task_id": "uuid",
  "geotiff_url": "/results/uuid_prediction.tif",
  "statistics": {
    "mean": 25.5,
    "std": 5.2,
    "min": 10.0,
    "max": 40.0
  }
}
```

### 5. 获取方差结果

**接口**: `GET /result/variance/{task_id}`

**描述**: 获取方差栅格结果

**响应**:
```json
{
  "task_id": "uuid",
  "geotiff_url": "/results/uuid_variance.tif",
  "statistics": {
    "mean": 2.5,
    "std": 1.2,
    "min": 0.5,
    "max": 8.0
  }
}
```

### 6. 生成分析报告

**接口**: `GET /result/report/{task_id}`

**描述**: 生成克里金分析报告

**响应**:
```json
{
  "task_id": "uuid",
  "method": "ordinary",
  "variogram_model": "spherical",
  "point_count": 100,
  "grid_resolution": 100,
  "cross_validation": {
    "rmse": 2.5,
    "mae": 1.8,
    "r2": 0.85,
    "mse": 6.25
  },
  "prediction_stats": {...},
  "variance_stats": {...},
  "execution_time": 15.5,
  "generated_at": "2024-01-01T00:02:00"
}
```

## 错误码

- 400: 请求参数错误
- 404: 资源不存在
- 500: 服务器内部错误

## 状态码说明

- pending: 任务待执行
- running: 任务执行中
- completed: 任务完成
- failed: 任务失败
