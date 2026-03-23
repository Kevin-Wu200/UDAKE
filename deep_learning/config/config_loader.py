"""YAML 配置加载、继承、覆盖与校验。"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


class ConfigValidationError(ValueError):
    pass


class ConfigLoader:
    def __init__(self) -> None:
        try:
            import yaml  # type: ignore

            self._yaml = yaml
        except Exception as exc:
            raise RuntimeError("缺少 PyYAML，无法加载 YAML 配置") from exc

    def load(
        self,
        path: str,
        overrides: dict[str, Any] | None = None,
        env_prefix: str = "DL_",
    ) -> dict[str, Any]:
        file_path = Path(path)
        raw = self._read_yaml(file_path)
        config = self._resolve_inheritance(raw, file_path.parent)

        self._apply_env_overrides(config, env_prefix=env_prefix)
        if overrides:
            config = self._deep_merge(config, overrides)

        self.validate(config)
        return config

    def validate(self, config: dict[str, Any]) -> None:
        required_top_level = ["model", "training", "inference"]
        missing = [k for k in required_top_level if k not in config]
        if missing:
            raise ConfigValidationError(f"缺少必须配置字段: {', '.join(missing)}")

        training = config.get("training", {})
        max_epochs = training.get("max_epochs", 0)
        batch_size = training.get("batch_size", 0)
        if not isinstance(max_epochs, int) or max_epochs <= 0:
            raise ConfigValidationError("training.max_epochs 必须为正整数")
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ConfigValidationError("training.batch_size 必须为正整数")

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fp:
            content = self._yaml.safe_load(fp) or {}
        if not isinstance(content, dict):
            raise ConfigValidationError("配置文件根节点必须是对象")
        return content

    def _resolve_inheritance(self, config: dict[str, Any], base_dir: Path) -> dict[str, Any]:
        base_ref = config.pop("_base", None)
        if not base_ref:
            return config

        base_path = (base_dir / base_ref).resolve()
        parent = self._read_yaml(base_path)
        parent = self._resolve_inheritance(parent, base_path.parent)
        return self._deep_merge(parent, config)

    def _apply_env_overrides(self, config: dict[str, Any], env_prefix: str = "DL_") -> None:
        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue
            path_parts = key[len(env_prefix):].lower().split("__")
            self._set_nested(config, path_parts, self._parse_env_value(value))

    def _set_nested(self, data: dict[str, Any], path_parts: list[str], value: Any) -> None:
        current = data
        for part in path_parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[path_parts[-1]] = value

    def _parse_env_value(self, raw: str) -> Any:
        lowered = raw.strip().lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            pass
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
