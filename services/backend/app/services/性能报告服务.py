"""
性能报告服务
"""
import json
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from ..schemas.性能报告模型 import (
    HistoricalPerformanceStats,
    PerformanceAnalysis,
    PerformanceBottleneck,
    PerformanceMetrics,
    PerformanceOptimization,
    PerformanceReport,
    PerformanceReportRequest,
    PerformanceReportResponse,
    PerformanceTrendAnalysis,
    ReportFormat,
    StagePerformance,
    TaskPerformanceData,
)
from ..services.资源监控服务 import resource_monitoring_service
from ..tasks.任务管理器 import TaskManager


class PerformanceReportService:
    """性能报告服务"""

    def __init__(self):
        self.task_manager = TaskManager()
        self.performance_history: Dict[str, List[TaskPerformanceData]] = {}
        self.lock = threading.Lock()
        self.reports_dir = Path(__file__).parent.parent / "结果文件" / "performance_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def collect_performance_data(self, task_id: str) -> Optional[TaskPerformanceData]:
        """收集任务性能数据"""
        try:
            # 获取任务基本信息
            task_info = self.task_manager.get_task_info(task_id)
            if not task_info:
                return None

            # 获取进度详情
            progress_detail = self.task_manager.get_progress_detail(task_id)

            # 构建性能数据
            performance_data = TaskPerformanceData(
                task_id=task_id,
                task_type=task_info.get("params", {}).get("method", "kriging"),
                created_at=task_info["created_at"],
                started_at=task_info.get("started_at"),
                completed_at=task_info.get("completed_at")
            )

            # 计算总耗时
            if progress_detail and progress_detail.elapsed_time:
                performance_data.total_duration = progress_detail.elapsed_time

            # 提取阶段性能
            if progress_detail and progress_detail.stages:
                for stage in progress_detail.stages:
                    if stage.duration:
                        stage_performance = StagePerformance(
                            stage_name=stage.stage_name,
                            duration=stage.duration,
                            start_time=stage.started_at or datetime.now(),
                            end_time=stage.completed_at or datetime.now()
                        )
                        performance_data.stages.append(stage_performance)

            # 添加资源使用数据
            task_resources = resource_monitoring_service.get_task_resource_usage(task_id)
            if task_resources:
                performance_data.memory_usage = {
                    "avg": sum(r.get("memory_usage", 0) for r in task_resources) / len(task_resources),
                    "max": max(r.get("memory_usage", 0) for r in task_resources),
                    "min": min(r.get("memory_usage", 0) for r in task_resources)
                }
                performance_data.cpu_usage = {
                    "avg": sum(r.get("cpu_usage", 0) for r in task_resources) / len(task_resources),
                    "max": max(r.get("cpu_usage", 0) for r in task_resources),
                    "min": min(r.get("cpu_usage", 0) for r in task_resources)
                }

            # 添加数据大小信息
            params = task_info.get("params", {})
            if params:
                performance_data.grid_resolution = params.get("grid_resolution")
                performance_data.point_count = params.get("point_count")

            return performance_data

        except Exception as e:
            print(f"收集性能数据失败: {str(e)}")
            return None

    def calculate_metrics(self, performance_data: TaskPerformanceData) -> PerformanceMetrics:
        """计算性能指标"""
        total_execution_time = performance_data.total_duration or 0

        # CPU使用率
        cpu_usage = performance_data.cpu_usage
        avg_cpu = cpu_usage.get("avg", 0) if cpu_usage else 0
        max_cpu = cpu_usage.get("max", 0) if cpu_usage else 0

        # 内存使用
        memory_usage = performance_data.memory_usage
        avg_memory = memory_usage.get("avg", 0) if memory_usage else 0
        max_memory = memory_usage.get("max", 0) if memory_usage else 0

        # 吞吐量
        point_count = performance_data.point_count or 1
        throughput = point_count / total_execution_time if total_execution_time > 0 else 0

        return PerformanceMetrics(
            total_execution_time=total_execution_time,
            avg_cpu_usage=avg_cpu,
            max_cpu_usage=max_cpu,
            avg_memory_usage=avg_memory,
            max_memory_usage=max_memory,
            total_disk_io=performance_data.disk_usage,
            throughput=throughput
        )

    def analyze_performance(
        self,
        performance_data: TaskPerformanceData,
        metrics: PerformanceMetrics
    ) -> PerformanceAnalysis:
        """分析性能"""
        bottlenecks: List[PerformanceBottleneck] = []
        optimizations: List[PerformanceOptimization] = []
        recommendations: List[str] = []

        # 分析CPU使用
        if metrics.max_cpu_usage > 90:
            bottlenecks.append(PerformanceBottleneck(
                bottleneck_type="cpu",
                stage="overall",
                severity="critical",
                description="CPU使用率过高",
                impact="严重影响系统响应速度",
                suggestion="考虑优化算法或减少并发任务"
            ))
            optimizations.append(PerformanceOptimization(
                optimization_type="cpu",
                title="优化CPU使用",
                description="通过算法优化和任务调度降低CPU使用率",
                expected_improvement="CPU使用率降低30-40%",
                implementation_difficulty="medium",
                priority="high"
            ))

        # 分析内存使用
        if metrics.max_memory_usage > 2000:  # 超过2GB
            bottlenecks.append(PerformanceBottleneck(
                bottleneck_type="memory",
                stage="data_processing",
                severity="high",
                description="内存使用量过大",
                impact="可能导致系统内存不足",
                suggestion="启用分块处理或优化数据结构"
            ))
            optimizations.append(PerformanceOptimization(
                optimization_type="memory",
                title="优化内存使用",
                description="通过分块处理和数据压缩减少内存占用",
                expected_improvement="内存使用量减少40-50%",
                implementation_difficulty="low",
                priority="high"
            ))

        # 分析执行时间
        if performance_data.stages:
            max_duration_stage = max(performance_data.stages, key=lambda s: s.duration)
            if max_duration_stage.duration > metrics.total_execution_time * 0.5:
                bottlenecks.append(PerformanceBottleneck(
                    bottleneck_type="io",
                    stage=max_duration_stage.stage_name,
                    severity="medium",
                    description=f"{max_duration_stage.stage_name}阶段耗时过长",
                    impact="影响整体执行效率",
                    suggestion="优化该阶段的算法或使用并行处理"
                ))

        # 总体评分
        if metrics.avg_cpu_usage < 50 and metrics.avg_memory_usage < 1000:
            overall_rating = "excellent"
        elif metrics.avg_cpu_usage < 70 and metrics.avg_memory_usage < 2000:
            overall_rating = "good"
        elif metrics.avg_cpu_usage < 85 and metrics.avg_memory_usage < 3000:
            overall_rating = "fair"
        else:
            overall_rating = "poor"

        # 生成推荐措施
        if overall_rating in ["fair", "poor"]:
            recommendations.append("建议优化算法以降低计算复杂度")
            recommendations.append("考虑使用并行处理提高效率")
            recommendations.append("优化数据加载和存储方式")

        # 资源效率评分
        resource_efficiency = {
            "cpu_efficiency": max(0, 100 - metrics.avg_cpu_usage),
            "memory_efficiency": max(0, 100 - (metrics.avg_memory_usage / 30)),  # 假设3GB为满分
            "time_efficiency": min(100, 1000 / (metrics.total_execution_time or 1))  # 假设10秒为满分
        }

        return PerformanceAnalysis(
            task_id=performance_data.task_id,
            overall_rating=overall_rating,
            metrics=metrics,
            bottlenecks=bottlenecks,
            optimizations=optimizations,
            resource_efficiency=resource_efficiency,
            recommendations=recommendations
        )

    def generate_report(self, request: PerformanceReportRequest) -> PerformanceReportResponse:
        """生成性能报告"""
        try:
            # 收集性能数据
            performance_data = self.collect_performance_data(request.task_id)
            if not performance_data:
                raise Exception("无法收集性能数据")

            # 计算性能指标
            metrics = self.calculate_metrics(performance_data)

            # 分析性能
            analysis = self.analyze_performance(performance_data, metrics) if request.include_analysis else None

            # 创建报告
            report_id = str(uuid.uuid4())
            report = PerformanceReport(
                report_id=report_id,
                task_id=request.task_id,
                task_type=performance_data.task_type,
                format=request.format,
                performance_data=performance_data,
                metrics=metrics,
                analysis=analysis
            )

            # 保存历史记录
            self._save_to_history(performance_data)

            # 生成报告文件
            download_url = self._export_report(report, request.format)

            return PerformanceReportResponse(
                report_id=report_id,
                task_id=request.task_id,
                format=request.format,
                status="completed",
                download_url=download_url,
                generated_at=datetime.now()
            )

        except Exception as e:
            raise Exception(f"生成报告失败: {str(e)}")

    def _export_report(self, report: PerformanceReport, format: ReportFormat) -> Optional[str]:
        """导出报告"""
        try:
            if format == ReportFormat.JSON:
                return self._export_json(report)
            elif format == ReportFormat.HTML:
                return self._export_html(report)
            elif format == ReportFormat.PDF:
                return self._export_pdf(report)
            return None
        except Exception as e:
            print(f"导出报告失败: {str(e)}")
            return None

    def _export_json(self, report: PerformanceReport) -> str:
        """导出为JSON格式"""
        filename = f"{report.report_id}.json"
        filepath = self.reports_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report.model_dump(), f, ensure_ascii=False, indent=2, default=str)

        return f"/api/results/performance_reports/{filename}"

    def _export_html(self, report: PerformanceReport) -> str:
        """导出为HTML格式"""
        filename = f"{report.report_id}.html"
        filepath = self.reports_dir / filename

        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>性能报告 - {report.task_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #e3f2fd; border-radius: 4px; }}
        .bottleneck {{ background: #ffebee; padding: 10px; margin: 5px 0; border-left: 4px solid #f44336; }}
        .optimization {{ background: #e8f5e9; padding: 10px; margin: 5px 0; border-left: 4px solid #4caf50; }}
        h1, h2, h3 {{ color: #333; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>性能报告</h1>
        <p><strong>任务ID:</strong> {report.task_id}</p>
        <p><strong>任务类型:</strong> {report.task_type}</p>
        <p><strong>生成时间:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="section">
        <h2>性能指标</h2>
        <div class="metric">总执行时间: {report.metrics.total_execution_time:.2f}秒</div>
        <div class="metric">平均CPU使用率: {report.metrics.avg_cpu_usage:.2f}%</div>
        <div class="metric">最大CPU使用率: {report.metrics.max_cpu_usage:.2f}%</div>
        <div class="metric">平均内存使用: {report.metrics.avg_memory_usage:.2f}MB</div>
        <div class="metric">最大内存使用: {report.metrics.max_memory_usage:.2f}MB</div>
        <div class="metric">吞吐量: {report.metrics.throughput:.2f}点/秒</div>
    </div>

    {f'''
    <div class="section">
        <h2>性能分析</h2>
        <p><strong>总体评分:</strong> {report.analysis.overall_rating}</p>

        <h3>性能瓶颈</h3>
        {"".join(f'<div class="bottleneck"><strong>{b.stage}:</strong> {b.description}<br><em>{b.suggestion}</em></div>' for b in report.analysis.bottlenecks)}

        <h3>优化建议</h3>
        {"".join(f'<div class="optimization"><strong>{o.title}:</strong> {o.description}<br><em>预期改善: {o.expected_improvement}</em></div>' for o in report.analysis.optimizations)}

        <h3>推荐措施</h3>
        <ul>{"".join(f'<li>{r}</li>' for r in report.analysis.recommendations)}</ul>
    </div>
    ''' if report.analysis else ''}
</body>
</html>
        """

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return f"/api/results/performance_reports/{filename}"

    def _export_pdf(self, report: PerformanceReport) -> str:
        """导出为PDF格式（简化版，使用HTML作为基础）"""
        # 这里简化实现，实际可以使用pdfkit或其他PDF生成库
        html_url = self._export_html(report)
        return html_url.replace('.html', '.pdf')  # 返回PDF路径（实际需要转换）

    def _save_to_history(self, performance_data: TaskPerformanceData):
        """保存到历史记录"""
        with self.lock:
            task_type = performance_data.task_type
            if task_type not in self.performance_history:
                self.performance_history[task_type] = []

            self.performance_history[task_type].append(performance_data)

            # 只保留最近100条记录
            if len(self.performance_history[task_type]) > 100:
                self.performance_history[task_type] = self.performance_history[task_type][-100:]

    def get_historical_stats(
        self,
        task_type: str,
        period_days: int = 30
    ) -> Optional[HistoricalPerformanceStats]:
        """获取历史统计"""
        with self.lock:
            if task_type not in self.performance_history:
                return None

            cutoff_time = datetime.now() - timedelta(days=period_days)
            recent_tasks = [
                t for t in self.performance_history[task_type]
                if t.created_at > cutoff_time and t.total_duration
            ]

            if not recent_tasks:
                return None

            durations = [t.total_duration for t in recent_tasks]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            # 分析趋势
            first_half = durations[:len(durations)//2]
            second_half = durations[len(durations)//2:]
            if len(first_half) > 0 and len(second_half) > 0:
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                if avg_second < avg_first * 0.9:
                    trend = "improving"
                elif avg_second > avg_first * 1.1:
                    trend = "degrading"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            return HistoricalPerformanceStats(
                avg_execution_time=avg_duration,
                min_execution_time=min_duration,
                max_execution_time=max_duration,
                total_tasks=len(recent_tasks),
                trend=trend
            )

    def get_trend_analysis(self, task_id: str, period_days: int = 30) -> Optional[PerformanceTrendAnalysis]:
        """获取趋势分析"""
        performance_data = self.collect_performance_data(task_id)
        if not performance_data:
            return None

        metrics = self.calculate_metrics(performance_data)
        historical_stats = self.get_historical_stats(performance_data.task_type, period_days)

        if not historical_stats:
            return None

        # 计算改善/恶化率
        improvement_rate = None
        degradation_rate = None

        if metrics.total_execution_time > 0 and historical_stats.avg_execution_time > 0:
            if metrics.total_execution_time < historical_stats.avg_execution_time:
                improvement_rate = (1 - metrics.total_execution_time / historical_stats.avg_execution_time) * 100
            else:
                degradation_rate = (metrics.total_execution_time / historical_stats.avg_execution_time - 1) * 100

        return PerformanceTrendAnalysis(
            task_id=task_id,
            period_days=period_days,
            current_performance=metrics,
            historical_average=historical_stats,
            trend=historical_stats.trend,
            improvement_rate=improvement_rate,
            degradation_rate=degradation_rate
        )

# 创建全局实例
performance_report_service = PerformanceReportService()
