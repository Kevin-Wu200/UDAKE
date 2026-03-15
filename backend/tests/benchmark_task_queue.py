"""
任务队列性能测试
测试任务队列在优化前后的性能对比
"""
import time
import asyncio
import threading
import statistics
from typing import Dict, Any
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.任务队列管理器 import TaskQueueManager
from app.schemas.任务队列模型 import QueueTaskPriority, QueueConfig


class BenchmarkResults:
    """性能测试结果"""

    def __init__(self):
        self.add_times: list = []
        self.process_times: list = []
        self.concurrent_add_times: list = []
        self.concurrent_process_times: list = []
        self.lock_contention_count: int = 0

    def print_summary(self):
        """打印性能测试摘要"""
        print("\n" + "=" * 60)
        print("性能测试结果摘要")
        print("=" * 60)

        if self.add_times:
            print(f"\n添加任务性能:")
            print(f"  平均耗时: {statistics.mean(self.add_times):.4f}s")
            print(f"  最小耗时: {min(self.add_times):.4f}s")
            print(f"  最大耗时: {max(self.add_times):.4f}s")
            print(f"  中位数: {statistics.median(self.add_times):.4f}s")

        if self.process_times:
            print(f"\n处理任务性能:")
            print(f"  平均耗时: {statistics.mean(self.process_times):.4f}s")
            print(f"  最小耗时: {min(self.process_times):.4f}s")
            print(f"  最大耗时: {max(self.process_times):.4f}s")
            print(f"  中位数: {statistics.median(self.process_times):.4f}s")

        if self.concurrent_add_times:
            print(f"\n并发添加任务性能:")
            print(f"  平均耗时: {statistics.mean(self.concurrent_add_times):.4f}s")
            print(f"  最小耗时: {min(self.concurrent_add_times):.4f}s")
            print(f"  最大耗时: {max(self.concurrent_add_times):.4f}s")
            print(f"  中位数: {statistics.median(self.concurrent_add_times):.4f}s")

        if self.concurrent_process_times:
            print(f"\n并发处理任务性能:")
            print(f"  平均耗时: {statistics.mean(self.concurrent_process_times):.4f}s")
            print(f"  最小耗时: {min(self.concurrent_process_times):.4f}s")
            print(f"  最大耗时: {max(self.concurrent_process_times):.4f}s")
            print(f"  中位数: {statistics.median(self.concurrent_process_times):.4f}s")

        print(f"\n锁竞争次数: {self.lock_contention_count}")
        print("=" * 60)


async def benchmark_add_tasks(queue_manager: TaskQueueManager, num_tasks: int = 1000) -> float:
    """
    测试添加任务性能

    Args:
        queue_manager: 任务队列管理器
        num_tasks: 任务数量

    Returns:
        耗时（秒）
    """
    start = time.time()

    priorities = [QueueTaskPriority.URGENT, QueueTaskPriority.HIGH,
                  QueueTaskPriority.MEDIUM, QueueTaskPriority.LOW]

    for i in range(num_tasks):
        priority = priorities[i % len(priorities)]
        queue_manager.add_task(
            task_type=f"test_task_{i}",
            parameters={"data": i, "iteration": i},
            priority=priority,
            metadata={"benchmark": True}
        )

    return time.time() - start


async def benchmark_concurrent_add_tasks(queue_manager: TaskQueueManager, num_tasks: int = 1000, num_workers: int = 10) -> float:
    """
    测试并发添加任务性能

    Args:
        queue_manager: 任务队列管理器
        num_tasks: 任务数量
        num_workers: 工作线程数

    Returns:
        耗时（秒）
    """
    start = time.time()

    async def add_batch(start_index: int, batch_size: int):
        priorities = [QueueTaskPriority.URGENT, QueueTaskPriority.HIGH,
                      QueueTaskPriority.MEDIUM, QueueTaskPriority.LOW]

        for i in range(start_index, start_index + batch_size):
            priority = priorities[i % len(priorities)]
            queue_manager.add_task(
                task_type=f"test_task_{i}",
                parameters={"data": i, "iteration": i},
                priority=priority,
                metadata={"benchmark": True}
            )

    batch_size = num_tasks // num_workers
    tasks = []
    for i in range(num_workers):
        start_index = i * batch_size
        tasks.append(add_batch(start_index, batch_size))

    await asyncio.gather(*tasks)

    return time.time() - start


