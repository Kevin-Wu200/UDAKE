/**
 * 推送通知管理器
 * 实现任务完成通知、错误提醒通知、更新提醒通知
 */

export type NotificationType = 'taskSuccess' | 'taskFailure' | 'taskBatch' | 'uploadError' | 'interpolationError' | 'networkError' | 'newFeature' | 'systemMaintenance' | 'dataUpdate';

export type NotificationPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface NotificationOptions {
    type: NotificationType;
    title: string;
    body: string;
    icon?: string;
    tag?: string;
    priority?: NotificationPriority;
    actions?: NotificationAction[];
    data?: any;
    timeout?: number;
    sound?: string;
}

export interface NotificationAction {
    id: string;
    label: string;
    icon?: string;
    action: () => void;
}

export interface NotificationSettings {
    enabled: boolean;
    types: Set<NotificationType>;
    doNotDisturb: boolean;
    doNotDisturbStart?: string; // HH:mm format
    doNotDisturbEnd?: string; // HH:mm format
    sound: boolean;
    vibration: boolean;
}

interface StoredNotification extends NotificationOptions {
    id: string;
    timestamp: number;
    read: boolean;
}

export class NotificationManager {
    private settings: NotificationSettings;
    private notifications: Map<string, StoredNotification> = new Map();
    private notificationHistory: StoredNotification[] = [];
    private permission: NotificationPermission = 'default';
    private pendingNotifications: NotificationOptions[] = [];

    constructor() {
        this.settings = this.loadSettings();
        this.init();
    }

    /**
     * 初始化
     */
    private async init(): Promise<void> {
        // 请求通知权限
        if ('Notification' in window) {
            this.permission = Notification.permission;

            if (this.permission === 'default') {
                this.permission = await Notification.requestPermission();
            }
        }

        // 加载历史通知
        this.loadNotificationHistory();

        // 处理通知点击
        if ('serviceWorker' in navigator && 'onnotificationclick' in ServiceWorkerRegistration.prototype) {
            // Service Worker 通知点击处理在 sw.js 中实现
        }
    }

