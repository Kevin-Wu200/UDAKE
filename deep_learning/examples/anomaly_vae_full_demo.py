"""VAE 异常检测完整使用示例。"""

from __future__ import annotations

from anomaly_examples_common import build_demo_dataset, quick_train_predict_workflow


def main() -> None:
    dataset = build_demo_dataset(seed=101)
    out = quick_train_predict_workflow("vae", dataset, epochs=12)
    print("[VAE] 训练摘要:", out["train"])
    print("[VAE] 预测摘要:", out["prediction_summary"])
    print("[VAE] 标准预测异常数:", out["predict_standard"]["anomaly_count"])
    print("[VAE] 分数组件:", out["score_bundle_keys"])
    print("[VAE] 潜空间预览:", out["extras"].get("latent_preview", []))
    print("[VAE] 注入异常索引(前10):", dataset.injected_indices[:10])


if __name__ == "__main__":
    main()
