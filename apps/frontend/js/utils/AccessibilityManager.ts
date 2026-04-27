/**
 * 无障碍管理器
 * 统一管理键盘、屏幕阅读器、视觉辅助、语音与手势增强
 */
import { I18n } from './I18n';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

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
        this.announce(t('accessibility.welcome'));
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
        sidebar?.setAttribute('aria-label', t('accessibility.panel.main'));

        const rightSidebar = document.getElementById('right-sidebar');
        rightSidebar?.setAttribute('aria-label', t('accessibility.panel.recommend'));

        const mapContainer = document.querySelector('.map-container');
        mapContainer?.setAttribute('role', 'region');
        mapContainer?.setAttribute('aria-label', t('accessibility.panel.mapShow'));

        const mapView = document.getElementById('viewDiv');
        if (mapView) {
            mapView.setAttribute('tabindex', '0');
            mapView.setAttribute('role', 'application');
            mapView.setAttribute('aria-label', t('accessibility.panel.mapSpatial'));
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
                toggle.innerHTML = `${labelHtml || t('accessibility.panel.name')} ${isOpen ? '▸' : '▾'}`;
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
            const isError = target.classList.contains('error') || text.includes(t('common.failed')) || text.includes(t('common.error'));
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
                    this.announce(t('accessibility.jump.main.success'));
                }
            } else if (event.key === '2') {
                event.preventDefault();
                const map = document.getElementById('viewDiv');
                if (map instanceof HTMLElement) {
                    map.focus();
                    this.announce(t('accessibility.jump.map.success'));
                }
            } else if (event.key === '3') {
                event.preventDefault();
                const sidebarToggle = document.getElementById('sidebar-toggle');
                if (sidebarToggle instanceof HTMLElement) {
                    sidebarToggle.focus();
                    this.announce(t('accessibility.jump.right-panel.switch-btn.success'));
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
                this.announce(t('accessibility.mobile-open.sidebar.success'));
            } else {
                sidebar.classList.remove('active');
                sidebar.classList.remove('mobile-open');
                overlay?.classList.remove('visible');
                overlay?.setAttribute('aria-hidden', 'true');
                this.announce(t('accessibility.mobile-close.sidebar.success'));
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
        return placeholder?.trim() || t('accessibility.inputControl');
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
                const titleText = titleNode?.textContent?.trim() || t('accessibility.titleText', { index: index + 1 });
                node.setAttribute('aria-label', t('accessibility.setAttribute', { titleText: titleText}));
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
        trigger.textContent = t('accessibility.name');
        trigger.setAttribute('aria-label', t('accessibility.open-settings'));
        trigger.setAttribute('aria-expanded', 'false');
        trigger.setAttribute('aria-controls', 'a11y-toolbar');
        headerRight.appendChild(trigger);

        const panel = document.createElement('div');
        panel.id = 'a11y-toolbar';
        panel.className = 'a11y-toolbar';
        panel.hidden = true;
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'false');
        panel.setAttribute('aria-label', t('accessibility.settings-panel.title'));
        panel.innerHTML = `
            <h3 class="a11y-toolbar-title">${t('accessibility.settings')}</h3>
            <div class="a11y-toolbar-group">
                <div class="a11y-toolbar-item">
                    <label for="a11y-high-contrast">${t('accessibility.high-constract')}</label>
                    <input id="a11y-high-contrast" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-dark-optimize">${t('accessibility.dark-optimize')}</label>
                    <input id="a11y-dark-optimize" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-reduce-motion">${t('accessibility.reduce-motion')}</label>
                    <input id="a11y-reduce-motion" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-font-scale">${t('accessibility.font-scale')}</label>
                    <input id="a11y-font-scale" type="range" min="0.9" max="1.4" step="0.1">
                </div>
                <div class="a11y-toolbar-hint" id="a11y-font-scale-value">100%</div>
            </div>
            <div class="a11y-toolbar-group">
                <label for="a11y-color-blind">${t('accessibility.color-blind')}</label>
                <select id="a11y-color-blind" class="a11y-toolbar-select">
                    <option value="none">${t('accessibility.color-blind.none')}</option>
                    <option value="protanopia">${t('accessibility.color-blind.protanopia')}</option>
                    <option value="deuteranopia">${t('accessibility.color-blind.deuteranopia')}</option>
                    <option value="tritanopia">${t('accessibility.color-blind.tritanopia')}</option>
                    <option value="grayscale">${t('accessibility.color-blind.grayscale')}</option>
                </select>
            </div>
            <div class="a11y-toolbar-group">
                <div class="a11y-toolbar-item">
                    <label for="a11y-voice-control">${t('accessibility.voice-control')}</label>
                    <input id="a11y-voice-control" type="checkbox">
                </div>
                <div class="a11y-toolbar-item">
                    <label for="a11y-smart-assist">${t('accessibility.smart-assist')}</label>
                    <input id="a11y-smart-assist" type="checkbox">
                </div>
                <button class="a11y-toolbar-button" id="a11y-shortcuts-help" type="button">${t('accessibility.shortcuts-help')}</button>
            </div>
            <p class="a11y-toolbar-hint">${t('accessibility.voice-control.template')}</p>
            <p class="a11y-toolbar-hint">${t('accessibility.shortcuts-jump.template')}</p>
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
            this.announce(t('accessibility.voice-control.invalid'), 'assertive');
            return;
        }

        if (!this.speechRecognition) {
            this.speechRecognition = new SpeechRecognitionCtor();
            this.speechRecognition.continuous = true;
            this.speechRecognition.interimResults = false;
            this.speechRecognition.lang = document.documentElement.lang || 'zh-CN' || 'en-US' || 'ja-JP' || 'ko-KR' || 'zh-TW';
            this.speechRecognition.maxAlternatives = 1

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
                this.announce(t('accessibility.voice-control.start'));
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

        if (normalized.includes(t('accessibility.newProject.title'))) {
            executeClick('new-project-btn');
            this.announce(t('accessibility.newProject.success'));
            return;
        }

        if (normalized.includes(t('accessibility.submit.data.title')) || normalized.includes(t('accessibility.submit.file.title'))) {
            executeClick('upload-btn');
            this.announce(t('accessibility.submit.data.success'));
            return;
        }

        if (normalized.includes(t('accessibility.interpolation.start.title')) || normalized.includes(t('accessibility.calculate.start.title'))) {
            const ok = executeClick('start-kriging-btn');
            this.announce(ok ? t('accessibility.interpolation.start.success') : t('accessibility.interpolation.start.failed'), ok ? 'polite' : 'assertive');
            return;
        }

        if (normalized.includes(t('accessibility.settings.open.title')) || normalized === t('accessibility.settings.title')) {
            executeClick('settings-btn');
            this.announce(t('accessibility.settings.open.success'));
            return;
        }

        if (normalized.includes(t('accessibility.theme-toggle.title'))) {
            executeClick('theme-toggle-btn');
            this.announce(t('accessibility.theme-toggle.success'));
            return;
        }

        if (normalized.includes(t('accessibility.shortcuts.panel.title'))) {
            if (this.options.onShowShortcutHelp) {
                this.options.onShowShortcutHelp();
            } else {
                document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', ctrlKey: true, bubbles: true }));
            }
            this.announce(t('accessibility.shortcuts.panel.open.success'));
            return;
        }

        if (normalized.includes(t('accessibility.high-constract.title'))) {
            this.preferences.highContrast = !normalized.includes(t('common.close'));
            this.savePreferences();
            this.applyPreferences();
            this.announce(this.preferences.highContrast ? t('accessibility.high-constract.open') : t('accessibility.high-constract.close'));
            return;
        }

        if (normalized.includes(t('accessibility.fontScale.larger.title'))) {
            this.preferences.fontScale = Math.min(1.4, this.preferences.fontScale + 0.1);
            this.savePreferences();
            this.applyPreferences();
            this.announce(t('accessibility.fontScale.change.success', { fontScale: Math.round(this.preferences.fontScale * 100) }));
            return;
        }

        if (normalized.includes(t('accessibility.fontScale.smaller.title'))) {
            this.preferences.fontScale = Math.max(0.9, this.preferences.fontScale - 0.1);
            this.savePreferences();
            this.applyPreferences();
            this.announce(t('accessibility.fontScale.change.success', { fontScale: Math.round(this.preferences.fontScale * 100) }));
            return;
        }

        if (normalized.includes(t('accessibility.voice-control.close.title')) || normalized.includes(t('accessibility.voice-control.stop.title'))) {
            this.preferences.voiceControlEnabled = false;
            this.savePreferences();
            this.applyPreferences();
            this.announce(t('accessibility.voice-control.close.success'));
            return;
        }

        this.announce(t('accessibility.voice-control.invalid-command', { transcript: transcript }));
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
                this.announce(t('accessibility.prompt.upload-data'));
                return;
            }

            if (uploadStatus?.classList.contains('error')) {
                this.announce(t('accessibility.prompt.upload-failed'), 'assertive');
                return;
            }

            if (projectPanel?.style.display === 'none') {
                this.announce(t('accessibility.prompt.newProject'));
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
