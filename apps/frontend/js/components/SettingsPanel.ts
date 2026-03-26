/**
 * 设置面板组件
 * 提供应用设置功能，包括语言切换、单位配置等
 */

import { I18n } from '../utils/I18n';
import { unitManager } from '../services/UnitManager';
import { CustomSelect } from './CustomSelect';
import { I18nDialog } from './I18nDialog.js';
import { TemplateStorageService } from '../services/TemplateStorageService.js';

interface SettingsOptions {
    onLanguageChange?: (language: string) => void;
}

export class SettingsPanel {
    private container: HTMLElement;
    private overlay!: HTMLElement;
    private panel!: HTMLElement;
    private onLanguageChange: ((language: string) => void) | null;

    // 自定义下拉组件实例
    private coordinateSystemSelect: CustomSelect | null = null;
    private lengthUnitSelect: CustomSelect | null = null;
    private areaUnitSelect: CustomSelect | null = null;

    constructor(container: HTMLElement | string, options: SettingsOptions = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.onLanguageChange = options.onLanguageChange || null;
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.initCustomSelects();
        this.bindEvents();
    }

    private createPanel(): void {
        const languageOptions = this.getLanguageOptionsHtml();

        // 创建遮罩层
        this.overlay = document.createElement('div');
        this.overlay.className = 'settings-overlay';
        this.overlay.style.display = 'none';

        // 创建设置面板
        this.panel = document.createElement('div');
        this.panel.className = 'settings-panel';
        this.panel.innerHTML = `
            <div class="settings-panel-content">
                <div class="settings-header">
                    <h2 class="settings-title">${I18n.t('settings.title')}</h2>
                    <button class="btn btn-icon settings-close-btn" title="${I18n.t('common.close')}">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                <div class="settings-body">
                    <div class="settings-section">
                        <h3 class="settings-section-title">${I18n.t('settings.language')}</h3>
                        <div class="settings-language-options">${languageOptions}</div>
                    </div>

                    <div class="settings-section">
                        <h3 class="settings-section-title settings-units-title">${I18n.t('settings.units')}</h3>
                        
                        <div class="settings-item">
                            <label class="settings-label settings-coordinate-label">${I18n.t('settings.unit.coordinate')}</label>
                            <div id="coordinate-system-container" class="custom-select-container"></div>
                        </div>

                        <div class="settings-item">
                            <label class="settings-label settings-length-label">${I18n.t('settings.unit.length')}</label>
                            <div id="length-unit-container" class="custom-select-container"></div>
                        </div>

                        <div class="settings-item">
                            <label class="settings-label settings-area-label">${I18n.t('settings.unit.area')}</label>
                            <div id="area-unit-container" class="custom-select-container"></div>
                        </div>
                    </div>

                    <div class="settings-section">
                        <h3 class="settings-section-title settings-storage-title">存储管理</h3>
                        <div class="settings-item">
                            <label class="settings-label settings-storage-path-label">模板存储路径</label>
                            <div class="settings-value settings-storage-path">--</div>
                        </div>
                        <div class="settings-item">
                            <label class="settings-label settings-storage-usage-label">已用空间</label>
                            <div class="settings-value settings-storage-usage">--</div>
                        </div>
                        <div class="settings-storage-actions">
                            <button class="btn btn-secondary settings-storage-refresh-btn">刷新</button>
                            <button class="btn btn-secondary settings-storage-open-btn">打开文件夹</button>
                            <button class="btn btn-secondary settings-storage-clear-btn">清空模板</button>
                        </div>
                    </div>
                </div>

                <div class="settings-footer">
                    <button class="btn btn-secondary settings-reset-btn">${I18n.t('settings.reset')}</button>
                    <button class="btn btn-primary settings-save-btn">${I18n.t('settings.save')}</button>
                </div>
            </div>
        `;

        this.overlay.appendChild(this.panel);
        this.container.appendChild(this.overlay);
    }

