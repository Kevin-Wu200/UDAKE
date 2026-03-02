# 克里金插值后端 - 完整实现文档

## 项目概述

基于 FastAPI 的高性能空间插值与不确定性分析后端服务，实现了完整的克里金插值算法流程，包括自动模型选择、交叉验证、趋势检测等高级功能。

## 核心特性

### 1. 智能模型选择
- **多变异函数拟合**: 自动测试球状、指数、高斯、线性四种模型
- **交叉验证评分**: 5折交叉验证，选择RMSE最小的模型
- **趋势检测**: 自动检测空间趋势，决定使用普通克里金或泛克里金
- **参数推荐**: 根据数据量自动推荐网格分辨率和滞后数

### 2. 多种克里金方法
- **普通克里金 (Ordinary Kriging)**: 适用于无趋势的数据
- **泛克里金 (Universal Kriging)**: 适用于有趋势的数据
- **分块克里金 (Block Kriging)**: 适用于大数据集（>1000点）

### 3. 完整的API接口
- 数据上传 (GeoJSON格式)
- 参数推荐 (自动模型选择)
- 启动插值任务 (异步执行)
- 任务状态查询 (实时进度)
- 结果下载 (GeoTIFF格式)
- 误差报告生成

### 4. 性能优化
- 异步任务机制 (FastAPI BackgroundTasks)
- NumPy向量化计算
- 分块处理大数据集
- 线程安全的任务管理

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     API接口层                            │
│  数据上传 | 模型推荐 | 任务管理 | 结果查询 | 报告生成    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    业务服务层                            │
│  数据预处理 | 模型选择 | 插值计算 | 不确定性分析        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    核心算法层                            │
│  克里金调度器 | 普通克里金 | 泛克里金 | 分块克里金      │
│  变异函数拟合 | 交叉验证 | 趋势检测                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    基础设施层                            │
│  PyKrige | GSTools | scikit-learn | NumPy | SciPy      │
└─────────────────────────────────────────────────────────┘
```

## 算法流程

```
1. 数据上传
   ↓
2. 数据预处理
   - 异常值检测
   - 坐标转换
   - 数据清洗
   ↓
3. 趋势检测
   - 线性回归分析
   - 判断是否使用泛克里金
   ↓
4. 多变异函数拟合
   - 球状模型
   - 指数模型
   - 高斯模型
   - 线性模型
   ↓
5. 交叉验证评分
   - 5折交叉验证
   - 计算RMSE、MAE、R²
   ↓
6. 自动选择最优模型
   - 选择RMSE最小的模型
   ↓
7. 执行克里金插值
   - 生成预测栅格
   - 生成方差栅格
   ↓
8. 输出结果
   - GeoTIFF格式
   - 统计信息
   - 交叉验证报告
```

## API使用示例

### 1. 上传数据

```bash
curl -X POST "http://localhost:8000/api/upload-data" \
  -F "file=@data.geojson"
```

响应:
```json
{
  "data_id": "uuid-string",
  "point_count": 50,
  "bounds": {
    "min_x": 0.0,
    "min_y": 0.0,
    "max_x": 100.0,
    "max_y": 100.0
  },
  "message": "数据上传成功"
}
```

### 2. 获取参数推荐

```bash
curl -X POST "http://localhost:8000/api/recommend-parameters" \
  -H "Content-Type: application/json" \
  -d '{
    "data_id": "uuid-string",
    "enable_auto_model": true
  }'
```

响应:
```json
{
  "recommended_variogram_model": "spherical",
  "recommended_method": "ordinary",
  "recommended_grid_resolution": 100,
  "recommended_nlags": 12,
  "has_trend": false,
  "model_scores": {
    "spherical": 2.34,
    "exponential": 2.56,
    "gaussian": 2.89,
    "linear": 3.12
  },
  "point_count": 50,
  "message": "参数推荐完成"
}
```

### 3. 启动插值任务

```bash
curl -X POST "http://localhost:8000/api/start-kriging" \
  -H "Content-Type: application/json" \
  -d '{
    "data_id": "uuid-string",
    "variogram_model": "spherical",
    "method": "ordinary",
    "grid_resolution": 100,
    "nlags": 12,
    "enable_cross_validation": true,
    "n_folds": 5
  }'
```

响应:
```json
{
  "task_id": "task-uuid",
  "status": "pending",
  "message": "克里金任务已启动"
}
```

### 4. 查询任务状态

```bash
curl "http://localhost:8000/api/task-status/task-uuid"
```

响应:
```json
{
  "task_id": "task-uuid",
  "status": "completed",
  "progress": 100.0,
  "message": "任务完成",
  "created_at": "2026-02-28T00:00:00",
  "updated_at": "2026-02-28T00:01:00",
  "error": null
}
```

### 5. 获取结果

```bash
# 预测结果
curl "http://localhost:8000/api/result/prediction/task-uuid"

