"""
Ollama LLM 客户端

通过 HTTP REST API 与本地 Ollama 服务通信。
支持 Qwen3:8b 等模型的对话生成和 RAG 提示词注入。
"""

import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from .config import siri_config

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama HTTP 客户端

    封装与 Ollama 服务的通信，支持：
    - 同步/异步对话生成
    - 流式输出
    - 健康检查
    """

    def __init__(self):
        self._host = siri_config.OLLAMA_HOST.rstrip("/")
        self._model = siri_config.OLLAMA_MODEL
        self._timeout = httpx.Timeout(siri_config.OLLAMA_REQUEST_TIMEOUT)
        self._available: Optional[bool] = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def model(self) -> str:
        return self._model

    async def check_health(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self._host}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    # 检查目标模型是否已下载
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_available = any(self._model in m for m in models)
                    self._available = model_available
                    if model_available:
                        logger.info(f"Ollama 服务正常，模型 {self._model} 可用")
                    else:
                        logger.warning(f"模型 {self._model} 未找到，可用模型: {models}")
                    return model_available
                self._available = False
                return False
        except Exception as e:
            logger.warning(f"Ollama 服务不可用: {e}")
            self._available = False
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """生成对话响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            stream: 是否流式

        Returns:
            生成的文本
        """
        if temperature is None:
            temperature = siri_config.OLLAMA_TEMPERATURE
        if max_tokens is None:
            max_tokens = siri_config.OLLAMA_MAX_TOKENS

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        # qwen3 系列模型禁用 thinking 模式以加速响应
        if "qwen3" in self._model.lower():
            payload["options"]["enable_thinking"] = False

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._host}/api/chat",
                    json=payload,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("content", "")
                else:
                    logger.error(f"Ollama API 错误: {response.status_code} - {response.text}")
                    return ""
        except httpx.TimeoutException:
            logger.error("Ollama 请求超时")
            return ""
        except Exception as e:
            logger.error(f"Ollama 请求失败: {e}")
            return ""

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成对话响应

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Yields:
            每次生成的文本片段
        """
        if temperature is None:
            temperature = siri_config.OLLAMA_TEMPERATURE
        if max_tokens is None:
            max_tokens = siri_config.OLLAMA_MAX_TOKENS

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        # qwen3 系列模型禁用 thinking 模式以加速响应
        if "qwen3" in self._model.lower():
            payload["options"]["enable_thinking"] = False

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", f"{self._host}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        logger.error(f"Ollama 流式请求失败: {response.status_code}")
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Ollama 流式请求失败: {e}")

    def build_rag_prompt(
        self,
        query: str,
        retrieved_docs: list[dict],
        context: Optional[str] = None,
    ) -> str:
        """构建 RAG 增强提示词

        将检索到的文档内容注入到提示词中。

        Args:
            query: 用户查询
            retrieved_docs: 检索到的文档列表
            context: 额外上下文

        Returns:
            增强后的提示词
        """
        prompt_parts = ["请基于以下文档内容回答问题。如果文档中没有相关信息，请明确告知用户。\n"]

        if retrieved_docs:
            prompt_parts.append("## 参考文档\n")
            for i, doc in enumerate(retrieved_docs[:siri_config.MAX_RETRIEVAL_RESULTS], 1):
                source = doc.get("source", "未知")
                content = doc.get("content", "")[:800]  # 限制每段长度
                prompt_parts.append(f"【文档{i} - 来源: {source}】\n{content}\n")

        if context:
            prompt_parts.append(f"## 上下文信息\n{context}\n")

        prompt_parts.append(f"## 用户问题\n{query}\n")
        prompt_parts.append("## 请回答\n")

        return "\n".join(prompt_parts)

    @property
    def is_available(self) -> Optional[bool]:
        """Ollama 是否可用（None 表示未检查）"""
        return self._available


# 全局 Ollama 客户端实例
ollama_client = OllamaClient()
