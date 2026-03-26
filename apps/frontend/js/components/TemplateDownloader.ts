import { I18nDialog } from './I18nDialog.js';
import { TemplateStorageService } from '../services/TemplateStorageService.js';

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

const FIRST_LAUNCH_GUIDE_KEY = 'udake_template_storage_guide_shown';

export class TemplateDownloader {
    /** 下载指定模板 */
    static download(index: unknown, triggerButton?: HTMLButtonElement | null): void {
        const numericIndex = Number(index);
        if (!Number.isInteger(numericIndex) || numericIndex < 0 || numericIndex >= TEMPLATES.length) {
            return;
        }

        const tpl = TEMPLATES[numericIndex];
        if (!tpl) {
            return;
        }

        void this.downloadTemplate(tpl, triggerButton);
    }

    /** 下载指定文件名和内容（用于行业模板等外部入口复用） */
    public static async downloadContent(filename: string, content: string): Promise<void> {
        const safeFilename = filename || 'template.geojson';
        const finalContent = content || '{}';

        if (TemplateStorageService.canUseNativeStorage()) {
            try {
                const init = await TemplateStorageService.ensureInitialized();
                if (!init.ready) {
                    throw new Error('PERMISSION_DENIED');
                }

                const exists = await TemplateStorageService.fileExists(safeFilename);
                const shouldOverwrite = !exists || I18nDialog.confirm('dialog.template.fileExistsOverwrite', {
                    filename: safeFilename
                });
                if (!shouldOverwrite) {
                    return;
                }

                const result = await TemplateStorageService.saveTemplate(safeFilename, finalContent, exists);
                this.showOpenLocationDialog(result.filePath, safeFilename);
                await this.refreshStoragePanels();
                return;
            } catch (error) {
                this.handleDownloadError(error);
                throw error;
            }
        }

        this.downloadContentByBrowser(safeFilename, finalContent);
    }

    private static async downloadTemplate(tpl: TemplateConfig, triggerButton?: HTMLButtonElement | null): Promise<void> {
        this.setButtonLoading(triggerButton, true);

        try {
            const json = JSON.stringify(tpl.data, null, 2);
            await this.downloadContent(tpl.filename, json);
        } catch {
            // 详细错误已在 downloadContent 内处理
        } finally {
            this.setButtonLoading(triggerButton, false);
        }
    }

    private static downloadContentByBrowser(filename: string, content: string): void {
        const blob = new Blob([content], { type: 'application/geo+json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // 下载后询问是否跳转到文件所在位置
        this.showOpenLocationDialog(filename, filename);
    }

    private static setButtonLoading(button?: HTMLButtonElement | null, loading = false): void {
        if (!button) {
            return;
        }

        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent || '下载';
        }

        button.disabled = loading;
        button.textContent = loading ? '下载中...' : (button.dataset.originalText || '下载');
    }

    /** 显示是否跳转到文件所在位置的弹窗 */
    public static showOpenLocationDialog(filePath: string, filename?: string): void {
        const dialog = document.createElement('div');
        dialog.className = 'template-download-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>下载完成</h3>
                <p>模板文件已成功保存到:</p>
                <p class="template-dialog-path">${filePath}</p>
                <p>您可以直接打开文件，或打开所在文件夹。</p>
                <div class="dialog-buttons">
                    <button class="btn btn-secondary open-file-btn">打开文件</button>
                    <button class="btn btn-primary open-location-btn">打开文件夹</button>
                    <button class="btn btn-secondary close-dialog-btn">关闭</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);

        // 打开文件按钮
        const openFileBtn = dialog.querySelector('.open-file-btn') as HTMLButtonElement | null;
        openFileBtn?.addEventListener('click', () => {
            void TemplateStorageService.openTemplateFile(filename || filePath);
            document.body.removeChild(dialog);
        });

        // 打开位置按钮
        const openBtn = dialog.querySelector('.open-location-btn') as HTMLButtonElement | null;
        openBtn?.addEventListener('click', () => {
            void (async () => {
                const opened = await TemplateStorageService.openStorageFolder();
                if (!opened) {
                    I18nDialog.alert('dialog.template.findInBrowserHistory');
                }
                document.body.removeChild(dialog);
            })();
        });

        // 关闭按钮
        const closeBtn = dialog.querySelector('.close-dialog-btn') as HTMLButtonElement | null;
        closeBtn?.addEventListener('click', () => {
            document.body.removeChild(dialog);
        });
    }

