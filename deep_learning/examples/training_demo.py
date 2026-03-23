"""训练链路示例。"""

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


if __name__ == "__main__":
    model = DummyModel()
    trainer = LightningTrainer(TrainingConfig(max_epochs=20, learning_rate=0.05, early_stopping_patience=3))
    samples = [[0.1, 1.0], [0.2, 0.9], [0.3, 1.1]]
    result = trainer.train(model, [samples], [samples])
    print(result)
