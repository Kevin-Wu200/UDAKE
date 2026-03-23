from __future__ import annotations

from pathlib import Path

import pytest

from deep_learning.config import ConfigLoader, ConfigValidationError


def test_config_inheritance_and_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "base.yaml"
    child = tmp_path / "child.yaml"

    base.write_text(
        """
model:
  name: demo
training:
  max_epochs: 50
  batch_size: 16
inference:
  batch_size: 64
""".strip(),
        encoding="utf-8",
    )

    child.write_text(
        """
_base: base.yaml
training:
  batch_size: 32
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("DL_TRAINING__MAX_EPOCHS", "120")

    cfg = ConfigLoader().load(str(child), overrides={"inference": {"batch_size": 128}})
    assert cfg["training"]["batch_size"] == 32
    assert cfg["training"]["max_epochs"] == 120
    assert cfg["inference"]["batch_size"] == 128


def test_config_validation_error(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        """
model:
  name: demo
training:
  max_epochs: 0
  batch_size: 0
inference:
  batch_size: 16
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError):
        ConfigLoader().load(str(invalid))
