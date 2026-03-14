"""
批量报告生成服务
"""
from ..schemas.批量处理模型 import BatchReportRequest, BatchReportResponse
from ..tasks.批量任务管理器 import BatchTaskManager
from ..services.报告生成服务 import ReportGenerator
from ..services.结果对比分析服务 import ResultComparisonService
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class BatchReportGenerator:
    """批量报告生成器"""

    def __init__(self):
        self.batch_manager = BatchTaskManager()
        self.report_generator = ReportGenerator()
        self.comparison_service = ResultComparisonService()
        self.reports_dir = Path(__file__).parent.parent / "结果文件" / "批量报告"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_batch_report(self, request: BatchReportRequest) -> BatchReportResponse:
        """
        生成批量任务报告

        参数说明：
        - batch_id: 批量任务ID
        - report_title: 报告标题（可选）
        - report_description: 报告描述（可选）
        - include_sections: 包含的章节（可选）
        - chart_types: 图表类型配置（可选）
        - format: 报告格式（pdf/html/word/excel）
        """
        try:
            # 获取批量任务信息
            batch_summary = self.batch_manager.get_batch_summary(request.batch_id)
            batch_details = self.batch_manager.get_batch_details(request.batch_id)

            if not batch_summary or not batch_details:
                raise ValueError(f"批量任务 {request.batch_id} 不存在")

            # 获取批量任务结果
            batch_results = self.batch_manager.get_batch_results(request.batch_id)

            if not batch_results:
                raise ValueError(f"批量任务 {request.batch_id} 没有结果")

            # 获取对比分析
            comparison = self.comparison_service.compare_batch_results(request.batch_id)

            # 生成报告内容
            report_content = self._generate_report_content(
                request,
                batch_summary,
                batch_details,
                batch_results,
                comparison
            )

            # 保存报告文件
            report_id = str(uuid.uuid4())
            report_file = self._save_report(report_id, report_content, request.format)

            return BatchReportResponse(
                report_id=report_id,
                batch_id=request.batch_id,
                format=request.format,
                status="completed",
                download_url=f"/results/批量报告/{report_file.name}",
                generated_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"生成批量报告失败: {str(e)}")
            raise e

    def _generate_report_content(
        self,
        request: BatchReportRequest,
        batch_summary: Any,
        batch_details: List[Any],
        batch_results: List[Dict[str, Any]],
        comparison: Optional[Any]
    ) -> str:
        """生成报告内容"""
        # 默认包含的章节
        default_sections = [
            "执行摘要",
            "任务列表",
            "结果汇总",
            "对比分析",
            "结论和建议"
        ]

        sections = request.include_sections if request.include_sections else default_sections

        # 构建报告内容
        content = []

        # 报告标题
        title = request.report_title if request.report_title else f"批量克里金插值分析报告 - {request.batch_id}"
        content.append(f"# {title}\n")
        content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        content.append(f"格式: {request.format.upper()}\n\n")

        # 报告描述
        if request.report_description:
            content.append(f"## 报告描述\n{request.report_description}\n\n")

        # 执行摘要
        if "执行摘要" in sections:
            content.append("## 执行摘要\n")
            content.append(f"- **批量任务ID**: {request.batch_id}\n")
            content.append(f"- **总任务数**: {batch_summary.total_tasks}\n")
            content.append(f"- **已完成**: {batch_summary.completed_tasks}\n")
            content.append(f"- **失败**: {batch_summary.failed_tasks}\n")
            content.append(f"- **成功率**: {(batch_summary.completed_tasks / batch_summary.total_tasks * 100):.2f}%\n")
            content.append(f"- **整体进度**: {batch_summary.overall_progress:.2f}%\n\n")

            if comparison and comparison.statistics:
                content.append("### 统计指标摘要\n")
                if "rmse" in comparison.statistics:
                    rmse_stats = comparison.statistics["rmse"]
                    content.append(f"- **RMSE**: 平均={rmse_stats['mean']:.4f}, 最小={rmse_stats['min']:.4f}, 最大={rmse_stats['max']:.4f}\n")
                if "mae" in comparison.statistics:
                    mae_stats = comparison.statistics["mae"]
                    content.append(f"- **MAE**: 平均={mae_stats['mean']:.4f}, 最小={mae_stats['min']:.4f}, 最大={mae_stats['max']:.4f}\n")
                if "r2" in comparison.statistics:
                    r2_stats = comparison.statistics["r2"]
                    content.append(f"- **R²**: 平均={r2_stats['mean']:.4f}, 最小={r2_stats['min']:.4f}, 最大={r2_stats['max']:.4f}\n")
                content.append("\n")

        # 任务列表
        if "任务列表" in sections:
            content.append("## 任务列表\n")
            content.append("| 序号 | 任务ID | 数据ID | 状态 | 进度 |\n")
            content.append("|------|--------|--------|------|------|\n")
            for i, detail in enumerate(batch_details, start=1):
                content.append(f"| {i} | {detail.task_id} | {detail.data_id} | {detail.status} | {detail.progress:.2f}% |\n")
            content.append("\n")

        # 结果汇总
        if "结果汇总" in sections:
            content.append("## 结果汇总\n")
            content.append("### 成功任务结果\n")
            for result in batch_results:
                if result["status"] == "completed":
                    task_id = result["task_id"]
                    data_id = result["data_id"]
                    result_data = result["result"]

                    content.append(f"#### 任务 {task_id} (数据: {data_id})\n")

                    if "cross_validation" in result_data:
                        cv = result_data["cross_validation"]
                        content.append(f"- **RMSE**: {cv.get('rmse', 'N/A')}\n")
                        content.append(f"- **MAE**: {cv.get('mae', 'N/A')}\n")
                        content.append(f"- **R²**: {cv.get('r2', 'N/A')}\n")
                        content.append(f"- **MSE**: {cv.get('mse', 'N/A')}\n")

                    if "prediction_stats" in result_data:
                        stats = result_data["prediction_stats"]
                        content.append(f"- **预测统计**: 最小={stats.get('min', 'N/A')}, 最大={stats.get('max', 'N/A')}, 平均={stats.get('mean', 'N/A')}\n")

                    if "variance_stats" in result_data:
                        var_stats = result_data["variance_stats"]
                        content.append(f"- **方差统计**: 最小={var_stats.get('min', 'N/A')}, 最大={var_stats.get('max', 'N/A')}, 平均={var_stats.get('mean', 'N/A')}\n")

                    content.append("\n")

        # 对比分析
        if "对比分析" in sections and comparison:
            content.append("## 对比分析\n")

            if comparison.best_result:
                content.append("### 最佳结果\n")
                content.append(f"- **任务ID**: {comparison.best_result['task_id']}\n")
                content.append(f"- **数据ID**: {comparison.best_result['data_id']}\n")
                content.append(f"- **RMSE**: {comparison.best_result['rmse']:.4f}\n")
                content.append(f"- **MAE**: {comparison.best_result['mae']:.4f}\n")
                content.append(f"- **R²**: {comparison.best_result['r2']:.4f}\n")
                content.append("\n")

            if comparison.worst_result:
                content.append("### 最差结果\n")
                content.append(f"- **任务ID**: {comparison.worst_result['task_id']}\n")
                content.append(f"- **数据ID**: {comparison.worst_result['data_id']}\n")
                content.append(f"- **RMSE**: {comparison.worst_result['rmse']:.4f}\n")
                content.append(f"- **MAE**: {comparison.worst_result['mae']:.4f}\n")
                content.append(f"- **R²**: {comparison.worst_result['r2']:.4f}\n")
                content.append("\n")

            if comparison.statistics:
                content.append("### 指标统计\n")
                for metric, stats in comparison.statistics.items():
                    content.append(f"#### {metric.upper()}\n")
                    content.append(f"- **最小值**: {stats['min']:.4f}\n")
                    content.append(f"- **最大值**: {stats['max']:.4f}\n")
                    content.append(f"- **平均值**: {stats['mean']:.4f}\n")
                    content.append(f"- **中位数**: {stats['median']:.4f}\n")
                    content.append(f"- **标准差**: {stats['stdev']:.4f}\n")
                    content.append("\n")

        # 结论和建议
        if "结论和建议" in sections:
            content.append("## 结论和建议\n")

            # 分析结果
            if batch_summary.failed_tasks > 0:
                content.append(f"### 风险提示\n")
                content.append(f"- 有 {batch_summary.failed_tasks} 个任务失败，建议检查数据质量和参数配置\n")
                content.append("\n")

            if comparison and comparison.statistics:
                content.append("### 性能分析\n")

                # 检查 RMSE 的变异性
                if "rmse" in comparison.statistics:
                    rmse_stdev = comparison.statistics["rmse"]["stdev"]
                    rmse_mean = comparison.statistics["rmse"]["mean"]
                    cv = (rmse_stdev / rmse_mean) * 100 if rmse_mean > 0 else 0

                    if cv > 20:
                        content.append(f"- **RMSE 变异性较高** ({cv:.2f}%)，不同数据集的插值精度差异较大\n")
                        content.append(f"  建议：考虑对不同数据集使用不同的参数配置\n")
                    else:
                        content.append(f"- **RMSE 变异性较低** ({cv:.2f}%)，参数配置较为稳定\n")

                # 检查 R² 的平均值
                if "r2" in comparison.statistics:
                    r2_mean = comparison.statistics["r2"]["mean"]
                    if r2_mean < 0.5:
                        content.append(f"- **模型拟合度较低** (平均 R² = {r2_mean:.4f})\n")
                        content.append(f"  建议：检查数据的空间相关性，考虑使用更复杂的变异函数模型\n")
                    elif r2_mean > 0.8:
                        content.append(f"- **模型拟合度较高** (平均 R² = {r2_mean:.4f})\n")
                        content.append(f"  当前参数配置效果良好\n")

                content.append("\n")

            content.append("### 建议\n")
            content.append("1. 定期运行批量任务以监控系统性能\n")
            content.append("2. 对于表现不佳的数据集，建议单独调整参数\n")
            content.append("3. 使用参数模板功能保存最佳参数配置\n")
            content.append("4. 定期审查和更新参数模板以适应新的数据特征\n")

        return "\n".join(content)

    def _save_report(self, report_id: str, content: str, format: str) -> Path:
        """保存报告文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "html":
            # 转换为 HTML
            html_content = self._markdown_to_html(content)
            filename = f"report_{report_id}_{timestamp}.html"
            file_path = self.reports_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

        elif format == "pdf":
            # 保存为 Markdown（PDF 需要额外的库支持）
            filename = f"report_{report_id}_{timestamp}.md"
            file_path = self.reports_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        elif format == "word":
            # 保存为 Markdown（Word 需要额外的库支持）
            filename = f"report_{report_id}_{timestamp}.md"
            file_path = self.reports_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        elif format == "excel":
            # 保存为 Markdown（Excel 需要额外的库支持）
            filename = f"report_{report_id}_{timestamp}.md"
            file_path = self.reports_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        else:
            # 默认保存为 Markdown
            filename = f"report_{report_id}_{timestamp}.md"
            file_path = self.reports_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return file_path

    def _markdown_to_html(self, markdown: str) -> str:
        """将 Markdown 转换为 HTML"""
        # 简单的 Markdown 到 HTML 转换
        html = markdown

        # 标题
        html = html.replace("# ", "<h1>").replace("\n", "</h1>\n", 1)
        html = html.replace("## ", "<h2>").replace("\n", "</h2>\n", 1)
        html = html.replace("### ", "<h3>").replace("\n", "</h3>\n", 1)
        html = html.replace("#### ", "<h4>").replace("\n", "</h4>\n", 1)

        # 粗体
        html = html.replace("**", "<strong>").replace("**", "</strong>")

        # 表格（简化处理）
        lines = html.split("\n")
        in_table = False
        processed_lines = []

        for line in lines:
            if "|" in line and not in_table:
                in_table = True
                processed_lines.append("<table>")
                processed_lines.append("<thead>")
                processed_lines.append("<tr>")
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                for cell in cells:
                    processed_lines.append(f"<th>{cell}</th>")
                processed_lines.append("</tr>")
                processed_lines.append("</thead>")
                processed_lines.append("<tbody>")
            elif "|" in line and in_table and "---" not in line:
                processed_lines.append("<tr>")
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                for cell in cells:
                    processed_lines.append(f"<td>{cell}</td>")
                processed_lines.append("</tr>")
            elif in_table:
                in_table = False
                processed_lines.append("</tbody>")
                processed_lines.append("</table>")
                processed_lines.append(line)
            else:
                processed_lines.append(line)

        html = "\n".join(processed_lines)

        # 段落
        html = html.replace("\n\n", "</p><p>")
        html = f"<html><head><meta charset='utf-8'><style>body{{font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;}} table{{border-collapse: collapse; width: 100%; margin: 20px 0;}} th,td{{border: 1px solid #ddd; padding: 8px; text-align: left;}} th{{background-color: #f2f2f2;}}</style></head><body><p>{html}</p></body></html>"

        return html

    def get_report_templates(self) -> List[Dict[str, Any]]:
        """获取报告模板列表"""
        templates = [
            {
                "template_id": "default",
                "name": "默认模板",
                "description": "包含所有章节的完整报告",
                "sections": ["执行摘要", "任务列表", "结果汇总", "对比分析", "结论和建议"]
            },
            {
                "template_id": "summary",
                "name": "摘要模板",
                "description": "仅包含执行摘要和结论",
                "sections": ["执行摘要", "结论和建议"]
            },
            {
                "template_id": "detailed",
                "name": "详细模板",
                "description": "包含所有章节和详细统计",
                "sections": ["执行摘要", "任务列表", "结果汇总", "对比分析", "结论和建议"]
            }
        ]

        return templates