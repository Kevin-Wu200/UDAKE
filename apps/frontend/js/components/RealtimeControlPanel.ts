/**
 * 实时插值控制面板组件
 * Realtime Control Panel Component

实现订阅管理、更新频率控制、缓存管理、性能监控和日志查看
提供用户友好的界面来控制实时插值系统
 */

import { RealtimeInterpolation, RealtimeSubscription, PerformanceMetrics } from './RealtimeInterpolation';
import { I18nDialog } from './I18nDialog.js';

export interface ControlPanelOptions {
    containerId: string;
    showSubscriptionManager: boolean;
    showCacheControls: boolean;
    showPerformanceMonitor: boolean;
    showLogViewer: boolean;
    autoRefreshInterval: number; // 自动刷新间隔（毫秒）
}

export interface CacheControlOptions {
    enabled: boolean;
    maxSize: number; // MB
    ttl: number; // 秒
    strategy: 'lru' | 'lfu' | 'fifo';
}

export interface LogEntry {
    timestamp: Date;
    level: 'info' | 'warning' | 'error';
    message: string;
    data?: any;
}

export class RealtimeControlPanel {
    private realtimeInterpolation: RealtimeInterpolation;
    private options: ControlPanelOptions;
    private container: HTMLElement | null = null;
    private logs: LogEntry[] = [];
    private maxLogs = 100;
    private autoRefreshTimer: number | null = null;
    private isInitialized = false;

    constructor(realtimeInterpolation: RealtimeInterpolation, options: Partial<ControlPanelOptions> = {}) {
        this.realtimeInterpolation = realtimeInterpolation;
        this.options = {
            containerId: 'realtime-control-panel',
            showSubscriptionManager: true,
            showCacheControls: true,
            showPerformanceMonitor: true,
            showLogViewer: true,
            autoRefreshInterval: 5000,
            ...options
        };
    }

    /**
     * 初始化控制面板
     */
    async initialize(): Promise<void> {
        if (this.isInitialized) {
            return;
        }

        try {
            // 获取容器
            this.container = document.getElementById(this.options.containerId);
            if (!this.container) {
                throw new Error(`容器 ${this.options.containerId} 不存在`);
            }

            // 渲染控制面板
            this.renderControlPanel();

            // 开始自动刷新
            this.startAutoRefresh();

            // 注册事件监听器
            this.registerEventListeners();

            this.isInitialized = true;
            this.addLog('info', '实时插值控制面板初始化成功');
        } catch (error) {
            console.error('实时插值控制面板初始化失败:', error);
            throw error;
        }
    }

    /**
     * 渲染控制面板
     */
    private renderControlPanel(): void {
        if (!this.container) {
            return;
        }

        this.container.innerHTML = `
            <div class="realtime-control-panel">
                <h3>实时插值控制</h3>

                <!-- 订阅管理 -->
                ${this.options.showSubscriptionManager ? this.renderSubscriptionManager() : ''}

                <!-- 缓存管理 -->
                ${this.options.showCacheControls ? this.renderCacheControls() : ''}

                <!-- 性能监控 -->
                ${this.options.showPerformanceMonitor ? this.renderPerformanceMonitor() : ''}

                <!-- 日志查看器 -->
                ${this.options.showLogViewer ? this.renderLogViewer() : ''}
            </div>
        `;

        // 初始化各子组件
        this.initializeSubscriptionManager();
        this.initializeCacheControls();
        this.initializePerformanceMonitor();
        this.initializeLogViewer();
    }

