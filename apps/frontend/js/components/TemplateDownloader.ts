import { I18nDialog } from './I18nDialog.js';
/**
 * 数据导入模板下载管理器
 * 提供 GeoJSON 模板下载、示例数据和验证规则说明
 */

interface TemplateConfig {
    name: string;
    description: string;
    filename: string;
    data: object;
}

const TEMPLATES: TemplateConfig[] = [
    {
        name: '基础采样点模板',
        description: '包含经纬度的基础采样点模板',
        filename: 'template_basic.geojson',
        data: {
            type: 'FeatureCollection',
            features: [
                {
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [116.39, 39.9]
                    },
                    properties: {
                        name: '采样点1',
                        value: 10.5
                    }
                }
            ]
        }
    },
    {
        name: '土壤采样模板',
        description: '包含多种土壤属性的采样点模板',
        filename: 'template_soil.geojson',
        data: {
            type: 'FeatureCollection',
            features: [
                {
                    type: 'Feature',
                    geometry: {
                        type: 'Point',
                        coordinates: [116.40, 39.91]
                    },
                    properties: {
                        name: '采样点1',
                        ph: 6.5,
                        organic_matter: 2.3,
                        nitrogen: 15.2,
                        phosphorus: 8.7,
                        potassium: 120.5
                    }
                }
            ]
        }
    },
    {
        name: '区域边界模板',
        description: '用于定义采样区域边界的多边形模板',
        filename: 'template_boundary.geojson',
        data: {
            type: 'FeatureCollection',
            features: [
                {
                    type: 'Feature',
                    geometry: {
                        type: 'Polygon',
                        coordinates: [[
                            [116.38, 39.89], [116.42, 39.89],
                            [116.42, 39.93], [116.38, 39.93],
                            [116.38, 39.89]
                        ]]
                    },
                    properties: { name: '采样区域A' }
                }
            ]
        }
    }
];

export class TemplateDownloader {
    /** 下载指定模板 */
    static download(index: number): void {
        const tpl = TEMPLATES[index];
        if (!tpl) return;
        const json = JSON.stringify(tpl.data, null, 2);
        const blob = new Blob([json], { type: 'application/geo+json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = tpl.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // 下载后询问是否跳转到文件所在位置
        this.showOpenLocationDialog(tpl.filename);
    }

    /** 显示是否跳转到文件所在位置的弹窗 */
    public static showOpenLocationDialog(filePath: string): void {
        const dialog = document.createElement('div');
        dialog.className = 'template-download-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>下载完成</h3>
                <p>模板文件已成功保存到:</p>
                <p style="font-family: monospace; font-size: 12px; color: var(--primary-color); word-break: break-all;">${filePath}</p>
                <p>是否要打开文件所在位置？</p>
                <div class="dialog-buttons">
                    <button class="btn btn-primary open-location-btn">打开位置</button>
                    <button class="btn btn-secondary close-dialog-btn">关闭</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);

        // 打开位置按钮
        const openBtn = dialog.querySelector('.open-location-btn') as HTMLButtonElement;
        openBtn.addEventListener('click', () => {
            // 在 Electron 环境中，打开文件所在位置
            if (window.electronAPI && (window.electronAPI as any).openDownloadFolder) {
                (window.electronAPI as any).openDownloadFolder();
            } else {
                // 在浏览器环境中，尝试打开下载文件夹
                I18nDialog.alert('请在浏览器的下载历史中找到下载的文件');
            }
            document.body.removeChild(dialog);
        });

        // 关闭按钮
        const closeBtn = dialog.querySelector('.close-dialog-btn') as HTMLButtonElement;
        closeBtn.addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
    }

    /** 获取所有模板信息 */
    static getTemplates(): Array<{ name: string; description: string }> {
        return TEMPLATES.map(t => ({ name: t.name, description: t.description }));
    }

    /** 创建模板下载面板 */
    static createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'template-download-panel';
        panel.innerHTML = `
            <h3 class="panel-title">模板下载</h3>
            <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
                下载 GeoJSON 模板文件，按格式填写数据后上传
            </p>
            <div class="template-list">
                ${TEMPLATES.map((t, i) => `
                    <div class="template-item" data-index="${i}">
                        <div class="template-info">
                            <span class="template-name">${t.name}</span>
                            <span class="template-desc">${t.description}</span>
                        </div>
                        <button class="btn btn-export template-dl-btn" data-index="${i}">下载</button>
                    </div>
                `).join('')}
            </div>
            <details class="template-rules" style="margin-top:12px;">
                <summary style="cursor:pointer;font-size:13px;font-weight:500;">数据格式要求</summary>
                <ul style="font-size:12px;color:var(--text-secondary);padding-left:20px;margin-top:8px;">
                    <li>文件格式：GeoJSON (.geojson 或 .json)</li>
                    <li>坐标系：WGS84 (EPSG:4326)</li>
                    <li>几何类型：Point（采样点）或 Polygon（区域边界）</li>
                    <li>必须包含 properties 中的数值字段作为插值目标</li>
                    <li>坐标格式：[经度, 纬度]，经度范围 -180~180，纬度范围 -90~90</li>
                    <li>至少需要 3 个采样点才能进行插值计算</li>
                </ul>
            </details>
        `;

        panel.querySelectorAll('.template-dl-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt((btn as HTMLElement).dataset.index!, 10);
                TemplateDownloader.download(idx);
            });
        });

        return panel;
    }
}
