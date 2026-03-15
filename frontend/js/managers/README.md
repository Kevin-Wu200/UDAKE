# 任务管理器使用指南

## 概述

任务管理器（TaskManager）是一个强大的后台任务管理系统，支持任务的创建、执行、监控、暂停、恢复和取消。它集成了本地通知、任务持久化存储和优先级队列管理等功能。

## 主要特性

- ✅ **任务队列管理**：支持优先级队列，智能调度任务执行
- ✅ **任务持久化**：使用 IndexedDB 存储任务数据，应用重启后自动恢复
- ✅ **本地通知**：集成 Capacitor Local Notifications，任务完成/失败时发送通知
- ✅ **任务控制**：支持暂停、恢复、取消任务
- ✅ **进度跟踪**：实时更新任务进度
- ✅ **错误处理**：自动重试失败任务
- ✅ **历史记录**：保存已完成/失败的任务历史
- ✅ **统计信息**：提供任务执行统计和成功率分析

## 快速开始

### 1. 初始化任务管理器

```typescript
import TaskManager from './managers/TaskManager';
import { initializeTaskManager } from './TaskManager集成示例';
import { APIService } from './services/API封装';

// 在应用启动时初始化
const apiService = new APIService();
const taskManager = initializeTaskManager(apiService);
```

### 2. 创建任务

```typescript
// 创建空间插值任务
const task = await taskManager.createTask(
    'interpolation',
    '空间插值分析',
    {
        boundary: boundaryData,
        samplePoints: pointsData,
        method: 'kriging'
    },
    {
        priority: 'high',
        notifyOnCompletion: true,
        estimatedDuration: 120000 // 2分钟
    }
);
```

### 3. 监听任务事件

```typescript
taskManager.on('created', (event) => {
    console.log('任务创建:', event.task);
});

taskManager.on('progress', (event) => {
    console.log('任务进度:', event.task.progress);
    updateProgressBar(event.task.progress);
});

taskManager.on('completed', (event) => {
    console.log('任务完成:', event.task.result);
    showResult(event.task.result);
});
```

### 4. 控制任务

```typescript
// 暂停任务
await taskManager.pauseTask(taskId);

// 恢复任务
await taskManager.resumeTask(taskId);

// 取消任务
await taskManager.cancelTask(taskId);
```

### 5. 查看任务

```typescript
// 获取单个任务
const task = await taskManager.getTask(taskId);

// 获取所有任务
const tasks = await taskManager.getAllTasks();

// 获取任务历史
const history = await taskManager.getTaskHistory(50);

// 获取统计信息
const stats = await taskManager.getStats();
```

## 任务类型

支持以下任务类型：

- `interpolation` - 空间插值任务
- `sampling` - 采样任务
- `analysis` - 数据分析任务
- `export` - 数据导出任务
- `import` - 数据导入任务
- `custom` - 自定义任务

## 任务优先级

- `urgent` - 紧急（最高优先级）
- `high` - 高优先级
- `normal` - 普通优先级（默认）
- `low` - 低优先级

## 任务状态

- `pending` - 待处理
- `running` - 运行中
- `paused` - 已暂停
- `completed` - 已完成
- `failed` - 失败
- `cancelled` - 已取消

## 注册自定义任务执行器

```typescript
import { TaskExecutor, Task } from '../types/task-manager';

class CustomTaskExecutor implements TaskExecutor {
    async execute(task: Task, onProgress: (progress: number) => void): Promise<any> {
        // 实现任务执行逻辑
        onProgress(0);

        // 执行任务...
        await doSomething();

        onProgress(100);

        return { result: 'done' };
    }

    async cancel(taskId: string): Promise<void> {
        // 实现取消逻辑（可选）
    }
}

// 注册执行器
taskManager.registerExecutor('custom', new CustomTaskExecutor());
```

## 使用任务管理面板

