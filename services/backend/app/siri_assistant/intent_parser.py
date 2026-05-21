"""
意图识别与分类器

解析用户自然语言输入，区分知识查询、功能调用和一般对话。
"""

import json
import logging
import re
from typing import Optional

from .config import siri_config
from .llm_client import ollama_client
from .models import IntentType, FunctionTarget

logger = logging.getLogger(__name__)


# --- 功能调用关键词映射 ---
FUNCTION_KEYWORDS: dict[FunctionTarget, list[str]] = {
    FunctionTarget.START_INTERPOLATION: [
        "插值", "计算", "kriging", "克里金", "空间插值", "开始计算",
        "运行插值", "执行插值", "做插值"
    ],
    FunctionTarget.UPLOAD_DATA: [
        "上传", "导入", "加载数据", "读取文件", "导入数据",
    ],
    FunctionTarget.QUERY_RESULTS: [
        "查看结果", "查询结果", "结果", "输出", "计算结果",
    ],
    FunctionTarget.CHECK_TASK_STATUS: [
        "任务状态", "进度", "运行状态", "任务", "进行中",
    ],
    FunctionTarget.CONFIGURE_PARAMS: [
        "配置", "设置参数", "参数", "调整", "修改参数",
    ],
    FunctionTarget.VIEW_DOCS: [
        "文档", "帮助", "手册", "教程", "使用说明", "api文档",
    ],
    FunctionTarget.START_SAMPLING: [
        "采样", "样本", "取样", "抽样",
    ],
    FunctionTarget.EXPORT_RESULTS: [
        "导出", "下载", "保存结果", "输出文件",
    ],
    FunctionTarget.MODEL_RECOMMENDATION: [
        "模型推荐", "推荐模型", "哪个模型", "选择模型", "模型选择",
    ],
    FunctionTarget.UNCERTAINTY_ANALYSIS: [
        "不确定性", "误差", "风险", "不确定性分析", "置信度",
    ],
}

# --- 知识查询关键词 ---
KNOWLEDGE_KEYWORDS = [
    "什么是", "如何", "怎么", "怎样", "为什么", "是什么",
    "解释", "说明", "介绍", "原理", "方法", "步骤",
    "区别", "比较", "区别是", "有什么不同",
    "文档", "指南", "教程", "手册",
    "哪些", "哪个", "那种", "几种",
    "支持", "能不能", "可以", "是否",
    "有没有", "有没有", "怎么做", "如何做",
]

# --- 知识查询句式模式（正则，比关键词优先级更高） ---
KNOWLEDGE_QUERY_PATTERNS = [
    re.compile(r"(?:什么|哪些|哪[个种些]|几[种个]).{0,10}(?:方法|模型|类型|功能|格式|步骤|参数)"),
    re.compile(r"(?:如何|怎么|怎样|能不能|可以|是否).{0,5}(?:用|做|实现|操作|配置|设置|开始)"),
    re.compile(r"(?:支持|兼容).{0,10}(?:哪些|什么|多少|几种)"),
    re.compile(r"(?:有什么|有哪些).*(?:区别|不同|特点|优势|缺点)"),
]

# --- 闲聊关键词 ---
CHAT_KEYWORDS = [
    "你好", "嗨", "谢谢", "再见", "你是谁", "你能做什么",
    "帮助", "hello", "hi", "thanks",
]


