# GPU加速计算系统方案

## 1. 目标
- 为矩阵运算、向量运算和克里金关键计算路径提供 GPU 加速能力。
- 在无 GPU 或无 CuPy 环境下自动回退 CPU，保证功能可用性。
- 提供任务调度、运行监控、设备管理、性能指标 API。

## 2. 架构
- `app/gpu_acceleration/device_manager.py`：检测设备、后端选择。
- `app/gpu_acceleration/memory_manager.py`：CPU/GPU 数据传输和统计。
- `app/gpu_acceleration/compute_engine.py`：矩阵/向量计算核心。
- `app/gpu_acceleration/kriging_accelerator.py`：变异函数、协方差、批量预测。
- `app/gpu_acceleration/task_scheduler.py`：任务生命周期管理。
- `app/gpu_acceleration/performance_monitor.py`：性能记录与汇总。
- `app/services/gpu_service.py`：统一服务入口。
- `app/api/GPU加速接口.py`：对外 REST API。

## 3. 核心策略
- 自动切换：基于数据规模阈值 `min_size_for_gpu`。
- 可控开关：`enable_gpu`、`auto_switch`。
- 性能采样：记录每次操作耗时、输入规模、后端类型。
- 异常处理：API 层区分参数错误（400）与系统错误（500）。

## 4. 主要接口
- `GET /api/gpu/health`：健康检查。
- `GET /api/gpu/status`：状态与配置。
- `PUT /api/gpu/config`：更新 GPU 策略。
- `GET /api/gpu/metrics`：性能和内存指标。
- `POST /api/gpu/compute/matrix/*`：矩阵加速运算。
- `POST /api/gpu/compute/vector/*`：向量加速运算。
- `POST /api/gpu/kriging/semivariogram`：变异函数加速。
- `POST /api/gpu/kriging/predict`：克里金批量预测。

## 5. 测试
- `services/backend/tests/test_gpu_service.py`
- `services/backend/tests/test_gpu_api.py`

通过上述测试验证：
- 核心算子输出正确
- API 可调用
- 任务状态可追踪
- 性能指标可查询