# 方差结果
curl "http://localhost:8000/api/result/variance/task-uuid"
```

## 快速开始

### 1. 安装依赖

```bash
cd /Users/wuchenkai/UDAKE
pip install -r requirements.txt
```

### 2. 启动服务

```bash
cd backend
python run.py
```

服务将在 `http://localhost:8000` 启动

### 3. 访问API文档

浏览器打开: `http://localhost:8000/docs`

### 4. 运行测试

```bash
cd backend
python test_backend.py
```

## 目录结构

```
backend/
├── app/
│   ├── api/                    # API接口层
│   │   ├── 数据上传接口.py      # 数据上传
│   │   ├── 模型推荐接口.py      # 参数推荐 (新增)
│   │   ├── 插值任务接口.py      # 任务启动
│   │   ├── 任务状态接口.py      # 状态查询
│   │   ├── 结果查询接口.py      # 结果下载
│   │   └── 报告生成接口.py      # 报告生成
│   ├── core/                   # 核心算法层
│   │   ├── 克里金调度器.py      # 算法调度
│   │   ├── 普通克里金引擎.py    # OK实现
│   │   ├── 泛克里金引擎.py      # UK实现
│   │   ├── 分块克里金引擎.py    # 大数据处理
│   │   ├── 变异函数拟合器.py    # 变异函数
│   │   └── 交叉验证模块.py      # 模型评估
│   ├── services/               # 业务服务层
│   │   ├── 数据预处理服务.py    # 数据处理
│   │   ├── 模型选择服务.py      # 自动选择 (增强)
│   │   ├── 插值计算服务.py      # 插值计算
│   │   ├── 不确定性分析服务.py  # 不确定性
│   │   └── 报告生成服务.py      # 报告生成
│   ├── tasks/                  # 任务管理层
│   │   ├── 任务管理器.py        # 任务管理
│   │   ├── 任务状态机.py        # 状态机
│   │   └── 异步执行器.py        # 异步执行
│   ├── schemas/                # 数据模型层
│   │   ├── 数据模型.py          # 数据结构
│   │   ├── 插值参数模型.py      # 参数模型
│   │   └── 输出结果模型.py      # 结果模型
│   ├── utils/                  # 工具层
│   │   ├── 栅格工具.py          # 栅格处理
│   │   ├── GeoJSON工具.py       # GeoJSON
│   │   ├── 日志工具.py          # 日志
│   │   └── 性能监控工具.py      # 监控
│   ├── config.py               # 配置
│   ├── dependencies.py         # 依赖注入
│   └── main.py                 # 主应用
├── run.py                      # 启动脚本
├── test_backend.py             # 测试脚本 (新增)
└── README.md                   # 文档
```

## 核心代码示例

### 自动模型选择

```python
from services.模型选择服务 import ModelSelector

selector = ModelSelector()

# 自动选择最优参数
params = selector.auto_select_parameters(x, y, values)

# 输出:
# {
#   "variogram_model": VariogramModel.SPHERICAL,
#   "method": KrigingMethod.ORDINARY,
#   "grid_resolution": 100,
#   "nlags": 12,
#   "has_trend": False,
#   "model_scores": {
#     "spherical": 2.34,
#     "exponential": 2.56,
#     ...
#   }
# }
```

### 交叉验证

```python
from core.交叉验证模块 import CrossValidator

validator = CrossValidator()

# 5折交叉验证
metrics = validator.validate(x, y, values, params)

# 输出:
# {
#   "rmse": 2.34,
#   "mae": 1.89,
#   "r2": 0.92,
#   "mse": 5.48
# }
```

### 趋势检测

```python
from services.模型选择服务 import ModelSelector

selector = ModelSelector()

# 检测空间趋势
has_trend = selector.detect_trend(x, y, values)

if has_trend:
    # 使用泛克里金
    method = KrigingMethod.UNIVERSAL
else:
    # 使用普通克里金
    method = KrigingMethod.ORDINARY
```

## 性能指标

- **小数据集 (<100点)**: 响应时间 < 5秒
- **中等数据集 (100-1000点)**: 响应时间 < 30秒
- **大数据集 (>1000点)**: 自动分块处理

## 待优化项

- [ ] 实现多进程并行计算
- [ ] 添加Redis缓存层
- [ ] WebSocket实时进度推送
- [ ] 3D克里金插值
- [ ] GPU加速计算
- [ ] 更多变异函数模型

## 技术支持

- API文档: http://localhost:8000/docs
- 项目地址: /Users/wuchenkai/UDAKE
- 测试脚本: backend/test_backend.py

## 总结

本后端服务实现了完整的克里金插值流程，具备以下优势:

1. **智能化**: 自动模型选择，无需手动调参
2. **工程化**: 清晰的分层架构，易于维护扩展
3. **高性能**: 异步任务、向量化计算、分块处理
4. **可靠性**: 交叉验证、异常处理、日志记录
5. **易用性**: RESTful API、完整文档、测试脚本

适用于竞赛展示、科研项目、生产环境。
