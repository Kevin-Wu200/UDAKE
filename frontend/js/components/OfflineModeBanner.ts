/**
 * 离线模式横幅
 * 在用户离线时显示功能降级提示和可用功能说明
 */

import { OfflineManager } from '../utils/OfflineManager';

interface FeatureStatus {
    name: string;
    available: boolean;
    icon: string;
    description: string;
}

export class OfflineModeBanner {
    private banner: HTMLElement | null = null;
    private isInitialized: boolean = false;
    private isOnline: boolean = true;
    private removeListener: (() => void) | null = null;

    /**
     * 初始化离线模式横幅
     */
    public async init(): Promise<void> {
        if (this.isInitialized) return;

        this.createBanner();
        this.bindEvents();
        this.isInitialized = true;

        // 监听网络状态变化
        this.removeListener = OfflineManager.onStatusChange((online) => {
            this.handleNetworkChange(online);
        });

        // 初始状态
        this.isOnline = OfflineManager.isOnline;
        this.updateBannerVisibility();
    }

    /**
     * 创建横幅元素
     */
    private createBanner(): void {
        const banner = document.createElement('div');
        banner.id = 'offline-mode-banner';
        banner.className = 'offline-mode-banner';
        banner.innerHTML = `
            <div class="offline-banner-content">
                <div class="offline-banner-header">
                    <div class="offline-banner-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0119 12.55M5 12.55a10.94 10.94 0 015.17-2.39M10.71 5.05A16 16 0 0122.58 9M1.42 9a15.91 15.91 0 014.7-2.88M8.53 16.11a6 6 0 016.95 0M12 20h.01"/>
                        </svg>
                    </div>
                    <div class="offline-banner-title">
                        <h3>离线模式</h3>
                        <p class="offline-banner-subtitle">您当前处于离线状态，部分功能受限</p>
                    </div>
                    <button class="offline-banner-close" aria-label="关闭提示">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <div class="offline-banner-features">
                    <div class="offline-feature-list"></div>
                </div>

                <div class="offline-banner-actions">
                    <button class="offline-btn offline-btn-primary" id="offline-view-cache">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        查看缓存数据
                    </button>
                    <button class="offline-btn offline-btn-secondary" id="offline-manage-cache">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
                            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        管理缓存
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(banner);
        this.banner = banner;

        // 更新功能列表
        this.updateFeatureList();
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (!this.banner) return;

        // 关闭按钮
        const closeBtn = this.banner.querySelector('.offline-banner-close');
        closeBtn?.addEventListener('click', () => this.dismiss());

        // 查看缓存数据按钮
        const viewCacheBtn = this.banner.querySelector('#offline-view-cache');
        viewCacheBtn?.addEventListener('click', () => this.handleViewCache());

        // 管理缓存按钮
        const manageCacheBtn = this.banner.querySelector('#offline-manage-cache');
        manageCacheBtn?.addEventListener('click', () => this.handleManageCache());
    }

    /**
     * 处理网络状态变化
     */
    private handleNetworkChange(online: boolean): void {
        this.isOnline = online;
        this.updateBannerVisibility();
    }

    /**
     * 更新横幅可见性
     */
    private updateBannerVisibility(): void {
        if (!this.banner) return;

        if (this.isOnline) {
            this.banner.classList.add('hidden');
            // 在线时延迟隐藏，给用户一个成功提示
            setTimeout(() => {
                if (this.isOnline) {
                    this.banner!.style.display = 'none';
                }
            }, 2000);
        } else {
            this.banner.style.display = 'block';
            setTimeout(() => {
                if (!this.isOnline) {
                    this.banner!.classList.remove('hidden');
                }
            }, 100);
        }
    }

    /**
     * 更新功能列表
     */
    private updateFeatureList(): void {
        if (!this.banner) return;

        const featureList = this.banner.querySelector('.offline-feature-list');
        if (!featureList) return;

        const features: FeatureStatus[] = [
            {
                name: '查看已有项目',
                available: true,
                icon: '📁',
                description: '可以浏览和查看本地缓存的项目信息',
            },
            {
                name: '数据采样',
                available: true,
                icon: '📍',
                description: '支持离线单点采样和区域采样',
            },
            {
                name: '地图浏览',
                available: true,
                icon: '🗺️',
                description: '可以查看已缓存的地图数据',
            },
            {
                name: '参数调整',
                available: true,
                icon: '⚙️',
                description: '可以调整插值参数配置',
            },
            {
                name: '数据上传',
                available: false,
                icon: '📤',
                description: '需要网络连接，操作已加入离线队列',
            },
            {
                name: '插值计算',
                available: false,
                icon: '🔄',
                description: '需要网络连接，请求已缓存',
            },
            {
                name: '结果导出',
                available: true,
                icon: '💾',
                description: '可以导出已缓存的计算结果',
            },
            {
                name: '新建项目',
                available: false,
                icon: '➕',
                description: '需要网络连接',
            },
        ];

        featureList.innerHTML = features.map(feature => `
            <div class="offline-feature-item ${feature.available ? 'available' : 'unavailable'}">
                <div class="offline-feature-icon">${feature.icon}</div>
                <div class="offline-feature-info">
                    <span class="offline-feature-name">${feature.name}</span>
                    <span class="offline-feature-desc">${feature.description}</span>
                </div>
                <div class="offline-feature-status">
                    ${feature.available ? '✅' : '❌'}
                </div>
            </div>
        `).join('');
    }

    /**
     * 查看缓存数据
     */
    private handleViewCache(): void {
        // 触发自定义事件，让主应用处理
        const event = new CustomEvent('offline-view-cache', {
            bubbles: true,
            detail: { source: 'offline-banner' }
        });
        document.dispatchEvent(event);
    }

    /**
     * 管理缓存
     */
    private handleManageCache(): void {
        // 触发自定义事件，让主应用处理
        const event = new CustomEvent('offline-manage-cache', {
            bubbles: true,
            detail: { source: 'offline-banner' }
        });
        document.dispatchEvent(event);
    }

    /**
     * 关闭横幅（临时）
     */
    private dismiss(): void {
        if (!this.banner) return;

        this.banner.classList.add('dismissed');

        // 如果处于离线状态，5分钟后自动重新显示
        if (!this.isOnline) {
            setTimeout(() => {
                if (!this.isOnline) {
                    this.banner!.classList.remove('dismissed');
                }
            }, 5 * 60 * 1000);
        }
    }

    /**
     * 显示横幅
     */
    public show(): void {
        if (!this.banner) return;

        this.banner.classList.remove('hidden', 'dismissed');
        this.banner.style.display = 'block';
    }

    /**
     * 隐藏横幅
     */
    public hide(): void {
        if (!this.banner) return;

        this.banner.classList.add('hidden');
    }

    /**
     * 销毁横幅
     */
    public destroy(): void {
        if (this.removeListener) {
            this.removeListener();
            this.removeListener = null;
        }

        if (this.banner) {
            this.banner.remove();
            this.banner = null;
        }

        this.isInitialized = false;
    }
}

// 导出单例实例
export default new OfflineModeBanner();