async def benchmark_lock_contention(queue_manager: TaskQueueManager, num_tasks: int = 1000, num_workers: int = 20) -> int:
    """
    测试锁竞争情况

    Args:
        queue_manager: 任务队列管理器
        num_tasks: 任务数量
        num_workers: 工作线程数

    Returns:
        锁竞争次数
    """
    lock_contention_count = 0
    lock_stats_list = []

    async def add_and_get_task(task_id: int):
        try:
            queue_manager.add_task(
                task_type=f"test_task_{task_id}",
                parameters={"data": task_id},
                priority=QueueTaskPriority.MEDIUM
            )
            task = queue_manager.get_task(f"test_task_{task_id}")

            # 收集锁统计信息
            lock_stats = queue_manager.get_lock_statistics()
            lock_stats_list.append(lock_stats)

        except Exception as e:
            nonlocal lock_contention_count
            lock_contention_count += 1

    tasks = [add_and_get_task(i) for i in range(num_tasks)]
    await asyncio.gather(*tasks)

    # 计算平均锁竞争情况
    if lock_stats_list:
        avg_locked_count = statistics.mean(
            [stats['task_lock']['locked_count'] for stats in lock_stats_list]
        )
        print(f"平均被锁住的分段数: {avg_locked_count:.2f}")

    return lock_contention_count


async def benchmark_statistics(queue_manager: TaskQueueManager) -> Dict[str, Any]:
    """
    测试统计功能性能

    Args:
        queue_manager: 任务队列管理器

    Returns:
        统计信息
    """
    start = time.time()
    stats = queue_manager.get_statistics()
    stats_time = time.time() - start

    lock_stats = queue_manager.get_lock_statistics()

    return {
        'statistics': stats,
        'lock_statistics': lock_stats,
        'stats_time': stats_time
    }


async def run_benchmark_suite():
    """运行完整的性能测试套件"""
    print("开始任务队列性能测试...")
    print("=" * 60)

    results = BenchmarkResults()

    # 测试1: 基础添加任务性能
    print("\n测试1: 基础添加任务性能 (500个任务)")
    queue_manager = TaskQueueManager()
    # 更新配置以支持更多任务
    config = QueueConfig(queue_size_limit=1000, max_concurrent_tasks=20)
    queue_manager.update_config(config)
    add_time = await benchmark_add_tasks(queue_manager, 500)
    results.add_times.append(add_time)
    print(f"✓ 完成，耗时: {add_time:.4f}s")

    # 测试2: 并发添加任务性能
    print("\n测试2: 并发添加任务性能 (500个任务，10个工作线程)")
    queue_manager = TaskQueueManager()
    config = QueueConfig(queue_size_limit=1000, max_concurrent_tasks=20)
    queue_manager.update_config(config)
    concurrent_add_time = await benchmark_concurrent_add_tasks(queue_manager, 500, 10)
    results.concurrent_add_times.append(concurrent_add_time)
    print(f"✓ 完成，耗时: {concurrent_add_time:.4f}s")

    # 测试3: 锁竞争测试
    print("\n测试3: 锁竞争测试 (500个任务，20个工作线程)")
    queue_manager = TaskQueueManager()
    config = QueueConfig(queue_size_limit=1000, max_concurrent_tasks=20)
    queue_manager.update_config(config)
    contention_count = await benchmark_lock_contention(queue_manager, 500, 20)
    results.lock_contention_count = contention_count
    print(f"✓ 完成，锁竞争次数: {contention_count}")

    # 测试4: 统计功能性能
    print("\n测试4: 统计功能性能")
    queue_manager = TaskQueueManager()
    # 先添加一些任务
    await benchmark_add_tasks(queue_manager, 100)
    stats_result = await benchmark_statistics(queue_manager)
    print(f"✓ 完成，统计耗时: {stats_result['stats_time']:.4f}s")

    # 打印结果摘要
    results.print_summary()

    # 性能评估
    print("\n性能评估:")
    print("-" * 60)

    # 评估添加任务性能
    if results.add_times and results.concurrent_add_times:
        sequential_avg = statistics.mean(results.add_times)
        concurrent_avg = statistics.mean(results.concurrent_add_times)
        speedup = sequential_avg / concurrent_avg if concurrent_avg > 0 else 0
        print(f"添加任务加速比: {speedup:.2f}x")
        if speedup > 1.5:
            print("  ✓ 并发性能优秀，分段锁有效减少了锁竞争")
        elif speedup > 1.2:
            print("  ✓ 并发性能良好")
        else:
            print("  ! 并发性能一般，可能需要优化")

    # 评估锁竞争
    print(f"锁竞争率: {results.lock_contention_count / 1000 * 100:.2f}%")
    if results.lock_contention_count < 50:
        print("  ✓ 锁竞争低，分段锁策略有效")
    elif results.lock_contention_count < 100:
        print("  ✓ 锁竞争适中")
    else:
        print("  ! 锁竞争较高，建议增加分段数或优化锁策略")

    print("\n优化建议:")
    print("-" * 60)
    print("1. 如果并发性能提升不明显，可以考虑:")
    print("   - 增加分段锁的分段数（当前16）")
    print("   - 使用更细粒度的锁策略")
    print("2. 如果锁竞争仍然较高，可以考虑:")
    print("   - 使用无锁数据结构")
    print("   - 实现乐观锁机制")
    print("3. 任务持久化可以根据实际需求:")
    print("   - 使用数据库替代文件存储")
    print("   - 实现批量写入以减少IO操作")

    print("\n测试完成!")


if __name__ == "__main__":
    # 运行性能测试
    asyncio.run(run_benchmark_suite())