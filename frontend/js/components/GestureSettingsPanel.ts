/**
 * 手势配置面板
 * 提供手势自定义配置功能
 */

import './config/主题变量';
import TouchGestureManager, { GestureType } from './TouchGestureManager';

export interface GestureSetting {
    type: GestureType;
    enabled: boolean;
    hapticEnabled: boolean;
    priority: number;
    customAction?: string;
}

export interface GestureSettingsPanelOptions {
    gestureManager: TouchGestureManager;
    onSave?: (settings: GestureSetting[]) => void;
    onReset?: () => void;
}

const defaultSettings: GestureSetting[] = [
    { type: 'tap', enabled: true, hapticEnabled: true, priority: 4 },
    { type: 'doubleTap', enabled: true, hapticEnabled: true, priority: 5 },
    { type: 'longPress', enabled: true, hapticEnabled: true, priority: 10 },
    { type: 'swipe', enabled: true, hapticEnabled: true, priority: 6 },
    { type: 'pinch', enabled: true, hapticEnabled: true, priority: 8 },
    { type: 'rotate', enabled: true, hapticEnabled: true, priority: 8 },
    { type: 'tripleFingerPinch', enabled: true, hapticEnabled: true, priority: 9 },
    { type: 'quickSwipe', enabled: true, hapticEnabled: true, priority: 7 },
    { type: 'layerSwipe', enabled: true, hapticEnabled: true, priority: 7 },
];

const gestureDescriptions: Record<GestureType, string> = {
    tap: '单击进行选择或标记',
    doubleTap: '双击进行放大或确认',
    longPress: '长按添加采样点或查看详情',
    swipe: '滑动平移地图',
    pinch: '双指缩放地图',
    rotate: '双指旋转地图',
    tripleFingerPinch: '三指缩放地图',
    quickSwipe: '快速滑动切换视图',
    layerSwipe: '水平滑动切换图层',
};

const gestureIcons: Record<GestureType, string> = {
    tap: '👆',
    doubleTap: '👆👆',
    longPress: '👇',
    swipe: '👉',
    pinch: '👌',
    rotate: '🔄',
    tripleFingerPinch: '✌️👇',
    quickSwipe: '💨',
    layerSwipe: '↔️',
};

class GestureSettingsPanel {
    private options: GestureSettingsPanelOptions;
    private container: HTMLElement | null = null;
    private settings: GestureSetting[] = [];
    private isVisible: boolean = false;
    private storageKey: string = 'gesture_settings';

    constructor(options: GestureSettingsPanelOptions) {
        this.options = options;
        this.loadSettings();
    }

    /**
     * 初始化面板
     */
    public init(container: HTMLElement): void {
        this.container = container;
    }

    /**
     * 显示面板
     */
    public show(): void {
        if (!this.container) return;

        this.isVisible = true;
        this.render();
    }

    /**
     * 隐藏面板
     */
    public hide(): void {
        if (this.container) {
            const panel = this.container.querySelector('.gesture-settings-panel');
            if (panel) {
                panel.remove();
            }
        }

        this.isVisible = false;
    }

