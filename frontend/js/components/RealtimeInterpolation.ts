/**
 * 实时插值组件
 * Realtime Interpolation Component

实现实时数据订阅、展示和更新状态显示
支持增量插值、实时更新和性能监控
 */

import { WebSocketService, WebSocketMessage } from '../services/WebSocketService';
import { NotificationManager } from './NotificationManager';

export interface RealtimeSubscription {
    id: string;
    name: string;
    area: {
        minLon: number;
        minLat: number;
        maxLon: number;
        maxLat: number;
    };
    updateInterval: number; // 更新间隔（毫秒）
    active: boolean;
    createdAt: Date;
}

export interface RealtimeUpdate {
    subscriptionId: string;
    timestamp: Date;
    affectedArea: {
        minLon: number;
        minLat: number;
        maxLon: number;
        maxLat: number;
    };
    updateType: 'incremental' | 'full' | 'partial';
    dataPoints: number;
    updateDuration: number; // 毫秒
    cacheHitRate: number; // 缓存命中率
}

export interface PerformanceMetrics {
    lastUpdateTime: Date;
    averageUpdateDuration: number;
    totalUpdates: number;
    cacheHitRate: number;
    activeSubscriptions: number;
    memoryUsage: number; // MB
    cpuUsage: number; // %
}

export interface HotspotArea {
    id: string;
    center: { lon: number; lat: number };
    radius: number;
    intensity: number;
    trend: 'increasing' | 'decreasing' | 'stable';
}

export class RealtimeInterpolation {
    private wsService: WebSocketService | null = null;
    private notificationManager: NotificationManager;
    private subscriptions: Map<string, RealtimeSubscription> = new Map();
    private updateHistory: RealtimeUpdate[] = [];
    private maxHistorySize = 100;
    private performanceMetrics: PerformanceMetrics;
    private hotspots: Map<string, HotspotArea> = new Map();
    private updateCallbacks: Set<(update: RealtimeUpdate) => void> = new Set();
    private hotspotCallbacks: Set<(hotspots: HotspotArea[]) => void> = new Set();
    private errorCallbacks: Set<(error: Error) => void> = new Set();
    private isMonitoring = false;
    private monitorInterval: number | null = null;

    constructor() {
        this.notificationManager = new NotificationManager();
        this.performanceMetrics = {
            lastUpdateTime: new Date(),
            averageUpdateDuration: 0,
            totalUpdates: 0,
            cacheHitRate: 0,
            activeSubscriptions: 0,
            memoryUsage: 0,
            cpuUsage: 0
        };
    }

    /**
     * 初始化组件
     */
    async initialize(): Promise<void> {
        try {
            // 初始化WebSocket服务
            const wsUrl = this.getWebSocketUrl();
            this.wsService = new WebSocketService(wsUrl);
            const clientId = this.generateClientId();
            await this.wsService.connect(clientId);

            // 注册消息处理器
            this.wsService.on('realtime_update', this.handleRealtimeUpdate.bind(this));
            this.wsService.on('hotspot_alert', this.handleHotspotAlert.bind(this));
            this.wsService.on('performance_metrics', this.handlePerformanceMetrics.bind(this));
            this.wsService.on('error', this.handleError.bind(this));

            // 开始性能监控
            this.startMonitoring();

            console.log('实时插值组件初始化成功');
        } catch (error) {
            console.error('实时插值组件初始化失败:', error);
            throw error;
        }
    }

    /**
     * 订阅实时数据
     */
    async subscribe(subscription: Omit<RealtimeSubscription, 'id' | 'createdAt'>): Promise<RealtimeSubscription> {
        if (!this.wsService || !this.wsService.isConnected()) {
            throw new Error('WebSocket未连接');
        }

        const newSubscription: RealtimeSubscription = {
            ...subscription,
            id: this.generateSubscriptionId(),
            createdAt: new Date(),
            active: true
        };

        // 发送订阅请求
        await this.wsService.send({
            type: 'subscribe',
            data: newSubscription,
            timestamp: new Date().toISOString()
        });

        // 存储订阅
        this.subscriptions.set(newSubscription.id, newSubscription);

        // 更新性能指标
        this.performanceMetrics.activeSubscriptions = this.subscriptions.size;

        console.log('订阅成功:', newSubscription.name);
        return newSubscription;
    }

