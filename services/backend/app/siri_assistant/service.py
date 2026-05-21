"""
Siri 助手核心服务

整合检索、LLM、安全、意图识别等模块，提供统一的智能交互服务。
"""

import json
import logging
import time
import uuid
from typing import Optional

from .config import siri_config
from .intent_parser import intent_parser
from .knowledge_store import knowledge_store
from .llm_client import ollama_client
from .models import (
    FunctionCallSuggestion,
    FunctionTarget,
    IntentType,
    InteractionLogEntry,
    SiriAssistantResponse,
    SiriFeedbackRequest,
    SiriQueryRequest,
    RetrievedDocument,
)
from .retriever import retriever
from .security import security

logger = logging.getLogger(__name__)


class SiriAssistantService:
    """Siri 助手核心服务

    处理用户查询的完整流水线：
    1. 安全检查 → 2. 意图识别 → 3. 文档检索 → 4. LLM 生成 → 5. 响应组装
    """

    _instance: Optional["SiriAssistantService"] = None
    _ollama_available: Optional[bool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self) -> bool:
        """初始化服务（异步安全的同步初始化）"""
        if self._initialized:
            return True

        try:
            # 确保知识库文件存在
            knowledge_store.ensure_file_exists()

            # 初始化文档检索器
            retriever.initialize()

            self._initialized = True
            logger.info("Siri 助手服务初始化完成")
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def ensure_ollama_available(self) -> bool:
        """确保 Ollama 可用（懒加载）"""
        if self._ollama_available is not None:
            return self._ollama_available
        self._ollama_available = await ollama_client.check_health()
        return self._ollama_available

    async def process_query(self, request: SiriQueryRequest) -> SiriAssistantResponse:
        """处理用户查询的主入口

        Args:
            request: 查询请求

        Returns:
            助手响应
        """
        start_time = time.time()
        session_id = request.session_id or str(uuid.uuid4())[:8]

        # 1. 安全检查
        is_safe, rejection_msg = security.validate_input(request.query)
        if not is_safe:
            return SiriAssistantResponse(
                success=True,
                intent=IntentType.UNKNOWN,
                answer=rejection_msg,
                fallback=True,
                session_id=session_id,
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # 2. 意图识别
        intent_result = await intent_parser.parse_intent(request.query)
        intent = intent_result["intent"]

        # 3. 根据意图分流处理
        if intent == IntentType.GENERAL_CHAT:
            return await self._handle_chat(request.query, session_id, start_time)

        elif intent == IntentType.FUNCTION_CALL:
            return await self._handle_function_call(
                request.query, intent_result, session_id, start_time
            )

        elif intent == IntentType.KNOWLEDGE_QUERY:
            return await self._handle_knowledge_query(
                request.query, intent_result, session_id, start_time
            )

        else:
            # UNKNOWN: 回退到知识库检索
            return await self._handle_knowledge_query(
                request.query, intent_result, session_id, start_time
            )

    async def _handle_chat(
        self, query: str, session_id: str, start_time: float
    ) -> SiriAssistantResponse:
        """处理一般对话"""
        # 规则匹配快速回复
        quick_responses = {
            "你好": "您好！我是 UDAKE 小U，您的智能助手。有什么可以帮助您的吗？",
            "hi": "Hi! 我是 UDAKE 小U，有什么可以帮您？",
            "hello": "Hello! 我是 UDAKE 小U，How can I help you today?",
            "谢谢": "不客气！很高兴能帮到您。",
            "thanks": "You're welcome!",
            "再见": "再见！祝您使用愉快！",
            "你是谁": "我是 UDAKE 小U，一个专为 UDAKE 空间决策平台打造的智能助手。我可以帮您解答技术问题、操作指导，还能帮您执行系统功能（如开始插值计算、查看结果等）。",
            "你能做什么": "我可以：\n1. 解答 UDAKE 平台的技术问题和操作指南\n2. 帮您执行系统功能（如开始插值计算、上传数据、导出结果等）\n3. 提供文档检索和知识查询\n4. 引导您完成空间数据分析工作流",
        }

        query_lower = query.lower().strip()
        for key, response_text in quick_responses.items():
            if key in query_lower:
                return SiriAssistantResponse(
                    success=True,
                    intent=IntentType.GENERAL_CHAT,
                    answer=response_text,
                    session_id=session_id,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

        # LLM 生成
        ollama_ok = await self.ensure_ollama_available()
        if ollama_ok:
            answer = await ollama_client.generate(
                prompt=query,
                system_prompt=security.get_system_prompt(),
            )
            answer = security.sanitize_response(answer)
        else:
            answer = "您好！我是 UDAKE 小U。我注意到 Ollama 服务当前不可用，但您仍可以向我提问 UDAKE 相关问题，我会从文档库中查找答案。"

        return SiriAssistantResponse(
            success=True,
            intent=IntentType.GENERAL_CHAT,
            answer=answer or "你好！有什么可以帮你的吗？",
            session_id=session_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    async def _handle_knowledge_query(
        self, query: str, intent_result: dict, session_id: str, start_time: float
    ) -> SiriAssistantResponse:
        """处理知识查询"""
        # 检索文档
        search_results = retriever.search_with_threshold(query, threshold=0.05)

        retrieved_docs = [
            RetrievedDocument(
                content=doc["content"][:600],
                source=doc["source"],
                relevance_score=doc["relevance_score"],
                title=doc.get("title"),
            )
            for doc in search_results
        ]

        # 如果检索到相关内容，使用 RAG 生成回答
        ollama_ok = await self.ensure_ollama_available()
        if ollama_ok and retrieved_docs:
            rag_prompt = ollama_client.build_rag_prompt(
                query=query,
                retrieved_docs=search_results,
            )
            answer = await ollama_client.generate(
                prompt=rag_prompt,
                system_prompt=security.get_system_prompt(),
            )
            answer = security.sanitize_response(answer)
        elif retrieved_docs:
            # 无 LLM 时直接返回检索到的内容
            top_doc = retrieved_docs[0]
            answer = f"我在文档中找到了相关内容：\n\n```\n{top_doc.content[:500]}\n```\n\n来源: {top_doc.source}"
        else:
            # 无检索结果
            answer = security.get_fallback_response("knowledge_query")
            # 记录未知问题，用于后续自学习
            self._log_unknown_query(query, session_id)

        return SiriAssistantResponse(
            success=True,
            intent=IntentType.KNOWLEDGE_QUERY,
            answer=answer or security.get_fallback_response("knowledge_query"),
            retrieved_docs=retrieved_docs,
            fallback=(not retrieved_docs),
            session_id=session_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    async def _handle_function_call(
        self, query: str, intent_result: dict, session_id: str, start_time: float
    ) -> SiriAssistantResponse:
        """处理功能调用"""
        function_target = intent_result.get("function_target")
        confidence = intent_result.get("confidence", 0.5)

        if not function_target:
            answer = security.get_fallback_response("function_call")
            return SiriAssistantResponse(
                success=True,
                intent=IntentType.FUNCTION_CALL,
                answer=answer,
                fallback=True,
                session_id=session_id,
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # 构建功能调用建议
        func_descriptions = {
            FunctionTarget.START_INTERPOLATION: "开始空间插值计算",
            FunctionTarget.UPLOAD_DATA: "上传采样数据文件",
            FunctionTarget.QUERY_RESULTS: "查询计算结果",
            FunctionTarget.CHECK_TASK_STATUS: "查看任务运行状态",
            FunctionTarget.CONFIGURE_PARAMS: "配置插值参数",
            FunctionTarget.VIEW_DOCS: "查看技术文档",
            FunctionTarget.START_SAMPLING: "开始采样",
            FunctionTarget.EXPORT_RESULTS: "导出计算结果",
            FunctionTarget.MODEL_RECOMMENDATION: "模型推荐",
            FunctionTarget.UNCERTAINTY_ANALYSIS: "不确定性分析",
        }

        description = func_descriptions.get(function_target, function_target.value)
        requires_confirmation = function_target in (
            FunctionTarget.START_INTERPOLATION,
            FunctionTarget.UPLOAD_DATA,
            FunctionTarget.START_SAMPLING,
            FunctionTarget.EXPORT_RESULTS,
        )

        func_suggestion = FunctionCallSuggestion(
            function=function_target,
            params={},
            confidence=confidence,
            description=description,
            requires_confirmation=requires_confirmation,
        )

        # 生成友好回答
        if requires_confirmation:
            answer = f"我理解您想要{description}。是否确认执行此操作？"
        else:
            answer = f"好的，我来帮您{description}。"

        return SiriAssistantResponse(
            success=True,
            intent=IntentType.FUNCTION_CALL,
            answer=answer,
            function_call=func_suggestion,
            session_id=session_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    async def process_feedback(self, feedback: SiriFeedbackRequest) -> bool:
        """处理用户反馈（用于自学习）

        Args:
            feedback: 用户反馈

        Returns:
            是否处理成功
        """
        try:
            # 记录反馈日志
            self._log_feedback(feedback)

            # 如果用户提供了正确答案，自动追加到知识库
            if not feedback.helpful and feedback.corrected_answer:
                knowledge_store.add_entry(
                    question=feedback.query,
                    answer=feedback.corrected_answer,
                )
                logger.info(f"已将用户纠正的答案写入知识库: {feedback.query[:50]}")

            return True
        except Exception as e:
            logger.error(f"处理反馈失败: {e}")
            return False

    async def get_health_status(self) -> dict:
        """获取助手健康状态"""
        ollama_ok = await self.ensure_ollama_available()
        stats = knowledge_store.get_statistics()

        return {
            "initialized": self._initialized,
            "ollama_available": ollama_ok,
            "ollama_model": siri_config.OLLAMA_MODEL,
            "retriever_docs": retriever.document_count,
            "knowledge_entries": stats["total_entries"],
            "knowledge_file": stats["file_path"],
        }

    def _log_unknown_query(self, query: str, session_id: str):
        """记录无法回答的查询（用于自学习）"""
        try:
            log_entry = InteractionLogEntry(
                query=query,
                intent=IntentType.KNOWLEDGE_QUERY,
                response="[无结果]",
                retrieved_count=0,
                processing_time_ms=0.0,
            )
            self._write_log(log_entry)
        except Exception as e:
            logger.debug(f"记录日志失败: {e}")

    def _log_feedback(self, feedback: SiriFeedbackRequest):
        """记录用户反馈"""
        try:
            log_entry = InteractionLogEntry(
                query=feedback.query,
                intent=IntentType.KNOWLEDGE_QUERY,
                response=feedback.response,
                user_feedback=feedback.helpful,
            )
            self._write_log(log_entry)
        except Exception as e:
            logger.debug(f"记录反馈日志失败: {e}")

    def _write_log(self, entry: InteractionLogEntry):
        """写入交互日志"""
        log_dir = siri_config.INTERACTION_LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"interactions_{entry.timestamp.strftime('%Y%m%d')}.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception:
            pass

    def get_function_list(self) -> list[dict]:
        """获取可用的系统功能列表"""
        func_descriptions = {
            FunctionTarget.START_INTERPOLATION: "开始空间插值计算",
            FunctionTarget.UPLOAD_DATA: "上传采样数据文件",
            FunctionTarget.QUERY_RESULTS: "查询计算结果",
            FunctionTarget.CHECK_TASK_STATUS: "查看任务运行状态",
            FunctionTarget.CONFIGURE_PARAMS: "配置插值参数",
            FunctionTarget.VIEW_DOCS: "查看技术文档",
            FunctionTarget.START_SAMPLING: "开始采样",
            FunctionTarget.EXPORT_RESULTS: "导出计算结果",
            FunctionTarget.MODEL_RECOMMENDATION: "模型推荐",
            FunctionTarget.UNCERTAINTY_ANALYSIS: "不确定性分析",
        }
        return [
            {"function": f.value, "description": d, "requires_confirmation": f in (
                FunctionTarget.START_INTERPOLATION,
                FunctionTarget.UPLOAD_DATA,
                FunctionTarget.START_SAMPLING,
                FunctionTarget.EXPORT_RESULTS,
            )}
            for f, d in func_descriptions.items()
        ]


# 全局服务实例
siri_service = SiriAssistantService()
