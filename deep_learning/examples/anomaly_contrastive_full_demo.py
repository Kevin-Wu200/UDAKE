"""对比学习异常检测完整使用示例。"""

from __future__ import annotations

from anomaly_examples_common import build_demo_dataset, quick_train_predict_workflow


def main() -> None:
    dataset = build_demo_dataset(seed=404)
    out = quick_train_predict_workflow("contrastive", dataset, epochs=18)
    print("[Contrastive] 训练摘要:", out["train"])
    print("[Contrastive] 预测摘要:", out["prediction_summary"])
    print("[Contrastive] 标准预测异常数:", out["predict_standard"]["anomaly_count"])
    print("[Contrastive] 分数组件:", out["score_bundle_keys"])
    print("[Contrastive] 在线更新结果:", out["extras"].get("online_update", {}))
    print("[Contrastive] 注入异常索引(前10):", dataset.injected_indices[:10])


if __name__ == "__main__":
    main()