class IntentParser:
    """意图识别与分类器

    使用关键词匹配 + LLM 辅助识别用户意图。
    优先使用关键词规则（快速），复杂情况回退到 LLM 分类。
    """

    def __init__(self):
        pass

    async def parse_intent(self, query: str) -> dict:
        """解析用户查询意图

        Args:
            query: 用户输入文本

        Returns:
            {
                "intent": IntentType,
                "function_target": Optional[FunctionTarget],
                "confidence": float,
                "params": dict,
                "requires_llm": bool  # 是否需要 LLM 辅助
            }
        """
        query_lower = query.lower().strip()

        # 1. 规则匹配 - 闲聊
        for keyword in CHAT_KEYWORDS:
            if keyword in query_lower:
                return {
                    "intent": IntentType.GENERAL_CHAT,
                    "function_target": None,
                    "confidence": 0.9,
                    "params": {},
                    "requires_llm": False
                }

        # 2. 规则匹配 - 知识查询（优先级高于功能调用，避免 "支持哪些方法" 误判）
        for keyword in KNOWLEDGE_KEYWORDS:
            if keyword in query_lower:
                return {
                    "intent": IntentType.KNOWLEDGE_QUERY,
                    "function_target": None,
                    "confidence": 0.7,
                    "params": {},
                    "requires_llm": True
                }

        # 2b. 知识查询句式匹配
        for pattern in KNOWLEDGE_QUERY_PATTERNS:
            if pattern.search(query_lower):
                return {
                    "intent": IntentType.KNOWLEDGE_QUERY,
                    "function_target": None,
                    "confidence": 0.8,
                    "params": {},
                    "requires_llm": True
                }

        # 3. 规则匹配 - 功能调用
        best_function = None
        best_score = 0
        for func, keywords in FUNCTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_function = func

        if best_score >= 1 and best_function:
            return {
                "intent": IntentType.FUNCTION_CALL,
                "function_target": best_function,
                "confidence": min(best_score * 0.25, 0.95),
                "params": {},
                "requires_llm": False
            }

        # 3. 规则匹配 - 知识查询
        for keyword in KNOWLEDGE_KEYWORDS:
            if keyword in query_lower:
                return {
                    "intent": IntentType.KNOWLEDGE_QUERY,
                    "function_target": None,
                    "confidence": 0.7,
                    "params": {},
                    "requires_llm": True
                }

        # 4. LLM 辅助分类（处理模糊意图）
        try:
            llm_result = await self._llm_classify(query)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.warning(f"LLM 分类失败: {e}")

        # 5. 默认：知识查询（库内检索兜底）
        return {
            "intent": IntentType.KNOWLEDGE_QUERY,
            "function_target": None,
            "confidence": 0.3,
            "params": {},
            "requires_llm": True
        }

    async def _llm_classify(self, query: str) -> Optional[dict]:
        """使用 LLM 进行意图分类"""
        prompt = f"""分析以下用户输入，判断用户意图类型。

意图类型：
- knowledge_query: 用户想了解 UDAKE 平台的知识、文档、使用方法等
- function_call: 用户想执行某个操作（如开始插值、上传数据、查询结果等）
- general_chat: 一般性对话（问候、闲聊等）

可用功能列表：{', '.join(f.value for f in FunctionTarget)}

请以 JSON 格式返回：
{{"intent": "...", "function_target": "..." or null, "confidence": 0.0-1.0}}

用户输入: {query}

仅返回 JSON，不要包含其他内容。"""

        response = await ollama_client.generate(
            prompt=prompt,
            system_prompt="你是一个文本分类器，只返回 JSON 格式结果。",
            temperature=0.1,
            max_tokens=100,
        )

        if response:
            # 提取 JSON
            json_match = re.search(r"\{[^}]+\}", response)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    intent_str = data.get("intent", "knowledge_query")
                    intent = IntentType(intent_str) if intent_str in IntentType._value2member_map_ else IntentType.KNOWLEDGE_QUERY
                    func_target = None
                    if data.get("function_target") and intent == IntentType.FUNCTION_CALL:
                        try:
                            func_target = FunctionTarget(data["function_target"])
                        except ValueError:
                            pass
                    return {
                        "intent": intent,
                        "function_target": func_target,
                        "confidence": float(data.get("confidence", 0.5)),
                        "params": {},
                        "requires_llm": False
                    }
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"解析 LLM 分类结果失败: {e}")

        return None


# 全局意图解析器实例
intent_parser = IntentParser()