```typescript
import { TaskManagementPanel } from './components/TaskManagementPanel';

// 创建面板
const container = document.getElementById('task-panel');
const panel = new TaskManagementPanel(container);

// 面板会自动显示任务列表、详情和操作按钮
```

## 示例代码

### 批量创建任务

```typescript
import { createBatchTasks } from './TaskManager集成示例';

const tasks = await createBatchTasks(taskManager, [
    {
        type: 'interpolation',
        name: '区域1插值',
        data: { boundary: region1 },
        priority: 'high'
    },
    {
        type: 'interpolation',
        name: '区域2插值',
        data: { boundary: region2 },
        priority: 'normal'
    },
    {
        type: 'sampling',
        name: '区域1采样',
        data: { boundary: region1 },
        priority: 'normal'
    }
]);
```

### 监控任务状态

```typescript
import { monitorTask } from './TaskManager集成示例';

try {
    const result = await monitorTask(taskManager, taskId, (task) => {
        console.log('任务进度:', task.progress);
        updateUI(task);
    });
    console.log('任务完成:', result);
} catch (error) {
    console.error('任务失败:', error);
}
```

### 获取统计信息

```typescript
import { getTaskStatistics } from './TaskManager集成示例';

const stats = await getTaskStatistics(taskManager);
console.log('任务统计:', stats);
// 输出:
// {
//   总任务数: 50,
//   待处理: 5,
//   运行中: 2,
//   已完成: 40,
//   失败: 3,
//   平均时长: "45.23秒",
//   成功率: "93.0%"
// }
```

## 注意事项

1. **应用生命周期**：任务管理器会在应用切换到后台时继续执行任务
2. **通知权限**：首次使用需要请求通知权限
3. **任务超时**：默认任务超时时间为 5 分钟，可在初始化时配置
4. **存储限制**：IndexedDB 有存储大小限制，建议定期清理历史记录
5. **Android 限制**：Android 系统对后台任务有限制，某些操作可能需要应用在前台

## 配置选项

```typescript
const taskManager = TaskManager.getInstance({
    enablePersistence: true,      // 启用任务持久化
    enableNotifications: true,    // 启用本地通知
    maxRetries: 3,                // 最大重试次数
    taskTimeout: 300000          // 任务超时时间（毫秒）
});
```

## 文件结构

```
frontend/js/
├── managers/
│   ├── TaskManager.ts           # 任务管理器核心
│   ├── TaskQueue.ts             # 任务队列
│   ├── TaskStorage.ts           # 任务持久化存储
│   └── TaskExecutors.ts         # 任务执行器示例
├── components/
│   ├── TaskManagementPanel.ts   # 任务管理UI组件
│   └── NotificationManager.ts   # 通知管理器
├── types/
│   └── task-manager.ts          # 类型定义
└── TaskManager集成示例.ts       # 集成示例和工具函数
```

## 样式文件

任务管理面板的样式在 `frontend/css/任务管理面板样式.css` 中，支持深色模式。

## 故障排除

### 任务不执行

1. 检查任务执行器是否已注册
2. 查看控制台是否有错误信息
3. 确认任务管理器已启动

### 通知不显示

1. 检查通知权限是否已授予
2. 确认 `enableNotifications` 已启用
3. 查看设备通知设置

### 任务恢复失败

1. 检查 IndexedDB 是否正常工作
2. 确认任务数据格式正确
3. 查看浏览器控制台错误信息

## 性能优化建议

1. **批量任务**：对于大量任务，使用批量创建减少数据库操作
2. **历史清理**：定期清理历史记录，避免 IndexedDB 过大
3. **优先级设置**：合理设置任务优先级，确保重要任务优先执行
4. **进度更新**：避免过于频繁的进度更新，建议每秒最多更新 1-2 次

## 更多示例

更多示例代码请参考 `TaskManager集成示例.ts` 文件。

## 贡献

如有问题或建议，请提交 Issue 或 Pull Request。

## 许可证

MIT License