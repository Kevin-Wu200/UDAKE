"""
任务持久化
提供任务存储接口和文件系统实现
"""
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class TaskStorage(ABC):
    """任务存储接口"""

    @abstractmethod
    async def save_task(self, task_id: str, task_data: Dict):
        """保存任务"""
        pass

    @abstractmethod
    async def load_task(self, task_id: str) -> Optional[Dict]:
        """加载任务"""
        pass

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        pass

    @abstractmethod
    async def list_tasks(self, status: str = None) -> List[Dict]:
        """列出任务"""
        pass


class FileTaskStorage(TaskStorage):
    """文件系统任务存储"""

    def __init__(self, storage_dir: str = "tasks"):
        """
        初始化文件存储

        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _get_task_path(self, task_id: str) -> str:
        """获取任务文件路径"""
        return os.path.join(self.storage_dir, f"{task_id}.json")

    async def save_task(self, task_id: str, task_data: Dict):
        """保存任务"""
        task_path = self._get_task_path(task_id)
        with open(task_path, 'w') as f:
            json.dump(task_data, f, indent=2, default=str)

    async def load_task(self, task_id: str) -> Optional[Dict]:
        """加载任务"""
        task_path = self._get_task_path(task_id)
        if not os.path.exists(task_path):
            return None

        with open(task_path, 'r') as f:
            return json.load(f)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        task_path = self._get_task_path(task_id)
        if os.path.exists(task_path):
            os.remove(task_path)
            return True
        return False

    async def list_tasks(self, status: str = None) -> List[Dict]:
        """列出任务"""
        tasks = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                task_id = filename[:-5]
                task = await self.load_task(task_id)
                if task:
                    if status is None or task.get('status') == status:
                        tasks.append(task)
        return tasks

    async def cleanup_old_tasks(self, days: int = 7):
        """
        清理旧任务

        Args:
            days: 保留天数
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                task_path = os.path.join(self.storage_dir, filename)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(task_path))

                if file_mtime < cutoff_date:
                    os.remove(task_path)
