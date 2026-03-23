from __future__ import annotations

from pathlib import Path

from deep_learning.training import LightningTrainer, TrainingConfig


class DummyModel:
    def __init__(self) -> None:
        self.bias = 0.0

    def train_step(self, batch, lr=0.01, mixed_precision=False):
        target = sum(item[-1] for item in batch) / len(batch)
        grad = self.bias - target
        self.bias -= lr * grad
        return abs(grad)

    def val_step(self, batch):
        target = sum(item[-1] for item in batch) / len(batch)
        return abs(self.bias - target)

    def get_state(self):
        return {"bias": self.bias}

    def load_state(self, state):
        self.bias = state["bias"]


def test_lightning_trainer_core_features(tmp_path: Path) -> None:
    model = DummyModel()
    trainer = LightningTrainer(
        TrainingConfig(
            max_epochs=20,
            learning_rate=0.1,
            early_stopping_patience=3,
            gradient_clip_norm=1.0,
            mixed_precision=True,
            lr_decay=0.9,
        ),
        log_dir=str(tmp_path / "tb"),
    )

    samples = [[0.2, 1.0], [0.3, 0.9], [0.1, 1.1]]
    result = trainer.train(model, [samples], [samples])

    assert result["epochs_ran"] >= 1
    assert result["mixed_precision"] is True
    assert result["best_val_loss"] < 2.0

    clipped = trainer.clip_gradients([10.0, 0.0])
    assert abs(clipped[0]) <= 1.0

    ckpt = tmp_path / "ckpt" / "demo.pkl"
    trainer.save_checkpoint(model, str(ckpt))
    model.bias = 99.0
    trainer.load_checkpoint(model, str(ckpt))
    assert model.bias != 99.0
