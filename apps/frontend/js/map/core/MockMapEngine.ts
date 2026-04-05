/**
 * Mock 地图引擎
 * 用于在没有 ArcGIS API Key 或网络问题时提供基本地图功能
 * 使用简单的 HTML/CSS 模拟地图界面
 */

import { BaseMapEngine } from './BaseMapEngine';
import type { Bounds, MapInitOptions, IMapView, IMap, GeoSceneConfig } from '../../../types/map-engine';

/**
 * Mock 视图对象
 */
class MockMapView {
    container: HTMLElement | null;
    center: [number, number];
    zoom: number;
    map: MockMap | null;
    ui: any;

    constructor(options: any) {
        this.container = document.getElementById(options.container) as HTMLElement;
        this.center = options.center || [116.39, 39.9];
        this.zoom = options.zoom || 10;
        this.map = null;
        this.ui = { components: ['attribution'] };
    }

    when(): Promise<void> {
        return Promise.resolve();
    }

    watch(property: string, callback: (value: any) => void): void {
        // Mock watch 方法
    }
}

/**
 * Mock 地图对象
 */
class MockMap {
    basemap: string;

    constructor(options: any) {
        this.basemap = options.basemap || 'gray-vector';
    }
}

/**
 * Mock 地图引擎
 * 提供基本的地图模拟功能
 */
export class MockMapEngine extends BaseMapEngine {
    /** Mock 视图 */
    view: MockMapView | null;

    /** Mock 地图 */
    map: MockMap | null;

    /** 配置选项 */
    options: GeoSceneConfig;

    /** DOM 元素 */
    container: HTMLElement | null;

    constructor(options: GeoSceneConfig = {}) {
        super();
        this.supportsCustomReset = true;

        this.view = null;
        this.map = null;
        this.options = options;
        this.container = null;
    }

    /**
     * 初始化地图
     */
    async init(container: HTMLElement | string, options: MapInitOptions = {}): Promise<void> {
        // 合并选项
        const finalOptions = { ...this.options, ...options };

        // 获取容器
        let containerId: string;
        if (typeof container === 'string') {
            containerId = container;
            this.container = document.getElementById(containerId) as HTMLElement;
        } else {
            containerId = container.id;
            this.container = container;
        }

        if (!this.container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        // 检测深色模式
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        // 创建模拟地图界面
        this.createMockMapUI(this.container, isDark);

        // 创建 Mock 视图和地图
        this.map = new MockMap({
            basemap: isDark ? 'dark-gray-vector' : 'gray-vector'
        });

        this.view = new MockMapView({
            container: containerId,
            map: this.map,
            center: finalOptions.center || [116.39, 39.9],
            zoom: finalOptions.zoom || 10,
            constraints: {
                minZoom: finalOptions.minZoom || 1,
                maxZoom: finalOptions.maxZoom || 18
            },
            ui: {
                components: ['attribution']
            }
        });

        this.view.map = this.map;

        // 添加提示信息
        this.addMockMessage(this.container);

        await this.view.when();

        console.log('✅ Mock 地图引擎初始化完成');
    }

    /**
     * 创建模拟地图 UI
     */
    private createMockMapUI(container: HTMLElement, isDark: boolean): void {
        // 清空容器
        container.innerHTML = '';

        // 设置样式
        container.style.position = 'relative';
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.overflow = 'hidden';

        // 创建模拟地图背景
        const mapBg = document.createElement('div');
        mapBg.style.position = 'absolute';
        mapBg.style.top = '0';
        mapBg.style.left = '0';
        mapBg.style.width = '100%';
        mapBg.style.height = '100%';
        mapBg.style.background = isDark ? '#1a1a1a' : '#e0e0e0';
        mapBg.style.backgroundImage = `
            linear-gradient(${isDark ? '#2a2a2a' : '#d0d0d0'} 1px, transparent 1px),
            linear-gradient(90deg, ${isDark ? '#2a2a2a' : '#d0d0d0'} 1px, transparent 1px)
        `;
        mapBg.style.backgroundSize = '50px 50px';
        container.appendChild(mapBg);

        // 创建中心点标记
        const centerMarker = document.createElement('div');
        centerMarker.style.position = 'absolute';
        centerMarker.style.top = '50%';
        centerMarker.style.left = '50%';
        centerMarker.style.transform = 'translate(-50%, -50%)';
        centerMarker.style.width = '20px';
        centerMarker.style.height = '20px';
        centerMarker.style.borderRadius = '50%';
        centerMarker.style.backgroundColor = isDark ? '#007aff' : '#007aff';
        centerMarker.style.opacity = '0.5';
        centerMarker.style.pointerEvents = 'none';
        container.appendChild(centerMarker);

        // 创建坐标显示
        const coordDisplay = document.createElement('div');
        coordDisplay.id = 'mock-coord-display';
        coordDisplay.style.position = 'absolute';
        coordDisplay.style.bottom = '20px';
        coordDisplay.style.left = '20px';
        coordDisplay.style.padding = '8px 12px';
        coordDisplay.style.backgroundColor = isDark ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
        coordDisplay.style.color = isDark ? '#ffffff' : '#000000';
        coordDisplay.style.borderRadius = '4px';
        coordDisplay.style.fontSize = '12px';
        coordDisplay.style.fontFamily = 'monospace';
        coordDisplay.style.zIndex = '1000';
        coordDisplay.textContent = '中心点: 116.390000, 39.900000';
        container.appendChild(coordDisplay);

        // 创建缩放控制
        const zoomControl = document.createElement('div');
        zoomControl.style.position = 'absolute';
        zoomControl.style.top = '20px';
        zoomControl.style.right = '20px';
        zoomControl.style.display = 'flex';
        zoomControl.style.flexDirection = 'column';
        zoomControl.style.gap = '8px';
        zoomControl.style.zIndex = '1000';

        const zoomInBtn = this.createZoomButton('+', () => this.setZoom(this.getZoom() + 1), isDark);
        const zoomOutBtn = this.createZoomButton('-', () => this.setZoom(this.getZoom() - 1), isDark);
        const homeBtn = this.createZoomButton('⌂', () => this.goHome(), isDark);

        zoomControl.appendChild(zoomInBtn);
        zoomControl.appendChild(zoomOutBtn);
        zoomControl.appendChild(homeBtn);
        container.appendChild(zoomControl);
    }

    /**
     * 创建缩放按钮
     */
    private createZoomButton(text: string, onClick: () => void, isDark: boolean): HTMLElement {
        const btn = document.createElement('button');
        btn.textContent = text;
        btn.style.width = '40px';
        btn.style.height = '40px';
        btn.style.borderRadius = '4px';
        btn.style.border = 'none';
        btn.style.backgroundColor = isDark ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
        btn.style.color = isDark ? '#ffffff' : '#000000';
        btn.style.fontSize = '18px';
        btn.style.cursor = 'pointer';
        btn.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.2)';
        btn.style.transition = 'all 0.2s';
        btn.style.display = 'flex';
        btn.style.alignItems = 'center';
        btn.style.justifyContent = 'center';

        btn.addEventListener('mouseenter', () => {
            btn.style.backgroundColor = isDark ? 'rgba(0, 122, 255, 0.8)' : 'rgba(0, 122, 255, 0.9)';
        });

        btn.addEventListener('mouseleave', () => {
            btn.style.backgroundColor = isDark ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
        });

        btn.addEventListener('click', onClick);

        return btn;
    }

