"""
Siri 助手 API 路由

提供 Restful API 供前端调用：
- POST /api/siri/query     主查询接口
- POST /api/siri/feedback  用户反馈
- GET  /api/siri/health    健康检查
- GET  /api/siri/functions 功能列表
- POST /api/siri/knowledge 知识库更新
- GET  /api/siri/knowledge/entries 知识库条目列表
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .knowledge_store import knowledge_store
from .models import (
    FunctionTarget,
    IntentType,
    KnowledgeUpdateRequest,
    SiriAssistantResponse,
    SiriFeedbackRequest,
    SiriQueryRequest,
)
from .retriever import retriever
from .security import security
from .service import siri_service

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/api/siri", tags=["Siri智能助手"])


# --- 查询接口 ---

@router.post("/query", response_model=SiriAssistantResponse)
async def siri_query(request: SiriQueryRequest):
    """Siri 助手主查询接口

    接收用户自然语言输入，返回智能响应。
    支持知识查询、功能调用和一般对话。
    """
    try:
        # 确保服务已初始化
        siri_service.initialize()

        response = await siri_service.process_query(request)
        return response

    except Exception as e:
        logger.error(f"处理查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"助手服务暂时不可用: {str(e)}")


# --- 反馈接口 ---

@router.post("/feedback")
async def siri_feedback(feedback: SiriFeedbackRequest):
    """用户反馈接口

    用于收集用户对助手回答的反馈，支持自学习迭代。
    如果用户提供正确答案，系统会自动将其追加到知识库。
    """
    try:
        success = await siri_service.process_feedback(feedback)
        # 如果追加了知识，刷新检索器
        if not feedback.helpful and feedback.corrected_answer:
            retriever.refresh()
        return {
            "success": success,
            "message": "感谢您的反馈！" if success else "反馈处理失败",
        }
    except Exception as e:
        logger.error(f"处理反馈失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"反馈处理失败: {str(e)}")


# --- 健康检查 ---

@router.get("/health")
async def siri_health():
    """助手健康检查接口"""
    try:
        status = await siri_service.get_health_status()
        return status
    except Exception as e:
        return {
            "initialized": False,
            "error": str(e),
        }


# --- 功能列表 ---

@router.get("/functions")
async def siri_functions():
    """获取助手可调用的系统功能列表"""
    return {
        "functions": siri_service.get_function_list(),
    }


# --- 知识库管理 ---

@router.post("/knowledge")
async def add_knowledge(entry: KnowledgeUpdateRequest):
    """向知识库添加新条目

    将新的 Q&A 追加到 docs/Helper.md。
    """
    success = knowledge_store.add_entry(
        question=entry.question,
        answer=entry.answer,
        category=entry.category or "general",
    )
    if not success:
        raise HTTPException(status_code=500, detail="知识库更新失败")
    # 刷新检索器索引以包含新知识
    retriever.refresh()
    return {"success": True, "message": "知识条目已添加"}


@router.get("/knowledge/entries")
async def list_knowledge_entries(
    query: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取知识库条目列表"""
    if query:
        entries = knowledge_store.search_entries(query)
    else:
        entries = knowledge_store.read_entries()
    return {"entries": entries, "total": len(entries)}


@router.get("/knowledge/stats")
async def knowledge_stats():
    """获取知识库统计信息"""
    return knowledge_store.get_statistics()


# --- 检索测试接口 ---

@router.get("/search")
async def search_docs(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量"),
):
    """文档检索测试接口

    直接测试检索能力，不经过 LLM。
    """
    results = retriever.search(q, top_k=top_k)
    return {
        "query": q,
        "total_results": len(results),
        "results": [
            {
                "content": r["content"][:500],
                "source": r["source"],
                "title": r.get("title", ""),
                "score": round(r["relevance_score"], 4),
            }
            for r in results
        ],
    }