    private getLanguageOptionsHtml(): string {
        return I18n.getAvailableLocales()
            .map((locale) => `
                <label class="settings-language-option">
                    <input type="radio" name="language" value="${locale.code}" ${I18n.locale === locale.code ? 'checked' : ''}>
                    <span class="settings-language-name" data-language-code="${locale.code}">${locale.name}</span>
                </label>
            `)
            .join('');
    }

    private getCoordinateOptions(): Array<{ value: string; label: string }> {
        return [
            { value: 'wgs84', label: I18n.t('settings.unit.wgs84') },
            { value: 'gcj02', label: I18n.t('settings.unit.gcj02') },
            { value: 'bd09', label: I18n.t('settings.unit.bd09') }
        ];
    }

    private getLengthOptions(): Array<{ value: string; label: string }> {
        return [
            { value: 'm', label: I18n.t('settings.unit.m') },
            { value: 'km', label: I18n.t('settings.unit.km') },
            { value: 'ft', label: I18n.t('settings.unit.ft') },
            { value: 'mi', label: I18n.t('settings.unit.mi') }
        ];
    }

    private getAreaOptions(): Array<{ value: string; label: string }> {
        return [
            { value: 'm2', label: I18n.t('settings.unit.m2') },
            { value: 'km2', label: I18n.t('settings.unit.km2') },
            { value: 'ha', label: I18n.t('settings.unit.ha') },
            { value: 'ac', label: I18n.t('settings.unit.ac') }
        ];
    }

    private initCustomSelects(): void {
        // 初始化坐标系统选择器
        const coordinateSystemContainer = this.panel.querySelector('#coordinate-system-container');
        if (coordinateSystemContainer) {
            this.coordinateSystemSelect = new CustomSelect(coordinateSystemContainer as HTMLElement, {
                name: 'coordinate-system',
                options: this.getCoordinateOptions(),
                value: unitManager.getCoordinateSystem(),
                onChange: (value) => {
                    unitManager.setCoordinateSystem(value as any);
                }
            });
        }

        // 初始化长度单位选择器
        const lengthUnitContainer = this.panel.querySelector('#length-unit-container');
        if (lengthUnitContainer) {
            this.lengthUnitSelect = new CustomSelect(lengthUnitContainer as HTMLElement, {
                name: 'length-unit',
                options: this.getLengthOptions(),
                value: unitManager.getLengthUnit(),
                onChange: (value) => {
                    unitManager.setLengthUnit(value as any);
                }
            });
        }

        // 初始化面积单位选择器
        const areaUnitContainer = this.panel.querySelector('#area-unit-container');
        if (areaUnitContainer) {
            this.areaUnitSelect = new CustomSelect(areaUnitContainer as HTMLElement, {
                name: 'area-unit',
                options: this.getAreaOptions(),
                value: unitManager.getAreaUnit(),
                onChange: (value) => {
                    unitManager.setAreaUnit(value as any);
                }
            });
        }
    }

