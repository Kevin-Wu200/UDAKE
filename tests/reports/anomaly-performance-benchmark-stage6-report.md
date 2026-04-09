# 异常检测性能基准测试报告（第6章节）

## 覆盖项
- 设计性能测试方案：阈值定义（单样本/批处理/并发均 < 10s）
- 测试单样本解释时间：VAE/GCAE/GAN/Contrastive
- 测试批处理性能：`max_explain_nodes=8` 批量解释
- 测试内存使用：校验 `performance.memory_bytes` 输出（VAE/GAN/Contrastive）
- 测试并发性能：4 并发缓存命中稳定性验证（GAN）
- 编写性能报告：本文件 + `tests/reports/stage6-anomaly-performance-benchmark.json`
- 优化性能瓶颈：VAE LIME 改为“解释器单次构建复用 + 压缩训练样本（<=96）+ 内存统计”

## 对应测试
- `tests/performance/test_anomaly_explainer_stage6_benchmark.py`
- `tests/performance/test_gcae_explainer_performance.py`
- `tests/performance/test_gan_explainer_performance.py`
- `tests/performance/test_contrastive_explainer_performance.py`
- `tests/performance/test_performance_optimization_unit.py`
- 回归：`tests/deep_learning/test_vae_adapter_stage1.py`

## 执行命令
```bash
./venv/bin/python -m pytest -q \
  tests/performance/test_anomaly_explainer_stage6_benchmark.py \
  tests/performance/test_gcae_explainer_performance.py \
  tests/performance/test_gan_explainer_performance.py \
  tests/performance/test_contrastive_explainer_performance.py \
  tests/performance/test_performance_optimization_unit.py \
  tests/deep_learning/test_vae_adapter_stage1.py
```

## 结果
- 测试结果：`17 passed`
- 阈值校验：通过（单样本/批处理/并发均远低于 10s）

### 批处理（8节点）基准摘录
- VAE: `314.848 ms`
- GCAE: `163.755 ms`
- GAN: `110.1 ms`
- Contrastive: `147.352 ms`

### 内存指标摘录
- VAE: `31152 bytes`
- GAN: `17568 bytes`
- Contrastive: `24240 bytes`

## 结论
- 第六章节性能基准测试项全部完成并通过。
- VAE 解释路径的瓶颈优化已落地，且新增性能可观测字段（`lime_training_size`/`lime_sampling_budget`/`memory_bytes`）。
