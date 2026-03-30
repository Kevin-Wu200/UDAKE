/**
 * 无障碍管理器
 * 统一管理键盘、屏幕阅读器、视觉辅助、语音与手势增强
 */

type ColorBlindMode = 'none' | 'protanopia' | 'deuteranopia' | 'tritanopia' | 'grayscale';

interface AccessibilityPreferences {
    highContrast: boolean;
    fontScale: number;
    colorBlindMode: ColorBlindMode;
    reduceMotion: boolean;
    darkModeOptimization: boolean;
    voiceControlEnabled: boolean;
    smartAssistEnabled: boolean;
}

interface MapCenter {
    lng: number;
    lat: number;
}

interface MapViewLike {
    getCenter?: () => [number, number] | MapCenter;
    setCenter?: (center: [number, number]) => void;
    getZoom?: () => number;
    setZoom?: (zoom: number) => void;
}

interface AccessibilityManagerOptions {
    getMapView?: () => MapViewLike | null;
    onShowShortcutHelp?: () => void;
}

const STORAGE_KEY = 'udake_accessibility_preferences';

const DEFAULT_PREFERENCES: AccessibilityPreferences = {
    highContrast: false,
    fontScale: 1,
    colorBlindMode: 'none',
    reduceMotion: false,
    darkModeOptimization: true,
    voiceControlEnabled: false,
    smartAssistEnabled: true
};

export class AccessibilityManager {
    private readonly options: AccessibilityManagerOptions;
    private preferences: AccessibilityPreferences;
    private liveRegion: HTMLDivElement | null = null;
    private assertiveLiveRegion: HTMLDivElement | null = null;
    private toolbarPanel: HTMLDivElement | null = null;
    private toolbarTrigger: HTMLButtonElement | null = null;
    private observers: MutationObserver[] = [];
    private speechRecognition: any = null;
    private isVoiceRunning: boolean = false;
    private smartAssistTimer: number | null = null;
    private resizeHandlerBound: (() => void) | null = null;
    private toolbarFocusHandler: ((event: KeyboardEvent) => void) | null = null;

    constructor(options: AccessibilityManagerOptions = {}) {
        this.options = options;
        this.preferences = this.loadPreferences();
    }

    public init(): void {
        this.ensureLiveRegions();
        this.ensureSemanticStructure();
        this.bindFilePickerKeyboardAccess();
        this.bindPanelCollapseToggle();
        this.bindStatusAnnouncements();
        this.bindMapKeyboardNavigation();
        this.bindGlobalKeyboardNavigation();
        this.bindAdaptiveInterface();
        this.bindGestureSupport();
        this.enhanceFormAccessibility();
        this.enhanceChartAccessibility();
        this.createToolbar();
        this.applyPreferences();
        this.bindCustomAnnouncementEvent();
        this.announce('无障碍增强已启用。按 Alt + 1 可跳转主内容，按 Ctrl + / 查看快捷键。');
    }

    public refresh(): void {
        this.ensureSemanticStructure();
        this.enhanceFormAccessibility();
        this.enhanceChartAccessibility();
        this.bindMapKeyboardNavigation();
    }

    public announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
        const target = priority === 'assertive' ? this.assertiveLiveRegion : this.liveRegion;
        if (!target) {
            return;
        }