    /**
     * 取消订阅
     */
    async unsubscribe(subscriptionId: string): Promise<void> {
        if (!this.wsService) {
            throw new Error('WebSocket服务未初始化');
        }

        const subscription = this.subscriptions.get(subscriptionId);
        if (!subscription) {
            throw new Error('订阅不存在');
        }

        // 发送取消订阅请求
        await this.wsService.send({
            type: 'unsubscribe',
            data: { subscriptionId },
            timestamp: new Date().toISOString()
        });

        // 移除订阅
        this.subscriptions.delete(subscriptionId);

        // 更新性能指标
        this.performanceMetrics.activeSubscriptions = this.subscriptions.size;

        console.log('取消订阅成功:', subscription.name);
    }

    /**
     * 获取所有订阅
     */
    getSubscriptions(): RealtimeSubscription[] {
        return Array.from(this.subscriptions.values());
    }

    /**
     * 获取活跃订阅
     */
    getActiveSubscriptions(): RealtimeSubscription[] {
        return Array.from(this.subscriptions.values()).filter(s => s.active);
    }

    /**
     * 获取更新历史
     */
    getUpdateHistory(): RealtimeUpdate[] {
        return [...this.updateHistory];
    }

    /**
     * 获取性能指标
     */
    getPerformanceMetrics(): PerformanceMetrics {
        return { ...this.performanceMetrics };
    }

    /**
     * 获取热点区域
     */
    getHotspots(): HotspotArea[] {
        return Array.from(this.hotspots.values());
    }

    /**
     * 注册更新回调
     */
    onUpdate(callback: (update: RealtimeUpdate) => void): void {
        this.updateCallbacks.add(callback);
    }

    /**
     * 注册热点回调
     */
    onHotspot(callback: (hotspots: HotspotArea[]) => void): void {
        this.hotspotCallbacks.add(callback);
    }

    /**
     * 注册错误回调
     */
    onError(callback: (error: Error) => void): void {
        this.errorCallbacks.add(callback);
    }

    /**
     * 取消回调
     */
    offUpdate(callback: (update: RealtimeUpdate) => void): void {
        this.updateCallbacks.delete(callback);
    }

    /**
     * 取消热点回调
     */
    offHotspot(callback: (hotspots: HotspotArea[]) => void): void {
        this.hotspotCallbacks.delete(callback);
    }

    /**
     * 取消错误回调
     */
    offError(callback: (error: Error) => void): void {
        this.errorCallbacks.delete(callback);
    }

    /**
     * 处理实时更新
     */
    private handleRealtimeUpdate(message: WebSocketMessage): void {
        try {
            const update: RealtimeUpdate = {
                ...message.data,
                timestamp: new Date(message.data.timestamp)
            };

            // 添加到历史记录
            this.updateHistory.push(update);
            if (this.updateHistory.length > this.maxHistorySize) {
                this.updateHistory.shift();
            }

            // 更新性能指标
            this.performanceMetrics.totalUpdates++;
            this.performanceMetrics.lastUpdateTime = update.timestamp;
            this.performanceMetrics.averageUpdateDuration =
                (this.performanceMetrics.averageUpdateDuration * (this.performanceMetrics.totalUpdates - 1) +
                 update.updateDuration) / this.performanceMetrics.totalUpdates;
            this.performanceMetrics.cacheHitRate = update.cacheHitRate;

            // 触发回调
            this.updateCallbacks.forEach(callback => callback(update));

            console.log('实时更新:', update);
        } catch (error) {
            console.error('处理实时更新失败:', error);
        }
    }

