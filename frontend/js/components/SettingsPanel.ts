/**
 * 设置面板组件
 * 提供应用设置功能，包括语言切换等
 */

import { I18n } from '../utils/I18n';

interface SettingsOptions {
    onLanguageChange?: (language: string) => void;
}

export class SettingsPanel {
    private container: HTMLElement;
    private overlay: HTMLElement;
    private panel: HTMLElement;
    private onLanguageChange: ((language: string) => void) | null;

    constructor(container: HTMLElement | string, options: SettingsOptions = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.onLanguageChange = options.onLanguageChange || null;
        this.init();
    }

    private init(): void {
        this.createPanel();
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

        this.hide();
    }

    public show(): void {
        this.overlay.style.display = 'flex';
        this.updateUIText();
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
        this.overlay.remove();
    }
}