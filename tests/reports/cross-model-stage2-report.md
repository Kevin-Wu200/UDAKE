# 跨模型测试第二阶段报告

## 测试范围
- 跨模型对比测试（解释结果、性能指标、准确性）
- 回归测试（关键功能点与自动化调度）
- 性能对比测试（时延对比与瓶颈识别）
- 稳定性测试（重复执行、边界条件、异常恢复）
- 压力测试（多模型并发任务）
- 兼容性测试（浏览器/操作系统/Python/依赖版本矩阵）

## 对比测试方案
- 统一使用固定随机种子生成数据，覆盖 anomaly/interpolation/uncertainty/fusion/rl 五类模型域。
- 解释方法采用 `hybrid`，并统一 `top_k`、`max_explain_nodes`、`num_samples`、`nsamples` 配置。
- 对比指标：
  - 解释一致性：`top_features` 稳定程度。
  - 性能指标：端到端推理+解释耗时 `latency_ms`。
  - 准确性代理：模型域评估分（用于跨模型综合评分）。
- 通过 `CrossModelStage2Toolkit.compare_models` 计算综合评分并排序。

## 回归测试策略
- 覆盖 5 个核心 API：
  - `POST /api/dl/anomaly/explain`
  - `POST /api/dl/interpolation/explain`
  - `POST /api/dl/uncertainty/explain`
  - `POST /api/dl/fusion/explain`
  - `POST /api/dl/rl/explain`
- 回归判定：
  - 时延退化阈值：`latency_ratio_limit`
  - 准确率下降阈值：`accuracy_drop_limit`
  - 稳定性下降阈值：`stability_drop_limit`
- 调度机制：`schedule_next_run(last_run_iso, interval_minutes)` 用于回归巡检到期判断。

## 性能与稳定性
- 性能瓶颈识别：`find_bottlenecks(records, latency_threshold_ms)`。
- 稳定性验证：
  - 同输入重复执行，校验解释签名稳定率。
  - 边界参数（`top_k=99`, `max_explain_nodes=99`）输出可用。
  - 非法参数触发可预期异常并可恢复继续执行。

## 压力与兼容性
- 多模型并发压力：异步 explain 任务并发提交，轮询完成状态并汇总队列指标。
- 兼容性矩阵：
  - 浏览器：Chromium / Firefox / WebKit（由 E2E 套件实际执行）
  - 操作系统：macOS / Linux / Windows
  - Python：3.9 / 3.10 / 3.11
  - 依赖：`numpy` / `fastapi` / `pydantic` 版本存在且可解析
- 向下兼容性：验证旧请求结构在默认参数下仍可实例化和执行。

## 自动化执行
```bash
./scripts/run_cross_model_stage2_tests.sh
```

该脚本会：
1. 运行 `tests/deep_learning/test_cross_model_stage2.py`
2. 更新本报告末尾最近执行时间

- 最近执行时间(UTC): 2026-04-14T02:19:30.873115+00:00
