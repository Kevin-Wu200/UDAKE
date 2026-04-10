"""异常检测批量处理示例。"""

from __future__ import annotations

import numpy as np

from anomaly_examples_common import build_demo_dataset, create_model, train_model


def split_batches(coords: np.ndarray, values: np.ndarray, batch_size: int) -> list[dict[str, list[float]]]:
    batches: list[dict[str, list[float]]] = []
    for i in range(0, len(values), batch_size):
        j = min(i + batch_size, len(values))
        batches.append(
            {
                "coords": coords[i:j].tolist(),
                "values": values[i:j].tolist(),
            }
        )
    return batches


def main() -> None:
    dataset = build_demo_dataset(n=120, seed=606)
    model_name = "gan"
    model = create_model(model_name)
    train_model(model_name, model, dataset.coords, dataset.values, epochs=15)

    stream_batches = split_batches(dataset.coords, dataset.values, batch_size=30)
    print("=== 批量流式处理结果 ===")
    total = 0
    for batch_idx, batch in enumerate(stream_batches):
        pred = model.predict(
            np.asarray(batch["coords"], dtype=float),
            np.asarray(batch["values"], dtype=float),
            threshold_method="adaptive",
            percentile=95.0,
            k=2.3,
        )
        anomaly_count = int(pred.get("anomaly_count", 0))
        total += anomaly_count
        print(f"batch={batch_idx}, anomaly_count={anomaly_count}")
    print("total_anomaly_count:", total)


if __name__ == "__main__":
    main()
