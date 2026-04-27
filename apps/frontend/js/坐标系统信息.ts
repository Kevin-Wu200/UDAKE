/**
 * 坐标系统信息组件
 * 显示当前MapView的坐标系信息
 */

import type { MapView } from '../types/app';
import { I18n } from './utils/I18n.js';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

/** 空间参考接口 */
interface SpatialReference {
    wkid?: number;
    latestWkid?: number;
    wkt?: string;
}

/** 投影坐标系映射 */
type ProjectionMapping = Record<number, string>;

export class CoordinateSystemInfo {
    private view: MapView;
    private container: HTMLElement | null = null;

    /** 常见投影坐标系映射表 */
    private readonly commonProjections: ProjectionMapping = {
        4326: 'WGS 1984',
        3857: 'Web Mercator',
        2154: 'RGF93 / Lambert-93',
        32633: 'WGS 84 / UTM zone 33N',
        32634: 'WGS 84 / UTM zone 34N',
        32635: 'WGS 84 / UTM zone 35N',
        32636: 'WGS 84 / UTM zone 36N',
        3395: 'WGS 84 / World Mercator',
        4269: 'NAD83',
        4267: 'NAD27',
        2163: 'US National Atlas Equal Area',
        102100: 'Web Mercator Auxiliary Sphere'
    };

    constructor(view: any) {
        this.view = view;
    }

    /**
     * 创建坐标系信息面板
     */
    createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'panel coordinate-system-panel';
        panel.innerHTML = `
            <h2 class="panel-title">${t('dataimport.section.coordinate_system')}</h2>
            <div class="panel-content">
                <div class="coordinate-info">
                    <div class="info-item">
                        <span class="info-label">${t('dataimport.label.projected_coordinate_system')}</span>
                        <span class="info-value" id="projection-name">${t('status.loading')}</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">${t('dataimport.label.projected_epsg')}</span>
                        <span class="info-value" id="projection-epsg">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">${t('dataimport.label.geographic_coordinate_system')}</span>
                        <span class="info-value" id="geographic-name">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">${t('dataimport.label.geographic_epsg')}</span>
                        <span class="info-value" id="geographic-epsg">-</span>
                    </div>
                    <div class="info-item wkt-item">
                        <span class="info-label">${t('dataimport.label.wkt')}</span>
                        <button class="btn-collapse" id="wkt-toggle">${t('common.expand')}</button>
                    </div>
                    <div class="wkt-content" id="wkt-content" style="display: none;">
                        <pre id="wkt-text">-</pre>
                    </div>
                </div>
            </div>
        `;

        this.container = panel;
        this.bindEvents();
        this.updateInfo();

        return panel;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        const toggleBtn = this.container?.querySelector('#wkt-toggle') as HTMLButtonElement;
        const wktContent = this.container?.querySelector('#wkt-content') as HTMLDivElement;

        if (toggleBtn && wktContent) {
            toggleBtn.addEventListener('click', () => {
                const isVisible = wktContent.style.display !== 'none';
                wktContent.style.display = isVisible ? 'none' : 'block';
                toggleBtn.textContent = isVisible ? t('common.expand') : t('common.collapse');
            });
        }
    }

    /**
     * 更新坐标系信息
     */
    private async updateInfo(): Promise<void> {
        const sr = this.view.spatialReference;

        if (!sr) {
            this.showUnknown();
            return;
        }

        // 获取 WKID
        const wkid = sr.wkid || sr.latestWkid;

        // 设置投影 EPSG
        const projectionEpsg = this.container?.querySelector('#projection-epsg') as HTMLSpanElement;
        if (projectionEpsg) {
            projectionEpsg.textContent = wkid ? `EPSG:${wkid}` : t('status.unrecognized');
        }

        // 获取坐标系名称
        try {
            const projectionName = await this.getProjectionName(wkid);
            const projectionNameEl = this.container?.querySelector('#projection-name') as HTMLSpanElement;
            if (projectionNameEl) {
                projectionNameEl.textContent = projectionName;
            }
        } catch (error) {
            const projectionNameEl = this.container?.querySelector('#projection-name') as HTMLSpanElement;
            if (projectionNameEl) {
                projectionNameEl.textContent = t('status.unrecognizedCoordinateSystem');
            }
        }

        // 设置地理坐标系信息（如果是投影坐标系）
        if (wkid && wkid !== 4326 && wkid !== 3857) {
            // 大多数投影坐标系基于 WGS84
            const geographicNameEl = this.container?.querySelector('#geographic-name') as HTMLSpanElement;
            const geographicEpsgEl = this.container?.querySelector('#geographic-epsg') as HTMLSpanElement;
            if (geographicNameEl) geographicNameEl.textContent = 'WGS 1984';
            if (geographicEpsgEl) geographicEpsgEl.textContent = 'EPSG:4326';
        } else if (wkid === 4326) {
            const geographicNameEl = this.container?.querySelector('#geographic-name') as HTMLSpanElement;
            const geographicEpsgEl = this.container?.querySelector('#geographic-epsg') as HTMLSpanElement;
            if (geographicNameEl) geographicNameEl.textContent = 'WGS 1984';
            if (geographicEpsgEl) geographicEpsgEl.textContent = 'EPSG:4326';
        } else if (wkid === 3857) {
            const geographicNameEl = this.container?.querySelector('#geographic-name') as HTMLSpanElement;
            const geographicEpsgEl = this.container?.querySelector('#geographic-epsg') as HTMLSpanElement;
            if (geographicNameEl) geographicNameEl.textContent = 'WGS 1984';
            if (geographicEpsgEl) geographicEpsgEl.textContent = 'EPSG:4326';
        }

        // 设置 WKT
        const wkt = sr.wkt || t('dataimport.status.noWktInfo');
        const wktTextEl = this.container?.querySelector('#wkt-text') as HTMLElement;
        if (wktTextEl) {
            wktTextEl.textContent = wkt;
        }
    }

    /**
     * 获取投影坐标系名称
     */
    private async getProjectionName(wkid?: number): Promise<string> {
        if (!wkid) {
            return t('status.unrecognized');
        }

        return this.commonProjections[wkid] || `EPSG:${wkid}`;
    }

    /**
     * 显示未识别状态
     */
    private showUnknown(): void {
        const projectionNameEl = this.container?.querySelector('#projection-name') as HTMLSpanElement;
        const projectionEpsgEl = this.container?.querySelector('#projection-epsg') as HTMLSpanElement;
        const geographicNameEl = this.container?.querySelector('#geographic-name') as HTMLSpanElement;
        const geographicEpsgEl = this.container?.querySelector('#geographic-epsg') as HTMLSpanElement;
        const wktTextEl = this.container?.querySelector('#wkt-text') as HTMLElement;

        if (projectionNameEl) projectionNameEl.textContent = t('status.unrecognizedCoordinateSystem');
        if (projectionEpsgEl) projectionEpsgEl.textContent = '-';
        if (geographicNameEl) geographicNameEl.textContent = '-';
        if (geographicEpsgEl) geographicEpsgEl.textContent = '-';
        if (wktTextEl) wktTextEl.textContent = '-';
    }
}