"""监控仪表板数据构建器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DashboardBuilder:
    output_path: str = "logs/deep_learning/dashboard.json"

    def build(self, metrics: dict[str, Any], resources: dict[str, float], alerts: list[str]) -> str:
        payload = {
            "metrics": metrics,
            "resources": resources,
            "alerts": alerts,
        }
        file_path = Path(self.output_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(file_path)
