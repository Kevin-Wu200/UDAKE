"""
目标函数基类
Base Objective Function class
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, Any
from ..core.population import Individual


class BaseObjective(ABC):
    """
    目标函数基类
    Base class for objective functions
    """

    def __init__(self, name: str, weight: float = 1.0, direction: str = 'minimize'):
        """
        初始化目标函数

        Args:
            name: 目标函数名称
            weight: 权重系数
            direction: 优化方向 ('minimize' 或 'maximize')
        """
        self.name = name
        self.weight = weight
        self.direction = direction

    @abstractmethod
    def evaluate(self, individual: Individual) -> float:
        """
        评估个体的目标函数值

        Args:
            individual: 个体

        Returns:
            float: 目标函数值
        """
        pass

    def normalize(self, value: float, min_val: float, max_val: float) -> float:
        """
        归一化目标函数值到[0, 1]

        Args:
            value: 原始值
            min_val: 最小值
            max_val: 最大值

        Returns:
            float: 归一化后的值
        """
        if max_val == min_val:
            return 0.0
        return (value - min_val) / (max_val - min_val)

    def get_weighted_value(self, value: float) -> float:
        """
        获取加权后的目标函数值

        Args:
            value: 目标函数值

        Returns:
            float: 加权后的值
        """
        return value * self.weight

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', weight={self.weight}, direction='{self.direction}')"