    private bindEvents(): void {
        const closeBtn = this.panel.querySelector('.settings-close-btn') as HTMLButtonElement;
        const resetBtn = this.panel.querySelector('.settings-reset-btn') as HTMLButtonElement;
        const saveBtn = this.panel.querySelector('.settings-save-btn') as HTMLButtonElement;
        const storageRefreshBtn = this.panel.querySelector('.settings-storage-refresh-btn') as HTMLButtonElement | null;
        const storageOpenBtn = this.panel.querySelector('.settings-storage-open-btn') as HTMLButtonElement | null;
        const storageClearBtn = this.panel.querySelector('.settings-storage-clear-btn') as HTMLButtonElement | null;
        const languageInputs = this.panel.querySelectorAll('input[name="language"]') as NodeListOf<HTMLInputElement>;

        // 关闭按钮
        closeBtn.addEventListener('click', () => this.hide());

        // 遮罩层点击关闭
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.hide();
            }
        });

        // ESC 键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible()) {
                this.hide();
            }
        });

        // 语言选项变化
        languageInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                const target = e.target as HTMLInputElement;
                void this.updateLanguage(target.value);
            });
        });

        // 重置按钮
        resetBtn.addEventListener('click', () => {
            this.resetSettings();
        });

        // 保存按钮
        saveBtn.addEventListener('click', () => {
            this.saveSettings();
        });

        storageRefreshBtn?.addEventListener('click', () => {
            void this.refreshStorageManagement();
        });

        storageOpenBtn?.addEventListener('click', () => {
            void (async () => {
                const opened = await TemplateStorageService.openStorageFolder();
                if (!opened) {
                    I18nDialog.alert('当前环境不支持直接打开文件夹，请在系统下载目录中查看。');
                }
            })();
        });

        storageClearBtn?.addEventListener('click', () => {
            void this.clearTemplateFiles();
        });
    }

    private async updateLanguage(language: string): Promise<void> {
        await I18n.setLocaleAsync(language);
        this.updateUIText();
        if (this.onLanguageChange) {
            this.onLanguageChange(language);
        }
    }

    private updateUIText(): void {
        const title = this.panel.querySelector('.settings-title') as HTMLElement;
        const closeBtn = this.panel.querySelector('.settings-close-btn') as HTMLButtonElement;
        const sectionTitle = this.panel.querySelector('.settings-section-title') as HTMLElement;
        const unitsTitle = this.panel.querySelector('.settings-units-title') as HTMLElement;
        const coordinateLabel = this.panel.querySelector('.settings-coordinate-label') as HTMLElement;
        const lengthLabel = this.panel.querySelector('.settings-length-label') as HTMLElement;
        const areaLabel = this.panel.querySelector('.settings-area-label') as HTMLElement;
        const storageTitle = this.panel.querySelector('.settings-storage-title') as HTMLElement;
        const storagePathLabel = this.panel.querySelector('.settings-storage-path-label') as HTMLElement;
        const storageUsageLabel = this.panel.querySelector('.settings-storage-usage-label') as HTMLElement;
        const storageRefreshBtn = this.panel.querySelector('.settings-storage-refresh-btn') as HTMLButtonElement;
        const storageOpenBtn = this.panel.querySelector('.settings-storage-open-btn') as HTMLButtonElement;
        const storageClearBtn = this.panel.querySelector('.settings-storage-clear-btn') as HTMLButtonElement;
        const resetBtn = this.panel.querySelector('.settings-reset-btn') as HTMLButtonElement;
        const saveBtn = this.panel.querySelector('.settings-save-btn') as HTMLButtonElement;

        if (title) title.textContent = I18n.t('settings.title');
        if (closeBtn) closeBtn.setAttribute('title', I18n.t('common.close'));
        if (sectionTitle) sectionTitle.textContent = I18n.t('settings.language');
        if (unitsTitle) unitsTitle.textContent = I18n.t('settings.units');
        if (coordinateLabel) coordinateLabel.textContent = I18n.t('settings.unit.coordinate');
        if (lengthLabel) lengthLabel.textContent = I18n.t('settings.unit.length');
        if (areaLabel) areaLabel.textContent = I18n.t('settings.unit.area');
        if (storageTitle) storageTitle.textContent = '存储管理';
        if (storagePathLabel) storagePathLabel.textContent = '模板存储路径';
        if (storageUsageLabel) storageUsageLabel.textContent = '已用空间';
        if (storageRefreshBtn) storageRefreshBtn.textContent = '刷新';
        if (storageOpenBtn) storageOpenBtn.textContent = '打开文件夹';
        if (storageClearBtn) storageClearBtn.textContent = '清空模板';
        if (resetBtn) resetBtn.textContent = I18n.t('settings.reset');
        if (saveBtn) saveBtn.textContent = I18n.t('settings.save');

        const languageOptions = this.panel.querySelectorAll('.settings-language-name');
        languageOptions.forEach((option) => {
            const language = (option as HTMLElement).dataset.languageCode;
            if (language) {
                option.textContent = I18n.t(`settings.language.${language}`);
            }
        });

        this.coordinateSystemSelect?.setOptions(this.getCoordinateOptions());
        this.lengthUnitSelect?.setOptions(this.getLengthOptions());
        this.areaUnitSelect?.setOptions(this.getAreaOptions());
    }

    private resetSettings(): void {
        // 重置为默认语言（中文）
        I18n.setLocale('zh-CN');

        // 更新单选按钮
        const languageInputs = this.panel.querySelectorAll('input[name="language"]') as NodeListOf<HTMLInputElement>;
        languageInputs.forEach(input => {
            input.checked = input.value === 'zh-CN';
        });

        // 重置单位配置为默认值
        unitManager.resetToDefaults();

        // 更新自定义选择器
        if (this.coordinateSystemSelect) {
            this.coordinateSystemSelect.setValue('wgs84');
        }
        if (this.lengthUnitSelect) {
            this.lengthUnitSelect.setValue('m');
        }
        if (this.areaUnitSelect) {
            this.areaUnitSelect.setValue('m2');
        }

        this.updateUIText();
        if (this.onLanguageChange) {
            this.onLanguageChange('zh-CN');
        }
    }

    private saveSettings(): void {
        // 获取当前选择的语言
        const selectedInput = this.panel.querySelector('input[name="language"]:checked') as HTMLInputElement;
        if (selectedInput) {
            const language = selectedInput.value;
            I18n.setLocale(language);
            if (this.onLanguageChange) {
                this.onLanguageChange(language);
            }
        }

        // 单位配置已经在事件监听器中自动保存到 store
        // 这里只需要隐藏面板
        this.hide();
    }

    public show(): void {
        this.overlay.style.display = 'flex';
        this.updateUIText();
        this.loadUnitSettings();
        void this.refreshStorageManagement();
    }

    private loadUnitSettings(): void {
        // 加载当前单位配置
        const coordinateSystem = unitManager.getCoordinateSystem();
        const lengthUnit = unitManager.getLengthUnit();
        const areaUnit = unitManager.getAreaUnit();

        // 更新自定义选择器
        if (this.coordinateSystemSelect) {
            this.coordinateSystemSelect.setValue(coordinateSystem);
        }
        if (this.lengthUnitSelect) {
            this.lengthUnitSelect.setValue(lengthUnit);
        }
        if (this.areaUnitSelect) {
            this.areaUnitSelect.setValue(areaUnit);
        }
    }

    public hide(): void {
        this.overlay.style.display = 'none';
    }

    public isVisible(): boolean {
        return this.overlay.style.display === 'flex';
    }

    public toggle(): void {
        if (this.isVisible()) {
            this.hide();
        } else {
            this.show();
        }
    }

    private async refreshStorageManagement(): Promise<void> {
        const pathNode = this.panel.querySelector('.settings-storage-path') as HTMLElement | null;
        const usageNode = this.panel.querySelector('.settings-storage-usage') as HTMLElement | null;

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

    private async clearTemplateFiles(): Promise<void> {
        const confirmed = I18nDialog.confirm('确定要清空已下载模板吗？此操作不可恢复。');
        if (!confirmed) {
            return;
        }

        try {
            const count = await TemplateStorageService.clearTemplates();
            await this.refreshStorageManagement();
            I18nDialog.alert(`已清理 ${count} 个模板文件`);
        } catch (error) {
            I18nDialog.alert(`清理失败：${String((error as Error)?.message || error)}`);
        }
    }

    private formatBytes(bytes: number): string {
        if (!bytes || bytes <= 0) {
            return '0 B';
        }

        const units = ['B', 'KB', 'MB', 'GB'];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const value = bytes / Math.pow(1024, index);
        return `${value.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
    }

    public destroy(): void {
        // 销毁自定义下拉组件
        if (this.coordinateSystemSelect) {
            this.coordinateSystemSelect.destroy();
        }
        if (this.lengthUnitSelect) {
            this.lengthUnitSelect.destroy();
        }
        if (this.areaUnitSelect) {
            this.areaUnitSelect.destroy();
        }
        
        this.overlay.remove();
    }
}