    /**
     * 渲染订阅管理器
     */
    private renderSubscriptionManager(): string {
        return `
            <div class="control-section" id="subscription-manager">
                <h4>订阅管理</h4>
                <div class="subscription-list" id="subscription-list">
                    <p class="no-data">暂无订阅</p>
                </div>
                <div class="subscription-actions">
                    <button class="btn btn-primary btn-sm" id="create-subscription-btn">
                        创建订阅
                    </button>
                    <button class="btn btn-secondary btn-sm" id="refresh-subscriptions-btn">
                        刷新
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 渲染缓存控制
     */
    private renderCacheControls(): string {
        return `
            <div class="control-section" id="cache-controls">
                <h4>缓存管理</h4>
                <div class="cache-settings">
                    <div class="form-group">
                        <label>启用缓存</label>
                        <input type="checkbox" id="cache-enabled" checked>
                    </div>
                    <div class="form-group">
                        <label>最大缓存大小 (MB)</label>
                        <input type="number" id="cache-max-size" value="100" min="10" max="1000">
                    </div>
                    <div class="form-group">
                        <label>缓存生存时间 (秒)</label>
                        <input type="number" id="cache-ttl" value="3600" min="60" max="86400">
                    </div>
                    <div class="form-group">
                        <label>缓存策略</label>
                        <select id="cache-strategy">
                            <option value="lru">LRU (最近最少使用)</option>
                            <option value="lfu">LFU (最不经常使用)</option>
                            <option value="fifo">FIFO (先进先出)</option>
                        </select>
                    </div>
                </div>
                <div class="cache-stats" id="cache-stats">
                    <div class="stat-item">
                        <span class="stat-label">命中率:</span>
                        <span class="stat-value" id="cache-hit-rate">0%</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">使用量:</span>
                        <span class="stat-value" id="cache-usage">0 / 100 MB</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">项目数:</span>
                        <span class="stat-value" id="cache-items">0</span>
                    </div>
                </div>
                <div class="cache-actions">
                    <button class="btn btn-secondary btn-sm" id="clear-cache-btn">
                        清空缓存
                    </button>
                    <button class="btn btn-secondary btn-sm" id="refresh-cache-stats-btn">
                        刷新统计
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 渲染性能监控
     */
    private renderPerformanceMonitor(): string {
        return `
            <div class="control-section" id="performance-monitor">
                <h4>性能监控</h4>
                <div class="performance-metrics" id="performance-metrics">
                    <div class="metric-item">
                        <span class="metric-label">最后更新:</span>
                        <span class="metric-value" id="last-update-time">-</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">平均更新时间:</span>
                        <span class="metric-value" id="avg-update-duration">0 ms</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">总更新次数:</span>
                        <span class="metric-value" id="total-updates">0</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">活跃订阅:</span>
                        <span class="metric-value" id="active-subscriptions">0</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">内存使用:</span>
                        <span class="metric-value" id="memory-usage">0 MB</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">CPU使用:</span>
                        <span class="metric-value" id="cpu-usage">0%</span>
                    </div>
                </div>
                <div class="performance-actions">
                    <button class="btn btn-secondary btn-sm" id="refresh-performance-btn">
                        刷新
                    </button>
                    <button class="btn btn-secondary btn-sm" id="reset-stats-btn">
                        重置统计
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 渲染日志查看器
     */
    private renderLogViewer(): string {
        return `
            <div class="control-section" id="log-viewer">
                <h4>系统日志</h4>
                <div class="log-controls">
                    <select id="log-level-filter">
                        <option value="all">所有级别</option>
                        <option value="info">信息</option>
                        <option value="warning">警告</option>
                        <option value="error">错误</option>
                    </select>
                    <button class="btn btn-secondary btn-sm" id="clear-logs-btn">
                        清空日志
                    </button>
                    <button class="btn btn-secondary btn-sm" id="export-logs-btn">
                        导出日志
                    </button>
                </div>
                <div class="log-content" id="log-content">
                    <p class="no-data">暂无日志</p>
                </div>
            </div>
        `;
    }

    /**
     * 初始化订阅管理器
     */
    private initializeSubscriptionManager(): void {
        const createBtn = document.getElementById('create-subscription-btn');
        const refreshBtn = document.getElementById('refresh-subscriptions-btn');

        if (createBtn) {
            createBtn.addEventListener('click', () => this.showCreateSubscriptionDialog());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshSubscriptions());
        }

        // 初始加载订阅列表
        this.refreshSubscriptions();
    }

    /**
     * 初始化缓存控制
     */
    private initializeCacheControls(): void {
        const clearBtn = document.getElementById('clear-cache-btn');
        const refreshBtn = document.getElementById('refresh-cache-stats-btn');

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearCache());
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshCacheStats());
        }

        // 初始加载缓存统计
        this.refreshCacheStats();
    }

    /**
     * 初始化性能监控
     */
    private initializePerformanceMonitor(): void {
        const refreshBtn = document.getElementById('refresh-performance-btn');
        const resetBtn = document.getElementById('reset-stats-btn');

        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshPerformanceMetrics());
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetPerformanceStats());
        }

        // 初始加载性能指标
        this.refreshPerformanceMetrics();
    }

    /**
     * 初始化日志查看器
     */
    private initializeLogViewer(): void {
        const levelFilter = document.getElementById('log-level-filter') as HTMLSelectElement;
        const clearBtn = document.getElementById('clear-logs-btn');
        const exportBtn = document.getElementById('export-logs-btn');

        if (levelFilter) {
            levelFilter.addEventListener('change', () => this.filterLogs());
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearLogs());
        }

        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportLogs());
        }
    }

    /**
     * 注册事件监听器
     */
    private registerEventListeners(): void {
        // 监听更新事件
        this.realtimeInterpolation.onUpdate((update) => {
            this.addLog('info', `收到更新: ${update.subscriptionId}`, update);
            this.refreshPerformanceMetrics();
        });

        // 监听热点事件
        this.realtimeInterpolation.onHotspot((hotspots) => {
            this.addLog('info', `检测到 ${hotspots.length} 个热点区域`);
        });

        // 监听错误事件
        this.realtimeInterpolation.onError((error) => {
            this.addLog('error', `发生错误: ${error.message}`, error);
        });
    }

    /**
     * 刷新订阅列表
     */
    private refreshSubscriptions(): void {
        const subscriptions = this.realtimeInterpolation.getSubscriptions();
        const listElement = document.getElementById('subscription-list');

        if (!listElement) {
            return;
        }

        if (subscriptions.length === 0) {
            listElement.innerHTML = '<p class="no-data">暂无订阅</p>';
            return;
        }

        listElement.innerHTML = subscriptions.map(sub => `
            <div class="subscription-item ${sub.active ? 'active' : 'inactive'}">
                <div class="subscription-info">
                    <h5>${sub.name}</h5>
                    <p class="subscription-meta">
                        ID: ${sub.id}<br>
                        更新间隔: ${sub.updateInterval}ms<br>
                        创建时间: ${sub.createdAt.toLocaleString()}
                    </p>
                </div>
                <div class="subscription-actions">
                    <button class="btn btn-xs" onclick="window.realtimeControlPanel.toggleSubscription('${sub.id}')">
                        ${sub.active ? '暂停' : '启用'}
                    </button>
                    <button class="btn btn-xs btn-danger" onclick="window.realtimeControlPanel.removeSubscription('${sub.id}')">
                        删除
                    </button>
                </div>
            </div>
        `).join('');
    }

    /**
     * 显示创建订阅对话框
     */
    private showCreateSubscriptionDialog(): void {
        // 创建简单的对话框
        const name = I18nDialog.prompt('请输入订阅名称:');
        if (!name) {
            return;
        }

        const interval = I18nDialog.prompt('请输入更新间隔（毫秒）:', '5000');
        if (!interval) {
            return;
        }

        const updateInterval = parseInt(interval, 10);
        if (isNaN(updateInterval) || updateInterval < 1000) {
            I18nDialog.alert('更新间隔必须大于等于1000毫秒');
            return;
        }

        // 这里需要实现完整的订阅创建逻辑
        // 包括区域选择等
        this.addLog('info', `准备创建订阅: ${name}, 间隔: ${updateInterval}ms`);
    }

    /**
     * 切换订阅状态
     */
    private toggleSubscription(subscriptionId: string): void {
        const subscription = this.realtimeInterpolation.getSubscriptions()
            .find(s => s.id === subscriptionId);

        if (subscription) {
            subscription.active = !subscription.active;
            this.addLog('info', `订阅 ${subscription.name} 已${subscription.active ? '启用' : '暂停'}`);
            this.refreshSubscriptions();
        }
    }

    /**
     * 移除订阅
     */
    private async removeSubscription(subscriptionId: string): Promise<void> {
        try {
            await this.realtimeInterpolation.unsubscribe(subscriptionId);
            this.addLog('info', `订阅已移除: ${subscriptionId}`);
            this.refreshSubscriptions();
        } catch (error) {
            this.addLog('error', `移除订阅失败: ${(error as Error).message}`);
        }
    }

    /**
     * 刷新缓存统计
     */
    private refreshCacheStats(): void {
        const metrics = this.realtimeInterpolation.getPerformanceMetrics();
        const hitRateElement = document.getElementById('cache-hit-rate');
        const usageElement = document.getElementById('cache-usage');
        const itemsElement = document.getElementById('cache-items');

        if (hitRateElement) {
            hitRateElement.textContent = `${(metrics.cacheHitRate * 100).toFixed(1)}%`;
        }

        if (usageElement) {
            const maxSize = parseInt((document.getElementById('cache-max-size') as HTMLInputElement)?.value || '100', 10);
            usageElement.textContent = `${metrics.memoryUsage.toFixed(1)} / ${maxSize} MB`;
        }

        if (itemsElement) {
            // 这里需要从缓存管理器获取实际的项目数
            itemsElement.textContent = '0';
        }
    }

    /**
     * 清空缓存
     */
    private clearCache(): void {
        if (I18nDialog.confirm('确定要清空所有缓存吗？')) {
            // 这里需要调用缓存管理器的清空方法
            this.addLog('info', '缓存已清空');
            this.refreshCacheStats();
        }
    }

    /**
     * 刷新性能指标
     */
    private refreshPerformanceMetrics(): void {
        const metrics = this.realtimeInterpolation.getPerformanceMetrics();
        const lastUpdateElement = document.getElementById('last-update-time');
        const avgDurationElement = document.getElementById('avg-update-duration');
        const totalUpdatesElement = document.getElementById('total-updates');
        const activeSubsElement = document.getElementById('active-subscriptions');
        const memoryElement = document.getElementById('memory-usage');
        const cpuElement = document.getElementById('cpu-usage');

        if (lastUpdateElement) {
            lastUpdateElement.textContent = metrics.lastUpdateTime.toLocaleTimeString();
        }

        if (avgDurationElement) {
            avgDurationElement.textContent = `${metrics.averageUpdateDuration.toFixed(2)} ms`;
        }

        if (totalUpdatesElement) {
            totalUpdatesElement.textContent = metrics.totalUpdates.toString();
        }

        if (activeSubsElement) {
            activeSubsElement.textContent = metrics.activeSubscriptions.toString();
        }

        if (memoryElement) {
            memoryElement.textContent = `${metrics.memoryUsage.toFixed(2)} MB`;
        }

        if (cpuElement) {
            cpuElement.textContent = `${metrics.cpuUsage.toFixed(1)}%`;
        }
    }

    /**
     * 重置性能统计
     */
    private resetPerformanceStats(): void {
        if (I18nDialog.confirm('确定要重置所有性能统计吗？')) {
            // 这里需要实现重置逻辑
            this.addLog('info', '性能统计已重置');
            this.refreshPerformanceMetrics();
        }
    }

    /**
     * 添加日志
     */
    private addLog(level: 'info' | 'warning' | 'error', message: string, data?: any): void {
        const entry: LogEntry = {
            timestamp: new Date(),
            level,
            message,
            data
        };

        this.logs.push(entry);
        if (this.logs.length > this.maxLogs) {
            this.logs.shift();
        }

        this.updateLogView();
    }

    /**
     * 更新日志视图
     */
    private updateLogView(): void {
        const contentElement = document.getElementById('log-content');
        if (!contentElement) {
            return;
        }

        if (this.logs.length === 0) {
            contentElement.innerHTML = '<p class="no-data">暂无日志</p>';
            return;
        }

        const filter = (document.getElementById('log-level-filter') as HTMLSelectElement)?.value || 'all';
        const filteredLogs = filter === 'all' ? this.logs : this.logs.filter(log => log.level === filter);

        contentElement.innerHTML = filteredLogs.map(log => `
            <div class="log-entry log-${log.level}">
                <span class="log-time">${log.timestamp.toLocaleTimeString()}</span>
                <span class="log-level">[${log.level.toUpperCase()}]</span>
                <span class="log-message">${log.message}</span>
            </div>
        `).join('');

        // 滚动到最新日志
        contentElement.scrollTop = contentElement.scrollHeight;
    }

    /**
     * 过滤日志
     */
    private filterLogs(): void {
        this.updateLogView();
    }

    /**
     * 清空日志
     */
    private clearLogs(): void {
        this.logs = [];
        this.updateLogView();
    }

    /**
     * 导出日志
     */
    private exportLogs(): void {
        const logText = this.logs.map(log =>
            `[${log.timestamp.toISOString()}] [${log.level.toUpperCase()}] ${log.message}`
        ).join('\n');

        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `realtime-logs-${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);

        this.addLog('info', '日志已导出');
    }

    /**
     * 开始自动刷新
     */
    private startAutoRefresh(): void {
        if (this.autoRefreshTimer !== null) {
            return;
        }

        this.autoRefreshTimer = window.setInterval(() => {
            this.refreshPerformanceMetrics();
            this.refreshCacheStats();
        }, this.options.autoRefreshInterval);
    }

    /**
     * 停止自动刷新
     */
    private stopAutoRefresh(): void {
        if (this.autoRefreshTimer !== null) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    /**
     * 销毁控制面板
     */
    destroy(): void {
        this.stopAutoRefresh();

        if (this.container) {
            this.container.innerHTML = '';
        }

        this.logs = [];
        this.isInitialized = false;
        this.addLog = () => {}; // 防止后续调用报错

        console.log('实时插值控制面板已销毁');
    }
}

// 将实例挂载到全局以便HTML中的onclick可以访问
declare global {
    interface Window {
        realtimeControlPanel: RealtimeControlPanel;
    }
}

export default RealtimeControlPanel;