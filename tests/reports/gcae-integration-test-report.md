# GCAE 集成测试记录（第2章节）

## 覆盖项
- 端到端测试流程：`tests/deep_learning/test_gcae_adapter_stage4.py::test_gcae_end_to_end_detection_explain_graph_processing_and_accuracy`
- 完整异常检测流程：训练 + 预测 + 结果结构校验
- 解释生成流程：LIME/SHAP/Hybrid 输出与关键字段校验
- 图数据处理：`preprocess_graph_data` 输出结构、特征维度、邻接矩阵与批次切片校验
- 与前端集成：校验后端 `anomaly/predict` 返回结构（含 `prediction` 包裹层）与前端面板 GCAE 兼容性
- 异步任务集成：并发执行 `predict_anomaly`、`explain_anomaly`、`detect_realtime_anomaly`
- 结果准确性：对注入异常点命中数进行断言（命中 >= 2）

## 执行命令
```bash
./venv/bin/python -m pytest -q tests/deep_learning/test_gcae_adapter_stage4.py
npm run test -- tests/components/AnomalyDetectionPanel.test.ts
./venv/bin/python -m pytest -q tests/deep_learning/test_gcae_adapter_stage1.py tests/deep_learning/test_gcae_adapter_stage2.py tests/deep_learning/test_gcae_adapter_stage3.py tests/deep_learning/test_gcae_adapter_stage4.py
```

## 结果
- `./venv/bin/python -m pytest -q tests/deep_learning/test_gcae_adapter_stage4.py`：`2 passed`
- `npm run test -- tests/components/AnomalyDetectionPanel.test.ts`：`12 passed`
- `./venv/bin/python -m pytest -q tests/deep_learning/test_gcae_adapter_stage1.py tests/deep_learning/test_gcae_adapter_stage2.py tests/deep_learning/test_gcae_adapter_stage3.py tests/deep_learning/test_gcae_adapter_stage4.py`：`12 passed`
