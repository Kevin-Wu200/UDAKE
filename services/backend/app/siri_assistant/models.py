"""
Siri 助手 Pydantic 数据模型

定义助手 API 的请求/响应数据结构。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# --- 意图分类枚举 ---

class IntentType(str, Enum):
    """意图类型"""
    KNOWLEDGE_QUERY = "knowledge_query"       # 知识查询（从 docs/ 检索）
    FUNCTION_CALL = "function_call"           # 功能调用（触发系统功能）
    GENERAL_CHAT = "general_chat"             # 一般对话（闲聊/问候）
    UNKNOWN = "unknown"                       # 无法识别


class FunctionTarget(str, Enum):
    """可调用的系统功能"""
    START_INTERPOLATION = "start_interpolation"         # 开始插值计算
    UPLOAD_DATA = "upload_data"                         # 上传数据
    QUERY_RESULTS = "query_results"                     # 查询结果
    CHECK_TASK_STATUS = "check_task_status"             # 查看任务状态
    CONFIGURE_PARAMS = "configure_params"               # 配置参数
    VIEW_DOCS = "view_docs"                             # 查看文档
    START_SAMPLING = "start_sampling"                   # 开始采样
    EXPORT_RESULTS = "export_results"                   # 导出结果
    MODEL_RECOMMENDATION = "model_recommendation"       # 模型推荐
    UNCERTAINTY_ANALYSIS = "uncertainty_analysis"       # 不确定性分析


# --- 请求模型 ---

class SiriQueryRequest(BaseModel):
    """助手查询请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="用户输入的自然语言问题或指令")
    session_id: Optional[str] = Field(None, description="会话 ID（用于上下文追踪）")
    voice_input: bool = Field(False, description="是否来自语音输入")
    user_preferences: Optional[dict[str, Any]] = Field(None, description="用户偏好设置")
    include_history: bool = Field(False, description="是否包含历史交互上下文")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """验证查询非空并去除首尾空白"""
        if not v or not v.strip():
            raise ValueError("查询不能为空")
        return v.strip()


class SiriFeedbackRequest(BaseModel):
    """用户反馈请求（用于自学习）"""
    query: str = Field(..., description="原始查询")
    response: str = Field(..., description="助手响应")
    helpful: bool = Field(..., description="用户是否认为有帮助")
    corrected_answer: Optional[str] = Field(None, description="用户提供的正确答案")
    session_id: Optional[str] = Field(None, description="会话 ID")


class KnowledgeUpdateRequest(BaseModel):
    """知识库更新请求"""
    question: str = Field(..., min_length=5, max_length=500, description="问题")
    answer: str = Field(..., min_length=5, max_length=2000, description="答案")
    category: Optional[str] = Field("general", description="分类标签")


# --- 响应模型 ---

class RetrievedDocument(BaseModel):
    """检索到的文档片段"""
    content: str = Field(..., description="文档内容片段")
    source: str = Field(..., description="来源文件路径")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="相关性评分")
    title: Optional[str] = Field(None, description="文档标题/条目标题")


class FunctionCallSuggestion(BaseModel):
    """功能调用建议"""
    function: FunctionTarget = Field(..., description="目标功能")
    params: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    description: str = Field("", description="功能描述")
    requires_confirmation: bool = Field(True, description="是否需要用户确认")


class SiriAssistantResponse(BaseModel):
    """助手响应"""
    success: bool = Field(True, description="请求是否成功处理")
    intent: IntentType = Field(IntentType.GENERAL_CHAT, description="识别到的意图类型")
    answer: str = Field("", description="自然语言回答")
    retrieved_docs: list[RetrievedDocument] = Field(default_factory=list, description="检索到的文档")
    function_call: Optional[FunctionCallSuggestion] = Field(None, description="功能调用建议")
    fallback: bool = Field(False, description="是否为安全回退响应（无法匹配时）")
    session_id: Optional[str] = Field(None, description="会话 ID")
    processing_time_ms: float = Field(0.0, description="处理耗时（毫秒）")


class KnowledgeEntry(BaseModel):
    """知识库条目"""
    question: str
    answer: str
    category: str = "general"
    created_at: datetime = Field(default_factory=datetime.now)


class InteractionLogEntry(BaseModel):
    """交互日志条目（用于自训练）"""
    timestamp: datetime = Field(default_factory=datetime.now)
    query: str
    intent: IntentType
    response: str
    retrieved_count: int = 0
    function_called: Optional[str] = None
    processing_time_ms: float = 0.0
    user_feedback: Optional[bool] = None