    /**
     * 添加 Mock 消息
     */
    private addMockMessage(container: HTMLElement): void {
        const message = document.createElement('div');
        message.style.position = 'absolute';
        message.style.top = '50%';
        message.style.left = '50%';
        message.style.transform = 'translate(-50%, -50%)';
        message.style.padding = '20px 30px';
        message.style.backgroundColor = 'rgba(0, 0, 0, 0.85)';
        message.style.color = '#ffffff';
        message.style.borderRadius = '8px';
        message.style.textAlign = 'center';
        message.style.zIndex = '999';
        message.style.maxWidth = '400px';
        message.innerHTML = `
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 10px;">
                🗺️ Mock 地图模式
            </div>
            <div style="font-size: 14px; line-height: 1.5;">
                当前使用 Mock 地图引擎<br>
                GeoScene API Key 未配置或无法访问<br>
                <span style="color: #ffd700;">应用功能不受影响，仅地图显示为模拟界面</span>
            </div>
        `;
        container.appendChild(message);

        // 3秒后自动隐藏消息
        setTimeout(() => {
            message.style.transition = 'opacity 0.5s';
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 500);
        }, 3000);
    }

    /**
     * 更新坐标显示
     */
    private updateCoordDisplay(): void {
        if (!this.container) return;
        const coordDisplay = this.container.querySelector('#mock-coord-display') as HTMLElement;
        if (coordDisplay && this.view) {
            const [lng, lat] = this.view.center;
            coordDisplay.textContent = `中心点: ${lng.toFixed(6)}, ${lat.toFixed(6)}`;
        }
    }

    /**
     * 设置中心点
     */
    setCenter(center: [number, number]): void {
        if (this.view) {
            this.view.center = center;
            this.updateCoordDisplay();
            this.triggerMoveCallbacks(center);
        }
    }

    /**
     * 获取中心点
     */
    getCenter(): [number, number] {
        return this.view ? this.view.center : [0, 0];
    }

    /**
     * 设置缩放级别
     */
    setZoom(zoom: number): void {
        if (this.view) {
            this.view.zoom = Math.max(1, Math.min(18, zoom));
            this.triggerZoomCallbacks(this.view.zoom);
        }
    }

    /**
     * 获取缩放级别
     */
    getZoom(): number {
        return this.view ? this.view.zoom : 0;
    }

    /**
     * 适配到指定边界
     */
    fitToBounds(bounds: Bounds): void {
        if (this.view) {
            const center: [number, number] = [
                (bounds.minLng + bounds.maxLng) / 2,
                (bounds.minLat + bounds.maxLat) / 2
            ];
            this.setCenter(center);
            this.setZoom(10);
        }
    }

    /**
     * 返回默认位置
     */
    goHome(): void {
        this.setCenter([116.39, 39.9]);
        this.setZoom(10);
    }

    /**
     * 获取视图对象
     */
    getView(): MockMapView | null {
        return this.view;
    }

    /**
     * 销毁地图实例
     */
    destroy(): void {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.view = null;
        this.map = null;
        this.container = null;
        super.destroy();
    }
}
