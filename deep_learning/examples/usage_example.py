"""深度学习基础架构使用示例。"""

from deep_learning.config import ConfigLoader
from deep_learning.inference import BatchPredictor


class DemoModel:
    def predict(self, batch: list[list[float]]) -> list[float]:
        return [sum(row) / max(1, len(row)) for row in batch]


if __name__ == "__main__":
    cfg = ConfigLoader().load("deep_learning/config/model_config.yaml")
    predictor = BatchPredictor(DemoModel())
    print("model:", cfg["model"]["name"])
    print("predictions:", predictor.predict([[1.0, 2.0], [3.0, 4.0]]))
