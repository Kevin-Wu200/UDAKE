# 时空克里金 API 文档

基础路径：`/api/spatiotemporal`

## 统一响应

成功：
```json
{"success": true, "data": {}, "message": "操作成功"}
```

失败：
```json
{
  "success": false,
  "error": {
    "code": "1001",
    "message": "模型不存在",
    "details": {},
    "timestamp": "2026-04-05T16:00:00+00:00",
    "request_id": "req_xxx"
  }
}
```

## 核心接口

- `POST /train` 训练模型
- `POST /predict` 模型预测
- `POST /auto-select` 自动模型选择
- `POST /update` 增量更新并生成新版本
- `GET /evaluate/{model_id}` 模型评估

## 辅助接口

- `GET /models` 模型列表（支持 `page/page_size/model_type/status`）
- `GET /models/{model_id}` 模型详情
- `DELETE /models/{model_id}` 模型删除

## 运维接口

- `POST /cache/warmup` 缓存预热
- `GET /performance/metrics` 性能指标

## Swagger

启动后端后访问：
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`
