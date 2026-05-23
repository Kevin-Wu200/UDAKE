"""PyTorch Lightning 风格训练器（轻量实现）。"""

from __future__ import annotations

import os
import pickle
from dataclasses import asdict
from typing import Any

from deep_learning.utils.monitoring import MetricMonitor

from .base_trainer import BaseTrainer, TrainingConfig


class _SummaryWriterStub:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.records: list[tuple[str, float, int]] = []

    def add_scalar(self, name: str, value: float, step: int) -> None:
        self.records.append((name, value, step))

    def flush(self) -> None:
        return


class LightningTrainer(BaseTrainer):
    """支持 TensorBoard、Checkpoint、早停、学习率调度与混合精度标记。"""

    def __init__(self, config: TrainingConfig | None = None, log_dir: str = "logs/tensorboard") -> None:
        super().__init__(config)
        self.log_dir = log_dir
        self.monitor = MetricMonitor()
        self.writer = self._build_writer(log_dir)

    def _build_writer(self, log_dir: str) -> Any:
        try:
            from torch.utils.tensorboard import SummaryWriter  # type: ignore

            return SummaryWriter(log_dir=log_dir)
        except Exception:
            return _SummaryWriterStub()

    def train(self, model: Any, train_loader: Any, val_loader: Any | None = None) -> dict[str, Any]:
        best_val = float("inf")
        wait = 0
        current_lr = self.config.learning_rate

        for epoch in range(self.config.max_epochs):
            train_loss = self._run_epoch(model, train_loader, current_lr)
            val_loss = self._run_validation(model, val_loader) if val_loader is not None else train_loss

            self.monitor.log("train_loss", train_loss)
            self.monitor.log("val_loss", val_loss)
            self.writer.add_scalar("train/loss", train_loss, epoch)
            self.writer.add_scalar("val/loss", val_loss, epoch)
            self.history.append({"epoch": float(epoch), "train_loss": train_loss, "val_loss": val_loss, "lr": current_lr})

            if val_loss < best_val:
                best_val = val_loss
                wait = 0
            else:
                wait += 1

            if wait >= self.config.early_stopping_patience:
                break

            current_lr *= self.config.lr_decay

        self.writer.flush()
        return {
            "best_val_loss": best_val,
            "epochs_ran": len(self.history),
            "config": asdict(self.config),
            "mixed_precision": self.config.mixed_precision,
            "distributed": self.config.use_distributed,
        }

    def _run_epoch(self, model: Any, train_loader: Any, lr: float) -> float:
        losses: list[float] = []
        for batch in train_loader:
            if hasattr(model, "train_step"):
                loss = float(model.train_step(batch, lr=lr, mixed_precision=self.config.mixed_precision))
            else:
                loss = float(model(batch))
            losses.append(loss)
        return sum(losses) / max(1, len(losses))

    def _run_validation(self, model: Any, val_loader: Any | None) -> float:
        if val_loader is None:
            return 0.0
        losses: list[float] = []
        for batch in val_loader:
            if hasattr(model, "val_step"):
                losses.append(float(model.val_step(batch)))
            elif hasattr(model, "train_step"):
                losses.append(float(model.train_step(batch, lr=0.0, mixed_precision=self.config.mixed_precision)))
            else:
                losses.append(float(model(batch)))
        return sum(losses) / max(1, len(losses))

    def clip_gradients(self, grads: list[float]) -> list[float]:
        norm = sum(g * g for g in grads) ** 0.5
        max_norm = self.config.gradient_clip_norm
        if norm <= max_norm or norm == 0:
            return grads
        scale = max_norm / norm
        return [g * scale for g in grads]

    def save_checkpoint(self, model: Any, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {"model_state": model.get_state() if hasattr(model, "get_state") else model.__dict__}
        with open(path, "wb") as fp:
            pickle.dump(payload, fp)

    def load_checkpoint(self, model: Any, path: str) -> Any:
        with open(path, "rb") as fp:
            payload = pickle.load(fp)
        state = payload.get("model_state", {})
        if hasattr(model, "load_state"):
            model.load_state(state)
        else:
            model.__dict__.update(state)
        return model
