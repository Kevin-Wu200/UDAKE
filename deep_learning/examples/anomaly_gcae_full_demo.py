"""GCAE 异常检测完整使用示例。"""

from __future__ import annotations

from anomaly_examples_common import build_demo_dataset, quick_train_predict_workflow


def main() -> None:
    dataset = build_demo_dataset(seed=202)
    out = quick_train_predict_workflow("gcae", dataset, epochs=14)
    print("[GCAE] 训练摘要:", out["train"])
    print("[GCAE] 预测摘要:", out["prediction_summary"])
    print("[GCAE] 标准预测异常数:", out["predict_standard"]["anomaly_count"])
    print("[GCAE] 分数组件:", out["score_bundle_keys"])
    print("[GCAE] 预处理特征(前6):", out["extras"].get("feature_names", []))
    print("[GCAE] 注入异常索引(前10):", dataset.injected_indices[:10])


if __name__ == "__main__":
    main()
