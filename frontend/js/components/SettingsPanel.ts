/**
 * 设置面板组件
 * 提供应用设置功能，包括语言切换、单位配置等
 */

import { I18n } from '../utils/I18n';
import { appStore } from '../store/Store';
import { unitManager } from '../services/UnitManager';
import { CustomSelect } from './CustomSelect';

interface SettingsOptions {
    onLanguageChange?: (language: string) => void;
}

export class SettingsPanel {
    private container: HTMLElement;
    private overlay: HTMLElement;
    private panel: HTMLElement;
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
                        <div class="settings-language-options">
                            <label class="settings-language-option">
                                <input type="radio" name="language" value="zh-CN" ${I18n.locale === 'zh-CN' ? 'checked' : ''}>
                                <span class="settings-language-name">${I18n.t('settings.language.zh-CN')}</span>
                            </label>
                            <label class="settings-language-option">
                                <input type="radio" name="language" value="en-US" ${I18n.locale === 'en-US' ? 'checked' : ''}>
                                <span class="settings-language-name">${I18n.t('settings.language.en-US')}</span>
                            </label>
                        </div>
                    </div>

                    <div class="settings-section">
                        <h3 class="settings-section-title">单位设置</h3>
                        
                        <div class="settings-item">
                            <label class="settings-label">坐标系统</label>
                            <div id="coordinate-system-container" class="custom-select-container"></div>
                        </div>

                        <div class="settings-item">
                            <label class="settings-label">长度单位</label>
                            <div id="length-unit-container" class="custom-select-container"></div>
                        </div>

                        <div class="settings-item">
                            <label class="settings-label">面积单位</label>
                            <div id="area-unit-container" class="custom-select-container"></div>
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

    private initCustomSelects(): void {
        // 初始化坐标系统选择器
        const coordinateSystemContainer = this.panel.querySelector('#coordinate-system-container');
        if (coordinateSystemContainer) {
            this.coordinateSystemSelect = new CustomSelect(coordinateSystemContainer as HTMLElement, {
                name: 'coordinate-system',
                options: [
                    { value: 'wgs84', label: 'WGS84 (经纬度)' },
                    { value: 'gcj02', label: 'GCJ02 (火星坐标)' },
                    { value: 'bd09', label: 'BD09 (百度坐标)' }
                ],
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
                options: [
                    { value: 'm', label: '米 (m)' },
                    { value: 'km', label: '千米 (km)' },
                    { value: 'ft', label: '英尺 (ft)' },
                    { value: 'mi', label: '英里 (mi)' }
                ],
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
                options: [
                    { value: 'm2', label: '平方米 (m²)' },
                    { value: 'km2', label: '平方千米 (km²)' },
                    { value: 'ha', label: '公顷 (ha)' },
                    { value: 'ac', label: '英亩 (ac)' }
                ],
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
                this.updateLanguage(target.value);
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
    }

    private updateLanguage(language: string): void {
        I18n.setLocale(language);
        this.updateUIText();
        if (this.onLanguageChange) {
            this.onLanguageChange(language);
        }
    }

    private updateUIText(): void {
        const title = this.panel.querySelector('.settings-title') as HTMLElement;
        const closeBtn = this.panel.querySelector('.settings-close-btn') as HTMLButtonElement;
        const sectionTitle = this.panel.querySelector('.settings-section-title') as HTMLElement;
        const resetBtn = this.panel.querySelector('.settings-reset-btn') as HTMLButtonElement;
        const saveBtn = this.panel.querySelector('.settings-save-btn') as HTMLButtonElement;

        if (title) title.textContent = I18n.t('settings.title');
        if (closeBtn) closeBtn.setAttribute('title', I18n.t('common.close'));
        if (sectionTitle) sectionTitle.textContent = I18n.t('settings.language');
        if (resetBtn) resetBtn.textContent = I18n.t('settings.reset');
        if (saveBtn) saveBtn.textContent = I18n.t('settings.save');

        // 更新语言选项文本
        const languageOptions = this.panel.querySelectorAll('.settings-language-name');
        languageOptions.forEach((option, index) => {
            const language = index === 0 ? 'zh-CN' : 'en-US';
            option.textContent = I18n.t(`settings.language.${language}`);
        });
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