    /**
     * 加载通知设置
     */
    private loadSettings(): NotificationSettings {
        const saved = localStorage.getItem('notificationSettings');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                return {
                    enabled: parsed.enabled ?? true,
                    types: new Set(parsed.types || ['taskSuccess', 'taskFailure', 'uploadError', 'interpolationError', 'networkError']),
                    doNotDisturb: parsed.doNotDisturb ?? false,
                    doNotDisturbStart: parsed.doNotDisturbStart,
                    doNotDisturbEnd: parsed.doNotDisturbEnd,
                    sound: parsed.sound ?? true,
                    vibration: parsed.vibration ?? true,
                };
            } catch (e) {
                console.error('加载通知设置失败:', e);
            }
        }

        return this.getDefaultSettings();
    }

    /**
     * 获取默认设置
     */
    private getDefaultSettings(): NotificationSettings {
        return {
            enabled: true,
            types: new Set(['taskSuccess', 'taskFailure', 'uploadError', 'interpolationError', 'networkError']),
            doNotDisturb: false,
            sound: true,
            vibration: true,
        };
    }

    /**
     * 保存通知设置
     */
    private saveSettings(): void {
        localStorage.setItem('notificationSettings', JSON.stringify({
            enabled: this.settings.enabled,
            types: Array.from(this.settings.types),
            doNotDisturb: this.settings.doNotDisturb,
            doNotDisturbStart: this.settings.doNotDisturbStart,
            doNotDisturbEnd: this.settings.doNotDisturbEnd,
            sound: this.settings.sound,
            vibration: this.settings.vibration,
        }));
    }

    /**
     * 加载通知历史
     */
    private loadNotificationHistory(): void {
        const saved = localStorage.getItem('notificationHistory');
        if (saved) {
            try {
                this.notificationHistory = JSON.parse(saved);
                // 限制历史记录数量
                if (this.notificationHistory.length > 100) {
                    this.notificationHistory = this.notificationHistory.slice(-100);
                }
            } catch (e) {
                console.error('加载通知历史失败:', e);
            }
        }
    }

    /**
     * 保存通知历史
     */
    private saveNotificationHistory(): void {
        localStorage.setItem('notificationHistory', JSON.stringify(this.notificationHistory));
    }

    /**
     * 检查是否在免打扰时段
     */
    private isInDoNotDisturbPeriod(): boolean {
        if (!this.settings.doNotDisturb) {
            return false;
        }

        const now = new Date();
        const currentTime = now.getHours() * 60 + now.getMinutes();

        const start = this.settings.doNotDisturbStart;
        const end = this.settings.doNotDisturbEnd;

        if (!start || !end) {
            return false;
        }

        const [startHour, startMin] = start.split(':').map(Number);
        const [endHour, endMin] = end.split(':').map(Number);

        const startTime = startHour * 60 + startMin;
        const endTime = endHour * 60 + endMin;

        // 处理跨天情况
        if (startTime < endTime) {
            return currentTime >= startTime && currentTime < endTime;
        } else {
            return currentTime >= startTime || currentTime < endTime;
        }
    }

    /**
     * 检查是否可以发送通知
     */
    private canSendNotification(type: NotificationType): boolean {
        // 检查全局开关
        if (!this.settings.enabled) {
            return false;
        }

        // 检查类型是否启用
        if (!this.settings.types.has(type)) {
            return false;
        }

        // 检查免打扰时段
        if (this.isInDoNotDisturbPeriod()) {
            return false;
        }

        // 检查权限
        if (this.permission !== 'granted') {
            return false;
        }

        return true;
    }

    /**
     * 发送通知
     */
    public show(options: NotificationOptions): void {
        if (!this.canSendNotification(options.type)) {
            return;
        }

        const notification: StoredNotification = {
            ...options,
            id: `notif_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            timestamp: Date.now(),
            read: false,
        };

        // 添加到历史记录
        this.notificationHistory.push(notification);
        if (this.notificationHistory.length > 100) {
            this.notificationHistory.shift();
        }
        this.saveNotificationHistory();

        // 显示浏览器通知
        if ('Notification' in window && this.permission === 'granted') {
            this.showBrowserNotification(notification);
        }

        // 播放声音
        if (this.settings.sound && options.sound) {
            this.playSound(options.sound);
        }

        // 震动反馈
        if (this.settings.vibration) {
            this.vibrate();
        }

        // 触发自定义事件
        this.dispatchEvent('notification', notification);
    }

    /**
     * 显示浏览器通知
     */
    private showBrowserNotification(notification: StoredNotification): void {
        const browserNotificationOptions: {
            body?: string;
            icon?: string;
            tag?: string;
            data?: any;
            actions?: Array<{
                action: string;
                title: string;
                icon?: string;
            }>;
        } = {
            body: notification.body,
            icon: notification.icon || '/icon-192.png',
            tag: notification.tag,
            data: notification.data,
        };

        // 添加操作按钮
        if (notification.actions && notification.actions.length > 0) {
            browserNotificationOptions.actions = notification.actions.map(action => ({
                action: action.id,
                title: action.label,
                icon: action.icon,
            }));
        }

        const browserNotification = new Notification(notification.title, browserNotificationOptions);

        // 点击事件
        browserNotification.onclick = () => {
            window.focus();
            browserNotification.close();

            // 标记为已读
            this.markAsRead(notification.id);

            // 触发点击事件
            this.dispatchEvent('notificationClick', notification);
        };

        // 关闭事件
        browserNotification.onclose = () => {
            this.dispatchEvent('notificationClose', notification);
        };
    }

    /**
     * 播放声音
     */
    private playSound(soundUrl: string): void {
        try {
            const audio = new Audio(soundUrl);
            audio.play().catch(e => {
                console.warn('播放通知声音失败:', e);
            });
        } catch (e) {
            console.warn('播放通知声音失败:', e);
        }
    }

    /**
     * 震动
     */
    private vibrate(): void {
        if ('vibrate' in navigator) {
            navigator.vibrate([200, 100, 200]);
        }
    }

    /**
     * 任务完成通知 - 成功
     */
    public notifyTaskSuccess(taskId: string, taskName: string): void {
        this.show({
            type: 'taskSuccess',
            title: '任务完成',
            body: `${taskName} 已成功完成`,
            icon: '/icons/success.png',
            tag: `task_${taskId}`,
            priority: 'normal',
            data: { taskId, taskName },
            sound: '/sounds/success.mp3',
        });
    }

    /**
     * 任务完成通知 - 失败
     */
    public notifyTaskFailure(taskId: string, taskName: string, error: string): void {
        this.show({
            type: 'taskFailure',
            title: '任务失败',
            body: `${taskName} 执行失败: ${error}`,
            icon: '/icons/error.png',
            tag: `task_${taskId}`,
            priority: 'high',
            data: { taskId, taskName, error },
            sound: '/sounds/error.mp3',
            actions: [
                {
                    id: 'retry',
                    label: '重试',
                    action: () => {
                        // 重试任务
                        this.dispatchEvent('retryTask', { taskId });
                    },
                },
            ],
        });
    }

    /**
     * 批量任务完成通知
     */
    public notifyTaskBatch(successCount: number, failureCount: number): void {
        this.show({
            type: 'taskBatch',
            title: '批量任务完成',
            body: `成功: ${successCount}, 失败: ${failureCount}`,
            icon: '/icons/batch.png',
            priority: 'normal',
            data: { successCount, failureCount },
            sound: '/sounds/batch.mp3',
        });
    }

    /**
     * 上传失败通知
     */
    public notifyUploadError(fileName: string, error: string): void {
        this.show({
            type: 'uploadError',
            title: '上传失败',
            body: `${fileName} 上传失败: ${error}`,
            icon: '/icons/upload-error.png',
            tag: `upload_${fileName}`,
            priority: 'high',
            data: { fileName, error },
            sound: '/sounds/error.mp3',
            actions: [
                {
                    id: 'retry',
                    label: '重试',
                    action: () => {
                        this.dispatchEvent('retryUpload', { fileName });
                    },
                },
            ],
        });
    }

    /**
     * 插值失败通知
     */
    public notifyInterpolationError(taskId: string, error: string): void {
        this.show({
            type: 'interpolationError',
            title: '插值失败',
            body: `插值任务执行失败: ${error}`,
            icon: '/icons/interpolation-error.png',
            tag: `interpolation_${taskId}`,
            priority: 'high',
            data: { taskId, error },
            sound: '/sounds/error.mp3',
        });
    }

    /**
     * 网络错误通知
     */
    public notifyNetworkError(): void {
        this.show({
            type: 'networkError',
            title: '网络错误',
            body: '网络连接失败，请检查网络设置',
            icon: '/icons/network-error.png',
            tag: 'network_error',
            priority: 'urgent',
            sound: '/sounds/error.mp3',
        });
    }

    /**
     * 新功能更新通知
     */
    public notifyNewFeature(featureName: string, description: string): void {
        this.show({
            type: 'newFeature',
            title: '新功能',
            body: `${featureName}: ${description}`,
            icon: '/icons/new-feature.png',
            priority: 'normal',
            data: { featureName, description },
            sound: '/sounds/new-feature.mp3',
            actions: [
                {
                    id: 'learnMore',
                    label: '了解更多',
                    action: () => {
                        this.dispatchEvent('learnMore', { featureName });
                    },
                },
            ],
        });
    }

    /**
     * 系统维护通知
     */
    public notifySystemMaintenance(startTime: string, endTime: string): void {
        this.show({
            type: 'systemMaintenance',
            title: '系统维护',
            body: `系统将在 ${startTime} 至 ${endTime} 进行维护`,
            icon: '/icons/maintenance.png',
            priority: 'normal',
            data: { startTime, endTime },
        });
    }

    /**
     * 数据更新通知
     */
    public notifyDataUpdate(updateType: string): void {
        this.show({
            type: 'dataUpdate',
            title: '数据更新',
            body: `${updateType} 数据已更新`,
            icon: '/icons/data-update.png',
            priority: 'low',
            data: { updateType },
        });
    }

    /**
     * 批量合并通知
     */
    public showBatchedNotifications(notifications: NotificationOptions[]): void {
        // 按优先级分组
        const grouped = notifications.reduce((acc, notif) => {
            const priority = notif.priority || 'normal';
            if (!acc[priority]) {
                acc[priority] = [];
            }
            acc[priority].push(notif);
            return acc;
        }, {} as Record<string, NotificationOptions[]>);

        // 按优先级顺序发送
        const priorities: NotificationPriority[] = ['urgent', 'high', 'normal', 'low'];
        for (const priority of priorities) {
            if (grouped[priority]) {
                // 去重
                const deduped = this.deduplicateNotifications(grouped[priority]);
                for (const notif of deduped) {
                    this.show(notif);
                }
            }
        }
    }

    /**
     * 去重通知
     */
    private deduplicateNotifications(notifications: NotificationOptions[]): NotificationOptions[] {
        const seen = new Set<string>();
        const result: NotificationOptions[] = [];

        for (const notif of notifications) {
            const key = `${notif.type}_${notif.title}_${notif.body}`;
            if (!seen.has(key)) {
                seen.add(key);
                result.push(notif);
            }
        }

        return result;
    }

    /**
     * 标记为已读
     */
    public markAsRead(notificationId: string): void {
        const notification = this.notificationHistory.find(n => n.id === notificationId);
        if (notification) {
            notification.read = true;
            this.saveNotificationHistory();
            this.dispatchEvent('notificationRead', notification);
        }
    }

    /**
     * 标记所有为已读
     */
    public markAllAsRead(): void {
        this.notificationHistory.forEach(n => n.read = true);
        this.saveNotificationHistory();
        this.dispatchEvent('allNotificationsRead');
    }

    /**
     * 删除通知
     */
    public deleteNotification(notificationId: string): void {
        this.notificationHistory = this.notificationHistory.filter(n => n.id !== notificationId);
        this.saveNotificationHistory();
        this.dispatchEvent('notificationDeleted', { notificationId });
    }

    /**
     * 清除所有通知
     */
    public clearAll(): void {
        this.notificationHistory = [];
        this.saveNotificationHistory();
        this.dispatchEvent('allNotificationsCleared');
    }

    /**
     * 获取未读通知
     */
    public getUnreadNotifications(): StoredNotification[] {
        return this.notificationHistory.filter(n => !n.read);
    }

    /**
     * 获取通知历史
     */
    public getNotificationHistory(limit: number = 50): StoredNotification[] {
        return this.notificationHistory.slice(-limit);
    }

    /**
     * 更新设置
     */
    public updateSettings(settings: Partial<NotificationSettings>): void {
        this.settings = { ...this.settings, ...settings };
        this.saveSettings();
        this.dispatchEvent('settingsUpdated', this.settings);
    }

    /**
     * 获取设置
     */
    public getSettings(): NotificationSettings {
        return { ...this.settings };
    }

    /**
     * 启用通知类型
     */
    public enableNotificationType(type: NotificationType): void {
        this.settings.types.add(type);
        this.saveSettings();
    }

    /**
     * 禁用通知类型
     */
    public disableNotificationType(type: NotificationType): void {
        this.settings.types.delete(type);
        this.saveSettings();
    }

    /**
     * 设置免打扰时段
     */
    public setDoNotDisturbPeriod(start: string, end: string): void {
        this.settings.doNotDisturbStart = start;
        this.settings.doNotDisturbEnd = end;
        this.settings.doNotDisturb = true;
        this.saveSettings();
    }

    /**
     * 禁用免打扰
     */
    public disableDoNotDisturb(): void {
        this.settings.doNotDisturb = false;
        this.saveSettings();
    }

    /**
     * 获取通知权限
     */
    public getPermission(): NotificationPermission {
        return this.permission;
    }

    /**
     * 请求通知权限
     */
    public async requestPermission(): Promise<NotificationPermission> {
        if ('Notification' in window) {
            this.permission = await Notification.requestPermission();
            return this.permission;
        }
        return 'denied';
    }

    /**
     * 事件监听
     */
    private listeners: Map<string, Set<Function>> = new Map();

    public on(event: string, callback: Function): void {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event)!.add(callback);
    }

    public off(event: string, callback: Function): void {
        const listeners = this.listeners.get(event);
        if (listeners) {
            listeners.delete(callback);
        }
    }

    private dispatchEvent(event: string, data?: any): void {
        const listeners = this.listeners.get(event);
        if (listeners) {
            listeners.forEach(callback => callback(data));
        }
    }

    /**
     * 销毁管理器
     */
    public destroy(): void {
        this.notifications.clear();
        this.notificationHistory = [];
        this.listeners.clear();
    }
}

// 导出单例
export default new NotificationManager();