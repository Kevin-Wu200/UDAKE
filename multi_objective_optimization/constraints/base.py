"""
约束条件基类
Base Constraint class
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..core.population import Individual


class BaseConstraint(ABC):
    """
    约束条件基类
    Base class for constraints
    """

    def __init__(self, name: str):
        """
        初始化约束条件

        Args:
            name: 约束条件名称
        """
        self.name = name

    @abstractmethod
    def evaluate(self, individual: Individual) -> float:
        """
        评估个体违反约束的程度

        Args:
            individual: 个体

        Returns:
            float: 违反程度（0表示满足，>0表示违反）
        """
        pass

    def is_satisfied(self, individual: Individual) -> bool:
        """
        判断个体是否满足约束

        Args:
            individual: 个体

        Returns:
            bool: 满足返回True，否则返回False
        """
        return self.evaluate(individual) == 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"