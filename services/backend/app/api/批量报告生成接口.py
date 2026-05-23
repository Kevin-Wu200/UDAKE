"""
批量报告生成接口
"""
import logging

from fastapi import APIRouter, HTTPException

from ..schemas.批量处理模型 import BatchReportRequest, BatchReportResponse
from ..services.批量报告生成服务 import BatchReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter()
batch_report_generator = BatchReportGenerator()


@router.post("/api/batch-reports/generate", response_model=BatchReportResponse)
async def generate_batch_report(request: BatchReportRequest):
    """
    生成批量任务报告

    参数说明：
    - batch_id: 批量任务ID
    - report_title: 报告标题（可选）
    - report_description: 报告描述（可选）
    - include_sections: 包含的章节（可选，默认包含所有章节）
    - chart_types: 图表类型配置（可选）
    - format: 报告格式（pdf/html/word/excel，默认为 pdf）

    可选章节：
    - 执行摘要
    - 任务列表
    - 结果汇总
    - 对比分析
    - 结论和建议
    """
    try:
        # 生成报告
        response = batch_report_generator.generate_batch_report(request)

        logger.info(f"批量报告已生成: {response.report_id}, 批量任务: {request.batch_id}, 格式: {request.format}")

        return response

    except ValueError as e:
        logger.error(f"生成批量报告失败: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成批量报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


@router.get("/api/batch-reports/templates")
async def get_report_templates():
    """
    获取报告模板列表

    返回可用的报告模板，包括：
    - 默认模板：包含所有章节
    - 摘要模板：仅包含执行摘要和结论
    - 详细模板：包含所有章节和详细统计
    """
    try:
        templates = batch_report_generator.get_report_templates()

        return {
            "templates": templates,
            "total": len(templates)
        }

    except Exception as e:
        logger.error(f"获取报告模板失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取模板失败: {str(e)}")


@router.get("/api/batch-reports/sections")
async def get_available_sections():
    """
    获取可用的报告章节列表

    返回可以包含在报告中的所有章节
    """
    try:
        sections = [
            {
                "id": "executive_summary",
                "name": "执行摘要",
                "description": "包含批量任务的基本信息和统计摘要"
            },
            {
                "id": "task_list",
                "name": "任务列表",
                "description": "列出所有任务的状态和进度"
            },
            {
                "id": "result_summary",
                "name": "结果汇总",
                "description": "汇总所有成功任务的结果"
            },
            {
                "id": "comparison_analysis",
                "name": "对比分析",
                "description": "分析不同任务的结果差异"
            },
            {
                "id": "conclusions",
                "name": "结论和建议",
                "description": "基于分析结果提供结论和建议"
            }
        ]

        return {
            "sections": sections,
            "total": len(sections)
        }

    except Exception as e:
        logger.error(f"获取可用章节失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取章节失败: {str(e)}")


@router.get("/api/batch-reports/formats")
async def get_available_formats():
    """
    获取支持的报告格式列表

    返回支持的报告格式：
    - pdf: PDF 格式（适合打印）
    - html: HTML 格式（适合在线查看）
    - word: Word 格式（适合编辑）
    - excel: Excel 格式（适合数据分析）
    """
    try:
        formats = [
            {
                "id": "pdf",
                "name": "PDF",
                "description": "适合打印和归档"
            },
            {
                "id": "html",
                "name": "HTML",
                "description": "适合在线查看和分享"
            },
            {
                "id": "word",
                "name": "Word",
                "description": "适合编辑和进一步处理"
            },
            {
                "id": "excel",
                "name": "Excel",
                "description": "适合数据分析和图表生成"
            }
        ]

        return {
            "formats": formats,
            "total": len(formats)
        }

    except Exception as e:
        logger.error(f"获取支持格式失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取格式失败: {str(e)}")


@router.get("/api/batch-reports/preview/{batch_id}")
async def preview_batch_report(batch_id: str):
    """
    预览批量报告

    参数说明：
    - batch_id: 批量任务ID

    返回报告的 Markdown 格式预览
    """
    try:
        # 使用默认配置生成报告内容
        request = BatchReportRequest(
            batch_id=batch_id,
            format="html"
        )

        # 生成报告内容
        report_content = batch_report_generator._generate_report_content(
            request,
            batch_report_generator.batch_manager.get_batch_summary(batch_id),
            batch_report_generator.batch_manager.get_batch_details(batch_id),
            batch_report_generator.batch_manager.get_batch_results(batch_id),
            batch_report_generator.comparison_service.compare_batch_results(batch_id)
        )

        return {
            "batch_id": batch_id,
            "preview": report_content,
            "format": "markdown"
        }

    except Exception as e:
        logger.error(f"预览批量报告失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")