    /**
     * 处理热点告警
     */
    private handleHotspotAlert(message: WebSocketMessage): void {
        try {
            const hotspots: HotspotArea[] = message.data;

            // 更新热点区域
            hotspots.forEach(hotspot => {
                this.hotspots.set(hotspot.id, hotspot);
            });

            // 触发回调
            this.hotspotCallbacks.forEach(callback => callback(hotspots));

            // 显示通知
            if (hotspots.length > 0) {
                this.notificationManager.notify({
                    type: 'dataUpdate',
                    title: `检测到 ${hotspots.length} 个热点区域`,
                    body: hotspots.map(h => `${h.id}: ${h.intensity.toFixed(2)}`).join(', '),
                    priority: 'high'
                });
            }

            console.log('热点告警:', hotspots);
        } catch (error) {
            console.error('处理热点告警失败:', error);
        }
    }

    /**
     * 处理性能指标
     */
    private handlePerformanceMetrics(message: WebSocketMessage): void {
        try {
            const metrics: Partial<PerformanceMetrics> = message.data;

            // 更新性能指标
            Object.assign(this.performanceMetrics, metrics);

            console.log('性能指标更新:', metrics);
        } catch (error) {
            console.error('处理性能指标失败:', error);
        }
    }

    /**
     * 处理错误
     */
    private handleError(message: WebSocketMessage): void {
        const error = new Error(message.data.message || '未知错误');
        console.error('实时插值错误:', error);

        // 触发错误回调
        this.errorCallbacks.forEach(callback => callback(error));

        // 显示通知
        this.notificationManager.notify({
            type: 'interpolationError',
            title: '实时插值错误',
            body: message.data.message || '发生未知错误',
            priority: 'urgent'
        });
    }

    /**
     * 开始性能监控
     */
    private startMonitoring(): void {
        if (this.isMonitoring) {
            return;
        }

        this.isMonitoring = true;
        this.monitorInterval = window.setInterval(() => {
            this.collectPerformanceMetrics();
        }, 5000); // 每5秒收集一次性能指标

        console.log('性能监控已启动');
    }

    /**
     * 停止性能监控
     */
    private stopMonitoring(): void {
        if (!this.isMonitoring) {
            return;
        }

        this.isMonitoring = false;
        if (this.monitorInterval !== null) {
            clearInterval(this.monitorInterval);
            this.monitorInterval = null;
        }

        console.log('性能监控已停止');
    }

    /**
     * 收集性能指标
     */
    private collectPerformanceMetrics(): void {
        if (performance && performance.memory) {
            this.performanceMetrics.memoryUsage = performance.memory.usedJSHeapSize / 1024 / 1024;
        }

        // CPU使用率需要在后端计算
        // 这里仅发送请求获取最新指标
        if (this.wsService && this.wsService.isConnected()) {
            this.wsService.send({
                type: 'get_metrics',
                timestamp: new Date().toISOString()
            });
        }
    }

    /**
     * 获取WebSocket URL
     */
    private getWebSocketUrl(): string {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/realtime`;
    }

    /**
     * 生成客户端ID
     */
    private generateClientId(): string {
        return `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 生成订阅ID
     */
    private generateSubscriptionId(): string {
        return `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 销毁组件
     */
    destroy(): void {
        // 停止监控
        this.stopMonitoring();

        // 断开WebSocket连接
        if (this.wsService) {
            this.wsService.disconnect();
            this.wsService = null;
        }

        // 清理数据
        this.subscriptions.clear();
        this.updateHistory = [];
        this.hotspots.clear();
        this.updateCallbacks.clear();
        this.hotspotCallbacks.clear();
        this.errorCallbacks.clear();

        console.log('实时插值组件已销毁');
    }
}

// 导出单例实例
export const realtimeInterpolation = new RealtimeInterpolation();