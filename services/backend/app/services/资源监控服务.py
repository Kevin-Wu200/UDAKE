"""
资源监控服务
"""
import psutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from ..schemas.资源监控模型 import (
    SystemResources, ResourceUsage, ResourceType,
    ResourceWarning, ResourceOptimizationSuggestion,
    ResourceMonitoringConfig, ResourceStatistics
)

class ResourceMonitoringService:
    """资源监控服务"""

    def __init__(self):
        self.config = ResourceMonitoringConfig()
        self.resource_history: Dict[str, List[SystemResources]] = {}
        self.task_resources: Dict[str, List[Dict[str, Any]]] = {}
        self.warnings: List[ResourceWarning] = []
        self.suggestions: List[ResourceOptimizationSuggestion] = []
        self.lock = threading.Lock()
        self.monitoring_thread: Optional[threading.Thread] = None
        self.is_monitoring = False

    def start_monitoring(self):
        """启动资源监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitoring_thread.start()

    def stop_monitoring(self):
        """停止资源监控"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                resources = self.get_system_resources()
                self._store_resources(resources)
                self._check_thresholds(resources)
                if self.config.enable_optimization_suggestions:
                    self._generate_suggestions(resources)
                time.sleep(self.config.monitoring_interval)
            except Exception as e:
                print(f"资源监控错误: {str(e)}")
                time.sleep(self.config.monitoring_interval)

    def get_system_resources(self) -> SystemResources:
        """获取系统资源使用情况"""
        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_usage = ResourceUsage(
            resource_type=ResourceType.CPU,
            usage_percent=cpu_percent,
            used_value=cpu_percent,
            total_value=100.0,
            unit="%"
        )

        # 内存使用情况
        memory = psutil.virtual_memory()
        memory_usage = ResourceUsage(
            resource_type=ResourceType.MEMORY,
            usage_percent=memory.percent,
            used_value=memory.used / (1024 ** 2),  # 转换为MB
            total_value=memory.total / (1024 ** 2),
            unit="MB"
        )

        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        disk_usage = ResourceUsage(
            resource_type=ResourceType.DISK,
            usage_percent=disk.percent,
            used_value=disk.used / (1024 ** 3),  # 转换为GB
            total_value=disk.total / (1024 ** 3),
            unit="GB"
        )

        # 网络使用情况
        network = psutil.net_io_counters()
        network_usage = {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv
        }

        return SystemResources(
            cpu=cpu_usage,
            memory=memory_usage,
            disk=disk_usage,
            network=network_usage
        )

    def _store_resources(self, resources: SystemResources):
        """存储资源使用记录"""
        with self.lock:
            timestamp = resources.timestamp.strftime("%Y%m%d")
            if timestamp not in self.resource_history:
                self.resource_history[timestamp] = []

            self.resource_history[timestamp].append(resources)

            # 只保留最近24小时的记录
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.resource_history[timestamp] = [
                r for r in self.resource_history[timestamp]
                if r.timestamp > cutoff_time
            ]

    def get_current_resources(self) -> SystemResources:
        """获取当前资源使用情况"""
        return self.get_system_resources()

    def get_resource_statistics(
        self,
        resource_type: ResourceType,
        period_hours: int = 24
    ) -> Optional[ResourceStatistics]:
        """获取资源统计信息"""
        with self.lock:
            period_start = datetime.now() - timedelta(hours=period_hours)
            period_end = datetime.now()

            all_values = []
            peak_usage_time = None
            max_usage = 0.0

            for date_str, resources_list in self.resource_history.items():
                for resources in resources_list:
                    if resources.timestamp < period_start or resources.timestamp > period_end:
                        continue

                    if resource_type == ResourceType.CPU:
                        value = resources.cpu.usage_percent
                    elif resource_type == ResourceType.MEMORY:
                        value = resources.memory.usage_percent
                    elif resource_type == ResourceType.DISK:
                        value = resources.disk.usage_percent
                    else:
                        continue

                    all_values.append(value)

                    if value > max_usage:
                        max_usage = value
                        peak_usage_time = resources.timestamp

            if not all_values:
                return None

            return ResourceStatistics(
                resource_type=resource_type,
                avg_usage=sum(all_values) / len(all_values),
                max_usage=max(all_values),
                min_usage=min(all_values),
                peak_usage_time=peak_usage_time,
                total_samples=len(all_values),
                period_start=period_start,
                period_end=period_end
            )

    def record_task_resource(self, task_id: str, resources: Dict[str, Any]):
        """记录任务资源使用情况"""
        with self.lock:
            if task_id not in self.task_resources:
                self.task_resources[task_id] = []

            self.task_resources[task_id].append({
                "timestamp": datetime.now(),
                **resources
            })

            # 只保留最近100条记录
            if len(self.task_resources[task_id]) > 100:
                self.task_resources[task_id] = self.task_resources[task_id][-100:]

    def get_task_resource_usage(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务资源使用情况"""
        with self.lock:
            return self.task_resources.get(task_id, [])

    def _check_thresholds(self, resources: SystemResources):
        """检查资源阈值"""
        # CPU检查
        if resources.cpu.usage_percent >= self.config.cpu_critical_threshold:
            self._add_warning(ResourceType.CPU, "critical", resources.cpu.usage_percent)
        elif resources.cpu.usage_percent >= self.config.cpu_warning_threshold:
            self._add_warning(ResourceType.CPU, "warning", resources.cpu.usage_percent)

        # 内存检查
        if resources.memory.usage_percent >= self.config.memory_critical_threshold:
            self._add_warning(ResourceType.MEMORY, "critical", resources.memory.usage_percent)
        elif resources.memory.usage_percent >= self.config.memory_warning_threshold:
            self._add_warning(ResourceType.MEMORY, "warning", resources.memory.usage_percent)

        # 磁盘检查
        if resources.disk.usage_percent >= self.config.disk_critical_threshold:
            self._add_warning(ResourceType.DISK, "critical", resources.disk.usage_percent)
        elif resources.disk.usage_percent >= self.config.disk_warning_threshold:
            self._add_warning(ResourceType.DISK, "warning", resources.disk.usage_percent)

    def _add_warning(self, resource_type: ResourceType, level: str, current_value: float):
        """添加资源警告"""
        threshold_map = {
            ResourceType.CPU: {
                "warning": self.config.cpu_warning_threshold,
                "critical": self.config.cpu_critical_threshold
            },
            ResourceType.MEMORY: {
                "warning": self.config.memory_warning_threshold,
                "critical": self.config.memory_critical_threshold
            },
            ResourceType.DISK: {
                "warning": self.config.disk_warning_threshold,
                "critical": self.config.disk_critical_threshold
            }
        }

        threshold = threshold_map[resource_type][level]
        warning = ResourceWarning(
            warning_id=f"{resource_type.value}_{int(time.time())}",
            resource_type=resource_type,
            warning_level=level,
            message=f"{resource_type.value.upper()}使用率超过{threshold}%阈值，当前值为{current_value:.1f}%",
            threshold=threshold,
            current_value=current_value
        )

        self.warnings.append(warning)

        # 只保留最近50条警告
        if len(self.warnings) > 50:
            self.warnings = self.warnings[-50:]

    def _generate_suggestions(self, resources: SystemResources):
        """生成优化建议"""
        suggestions = []

        # CPU使用率过高建议
        if resources.cpu.usage_percent >= self.config.cpu_warning_threshold:
            suggestions.append(ResourceOptimizationSuggestion(
                suggestion_id=f"cpu_opt_{int(time.time())}",
                resource_type=ResourceType.CPU,
                suggestion_type="reduce_concurrent",
                title="减少并发任务数",
                description="CPU使用率过高，建议减少同时运行的任务数量",
                priority="high",
                expected_improvement="CPU使用率预计降低20-30%",
                action_steps=[
                    "将最大并发任务数降低至2-3个",
                    "考虑将任务分散到不同时间段执行",
                    "检查是否有任务陷入死循环或异常高CPU使用"
                ]
            ))

        # 内存使用率过高建议
        if resources.memory.usage_percent >= self.config.memory_warning_threshold:
            suggestions.append(ResourceOptimizationSuggestion(
                suggestion_id=f"mem_opt_{int(time.time())}",
                resource_type=ResourceType.MEMORY,
                suggestion_type="batch_processing",
                title="启用分块处理",
                description="内存使用率过高，建议启用数据分块处理",
                priority="high",
                expected_improvement="内存使用量预计降低30-50%",
                action_steps=[
                    "将大数据集分成较小的块进行处理",
                    "增加分块数量，减少每块的数据量",
                    "考虑使用流式处理代替全量加载"
                ]
            ))

        # 磁盘空间不足建议
        if resources.disk.usage_percent >= self.config.disk_warning_threshold:
            suggestions.append(ResourceOptimizationSuggestion(
                suggestion_id=f"disk_opt_{int(time.time())}",
                resource_type=ResourceType.DISK,
                suggestion_type="cleanup_temp",
                title="清理临时文件",
                description="磁盘空间不足，建议清理临时文件",
                priority="medium",
                expected_improvement="磁盘空间预计释放数GB",
                action_steps=[
                    "清理结果目录中的临时文件",
                    "删除已完成任务的无用中间文件",
                    "考虑将结果文件压缩存储"
                ]
            ))

        self.suggestions.extend(suggestions)

        # 只保留最近20条建议
        if len(self.suggestions) > 20:
            self.suggestions = self.suggestions[-20:]

    def get_warnings(self, limit: int = 10) -> List[ResourceWarning]:
        """获取资源警告"""
        with self.lock:
            return self.warnings[-limit:]

    def get_suggestions(self, limit: int = 10) -> List[ResourceOptimizationSuggestion]:
        """获取优化建议"""
        with self.lock:
            return self.suggestions[-limit:]

    def clear_warnings(self):
        """清除警告"""
        with self.lock:
            self.warnings = []

    def clear_suggestions(self):
        """清除建议"""
        with self.lock:
            self.suggestions = []

    def update_config(self, config: ResourceMonitoringConfig):
        """更新监控配置"""
        with self.lock:
            self.config = config

    def get_config(self) -> ResourceMonitoringConfig:
        """获取监控配置"""
        return self.config

# 创建全局实例
resource_monitoring_service = ResourceMonitoringService()