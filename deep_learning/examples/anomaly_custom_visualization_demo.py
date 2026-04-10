"""异常检测自定义可视化示例（ASCII + HTML）。"""

from __future__ import annotations

import json
from pathlib import Path

from anomaly_examples_common import build_demo_dataset, create_model, train_model


OUTPUT_DIR = Path("deep_learning/examples/output")


def ascii_bar(value: float, max_value: float, width: int = 30) -> str:
    if max_value <= 0.0:
        return "." * width
    n = int(round(width * max(0.0, value) / max_value))
    return "#" * n + "." * (width - n)


def build_html(scores: list[float], anomaly_indices: list[int]) -> str:
    peak = max(scores) if scores else 1.0
    bars = []
    for idx, score in enumerate(scores):
        ratio = max(0.0, min(1.0, score / peak))
        color = "#d9534f" if idx in anomaly_indices else "#4a90e2"
        bars.append(
            f"<div style='width:8px;height:{int(14 + 120 * ratio)}px;background:{color};margin-right:2px'></div>"
        )
    return (
        "<html><head><meta charset='utf-8'><title>Anomaly Visualization</title></head><body>"
        "<h3>异常分数柱状图</h3>"
        "<div style='display:flex;align-items:flex-end;border:1px solid #ddd;padding:12px;overflow-x:auto;'>"
        + "".join(bars)
        + "</div></body></html>"
    )


def main() -> None:
    dataset = build_demo_dataset(n=96, seed=707)
    model_name = "gcae"
    model = create_model(model_name)
    train_model(model_name, model, dataset.coords, dataset.values, epochs=12)
    prediction = model.predict(dataset.coords, dataset.values, percentile=92.0, k=2.2)

    scores = [float(x) for x in prediction.get("anomaly_scores", prediction.get("scores", []))]
    anomaly_indices = [int(i) for i in prediction.get("anomaly_indices", [])]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    peak = max(scores) if scores else 1.0
    print("=== 自定义 ASCII 可视化（前20个点）===")
    for idx, score in enumerate(scores[:20]):
        mark = "*" if idx in anomaly_indices else " "
        print(f"{idx:02d}{mark} {ascii_bar(score, peak)} {score:.4f}")

    html_path = OUTPUT_DIR / "anomaly_custom_visualization.html"
    json_path = OUTPUT_DIR / "anomaly_custom_visualization.json"
    html_path.write_text(build_html(scores, anomaly_indices), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "scores": scores,
                "anomaly_indices": anomaly_indices,
                "top10_anomalies": sorted(anomaly_indices[:10]),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("HTML 输出:", html_path)
    print("JSON 输出:", json_path)


if __name__ == "__main__":
    main()