    /** 获取所有模板信息 */
    static getTemplates(): Array<{ name: string; description: string }> {
        return TEMPLATES.map(t => ({ name: t.name, description: t.description }));
    }

    /** 刷新所有模板面板中的文件列表 */
    public static async refreshStoragePanels(): Promise<void> {
        const panels = document.querySelectorAll('.template-download-panel');
        for (const panel of Array.from(panels)) {
            await this.updateStorageInfo(panel as HTMLElement);
            await this.renderFileList(panel as HTMLElement);
        }
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

            <div class="template-storage-section">
                <div class="template-storage-actions">
                    <button class="btn btn-secondary template-refresh-btn">刷新文件列表</button>
                    <button class="btn btn-secondary template-open-folder-btn">打开文件夹</button>
                    <button class="btn btn-secondary template-clear-btn">清空模板</button>
                </div>
                <div class="template-storage-summary">
                    <div>存储路径：<span class="template-storage-path"></span></div>
                    <div>已用空间：<span class="template-storage-usage">--</span></div>
                </div>
                <div class="template-file-list"></div>
            </div>
        `;

        panel.querySelectorAll('.template-dl-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt((btn as HTMLElement).dataset.index || '-1', 10);
                TemplateDownloader.download(idx, btn as HTMLButtonElement);
            });
        });

        const refreshBtn = panel.querySelector('.template-refresh-btn') as HTMLButtonElement | null;
        refreshBtn?.addEventListener('click', () => {
            void (async () => {
                await this.updateStorageInfo(panel);
                await this.renderFileList(panel);
            })();
        });

        const openFolderBtn = panel.querySelector('.template-open-folder-btn') as HTMLButtonElement | null;
        openFolderBtn?.addEventListener('click', () => {
            void (async () => {
                const opened = await TemplateStorageService.openStorageFolder();
                if (!opened) {
                    I18nDialog.alert('dialog.template.findInBrowserHistory');
                }
            })();
        });

        const clearBtn = panel.querySelector('.template-clear-btn') as HTMLButtonElement | null;
        clearBtn?.addEventListener('click', () => {
            void this.clearTemplates(panel);
        });

        void this.bootstrapStorage(panel);

        return panel;
    }

    private static async bootstrapStorage(panel: HTMLElement): Promise<void> {
        await this.updateStorageInfo(panel);
        await this.renderFileList(panel);

        if (!TemplateStorageService.canUseNativeStorage()) {
            return;
        }

        const init = await TemplateStorageService.ensureInitialized();
        if (!init.ready) {
            I18nDialog.alert('dialog.template.storagePermissionNotGranted');
            return;
        }

        this.showFirstLaunchGuide(init.path);
        await this.updateStorageInfo(panel);
        await this.renderFileList(panel);
    }

    private static showFirstLaunchGuide(path: string): void {
        if (!TemplateStorageService.canUseNativeStorage()) {
            return;
        }

        try {
            if (typeof localStorage !== 'undefined' && localStorage.getItem(FIRST_LAUNCH_GUIDE_KEY)) {
                return;
            }
        } catch {
            return;
        }

        const dialog = document.createElement('div');
        dialog.className = 'template-download-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>欢迎使用模板本地存储</h3>
                <p>模版文件已保存到:</p>
                <p class="template-dialog-path">${path}</p>
                <p>后续下载会自动写入该目录，便于离线使用与文件管理。</p>
                <div class="dialog-buttons">
                    <button class="btn btn-primary open-location-btn">打开文件夹</button>
                    <button class="btn btn-secondary close-dialog-btn">我知道了</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);

        const openBtn = dialog.querySelector('.open-location-btn') as HTMLButtonElement | null;
        openBtn?.addEventListener('click', () => {
            void TemplateStorageService.openStorageFolder();
            document.body.removeChild(dialog);
        });

        const closeBtn = dialog.querySelector('.close-dialog-btn') as HTMLButtonElement | null;
        closeBtn?.addEventListener('click', () => {
            document.body.removeChild(dialog);
        });

        try {
            if (typeof localStorage !== 'undefined') {
                localStorage.setItem(FIRST_LAUNCH_GUIDE_KEY, 'true');
            }
        } catch {
            // localStorage 不可用时忽略
        }
    }

    private static async updateStorageInfo(panel: HTMLElement): Promise<void> {
        const pathNode = panel.querySelector('.template-storage-path') as HTMLElement | null;
        const usageNode = panel.querySelector('.template-storage-usage') as HTMLElement | null;

        if (!pathNode || !usageNode) {
            return;
        }

        try {
            const summary = await TemplateStorageService.getStorageSummary();
            pathNode.textContent = summary.path;
            usageNode.textContent = `${this.formatBytes(summary.usedBytes)}（${summary.fileCount} 个文件）`;
        } catch {
            pathNode.textContent = TemplateStorageService.getPreferredStoragePath();
            usageNode.textContent = '--';
        }
    }

    private static async renderFileList(panel: HTMLElement): Promise<void> {
        const fileList = panel.querySelector('.template-file-list') as HTMLElement | null;
        if (!fileList) {
            return;
        }

        if (!TemplateStorageService.canUseNativeStorage()) {
            fileList.innerHTML = '<div class="template-file-empty">当前环境不支持读取本地文件列表。</div>';
            return;
        }

        const files = await TemplateStorageService.listTemplates();
        if (files.length === 0) {
            fileList.innerHTML = '<div class="template-file-empty">当前目录暂无已下载模板。</div>';
            return;
        }

        fileList.innerHTML = files.map(file => `
            <div class="template-file-row" data-filename="${file.name}">
                <div class="template-file-meta">
                    <div class="template-file-name">${file.name}</div>
                    <div class="template-file-info">${this.formatBytes(file.size)} · ${this.formatTime(file.mtime || file.ctime || 0)}</div>
                </div>
                <div class="template-file-actions">
                    <button class="btn btn-secondary template-open-file-btn" data-filename="${file.name}">打开</button>
                    <button class="btn btn-secondary template-delete-file-btn" data-filename="${file.name}">删除</button>
                </div>
            </div>
        `).join('');

        fileList.querySelectorAll('.template-open-file-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const filename = (btn as HTMLElement).dataset.filename;
                if (filename) {
                    void TemplateStorageService.openTemplateFile(filename);
                }
            });
        });

        fileList.querySelectorAll('.template-delete-file-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const filename = (btn as HTMLElement).dataset.filename;
                if (!filename) {
                    return;
                }

                const confirmed = I18nDialog.confirm('dialog.template.fileDeleteConfirm', { filename });
                if (!confirmed) {
                    return;
                }

                void (async () => {
                    try {
                        await TemplateStorageService.deleteTemplate(filename);
                        await this.updateStorageInfo(panel);
                        await this.renderFileList(panel);
                    } catch (error) {
                        I18nDialog.alert('dialog.template.fileDeleteFailed', {
                            error: String((error as Error)?.message || error)
                        });
                    }
                })();
            });
        });
    }

    private static async clearTemplates(panel: HTMLElement): Promise<void> {
        const confirmed = I18nDialog.confirm('dialog.template.clear.confirm');
        if (!confirmed) {
            return;
        }

        try {
            const deletedCount = await TemplateStorageService.clearTemplates();
            await this.updateStorageInfo(panel);
            await this.renderFileList(panel);
            I18nDialog.alert('dialog.template.cleaned', { count: deletedCount });
        } catch (error) {
            I18nDialog.alert('dialog.template.clearFailed', {
                error: String((error as Error)?.message || error)
            });
        }
    }

    private static formatBytes(bytes: number): string {
        if (!bytes || bytes <= 0) {
            return '0 B';
        }

        const units = ['B', 'KB', 'MB', 'GB'];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const value = bytes / Math.pow(1024, index);
        return `${value.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
    }

    private static formatTime(timestamp: number): string {
        if (!timestamp) {
            return '未知时间';
        }

        try {
            return new Date(timestamp).toLocaleString();
        } catch {
            return '未知时间';
        }
    }

    private static handleDownloadError(error: unknown): void {
        const message = String((error as { message?: string })?.message || error || '');

        if (message.includes('PERMISSION_DENIED') || message.includes('denied')) {
            I18nDialog.alert('dialog.template.storagePermissionDenied');
            return;
        }

        if (message.includes('No space') || message.includes('ENOSPC') || message.includes('quota')) {
            I18nDialog.alert('dialog.template.insufficientStorage');
            return;
        }

        I18nDialog.alert('dialog.template.downloadFailedWithError', {
            message: message || '未知错误'
        });
    }
}
