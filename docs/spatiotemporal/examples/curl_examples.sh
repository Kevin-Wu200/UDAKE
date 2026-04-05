#!/usr/bin/env bash
set -euo pipefail

BASE='http://127.0.0.1:8000/api/spatiotemporal'

TRAIN_RESP=$(curl -sS -X POST "$BASE/train" -H 'Content-Type: application/json' -d '{
  "data": {
    "x": [120.1, 120.2, 120.3],
    "y": [30.1, 30.2, 30.3],
    "z": [10.0, 10.2, 10.4],
    "t": [1711929600, 1712016000, 1712102400],
    "value": [80.0, 82.5, 84.2]
  },
  "model_type": "nonseparable",
  "options": {"optimization": {"method": "mle", "max_iterations": 120}}
}')

echo "$TRAIN_RESP"
MODEL_ID=$(echo "$TRAIN_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["data"]["model_id"])')

curl -sS -X POST "$BASE/predict" -H 'Content-Type: application/json' -d "{
  \"model_id\": \"$MODEL_ID\",
  \"target_positions\": {\"x\": [120.4], \"y\": [30.4], \"z\": [10.6]},
  \"target_times\": [1712188800],
  \"prediction_days\": 7,
  \"options\": {\"use_cache\": true}
}"
