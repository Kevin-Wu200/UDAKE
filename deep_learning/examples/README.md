# 通用框架示例集合

本目录用于覆盖“文档完善-使用示例集合”任务中的核心场景，所有示例可直接运行。

## 场景映射

- 异常检测使用示例：`anomaly_inference_demo.py`
- 空间插值使用示例：`spatial_interpolation_adapter_usage_demo.py`
- 不确定性使用示例：`uncertainty_inference_demo.py`
- 融合模型使用示例：`fusion_adapter_usage_demo.py`
- 强化学习使用示例：`rl_adapter_usage_demo.py`
- 多模型对比示例：`anomaly_multi_model_comparison_demo.py`
- 高级用法示例：`advanced_usage_demo.py`

## 运行方式

在仓库根目录执行：

```bash
./venv/bin/python deep_learning/examples/anomaly_inference_demo.py
./venv/bin/python deep_learning/examples/spatial_interpolation_adapter_usage_demo.py
./venv/bin/python deep_learning/examples/uncertainty_inference_demo.py
./venv/bin/python deep_learning/examples/fusion_adapter_usage_demo.py
./venv/bin/python deep_learning/examples/rl_adapter_usage_demo.py
./venv/bin/python deep_learning/examples/anomaly_multi_model_comparison_demo.py
./venv/bin/python deep_learning/examples/advanced_usage_demo.py
```

## 一键验证可运行性

```bash
./venv/bin/python deep_learning/examples/verify_usage_examples.py
```

