"""GAN 异常检测完整使用示例。"""

from __future__ import annotations

from anomaly_examples_common import build_demo_dataset, quick_train_predict_workflow


def main() -> None:
    dataset = build_demo_dataset(seed=303)
    out = quick_train_predict_workflow("gan", dataset, epochs=16)
    print("[GAN] 训练摘要:", out["train"])
    print("[GAN] 预测摘要:", out["prediction_summary"])
    print("[GAN] 标准预测异常数:", out["predict_standard"]["anomaly_count"])
    print("[GAN] 分数组件:", out["score_bundle_keys"])
    print("[GAN] 预处理特征(前6):", out["extras"].get("feature_names", []))
    print("[GAN] 注入异常索引(前10):", dataset.injected_indices[:10])


if __name__ == "__main__":
    main()
