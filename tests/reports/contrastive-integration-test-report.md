# 对比学习集成测试记录（第4章节）

## 覆盖项
- 端到端测试流程：`tests/deep_learning/test_contrastive_adapter_stage4.py::test_contrastive_end_to_end_detection_explain_pipeline_and_accuracy`
- 完整异常检测流程：训练 + 预测 + 结果结构校验
- 解释生成流程：LIME/SHAP/Hybrid 输出与关键字段校验
- 对比学习流程：`preprocess_contrastive_data`、`encode`、`score_components`、`online_feature_bank_size` 校验
- 与前端集成：校验后端 `anomaly/predict` 返回结构（含 `prediction` 包裹层）与前端面板 Contrastive 兼容性
- 异步任务集成：并发执行 `predict_anomaly`、`explain_anomaly`、`detect_realtime_anomaly`
- 结果准确性：注入异常点平均异常分数高于非注入点

## 执行命令
```bash
./venv/bin/python -m pytest -q tests/deep_learning/test_contrastive_adapter_stage4.py
npm run test -- tests/components/AnomalyDetectionPanel.test.ts
./venv/bin/python -m pytest -q tests/deep_learning/test_contrastive_adapter_stage1.py tests/deep_learning/test_contrastive_adapter_stage2.py tests/deep_learning/test_contrastive_adapter_stage3.py tests/deep_learning/test_contrastive_adapter_stage4.py
```

## 结果
- `./venv/bin/python -m pytest -q tests/deep_learning/test_contrastive_adapter_stage4.py`：`4 passed`
- `npm run test -- tests/components/AnomalyDetectionPanel.test.ts`：`14 passed`
- `./venv/bin/python -m pytest -q tests/deep_learning/test_contrastive_adapter_stage1.py tests/deep_learning/test_contrastive_adapter_stage2.py tests/deep_learning/test_contrastive_adapter_stage3.py tests/deep_learning/test_contrastive_adapter_stage4.py`：`15 passed`
