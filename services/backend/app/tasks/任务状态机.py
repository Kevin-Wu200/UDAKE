"""
任务状态机
"""
from enum import Enum
from typing import Dict, Set


class TaskState(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskStateMachine:
    """任务状态机"""

    # 状态转换规则
    TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
        TaskState.PENDING: {TaskState.RUNNING, TaskState.CANCELLED},
        TaskState.RUNNING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED},
        TaskState.COMPLETED: set(),
        TaskState.FAILED: set(),
        TaskState.CANCELLED: set()
    }

    def __init__(self, initial_state: TaskState = TaskState.PENDING):
        self.current_state = initial_state

    def can_transition(self, new_state: TaskState) -> bool:
        """检查是否可以转换到新状态"""
        return new_state in self.TRANSITIONS.get(self.current_state, set())

    def transition(self, new_state: TaskState) -> bool:
        """转换状态"""
        if self.can_transition(new_state):
            self.current_state = new_state
            return True
        return False

    def is_terminal(self) -> bool:
        """检查是否为终止状态"""
        return self.current_state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED
        }
