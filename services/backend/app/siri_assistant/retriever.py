"""
文档检索器

基于 TF-IDF 的轻量级文档检索引擎，支持读取 docs/ 目录和 Helper.md 知识库。
提供关键词匹配、TF-IDF 相似度计算等检索能力。
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import math

from .config import siri_config

logger = logging.getLogger(__name__)


class DocumentRetriever:
    """文档检索器

    使用 TF-IDF 算法对文档进行索引和检索。
    支持 docs/ 目录下的 Markdown 文件读取和 Helper.md 知识库解析。
    """

    def __init__(self):
        self._documents: list[dict] = []           # 文档列表 [{content, source, title}]
        self._tfidf_index: dict[str, dict[str, float]] = {}  # TF-IDF 索引
        self._doc_freq: dict[str, int] = defaultdict(int)    # 文档频率
        self._total_docs: int = 0
        self._initialized: bool = False

    def initialize(self) -> bool:
        """初始化检索器，加载文档索引

        Returns:
            是否成功初始化
        """
        try:
            self._load_documents()
            self._build_index()
            self._initialized = True
            logger.info(f"检索器初始化完成: {self._total_docs} 个文档片段")
            return True
        except Exception as e:
            logger.error(f"检索器初始化失败: {e}")
            self._initialized = False
            return False

    def refresh(self) -> bool:
        """刷新索引（从磁盘重新加载文档，用于知识库更新后）"""
        logger.info("刷新检索器索引...")
        return self.initialize()

    def _load_documents(self):
        """加载所有文档"""
        self._documents = []
        docs_dir = siri_config.DOCS_DIR

        # 加载 Helper.md 知识库
        if siri_config.HELPER_FILE.exists():
            self._load_helper_md(siri_config.HELPER_FILE)

        # 加载 docs/ 目录下的 Markdown 文件
        if docs_dir.exists():
            self._load_docs_directory(docs_dir)

        # 去重
        seen = set()
        unique_docs = []
        for doc in self._documents:
            key = doc["content"][:200]
            if key not in seen:
                seen.add(key)
                unique_docs.append(doc)
        self._documents = unique_docs
        self._total_docs = len(self._documents)

    def _load_helper_md(self, filepath: Path):
        """解析 Helper.md 知识库（Q&A 格式）"""
        try:
            content = filepath.read_text(encoding="utf-8")
            # 解析 Q&A 条目
            entries = re.split(r'\n(?=### Q:)', content)
            for entry in entries:
                entry = entry.strip()
                if not entry or not entry.startswith("### Q:"):
                    continue
                # 提取问题标题和答案
                q_match = re.search(r'### Q:\s*(.+?)(?:\n|$)', entry)
                a_match = re.search(r'\*\*A:\*\*\s*(.+)', entry, re.DOTALL)

                if q_match:
                    title = q_match.group(1).strip()
                    question = entry
                    answer = a_match.group(1).strip() if a_match else ""

                    self._documents.append({
                        "content": f"Q: {title}\nA: {answer}",
                        "source": str(filepath.name),
                        "title": title,
                        "type": "helper_qa"
                    })
        except Exception as e:
            logger.warning(f"解析 Helper.md 失败: {e}")

    def _load_docs_directory(self, docs_dir: Path, max_depth: int = 2):
        """加载 docs/ 目录下的 Markdown 文件"""
        for filepath in docs_dir.rglob("*.md"):
            # 限制深度避免过深递归
            relative_depth = len(filepath.relative_to(docs_dir).parts)
            if relative_depth > max_depth:
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                if len(content) < 10:
                    continue
                # 将长文档分段
                chunks = self._chunk_document(content, max_chunk_size=1000)
                for i, chunk in enumerate(chunks):
                    self._documents.append({
                        "content": chunk,
                        "source": str(filepath.relative_to(docs_dir)),
                        "title": filepath.stem,
                        "type": "doc_chunk",
                        "chunk_index": i
                    })
            except Exception as e:
                logger.debug(f"跳过文件 {filepath}: {e}")

    @staticmethod
    def _chunk_document(content: str, max_chunk_size: int = 1000) -> list[str]:
        """将长文档分段"""
        # 按段落分割
        paragraphs = content.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _tokenize(self, text: str) -> list[str]:
        """中文+英文分词"""
        # 中文字符单独切分，英文按空格和标点
        tokens = []
        # 先提取中文词（连续中文）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        for c in chinese_chars:
            # 对中文进行2-gram切分
            for i in range(len(c)):
                if i + 1 < len(c):
                    tokens.append(c[i:i+2])
                tokens.append(c[i])

        # 英文词
        english_words = re.findall(r'[a-zA-Z0-9]+', text)
        tokens.extend(w.lower() for w in english_words)

        return tokens

    def _build_index(self):
        """构建 TF-IDF 索引"""
        self._doc_freq = defaultdict(int)
        doc_tokens = []

        for doc in self._documents:
            tokens = self._tokenize(doc["content"])
            # 去重用于 IDF 计算
            unique_tokens = set(tokens)
            doc_tokens.append(tokens)

            for token in unique_tokens:
                self._doc_freq[token] += 1

        # 计算 IDF
        idf = {}
        N = max(self._total_docs, 1)
        for token, freq in self._doc_freq.items():
            idf[token] = math.log((N + 1) / (freq + 1)) + 1

        # 计算每个文档的 TF-IDF 向量
        self._tfidf_index = {}
        for i, tokens in enumerate(doc_tokens):
            tf = defaultdict(int)
            for token in tokens:
                tf[token] += 1

            max_tf = max(tf.values()) if tf else 1
            tfidf_vector = {}
            for token, count in tf.items():
                tfidf_vector[token] = (count / max_tf) * idf.get(token, 0)

            self._tfidf_index[str(i)] = tfidf_vector

    def search(self, query: str, top_k: int = None) -> list[dict]:
        """检索与查询最相关的文档

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            [{content, source, relevance_score, title}, ...]
        """
        if not self._initialized:
            self.initialize()

        if top_k is None:
            top_k = siri_config.MAX_RETRIEVAL_RESULTS

        if not self._documents:
            return []

        # 计算查询 TF 向量
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        tf = defaultdict(int)
        for token in query_tokens:
            tf[token] += 1

        # 计算每个文档的余弦相似度
        scores = []
        query_norm = math.sqrt(sum(tf.values()))

        for i, doc in enumerate(self._documents):
            doc_vector = self._tfidf_index.get(str(i), {})
            if not doc_vector:
                continue

            # 点积
            dot_product = sum(tf.get(token, 0) * weight for token, weight in doc_vector.items())

            doc_norm = math.sqrt(sum(w * w for w in doc_vector.values()))

            if query_norm > 0 and doc_norm > 0:
                similarity = dot_product / (query_norm * doc_norm)
            else:
                similarity = 0.0

            # 额外奖励：直接关键词匹配
            keyword_bonus = 0.0
            query_lower = query.lower()
            doc_content_lower = doc["content"].lower()
            # 精确短语匹配
            if query_lower in doc_content_lower:
                keyword_bonus = 0.3

            scores.append({
                "content": doc["content"],
                "source": doc["source"],
                "title": doc.get("title", ""),
                "relevance_score": min(similarity + keyword_bonus, 1.0),
                "type": doc.get("type", "doc_chunk"),
                "index": i
            })

        # 按相关性排序
        scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scores[:top_k]

    def search_with_threshold(self, query: str, threshold: float = 0.1, top_k: int = None) -> list[dict]:
        """带阈值过滤的检索"""
        results = self.search(query, top_k=top_k)
        return [r for r in results if r["relevance_score"] >= threshold]

    def get_knowledge_entries(self) -> list[dict]:
        """获取知识库中的所有 Q&A 条目"""
        return [d for d in self._documents if d.get("type") == "helper_qa"]

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def document_count(self) -> int:
        return self._total_docs


# 全局检索器实例
retriever = DocumentRetriever()