    /**
     * 切换面板显示状态
     */
    public toggle(): void {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * 加载设置
     */
    private loadSettings(): void {
        try {
            const data = localStorage.getItem(this.storageKey);
            if (data) {
                this.settings = JSON.parse(data);
            } else {
                this.settings = [...defaultSettings];
            }
        } catch (e) {
            console.warn('加载手势设置失败:', e);
            this.settings = [...defaultSettings];
        }
    }

    /**
     * 保存设置
     */
    private saveSettings(): void {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.settings));
        } catch (e) {
            console.warn('保存手势设置失败:', e);
        }
    }

    /**
     * 应用设置到手势管理器
     */
    public applySettings(): void {
        this.settings.forEach(setting => {
            if (setting.enabled) {
                this.options.gestureManager.enable(setting.type);
            } else {
                this.options.gestureManager.disable(setting.type);
            }

            this.options.gestureManager.setGesturePriority(setting.type, setting.priority);
        });
    }

    /**
     * 重置设置为默认值
     */
    public resetToDefaults(): void {
        this.settings = [...defaultSettings];
        this.saveSettings();
        this.applySettings();

        if (this.options.onReset) {
            this.options.onReset();
        }

        if (this.isVisible) {
            this.render();
        }
    }

    /**
     * 更新手势设置
     */
    private updateSetting(type: GestureType, updates: Partial<GestureSetting>): void {
        const setting = this.settings.find(s => s.type === type);
        if (setting) {
            Object.assign(setting, updates);
        }
    }

    /**
     * 渲染面板
     */
    private render(): void {
        if (!this.container) return;

        // 移除现有面板
        const existingPanel = this.container.querySelector('.gesture-settings-panel');
        if (existingPanel) {
            existingPanel.remove();
        }

        // 创建面板
        const panel = document.createElement('div');
        panel.className = 'gesture-settings-panel';
        panel.innerHTML = `
            <div class="gesture-settings-content">
                <div class="gesture-settings-header">
                    <h2>手势设置</h2>
                    <button class="close-button" aria-label="关闭">×</button>
                </div>

                <div class="gesture-settings-body">
                    <div class="settings-section">
                        <h3>手势配置</h3>
                        <div class="gesture-settings-list">
                            ${this.settings.map(setting => `
                                <div class="gesture-setting-item" data-gesture="${setting.type}">
                                    <div class="gesture-info">
                                        <div class="gesture-icon">${gestureIcons[setting.type]}</div>
                                        <div class="gesture-details">
                                            <div class="gesture-name">${this.getGestureName(setting.type)}</div>
                                            <div class="gesture-description">${gestureDescriptions[setting.type]}</div>
                                        </div>
                                    </div>

                                    <div class="gesture-controls">
                                        <label class="toggle-switch">
                                            <input type="checkbox" ${setting.enabled ? 'checked' : ''} class="gesture-enable-toggle">
                                            <span class="toggle-slider"></span>
                                        </label>

                                        <label class="toggle-switch">
                                            <input type="checkbox" ${setting.hapticEnabled ? 'checked' : ''} class="gesture-haptic-toggle">
                                            <span class="toggle-slider"></span>
                                        </label>

                                        <div class="priority-control">
                                            <input type="range" min="1" max="10" value="${setting.priority}" class="priority-slider">
                                            <span class="priority-value">${setting.priority}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="settings-section">
                        <h3>优先级说明</h3>
                        <p class="priority-description">
                            优先级数值越大，手势优先级越高。当多个手势同时触发时，高优先级的手势会优先生效。
                        </p>
                    </div>
                </div>

                <div class="gesture-settings-footer">
                    <button class="button button-secondary reset-button">重置默认</button>
                    <button class="button button-primary save-button">保存设置</button>
                </div>
            </div>
        `;

        // 添加样式
        this.injectStyles();

        // 绑定事件
        this.bindEvents(panel);

        this.container.appendChild(panel);
    }

    /**
     * 绑定事件
     */
    private bindEvents(panel: HTMLElement): void {
        const closeButton = panel.querySelector('.close-button') as HTMLElement;
        const saveButton = panel.querySelector('.save-button') as HTMLElement;
        const resetButton = panel.querySelector('.reset-button') as HTMLElement;

        if (closeButton) {
            closeButton.addEventListener('click', () => this.hide());
        }

        if (saveButton) {
            saveButton.addEventListener('click', () => {
                this.saveSettings();
                this.applySettings();

                if (this.options.onSave) {
                    this.options.onSave(this.settings);
                }

                this.hide();
            });
        }

        if (resetButton) {
            resetButton.addEventListener('click', () => {
                if (confirm('确定要重置所有手势设置为默认值吗？')) {
                    this.resetToDefaults();
                }
            });
        }

        // 绑定手势项事件
        const gestureItems = panel.querySelectorAll('.gesture-setting-item');
        gestureItems.forEach(item => {
            const gestureType = item.dataset.gesture as GestureType;

            const enableToggle = item.querySelector('.gesture-enable-toggle') as HTMLInputElement;
            const hapticToggle = item.querySelector('.gesture-haptic-toggle') as HTMLInputElement;
            const prioritySlider = item.querySelector('.priority-slider') as HTMLInputElement;
            const priorityValue = item.querySelector('.priority-value') as HTMLElement;

            if (enableToggle) {
                enableToggle.addEventListener('change', (e) => {
                    this.updateSetting(gestureType, { enabled: (e.target as HTMLInputElement).checked });
                });
            }

            if (hapticToggle) {
                hapticToggle.addEventListener('change', (e) => {
                    this.updateSetting(gestureType, { hapticEnabled: (e.target as HTMLInputElement).checked });
                });
            }

            if (prioritySlider && priorityValue) {
                prioritySlider.addEventListener('input', (e) => {
                    const value = parseInt((e.target as HTMLInputElement).value, 10);
                    this.updateSetting(gestureType, { priority: value });
                    priorityValue.textContent = value.toString();
                });
            }
        });
    }

    /**
     * 获取手势名称
     */
    private getGestureName(type: GestureType): string {
        const names: Record<GestureType, string> = {
            tap: '点击',
            doubleTap: '双击',
            longPress: '长按',
            swipe: '滑动',
            pinch: '双指缩放',
            rotate: '双指旋转',
            tripleFingerPinch: '三指缩放',
            quickSwipe: '快速滑动',
            layerSwipe: '图层切换',
        };
        return names[type] || type;
    }

    /**
     * 注入样式
     */
    private injectStyles(): void {
        if (document.getElementById('gesture-settings-styles')) return;

        const style = document.createElement('style');
        style.id = 'gesture-settings-styles';
        style.textContent = `
            .gesture-settings-panel {
                position: fixed;
                top: 0;
                right: 0;
                bottom: 0;
                width: 400px;
                max-width: 90vw;
                background: var(--background-primary);
                box-shadow: -4px 0 20px rgba(0, 0, 0, 0.2);
                z-index: 10000;
                animation: slideInRight 0.3s ease-out;
                overflow-y: auto;
            }

            .gesture-settings-content {
                display: flex;
                flex-direction: column;
                height: 100%;
            }

            .gesture-settings-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 20px;
                border-bottom: 1px solid var(--border-color);
            }

            .gesture-settings-header h2 {
                margin: 0;
                font-size: 20px;
                color: var(--text-primary);
            }

            .close-button {
                background: none;
                border: none;
                font-size: 32px;
                color: var(--text-secondary);
                cursor: pointer;
                padding: 0;
                width: 32px;
                height: 32px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                transition: background 0.2s;
            }

            .close-button:hover {
                background: var(--background-secondary);
                color: var(--text-primary);
            }

            .gesture-settings-body {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
            }

            .settings-section {
                margin-bottom: 24px;
            }

            .settings-section h3 {
                margin: 0 0 12px;
                font-size: 16px;
                color: var(--text-primary);
            }

            .gesture-settings-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .gesture-setting-item {
                background: var(--background-secondary);
                border-radius: 12px;
                padding: 16px;
                transition: all 0.2s;
            }

            .gesture-setting-item:hover {
                background: var(--background-hover);
            }

            .gesture-info {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
            }

            .gesture-icon {
                font-size: 32px;
                width: 48px;
                height: 48px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: var(--background-primary);
                border-radius: 8px;
            }

            .gesture-details {
                flex: 1;
            }

            .gesture-name {
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary);
                margin-bottom: 4px;
            }

            .gesture-description {
                font-size: 12px;
                color: var(--text-secondary);
            }

            .gesture-controls {
                display: flex;
                align-items: center;
                gap: 16px;
            }

            .toggle-switch {
                position: relative;
                display: inline-block;
                width: 44px;
                height: 24px;
            }

            .toggle-switch input {
                opacity: 0;
                width: 0;
                height: 0;
            }

            .toggle-slider {
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: var(--border-color);
                transition: 0.3s;
                border-radius: 24px;
            }

            .toggle-slider:before {
                position: absolute;
                content: "";
                height: 18px;
                width: 18px;
                left: 3px;
                bottom: 3px;
                background-color: white;
                transition: 0.3s;
                border-radius: 50%;
            }

            input:checked + .toggle-slider {
                background-color: var(--accent-color, #3b82f6);
            }

            input:checked + .toggle-slider:before {
                transform: translateX(20px);
            }

            .priority-control {
                display: flex;
                align-items: center;
                gap: 8px;
                flex: 1;
            }

            .priority-slider {
                flex: 1;
                -webkit-appearance: none;
                height: 6px;
                border-radius: 3px;
                background: var(--border-color);
                outline: none;
            }

            .priority-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: var(--accent-color, #3b82f6);
                cursor: pointer;
            }

            .priority-slider::-moz-range-thumb {
                width: 18px;
                height: 18px;
                border-radius: 50%;
                background: var(--accent-color, #3b82f6);
                cursor: pointer;
                border: none;
            }

            .priority-value {
                min-width: 24px;
                text-align: center;
                font-size: 14px;
                color: var(--text-primary);
                font-weight: 600;
            }

            .priority-description {
                font-size: 13px;
                color: var(--text-secondary);
                line-height: 1.5;
                margin: 0;
            }

            .gesture-settings-footer {
                display: flex;
                gap: 12px;
                padding: 20px;
                border-top: 1px solid var(--border-color);
                justify-content: flex-end;
            }

            .button {
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
            }

            .button-primary {
                background: var(--accent-color, #3b82f6);
                color: white;
            }

            .button-primary:hover {
                background: var(--accent-hover, #2563eb);
            }

            .button-secondary {
                background: var(--background-secondary);
                color: var(--text-primary);
            }

            .button-secondary:hover {
                background: var(--background-hover);
            }

            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                }
                to {
                    transform: translateX(0);
                }
            }

            @media (max-width: 768px) {
                .gesture-settings-panel {
                    width: 100%;
                    max-width: 100%;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * 销毁面板
     */
    public destroy(): void {
        this.hide();
        const styles = document.getElementById('gesture-settings-styles');
        if (styles) {
            styles.remove();
        }
    }
}

export default GestureSettingsPanel;