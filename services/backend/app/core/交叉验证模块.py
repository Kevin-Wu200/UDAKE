"""
交叉验证模块
"""
import logging
from typing import Dict

import numpy as np
from pykrige.ok import OrdinaryKriging
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

from ..schemas.插值参数模型 import KrigingParameters

logger = logging.getLogger(__name__)

class CrossValidator:
    """交叉验证器"""

    def validate(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray,
        params: KrigingParameters
    ) -> Dict[str, float]:
        """
        执行K折交叉验证
        """
        kf = KFold(n_splits=params.n_folds, shuffle=True, random_state=42)

        predictions = []
        actuals = []

        for train_idx, test_idx in kf.split(x):
            # 训练集和测试集
            x_train, x_test = x[train_idx], x[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            values_train, values_test = values[train_idx], values[test_idx]

            try:
                # 创建克里金模型
                ok = OrdinaryKriging(
                    x_train, y_train, values_train,
                    variogram_model=params.variogram_model.value,
                    nlags=params.nlags,
                    enable_plotting=False
                )

                # 预测测试集
                z, _ = ok.execute('points', x_test, y_test)

                predictions.extend(z)
                actuals.extend(values_test)

            except Exception as e:
                logger.warning(f"交叉验证折失败: {str(e)}")
                continue

        if len(predictions) == 0:
            return {
                "rmse": 0.0,
                "mae": 0.0,
                "r2": 0.0,
                "mse": 0.0
            }

        predictions = np.array(predictions)
        actuals = np.array(actuals)

        # 计算指标
        mse = mean_squared_error(actuals, predictions)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(actuals, predictions)
        r2 = r2_score(actuals, predictions)

        return {
            "rmse": float(rmse),
            "mae": float(mae),
            "r2": float(r2),
            "mse": float(mse)
        }
