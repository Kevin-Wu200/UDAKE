"""异常检测多模型对比示例。"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from anomaly_examples_common import build_demo_dataset, create_model, train_model


def jaccard(a: set[int], b: set[int]) -> float:
    union = len(a | b)
    if union == 0:
        return 1.0
    return len(a & b) / union


def main() -> None:
    dataset = build_demo_dataset(n=110, seed=505)
    coords = dataset.coords
    values = dataset.values

    predictions: dict[str, dict[str, Any]] = {}
    for model_name in ("vae", "gcae", "gan", "contrastive"):
        model = create_model(model_name)
        train_model(model_name, model, coords, values, epochs=12)
        pred = model.predict(
            coords,
            values,
            threshold_method="percentile",
            percentile=92.0,
            k=2.2,
        )
        predictions[model_name] = pred

    print("=== 多模型异常数量对比 ===")
    for model_name, result in predictions.items():
        print(f"{model_name:12s} -> anomaly_count={result.get('anomaly_count', 0)}")

    print("\n=== 模型间 Jaccard 一致性 ===")
    for a, b in combinations(predictions.keys(), 2):
        sa = set(int(i) for i in predictions[a].get("anomaly_indices", []))
        sb = set(int(i) for i in predictions[b].get("anomaly_indices", []))
        print(f"{a:12s} vs {b:12s} -> {jaccard(sa, sb):.3f}")

    injected = set(dataset.injected_indices)
    print("\n=== 对注入异常的命中数 ===")
    for model_name, result in predictions.items():
        hit = len(injected & set(int(i) for i in result.get("anomaly_indices", [])))
        print(f"{model_name:12s} -> hit={hit}/{len(injected)}")


if __name__ == "__main__":
    main()
