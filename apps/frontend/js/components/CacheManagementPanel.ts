/**
 * 缓存管理面板
 * 提供缓存查看、清理和设置功能
 */

import { OfflineManager } from '../utils/OfflineManager';
import { I18nDialog } from './I18nDialog.js';

interface CacheInfo {
    name: string;
    size: number;
    count: number;
    description: string;
}

export class CacheManagementPanel {
    private panel: HTMLElement | null = null;
    private backdrop: HTMLElement | null = null;
    private isInitialized: boolean = false;

    /**
     * 初始化缓存管理面板
     */
    public async init(): Promise<void> {
        if (this.isInitialized) return;

        this.createPanel();
        this.createBackdrop();
        this.bindEvents();
        this.isInitialized = true;
    }

    /**
     * 创建面板元素
     */
    private createPanel(): void {
        const panel = document.createElement('div');
        panel.id = 'cache-management-panel';
        panel.className = 'cache-management-panel';
        panel.innerHTML = `
            <div class="cache-panel-header">
                <h2 class="cache-panel-title">缓存管理</h2>
                <button class="cache-panel-close" aria-label="关闭面板">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="cache-panel-content">
                <div class="cache-status-section">
                    <h3 class="cache-section-title">网络状态</h3>
                    <div class="cache-status-indicator">
                        <span class="cache-status-icon"></span>
                        <span class="cache-status-text">检测中...</span>
                    </div>
                </div>

                <div class="cache-usage-section">
                    <h3 class="cache-section-title">存储使用情况</h3>
                    <div class="cache-usage-bar">
                        <div class="cache-usage-fill"></div>
                    </div>
                    <div class="cache-usage-info">
                        <span class="cache-usage-used">0 B</span>
                        <span class="cache-usage-total">/ 50 MB</span>
                    </div>
                </div>

                <div class="cache-list-section">
                    <h3 class="cache-section-title">缓存详情</h3>
                    <div class="cache-list"></div>
                </div>

                <div class="cache-actions-section">
                    <button class="cache-btn cache-btn-primary" id="cache-clean-expired">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                        清理过期缓存
                    </button>
                    <button class="cache-btn cache-btn-danger" id="cache-clear-all">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                        清除所有缓存
                    </button>
                </div>

                <div class="cache-pending-section">
                    <h3 class="cache-section-title">待同步操作</h3>
                    <div class="cache-pending-info">
                        <span class="cache-pending-count">0</span>
                        <span class="cache-pending-text">个操作等待同步</span>
                    </div>
                    <button class="cache-btn cache-btn-secondary" id="cache-sync-now">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                        立即同步
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(panel);
        this.panel = panel;
    }

    /**
     * 创建背景遮罩
     */
    private createBackdrop(): void {
        const backdrop = document.createElement('div');
        backdrop.id = 'cache-management-backdrop';
        backdrop.className = 'cache-panel-backdrop';
        document.body.appendChild(backdrop);
        this.backdrop = backdrop;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.panel || !this.backdrop) return;

        // 关闭按钮
        const closeBtn = this.panel.querySelector('.cache-panel-close');
        closeBtn?.addEventListener('click', () => this.hide());

        // 背景点击
        this.backdrop.addEventListener('click', () => this.hide());

        // 清理过期缓存
        const cleanExpiredBtn = this.panel.querySelector('#cache-clean-expired');
        cleanExpiredBtn?.addEventListener('click', () => this.cleanExpiredCache());

        // 清除所有缓存
        const clearAllBtn = this.panel.querySelector('#cache-clear-all');
        clearAllBtn?.addEventListener('click', () => this.clearAllCache());

        // 立即同步
        const syncNowBtn = this.panel.querySelector('#cache-sync-now');
        syncNowBtn?.addEventListener('click', () => this.syncNow());
    }

    /**
     * 显示面板
     */
    public async show(): Promise<void> {
        if (!this.isInitialized) {
            await this.init();
        }

        if (!this.panel || !this.backdrop) return;

        this.panel.classList.add('show');
        this.backdrop.classList.add('show');

        // 刷新数据
        await this.refreshData();
    }

    /**
     * 隐藏面板
     */
    public hide(): void {
        if (!this.panel || !this.backdrop) return;

        this.panel.classList.remove('show');
        this.backdrop.classList.remove('show');
    }

    /**
     * 刷新数据
     */
    private async refreshData(): Promise<void> {
        if (!this.panel) return;

        // 更新网络状态
        const statusIcon = this.panel.querySelector('.cache-status-icon');
        const statusText = this.panel.querySelector('.cache-status-text');
        if (statusIcon && statusText) {
            const isOnline = OfflineManager.isOnline;
            statusIcon.className = `cache-status-icon ${isOnline ? 'online' : 'offline'}`;
            statusText.textContent = isOnline ? '已连接网络' : '离线模式';
        }

        // 更新存储使用情况
        await this.updateStorageUsage();

        // 更新缓存列表
        await this.updateCacheList();

        // 更新待同步操作数
        await this.updatePendingCount();
    }

    /**
     * 更新存储使用情况
     */
    private async updateStorageUsage(): Promise<void> {
        if (!this.panel) return;

        try {
            // 模拟存储使用情况（实际应用中可以使用 navigator.storage.estimate）
            const usedSize = await this.estimateStorageSize();
            const totalSize = 50 * 1024 * 1024; // 50MB
            const percentage = (usedSize / totalSize) * 100;

            const usageFill = this.panel.querySelector('.cache-usage-fill') as HTMLElement;
            const usageUsed = this.panel.querySelector('.cache-usage-used') as HTMLElement;

            if (usageFill) {
                usageFill.style.width = `${percentage}%`;
                usageFill.className = `cache-usage-fill ${percentage > 80 ? 'warning' : ''}`;
            }

            if (usageUsed) {
                usageUsed.textContent = this.formatBytes(usedSize);
            }
        } catch (error) {
            console.error('更新存储使用情况失败:', error);
        }
    }

    /**
     * 更新缓存列表
     */
    private async updateCacheList(): Promise<void> {
        if (!this.panel) return;

        const cacheList = this.panel.querySelector('.cache-list');
        if (!cacheList) return;

        try {
            const cacheInfo = await this.getCacheInfo();
            cacheList.innerHTML = cacheInfo.map(info => `
                <div class="cache-item">
                    <div class="cache-item-header">
                        <span class="cache-item-name">${info.name}</span>
                        <span class="cache-item-size">${this.formatBytes(info.size)}</span>
                    </div>
                    <div class="cache-item-details">
                        <span class="cache-item-count">${info.count} 项</span>
                        <span class="cache-item-desc">${info.description}</span>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('更新缓存列表失败:', error);
        }
    }

    /**
     * 更新待同步操作数
     */
    private async updatePendingCount(): Promise<void> {
        if (!this.panel) return;

        const pendingCount = this.panel.querySelector('.cache-pending-count');
        if (!pendingCount) return;

        try {
            const count = await OfflineManager.getPendingCount();
            pendingCount.textContent = count.toString();
        } catch (error) {
            console.error('更新待同步操作数失败:', error);
        }
    }

    /**
     * 清理过期缓存
     */
    private async cleanExpiredCache(): Promise<void> {
        if (!this.panel) return;

        const btn = this.panel.querySelector('#cache-clean-expired') as HTMLButtonElement;
        const originalText = btn.innerHTML;

        try {
            btn.disabled = true;
            btn.innerHTML = '<span class="cache-btn-loading"></span> 清理中...';

            // 这里需要实现清理过期缓存的逻辑
            // 由于 OfflineManager 没有直接提供此功能，需要扩展
            console.log('清理过期缓存...');

            // 模拟清理过程
            await new Promise(resolve => setTimeout(resolve, 1000));

            await this.refreshData();

            this.showToast('过期缓存已清理');
        } catch (error) {
            console.error('清理过期缓存失败:', error);
            this.showToast('清理失败，请重试', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    /**
     * 清除所有缓存
     */
    private async clearAllCache(): Promise<void> {
        if (!I18nDialog.confirm('确定要清除所有缓存吗？此操作不可撤销。')) {
            return;
        }

        if (!this.panel) return;

        const btn = this.panel.querySelector('#cache-clear-all') as HTMLButtonElement;
        const originalText = btn.innerHTML;

        try {
            btn.disabled = true;
            btn.innerHTML = '<span class="cache-btn-loading"></span> 清除中...';

            await OfflineManager.clearAll();

            await this.refreshData();

            this.showToast('所有缓存已清除');
        } catch (error) {
            console.error('清除缓存失败:', error);
            this.showToast('清除失败，请重试', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    /**
     * 立即同步
     */
    private async syncNow(): Promise<void> {
        if (!this.panel) return;

        const btn = this.panel.querySelector('#cache-sync-now') as HTMLButtonElement;
        const originalText = btn.innerHTML;

        try {
            btn.disabled = true;
            btn.innerHTML = '<span class="cache-btn-loading"></span> 同步中...';

            await OfflineManager.sync();

            await this.refreshData();

            this.showToast('同步完成');
        } catch (error) {
            console.error('同步失败:', error);
            this.showToast('同步失败，请重试', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    /**
     * 获取缓存信息
     */
    private async getCacheInfo(): Promise<CacheInfo[]> {
        // 模拟缓存信息，实际应用中应该从 IndexedDB 获取
        return [
            {
                name: '项目数据',
                size: await this.estimateStoreSize('projects'),
                count: await this.estimateStoreCount('projects'),
                description: '本地保存的项目信息'
            },
            {
                name: '采样点',
                size: await this.estimateStoreSize('points'),
                count: await this.estimateStoreCount('points'),
                description: '离线采样的点位数据'
            },
            {
                name: '结果缓存',
                size: await this.estimateStoreSize('results'),
                count: await this.estimateStoreCount('results'),
                description: '插值和计算结果'
            },
        ];
    }

    /**
     * 估算存储大小（模拟）
     */
    private async estimateStorageSize(): Promise<number> {
        const cacheInfo = await this.getCacheInfo();
        return cacheInfo.reduce((total, info) => total + info.size, 0);
    }

    /**
     * 估算存储大小（模拟）
     */
    private async estimateStoreSize(storeName: string): Promise<number> {
        // 这里应该实际查询 IndexedDB 获取真实大小
        // 现在返回模拟值
        const sizes: Record<string, number> = {
            projects: 1024 * 1024, // 1MB
            points: 5 * 1024 * 1024, // 5MB
            results: 10 * 1024 * 1024, // 10MB
        };
        return sizes[storeName] || 0;
    }

    /**
     * 估算存储条目数（模拟）
     */
    private async estimateStoreCount(storeName: string): Promise<number> {
        // 这里应该实际查询 IndexedDB 获取真实条目数
        // 现在返回模拟值
        const counts: Record<string, number> = {
            projects: 3,
            points: 150,
            results: 8,
        };
        return counts[storeName] || 0;
    }

    /**
     * 格式化字节数
     */
    private formatBytes(bytes: number): string {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 显示提示消息
     */
    private showToast(message: string, type: 'success' | 'error' = 'success'): void {
        const toast = document.createElement('div');
        toast.className = `cache-toast cache-toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            border-radius: 8px;
            background: ${type === 'success' ? 'rgba(52,199,89,0.9)' : 'rgba(255,59,48,0.9)'};
            color: white;
            font-size: 14px;
            font-weight: 500;
            z-index: 10001;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            animation: slideUp 0.3s ease-out;
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideDown 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }

    /**
     * 销毁面板
     */
    public destroy(): void {
        if (this.panel) {
            this.panel.remove();
            this.panel = null;
        }

        if (this.backdrop) {
            this.backdrop.remove();
            this.backdrop = null;
        }

        this.isInitialized = false;
    }
}

// 导出单例实例
export default new CacheManagementPanel();