import requests

BASE = "http://127.0.0.1:8000/api/spatiotemporal"

train_payload = {
    "data": {
        "x": [120.1, 120.2, 120.3],
        "y": [30.1, 30.2, 30.3],
        "z": [10.0, 10.2, 10.4],
        "t": [1711929600, 1712016000, 1712102400],
        "value": [80.0, 82.5, 84.2],
    },
    "model_type": "nonseparable",
    "options": {"optimization": {"method": "mle", "max_iterations": 120}},
}

train_resp = requests.post(f"{BASE}/train", json=train_payload, timeout=30)
train_resp.raise_for_status()
model_id = train_resp.json()["data"]["model_id"]

predict_payload = {
    "model_id": model_id,
    "target_positions": {"x": [120.4], "y": [30.4], "z": [10.6]},
    "target_times": [1712188800],
    "prediction_days": 7,
    "options": {"use_cache": True},
}

predict_resp = requests.post(f"{BASE}/predict", json=predict_payload, timeout=30)
predict_resp.raise_for_status()
print(predict_resp.json())
