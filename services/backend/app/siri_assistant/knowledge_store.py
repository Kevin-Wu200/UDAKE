"""
知识库读写管理

实现 Helper.md 的知识库原子化读写操作。
- 读取解析 Helper.md 中的 Q&A 条目
- 追加新 Q&A 条目（原子化文件写入）
- 支持条目的分类和索引
"""

import fcntl
import logging
import os
import platform
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import siri_config

logger = logging.getLogger(__name__)

# Windows 平台 fcntl 不可用，使用替代方案
_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    import msvcrt


def _acquire_file_lock(file_handle) -> bool:
    """跨平台文件锁获取"""
    try:
        if _IS_WINDOWS:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
        return True
    except Exception as e:
        logger.warning(f"获取文件锁失败: {e}")
        return False


def _release_file_lock(file_handle):
    """跨平台文件锁释放"""
    try:
        if _IS_WINDOWS:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


class KnowledgeStore:
    """知识库管理器

    管理 docs/Helper.md 文件的读写操作。
    采用文件锁确保多进程安全。
    """

    def __init__(self):
        self._filepath = siri_config.HELPER_FILE
        self._entries_cache: list[dict] = []
        self._cache_time: Optional[datetime] = None

    def ensure_file_exists(self) -> bool:
        """确保 Helper.md 文件存在，不存在则创建模板"""
        if self._filepath.exists():
            return True

        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            template = siri_config.HELPER_TEMPLATE.format(
                update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                entries=""
            )
            self._filepath.write_text(template, encoding="utf-8")
            logger.info(f"创建 Helper.md 知识库: {self._filepath}")
            return True
        except Exception as e:
            logger.error(f"创建 Helper.md 失败: {e}")
            return False

    def read_entries(self, force_reload: bool = False) -> list[dict]:
        """读取所有 Q&A 条目

        Args:
            force_reload: 是否强制重新读取

        Returns:
            [{question, answer, category, title}, ...]
        """
        # 缓存检查
        if not force_reload and self._entries_cache and self._cache_time:
            mtime = self._filepath.stat().st_mtime if self._filepath.exists() else 0
            if mtime <= self._cache_time.timestamp():
                return self._entries_cache

        if not self._filepath.exists():
            return []

        try:
            content = self._filepath.read_text(encoding="utf-8")
            entries = self._parse_entries(content)
            self._entries_cache = entries
            self._cache_time = datetime.now()
            return entries
        except Exception as e:
            logger.error(f"读取 Helper.md 失败: {e}")
            return self._entries_cache if self._entries_cache else []

    def _parse_entries(self, content: str) -> list[dict]:
        """解析 Helper.md 内容中的 Q&A 条目"""
        entries = []
        # 匹配格式: ### Q: 标题\n问题内容\n**A:** 答案
        pattern = r'### Q:\s*(.+?)\n(.*?)\n\*\*A:\*\*\s*(.+?)(?=\n### Q:|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        for title, question, answer in matches:
            entries.append({
                "title": title.strip(),
                "question": question.strip(),
                "answer": answer.strip(),
                "category": "general",
            })

        return entries

    def add_entry(self, question: str, answer: str, category: str = "general") -> bool:
        """向 Helper.md 追加新 Q&A 条目（原子化操作）

        Args:
            question: 问题
            answer: 答案
            category: 分类标签

        Returns:
            是否成功追加
        """
        if not self.ensure_file_exists():
            return False

        entry_text = siri_config.HELPER_ENTRY_TEMPLATE.format(
            title=question[:50],
            question=question,
            answer=answer,
        )

        try:
            # 使用文件锁实现原子化写入
            with open(self._filepath, "r+", encoding="utf-8") as f:
                # 获取排他锁
                if not _acquire_file_lock(f):
                    return False

                try:
                    content = f.read()

                    # 检查文件大小
                    if len(content.encode("utf-8")) > siri_config.HELPER_MAX_FILE_SIZE_MB * 1024 * 1024:
                        logger.warning(f"Helper.md 超过大小限制 ({siri_config.HELPER_MAX_FILE_SIZE_MB}MB)")
                        _release_file_lock(f)
                        return False

                    # 检查条目是否已存在
                    if question.strip() in content:
                        logger.info(f"条目已存在，跳过: {question[:50]}")
                        _release_file_lock(f)
                        return True

                    # 在末尾追加新条目
                    content = content.rstrip() + "\n\n" + entry_text + "\n"

                    # 更新最后修改时间
                    update_line = f"> 最后更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    content = re.sub(
                        r'> 最后更新时间: .+',
                        update_line,
                        content
                    )

                    f.seek(0)
                    f.write(content)
                    f.truncate()
                finally:
                    _release_file_lock(f)

            # 清除缓存
            self._entries_cache = []
            self._cache_time = None

            logger.info(f"成功追加知识库条目: {question[:50]}")
            return True

        except Exception as e:
            logger.error(f"追加知识库条目失败: {e}")
            return False

    def search_entries(self, query: str) -> list[dict]:
        """在 Helper.md 中搜索相关条目

        Args:
            query: 搜索关键词

        Returns:
            匹配的条目列表
        """
        entries = self.read_entries()
        results = []

        query_lower = query.lower()
        for entry in entries:
            score = 0
            if query_lower in entry["question"].lower():
                score += 3
            if query_lower in entry["answer"].lower():
                score += 1
            if query_lower in entry["title"].lower():
                score += 2

            if score > 0:
                results.append({**entry, "relevance_score": min(score / 6.0, 1.0)})

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    def get_statistics(self) -> dict:
        """获取知识库统计信息"""
        entries = self.read_entries()
        file_exists = self._filepath.exists()
        file_size = self._filepath.stat().st_size if file_exists else 0

        categories = {}
        for entry in entries:
            cat = entry.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "file_path": str(self._filepath),
            "file_exists": file_exists,
            "file_size_bytes": file_size,
            "total_entries": len(entries),
            "categories": categories,
            "last_updated": datetime.fromtimestamp(self._filepath.stat().st_mtime).isoformat() if file_exists else None,
        }

    @property
    def filepath(self) -> Path:
        return self._filepath


# 全局知识库实例
knowledge_store = KnowledgeStore()