        target.textContent = '';
        window.setTimeout(() => {
            target.textContent = message;
        }, 10);
    }

    public destroy(): void {
        this.observers.forEach((observer) => observer.disconnect());
        this.observers = [];
        this.stopVoiceRecognition();
        if (this.smartAssistTimer !== null) {
            window.clearInterval(this.smartAssistTimer);
            this.smartAssistTimer = null;
        }
        if (this.resizeHandlerBound) {
            window.removeEventListener('resize', this.resizeHandlerBound);
            this.resizeHandlerBound = null;
        }
        if (this.toolbarFocusHandler) {
            document.removeEventListener('keydown', this.toolbarFocusHandler);
            this.toolbarFocusHandler = null;
        }
    }

    private ensureLiveRegions(): void {
        if (!this.liveRegion) {
            const region = document.createElement('div');
            region.className = 'a11y-live-region';
            region.setAttribute('aria-live', 'polite');
            region.setAttribute('aria-atomic', 'true');
            region.id = 'a11y-live-region';
            document.body.appendChild(region);
            this.liveRegion = region;
        }

        if (!this.assertiveLiveRegion) {
            const region = document.createElement('div');
            region.className = 'a11y-live-region';
            region.setAttribute('aria-live', 'assertive');
            region.setAttribute('aria-atomic', 'true');
            region.id = 'a11y-live-region-assertive';
            document.body.appendChild(region);
            this.assertiveLiveRegion = region;
        }
    }

    private ensureSemanticStructure(): void {
        const header = document.querySelector('.header');
        header?.setAttribute('role', 'banner');

        const main = document.querySelector('.main-content');
        if (main) {
            main.setAttribute('role', 'main');
            main.setAttribute('tabindex', '-1');
            if (!main.id) {
                main.id = 'main-content';
            }
        }

        const sidebar = document.querySelector('.sidebar');
        sidebar?.setAttribute('aria-label', '主控制面板');

        const rightSidebar = document.getElementById('right-sidebar');
        rightSidebar?.setAttribute('aria-label', '推荐与辅助面板');

        const mapContainer = document.querySelector('.map-container');
        mapContainer?.setAttribute('role', 'region');
        mapContainer?.setAttribute('aria-label', '地图展示区域');

        const mapView = document.getElementById('viewDiv');
        if (mapView) {
            mapView.setAttribute('tabindex', '0');
            mapView.setAttribute('role', 'application');
            mapView.setAttribute('aria-label', '空间地图视图');
            mapView.setAttribute('aria-keyshortcuts', 'ArrowUp ArrowDown ArrowLeft ArrowRight + -');
        }

        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            progressBar.setAttribute('role', 'progressbar');
            progressBar.setAttribute('aria-valuemin', '0');
            progressBar.setAttribute('aria-valuemax', '100');
            if (!progressBar.getAttribute('aria-valuenow')) {
                progressBar.setAttribute('aria-valuenow', '0');
            }
        }

        const statusTargets = ['upload-status', 'export-status', 'task-status'];
        statusTargets.forEach((id) => {
            const element = document.getElementById(id);
            if (element) {
                element.setAttribute('role', 'status');
                element.setAttribute('aria-live', 'polite');
                element.setAttribute('aria-atomic', 'true');
            }
        });

        const settingButton = document.getElementById('settings-btn');
        settingButton?.setAttribute('aria-keyshortcuts', 'Ctrl+,');
        const newProjectButton = document.getElementById('new-project-btn');
        newProjectButton?.setAttribute('aria-keyshortcuts', 'Ctrl+N');
        const uploadButton = document.getElementById('upload-btn');
        uploadButton?.setAttribute('aria-keyshortcuts', 'Ctrl+U');
        const startButton = document.getElementById('start-kriging-btn');
        startButton?.setAttribute('aria-keyshortcuts', 'Ctrl+Enter');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        sidebarToggle?.setAttribute('aria-keyshortcuts', 'Alt+3');
    }

    private bindFilePickerKeyboardAccess(): void {
        const picker = document.getElementById('file-picker');
        if (!picker || picker.dataset.a11yKeyboardBound === 'true') {
            return;
        }

        picker.dataset.a11yKeyboardBound = 'true';
        picker.setAttribute('role', 'button');
        picker.setAttribute('tabindex', '0');
        picker.addEventListener('keydown', (event: KeyboardEvent) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                picker.click();
            }
        });
    }

    private bindPanelCollapseToggle(): void {
        const toggles = document.querySelectorAll<HTMLButtonElement>('.panel-title-toggle[data-a11y-collapse="simple"]');
        toggles.forEach((toggle) => {
            if (toggle.dataset.a11yBound === 'true') {
                return;
            }
            toggle.dataset.a11yBound = 'true';
            toggle.addEventListener('click', () => {
                const targetId = toggle.getAttribute('data-collapse-target');
                if (!targetId) {
                    return;
                }
                const target = document.getElementById(targetId);
                if (!target) {
                    return;
                }

                const isOpen = target.style.display !== 'none';
                target.style.display = isOpen ? 'none' : 'block';
                toggle.setAttribute('aria-expanded', String(!isOpen));
                const labelSpan = toggle.querySelector('span');
                const labelHtml = labelSpan
                    ? labelSpan.outerHTML
                    : (toggle.textContent || '').replace(/[▾▸]/g, '').trim();
                toggle.innerHTML = `${labelHtml || '面板'} ${isOpen ? '▸' : '▾'}`;
            });
        });
    }

    private bindStatusAnnouncements(): void {
        this.observeAnnouncementTarget('upload-status');
        this.observeAnnouncementTarget('export-status');
        this.observeAnnouncementTarget('task-status');
    }

    private observeAnnouncementTarget(id: string): void {
        const target = document.getElementById(id);
        if (!target) {
            return;
        }

        let lastText = '';
        const observer = new MutationObserver(() => {
            const text = target.textContent?.trim() || '';
            if (!text || text === lastText) {
                return;
            }
            lastText = text;
            const isError = target.classList.contains('error') || text.includes('失败') || text.includes('错误');
            this.announce(text, isError ? 'assertive' : 'polite');
        });

        observer.observe(target, {
            subtree: true,
            childList: true,
            characterData: true
        });
        this.observers.push(observer);
    }

    private bindMapKeyboardNavigation(): void {
        const mapViewElement = document.getElementById('viewDiv');
        if (!mapViewElement || mapViewElement.dataset.a11yMapKeyboardBound === 'true') {
            return;
        }

        mapViewElement.dataset.a11yMapKeyboardBound = 'true';
        mapViewElement.addEventListener('keydown', (event: KeyboardEvent) => {
            const mapView = this.options.getMapView?.();
            if (!mapView) {
                return;
            }

            const centerRaw = mapView.getCenter?.();
            const center = this.normalizeCenter(centerRaw);
            const zoom = mapView.getZoom?.();
            if (!center) {
                return;
            }

            const delta = event.shiftKey ? 0.03 : 0.01;
            let hasChanged = false;
            if (event.key === 'ArrowUp') {
                center[1] += delta;
                hasChanged = true;
            } else if (event.key === 'ArrowDown') {
                center[1] -= delta;
                hasChanged = true;
            } else if (event.key === 'ArrowLeft') {
                center[0] -= delta;
                hasChanged = true;
            } else if (event.key === 'ArrowRight') {
                center[0] += delta;
                hasChanged = true;
            } else if ((event.key === '+' || event.key === '=') && typeof zoom === 'number') {
                mapView.setZoom?.(zoom + 1);
                hasChanged = true;
            } else if ((event.key === '-' || event.key === '_') && typeof zoom === 'number') {
                mapView.setZoom?.(zoom - 1);
                hasChanged = true;
            }

            if (hasChanged) {
                event.preventDefault();
                mapView.setCenter?.(center);
            }
        });
    }

    private normalizeCenter(center: [number, number] | MapCenter | undefined): [number, number] | null {
        if (Array.isArray(center) && center.length === 2) {
            return [center[0], center[1]];
        }
        if (center && typeof center === 'object') {
            const lng = Number((center as MapCenter).lng);
            const lat = Number((center as MapCenter).lat);
            if (!Number.isNaN(lng) && !Number.isNaN(lat)) {
                return [lng, lat];
            }
        }
        return null;
    }

    private bindGlobalKeyboardNavigation(): void {
        document.addEventListener('keydown', (event: KeyboardEvent) => {
            if (!(event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey)) {
                return;
            }

            if (event.key === '1') {
                event.preventDefault();
                const main = document.getElementById('main-content');
                if (main instanceof HTMLElement) {
                    main.focus();
                    this.announce('已跳转到主内容区域');
                }
            } else if (event.key === '2') {
                event.preventDefault();
                const map = document.getElementById('viewDiv');
                if (map instanceof HTMLElement) {
                    map.focus();
                    this.announce('已跳转到地图区域');
                }
            } else if (event.key === '3') {
                event.preventDefault();
                const sidebarToggle = document.getElementById('sidebar-toggle');
                if (sidebarToggle instanceof HTMLElement) {
                    sidebarToggle.focus();
                    this.announce('已跳转到右侧面板切换按钮');
                }
            }
        });
    }

    private bindAdaptiveInterface(): void {
        const applyAdaptiveClass = () => {
            const isMobileWidth = window.innerWidth <= 767;
            const isCoarsePointer = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
            document.documentElement.classList.toggle('a11y-adaptive-mobile', isMobileWidth || isCoarsePointer);
        };

        applyAdaptiveClass();
        this.resizeHandlerBound = applyAdaptiveClass;
        window.addEventListener('resize', applyAdaptiveClass);
    }

    private bindGestureSupport(): void {
        const mapContainer = document.querySelector('.map-container');
        if (!mapContainer || (mapContainer as HTMLElement).dataset.a11yGestureBound === 'true') {
            return;
        }

        (mapContainer as HTMLElement).dataset.a11yGestureBound = 'true';
        let startX = 0;
        let startY = 0;

        mapContainer.addEventListener('touchstart', (event: Event) => {
            const touchEvent = event as TouchEvent;
            if (!touchEvent.changedTouches || touchEvent.changedTouches.length === 0) {
                return;
            }
            const touch = touchEvent.changedTouches[0];
            startX = touch.clientX;
            startY = touch.clientY;
        }, { passive: true });

        mapContainer.addEventListener('touchend', (event: Event) => {
            const touchEvent = event as TouchEvent;
            if (!touchEvent.changedTouches || touchEvent.changedTouches.length === 0) {
                return;
            }
            const touch = touchEvent.changedTouches[0];
            const deltaX = touch.clientX - startX;
            const deltaY = touch.clientY - startY;
            if (Math.abs(deltaX) < 80 || Math.abs(deltaY) > 48) {
                return;
            }

            const sidebar = document.querySelector('.sidebar');
            if (!(sidebar instanceof HTMLElement)) {
                return;
            }
            const overlay = document.getElementById('sidebar-overlay');

            if (deltaX > 0) {
                sidebar.classList.add('active');
                sidebar.classList.add('mobile-open');
                overlay?.classList.add('visible');
                overlay?.setAttribute('aria-hidden', 'false');
                this.announce('手势已打开侧边栏');
            } else {
                sidebar.classList.remove('active');
                sidebar.classList.remove('mobile-open');
                overlay?.classList.remove('visible');
                overlay?.setAttribute('aria-hidden', 'true');
                this.announce('手势已关闭侧边栏');
            }
        }, { passive: true });
    }

    private enhanceFormAccessibility(): void {
        const controls = document.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea');
        controls.forEach((control) => {
            if (!control.getAttribute('aria-label')) {
                const labelText = this.findLabelText(control);
                if (labelText) {
                    control.setAttribute('aria-label', labelText);
                }
            }

            if (control.classList.contains('error')) {
                control.setAttribute('aria-invalid', 'true');
            } else if (control.hasAttribute('aria-invalid')) {
                control.setAttribute('aria-invalid', 'false');
            }
        });
    }

    private findLabelText(control: HTMLElement): string {
        const id = control.getAttribute('id');
        if (id) {
            const directLabel = document.querySelector(`label[for="${id}"]`);
            if (directLabel?.textContent) {
                return directLabel.textContent.trim();
            }
        }

        const formGroup = control.closest('.form-group');
        const nearbyLabel = formGroup?.querySelector('label');
        if (nearbyLabel?.textContent) {
            return nearbyLabel.textContent.trim();
        }

        const placeholder = control.getAttribute('placeholder');
        return placeholder?.trim() || '输入控件';
    }

    private enhanceChartAccessibility(): void {
        const chartNodes = document.querySelectorAll<HTMLElement>(
            '.chart-container canvas, .chart-container svg, .echarts-for-react canvas, .echarts canvas'
        );

        chartNodes.forEach((node, index) => {
            if (!node.getAttribute('role')) {
                node.setAttribute('role', 'img');
            }
            if (!node.getAttribute('aria-label')) {
                const titleNode = node.closest('.panel')?.querySelector('.panel-title, h2, h3');
                const titleText = titleNode?.textContent?.trim() || `图表 ${index + 1}`;
                node.setAttribute('aria-label', `${titleText}，可通过表单参数调整`);
            }
        });
    }

    private createToolbar(): void {
        if (this.toolbarPanel && this.toolbarTrigger) {
            return;
        }

        const headerRight = document.querySelector('.header-right');
        if (!(headerRight instanceof HTMLElement)) {
            return;
        }

        const trigger = document.createElement('button');
        trigger.id = 'a11y-toolbar-trigger';
        trigger.className = 'btn a11y-toolbar-trigger';
        trigger.type = 'button';
        trigger.textContent = '无障碍';
        trigger.setAttribute('aria-label', '打开无障碍设置');
        trigger.setAttribute('aria-expanded', 'false');
        trigger.setAttribute('aria-controls', 'a11y-toolbar');
        headerRight.appendChild(trigger);

        const panel = document.createElement('div');
        panel.id = 'a11y-toolbar';
        panel.className = 'a11y-toolbar';
        panel.hidden = true;
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'false');
        panel.setAttribute('aria-label', '无障碍设置面板');
        panel.innerHTML = `
            <h3 class="a11y-toolbar-title">无障碍设置</h3>
            <div class="a11y-toolbar-group">
                <div class="a11y-toolbar-item">
                    <label for="a11y-high-contrast">高对比度模式</label>
                    <input id="a11y-high-contrast" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-dark-optimize">暗色模式优化</label>
                    <input id="a11y-dark-optimize" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-reduce-motion">减少动画</label>
                    <input id="a11y-reduce-motion" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-font-scale">字体缩放</label>
                    <input id="a11y-font-scale" type="range" min="0.9" max="1.4" step="0.1">
                </div>
                <div class="a11y-toolbar-hint" id="a11y-font-scale-value">100%</div>
            </div>
            <div class="a11y-toolbar-group">
                <label for="a11y-color-blind">色盲模式</label>
                <select id="a11y-color-blind" class="a11y-toolbar-select">
                    <option value="none">关闭</option>
                    <option value="protanopia">红色弱化</option>
                    <option value="deuteranopia">绿色弱化</option>
                    <option value="tritanopia">蓝色弱化</option>
                    <option value="grayscale">灰度模式</option>
                </select>
            </div>
            <div class="a11y-toolbar-group">
                <div class="a11y-toolbar-item">
                    <label for="a11y-voice-control">语音控制（Web Speech API）</label>
                    <input id="a11y-voice-control" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-smart-assist">智能辅助提示</label>
                    <input id="a11y-smart-assist" type="checkbox">
                </div>
                <button class="a11y-toolbar-button" id="a11y-shortcuts-help" type="button">查看键盘快捷键</button>
            </div>
            <p class="a11y-toolbar-hint">语音命令示例：新建项目、上传数据、开始插值、打开设置、切换主题。</p>
            <p class="a11y-toolbar-hint">快捷跳转：Alt+1 主内容，Alt+2 地图，Alt+3 侧边栏。</p>
        `;
        document.body.appendChild(panel);

        trigger.addEventListener('click', () => {
            const willOpen = panel.hidden;
            panel.hidden = !willOpen;
            trigger.setAttribute('aria-expanded', String(willOpen));
            if (willOpen) {
                this.installToolbarFocusTrap();
                const firstControl = panel.querySelector('input, select, button') as HTMLElement | null;
                firstControl?.focus();
            } else {
                this.releaseToolbarFocusTrap();
            }
        });

        const bindToggle = (id: string, handler: (checked: boolean) => void) => {
            const input = panel.querySelector<HTMLInputElement>(`#${id}`);
            if (!input) {
                return;
            }
            input.addEventListener('change', () => {
                handler(input.checked);
                this.savePreferences();
                this.applyPreferences();
            });
        };

        bindToggle('a11y-high-contrast', (checked) => {
            this.preferences.highContrast = checked;
        });
        bindToggle('a11y-dark-optimize', (checked) => {
            this.preferences.darkModeOptimization = checked;
        });
        bindToggle('a11y-reduce-motion', (checked) => {
            this.preferences.reduceMotion = checked;
        });
        bindToggle('a11y-voice-control', (checked) => {
            this.preferences.voiceControlEnabled = checked;
        });
        bindToggle('a11y-smart-assist', (checked) => {
            this.preferences.smartAssistEnabled = checked;
        });

        const fontScaleInput = panel.querySelector<HTMLInputElement>('#a11y-font-scale');
        const fontScaleValue = panel.querySelector<HTMLElement>('#a11y-font-scale-value');
        fontScaleInput?.addEventListener('input', () => {
            this.preferences.fontScale = Number(fontScaleInput.value);
            if (fontScaleValue) {
                fontScaleValue.textContent = `${Math.round(this.preferences.fontScale * 100)}%`;
            }
            this.savePreferences();
            this.applyPreferences();
        });

        const colorBlindSelect = panel.querySelector<HTMLSelectElement>('#a11y-color-blind');
        colorBlindSelect?.addEventListener('change', () => {
            this.preferences.colorBlindMode = colorBlindSelect.value as ColorBlindMode;
            this.savePreferences();
            this.applyPreferences();
        });

        const shortcutButton = panel.querySelector<HTMLButtonElement>('#a11y-shortcuts-help');
        shortcutButton?.addEventListener('click', () => {
            if (this.options.onShowShortcutHelp) {
                this.options.onShowShortcutHelp();
            } else {
                document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', ctrlKey: true, bubbles: true }));
            }
        });

        panel.addEventListener('click', (event) => {
            if (event.target === panel) {
                panel.hidden = true;
                trigger.setAttribute('aria-expanded', 'false');
                this.releaseToolbarFocusTrap();
                trigger.focus();
            }
        });

        this.toolbarPanel = panel;
        this.toolbarTrigger = trigger;
        this.syncToolbarFromPreferences();
    }

    private installToolbarFocusTrap(): void {
        if (!this.toolbarPanel || this.toolbarFocusHandler) {
            return;
        }

        this.toolbarFocusHandler = (event: KeyboardEvent) => {
            if (!this.toolbarPanel || this.toolbarPanel.hidden) {
                return;
            }

            if (event.key === 'Escape') {
                event.preventDefault();
                this.toolbarPanel.hidden = true;
                this.toolbarTrigger?.setAttribute('aria-expanded', 'false');
                this.releaseToolbarFocusTrap();
                this.toolbarTrigger?.focus();
                return;
            }

            if (event.key !== 'Tab') {
                return;
            }

            const focusable = this.toolbarPanel.querySelectorAll<HTMLElement>(
                'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            if (focusable.length === 0) {
                return;
            }

            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        };

        document.addEventListener('keydown', this.toolbarFocusHandler);
    }

    private releaseToolbarFocusTrap(): void {
        if (this.toolbarFocusHandler) {
            document.removeEventListener('keydown', this.toolbarFocusHandler);
            this.toolbarFocusHandler = null;
        }
    }

    private syncToolbarFromPreferences(): void {
        if (!this.toolbarPanel) {
            return;
        }

        const setChecked = (id: string, checked: boolean) => {
            const input = this.toolbarPanel?.querySelector<HTMLInputElement>(`#${id}`);
            if (input) {
                input.checked = checked;
            }
        };

        setChecked('a11y-high-contrast', this.preferences.highContrast);
        setChecked('a11y-dark-optimize', this.preferences.darkModeOptimization);
        setChecked('a11y-reduce-motion', this.preferences.reduceMotion);
        setChecked('a11y-voice-control', this.preferences.voiceControlEnabled);
        setChecked('a11y-smart-assist', this.preferences.smartAssistEnabled);

        const fontScaleInput = this.toolbarPanel.querySelector<HTMLInputElement>('#a11y-font-scale');
        const fontScaleValue = this.toolbarPanel.querySelector<HTMLElement>('#a11y-font-scale-value');
        if (fontScaleInput) {
            fontScaleInput.value = String(this.preferences.fontScale);
        }
        if (fontScaleValue) {
            fontScaleValue.textContent = `${Math.round(this.preferences.fontScale * 100)}%`;
        }

        const colorBlindSelect = this.toolbarPanel.querySelector<HTMLSelectElement>('#a11y-color-blind');
        if (colorBlindSelect) {
            colorBlindSelect.value = this.preferences.colorBlindMode;
        }
    }

    private applyPreferences(): void {
        const root = document.documentElement;

        root.classList.toggle('a11y-high-contrast', this.preferences.highContrast);
        root.classList.toggle('a11y-reduced-motion', this.preferences.reduceMotion);
        root.classList.toggle('a11y-dark-optimize', this.preferences.darkModeOptimization);
        root.style.setProperty('--a11y-font-scale', String(this.preferences.fontScale));
        this.applyScaledFontVariables(this.preferences.fontScale);

        root.classList.remove(
            'a11y-color-blind-protanopia',
            'a11y-color-blind-deuteranopia',
            'a11y-color-blind-tritanopia',
            'a11y-color-blind-grayscale'
        );
        if (this.preferences.colorBlindMode !== 'none') {
            root.classList.add(`a11y-color-blind-${this.preferences.colorBlindMode}`);
        }

        if (this.preferences.voiceControlEnabled) {
            this.startVoiceRecognition();
        } else {
            this.stopVoiceRecognition();
        }

        this.syncToolbarFromPreferences();
        this.toggleSmartAssist(this.preferences.smartAssistEnabled);
    }

    private applyScaledFontVariables(scale: number): void {
        const root = document.documentElement;
        root.style.setProperty('--font-size-sm', `${Math.round(12 * scale)}px`);
        root.style.setProperty('--font-size-md', `${Math.round(14 * scale)}px`);
        root.style.setProperty('--font-size-lg', `${Math.round(16 * scale)}px`);
        root.style.setProperty('--font-size-xl', `${Math.round(20 * scale)}px`);
    }

    private startVoiceRecognition(): void {
        const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (!SpeechRecognitionCtor) {
            this.preferences.voiceControlEnabled = false;
            this.savePreferences();
            this.syncToolbarFromPreferences();
            this.announce('当前浏览器不支持语音识别', 'assertive');
            return;
        }

        if (!this.speechRecognition) {
            this.speechRecognition = new SpeechRecognitionCtor();
            this.speechRecognition.continuous = true;
            this.speechRecognition.interimResults = false;
            this.speechRecognition.lang = document.documentElement.lang || 'zh-CN';

            this.speechRecognition.onresult = (event: any) => {
                const result = event.results?.[event.results.length - 1]?.[0]?.transcript;
                const transcript = String(result || '').trim();
                if (!transcript) {
                    return;
                }
                this.handleVoiceCommand(transcript);
            };

            this.speechRecognition.onend = () => {
                this.isVoiceRunning = false;
                if (this.preferences.voiceControlEnabled) {
                    window.setTimeout(() => this.startVoiceRecognition(), 400);
                }
            };

            this.speechRecognition.onerror = () => {
                this.isVoiceRunning = false;
            };
        }

        if (!this.isVoiceRunning) {
            try {
                this.speechRecognition.start();
                this.isVoiceRunning = true;
                this.announce('语音控制已开启');
            } catch {
                this.isVoiceRunning = false;
            }
        }
    }

    private stopVoiceRecognition(): void {
        if (this.speechRecognition && this.isVoiceRunning) {
            try {
                this.speechRecognition.stop();
            } catch {
                // 忽略浏览器 stop 时序异常
            }
        }
        this.isVoiceRunning = false;
    }

    private handleVoiceCommand(transcript: string): void {
        const normalized = transcript.replace(/\s+/g, '').toLowerCase();
        const executeClick = (id: string): boolean => {
            const target = document.getElementById(id) as HTMLButtonElement | null;
            if (!target || target.disabled) {
                return false;
            }
            target.click();
            return true;
        };

        if (normalized.includes('新建项目')) {
            executeClick('new-project-btn');
            this.announce('已执行新建项目');
            return;
        }

        if (normalized.includes('上传数据') || normalized.includes('上传文件')) {
            executeClick('upload-btn');
            this.announce('已执行上传数据');
            return;
        }

        if (normalized.includes('开始插值') || normalized.includes('开始计算')) {
            const ok = executeClick('start-kriging-btn');
            this.announce(ok ? '已开始插值' : '当前条件不足，无法开始插值', ok ? 'polite' : 'assertive');
            return;
        }

        if (normalized.includes('打开设置') || normalized === '设置') {
            executeClick('settings-btn');
            this.announce('已打开设置');
            return;
        }

        if (normalized.includes('切换主题')) {
            executeClick('theme-toggle-btn');
            this.announce('已切换主题');
            return;
        }

        if (normalized.includes('快捷键')) {
            if (this.options.onShowShortcutHelp) {
                this.options.onShowShortcutHelp();
            } else {
                document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', ctrlKey: true, bubbles: true }));
            }
            this.announce('已打开快捷键面板');
            return;
        }

        if (normalized.includes('高对比')) {
            this.preferences.highContrast = !normalized.includes('关闭');
            this.savePreferences();
            this.applyPreferences();
            this.announce(this.preferences.highContrast ? '高对比度模式已开启' : '高对比度模式已关闭');
            return;
        }

        if (normalized.includes('放大字体')) {
            this.preferences.fontScale = Math.min(1.4, this.preferences.fontScale + 0.1);
            this.savePreferences();
            this.applyPreferences();
            this.announce(`字体已调整为 ${Math.round(this.preferences.fontScale * 100)}%`);
            return;
        }

        if (normalized.includes('缩小字体')) {
            this.preferences.fontScale = Math.max(0.9, this.preferences.fontScale - 0.1);
            this.savePreferences();
            this.applyPreferences();
            this.announce(`字体已调整为 ${Math.round(this.preferences.fontScale * 100)}%`);
            return;
        }

        if (normalized.includes('关闭语音') || normalized.includes('停止语音')) {
            this.preferences.voiceControlEnabled = false;
            this.savePreferences();
            this.applyPreferences();
            this.announce('语音控制已关闭');
            return;
        }

        this.announce(`未识别语音命令：${transcript}`);
    }

    private toggleSmartAssist(enabled: boolean): void {
        if (!enabled) {
            if (this.smartAssistTimer !== null) {
                window.clearInterval(this.smartAssistTimer);
                this.smartAssistTimer = null;
            }
            return;
        }

        if (this.smartAssistTimer !== null) {
            return;
        }

        const runHint = () => {
            const startButton = document.getElementById('start-kriging-btn') as HTMLButtonElement | null;
            const uploadStatus = document.getElementById('upload-status');
            const projectPanel = document.getElementById('project-panel');

            if (startButton?.disabled) {
                this.announce('提示：可先上传数据或添加至少 3 个采样点后开始插值。');
                return;
            }

            if (uploadStatus?.classList.contains('error')) {
                this.announce('提示：上传出现错误，可检查文件格式是否为 GeoJSON。', 'assertive');
                return;
            }

            if (projectPanel?.style.display === 'none') {
                this.announce('提示：可按 Ctrl + N 快速新建项目。');
            }
        };

        runHint();
        this.smartAssistTimer = window.setInterval(runHint, 45000);
    }

    private bindCustomAnnouncementEvent(): void {
        document.addEventListener('udake-a11y-announce', (event: Event) => {
            const detail = (event as CustomEvent<{ message?: string; priority?: 'polite' | 'assertive' }>).detail;
            if (!detail?.message) {
                return;
            }
            this.announce(detail.message, detail.priority || 'polite');
        });
    }

    private loadPreferences(): AccessibilityPreferences {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return { ...DEFAULT_PREFERENCES };
            }
            return {
                ...DEFAULT_PREFERENCES,
                ...JSON.parse(raw)
            };
        } catch {
            return { ...DEFAULT_PREFERENCES };
        }
    }

    private savePreferences(): void {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.preferences));
    }
}
