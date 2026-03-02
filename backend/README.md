# 克里金插值后端服务

基于 FastAPI 的空间插值与不确定性分析后端服务。

## 技术栈

- **FastAPI**: 高性能异步Web框架
- **PyKrige**: 克里金插值核心库
- **GSTools**: 地统计工具
- **scikit-learn**: 交叉验证与模型评估
- **NumPy/SciPy**: 科学计算
- **GDAL/Rasterio**: 地理空间数据处理

## 项目结构

```
backend/
├── app/
│   ├── api/              # API接口层
│   │   ├── 数据上传接口.py
│   │   ├── 插值任务接口.py
│   │   ├── 任务状态接口.py
│   │   ├── 结果查询接口.py
│   │   └── 报告生成接口.py
│   ├── core/             # 核心算法层
│   │   ├── 克里金调度器.py
│   │   ├── 普通克里金引擎.py
│   │   ├── 泛克里金引擎.py
│   │   ├── 分块克里金引擎.py
│   │   ├── 变异函数拟合器.py
│   │   └── 交叉验证模块.py
│   ├── services/         # 业务服务层
│   │   ├── 数据预处理服务.py
│   │   ├── 插值计算服务.py
│   │   ├── 模型选择服务.py
│   │   ├── 不确定性分析服务.py
│   │   └── 报告生成服务.py
│   ├── tasks/            # 任务管理层
│   │   ├── 任务管理器.py
│   │   ├── 任务状态机.py
│   │   └── 异步执行器.py
│   ├── schemas/          # 数据模型层
│   │   ├── 数据模型.py
│   │   ├── 插值参数模型.py
│   │   └── 输出结果模型.py
│   ├── utils/            # 工具层
│   │   ├── 栅格工具.py
│   │   ├── GeoJSON工具.py
│   │   ├── 日志工具.py
│   │   └── 性能监控工具.py
│   ├── config.py         # 配置文件
│   ├── dependencies.py   # 依赖注入
│   └── main.py           # 主应用
├── run.py                # 启动脚本
└── README.md             # 本文件
```

## API接口

### 1. 数据上传
```
POST /api/upload-data
```

### 2. 启动插值任务
```
POST /api/start-kriging
```

### 3. 获取任务状态
```
GET /api/task-status/{task_id}
```

### 4. 获取预测栅格
```
GET /api/prediction/{task_id}
```

### 5. 获取方差栅格
```
GET /api/variance/{task_id}
```

### 6. 获取误差报告
```
GET /api/error-report/{task_id}
```

## 算法流程

1. **数据预处理**: 数据清洗、异常值检测、坐标转换
2. **趋势检测**: 判断是否存在空间趋势，决定使用普通克里金或泛克里金
3. **变异函数拟合**: 自动拟合多种变异函数模型（球状、指数、高斯等）
4. **交叉验证**: K折交叉验证评估模型性能
5. **模型选择**: 基于交叉验证结果自动选择最优模型
6. **插值计算**: 生成预测值和方差栅格
7. **结果输出**: 导出GeoTIFF或GeoJSON格式

## 性能优化

- **分块处理**: 大数据集自动分块，避免内存溢出
- **NumPy优化**: 向量化计算，提升运算速度
- **异步任务**: 后台任务机制，不阻塞API响应
- **并行计算**: 多核并行处理（待实现）

## 快速开始

### 安装依赖
```bash
pip install -r ../requirements.txt
```

### 启动服务
```bash
python run.py
```

### 访问API文档
```
http://localhost:8000/docs
```

## 配置说明

编辑 `.env` 文件或修改 `app/config.py`:

```python
# 服务器配置
HOST = "0.0.0.0"
PORT = 8000

# 克里金配置
DEFAULT_VARIOGRAM_MODEL = "spherical"
GRID_RESOLUTION = 100

# 任务配置
MAX_CONCURRENT_TASKS = 5
TASK_TIMEOUT = 3600
```

## 开发规范

- 使用中文命名模块和函数（便于团队协作）
- 遵循PEP 8代码规范
- 添加类型注解
- 编写单元测试
- 记录详细日志

## 待优化项

- [ ] 实现多进程并行计算
- [ ] 添加Redis缓存层
- [ ] 实现WebSocket实时进度推送
- [ ] 优化大数据集内存管理
- [ ] 添加更多变异函数模型
- [ ] 实现3D克里金插值
