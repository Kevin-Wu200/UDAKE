/**
 * 用户偏好设置面板
 * 主题、语言、通知、显示、数据导出等设置
 */

interface UserPreferences {
    theme: 'light' | 'dark' | 'auto';
    language: string;
    notifications: boolean;
    mapEngine: 'geoscene';
    gridResolution: number;
    exportFormat: 'geojson' | 'shp' | 'tif';
    autoSave: boolean;
    showCoordinates: boolean;
    animationsEnabled: boolean;
}

const DEFAULT_PREFS: UserPreferences = {
    theme: 'auto',
    language: 'zh-CN',
    notifications: true,
    mapEngine: 'geoscene',
    gridResolution: 100,
    exportFormat: 'geojson',
    autoSave: true,
    showCoordinates: true,
    animationsEnabled: true,
};

const STORAGE_KEY = 'udake_preferences';

export class PreferencesPanel {
    private prefs: UserPreferences;
    private overlay: HTMLElement | null = null;
    private onChange: ((prefs: UserPreferences) => void) | null;

    constructor(onChange?: (prefs: UserPreferences) => void) {
        this.onChange = onChange ?? null;
        this.prefs = this._load();
    }

    get preferences(): UserPreferences {
        return { ...this.prefs };
    }

    show(): void {
        if (this.overlay) return;
        this.overlay = this._createOverlay();
        document.body.appendChild(this.overlay);
        requestAnimationFrame(() => this.overlay?.classList.add('modal-show'));
    }

    hide(): void {
        if (!this.overlay) return;
        this.overlay.classList.remove('modal-show');
        setTimeout(() => {
            this.overlay?.remove();
            this.overlay = null;
        }, 300);
    }

    private _load(): UserPreferences {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            return saved ? { ...DEFAULT_PREFS, ...JSON.parse(saved) } : { ...DEFAULT_PREFS };
        } catch {
            return { ...DEFAULT_PREFS };
        }
    }

    private _save(): void {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.prefs));
        this.onChange?.(this.prefs);
    }

    private _createOverlay(): HTMLElement {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-label', '偏好设置');

        overlay.innerHTML = `
            <div class="modal preferences-modal">
                <div class="modal-header">
                    <h2 class="modal-title">偏好设置</h2>
                    <button class="modal-close" aria-label="关闭">&times;</button>
                </div>
                <div class="modal-body preferences-body">
                    <div class="pref-section">
                        <h3 class="pref-section-title">外观</h3>
                        <div class="pref-item">
                            <label for="pref-theme">主题模式</label>
                            <select id="pref-theme" class="select">
                                <option value="auto">跟随系统</option>
                                <option value="light">浅色</option>
                                <option value="dark">深色</option>
                            </select>
                        </div>
                        <div class="pref-item">
                            <label for="pref-animations">启用动画</label>
                            <input type="checkbox" id="pref-animations" class="toggle">
                        </div>
                    </div>
                    <div class="pref-section">
                        <h3 class="pref-section-title">地图</h3>
                        <div class="pref-item">
                            <label for="pref-show-coords">显示坐标信息</label>
                            <input type="checkbox" id="pref-show-coords" class="toggle">
                        </div>
                    </div>
                    <div class="pref-section">
                        <h3 class="pref-section-title">数据</h3>
                        <div class="pref-item">
                            <label for="pref-grid-res">默认网格分辨率</label>
                            <input type="number" id="pref-grid-res" class="input" min="1" max="10000">
                        </div>
                        <div class="pref-item">
                            <label for="pref-export-fmt">默认导出格式</label>
                            <select id="pref-export-fmt" class="select">
                                <option value="geojson">GeoJSON</option>
                                <option value="shp">Shapefile</option>
                                <option value="tif">GeoTIFF</option>
                            </select>
                        </div>
                        <div class="pref-item">
                            <label for="pref-autosave">自动保存</label>
                            <input type="checkbox" id="pref-autosave" class="toggle">
                        </div>
                    </div>
                    <div class="pref-section">
                        <h3 class="pref-section-title">通知</h3>
                        <div class="pref-item">
                            <label for="pref-notifications">启用通知</label>
                            <input type="checkbox" id="pref-notifications" class="toggle">
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn" id="pref-reset">恢复默认</button>
                    <button class="btn btn-primary" id="pref-save">保存</button>
                </div>
            </div>
        `;

        // 填充当前值
        this._populateValues(overlay);

        // 绑定事件
        overlay.querySelector('.modal-close')!.addEventListener('click', () => this.hide());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.hide();
        });
        overlay.querySelector('#pref-reset')!.addEventListener('click', () => {
            this.prefs = { ...DEFAULT_PREFS };
            this._populateValues(overlay);
        });
        overlay.querySelector('#pref-save')!.addEventListener('click', () => {
            this._collectValues(overlay);
            this._save();
            this.hide();
        });

        return overlay;
    }

    private _populateValues(root: HTMLElement): void {
        (root.querySelector('#pref-theme') as HTMLSelectElement).value = this.prefs.theme;
        (root.querySelector('#pref-animations') as HTMLInputElement).checked = this.prefs.animationsEnabled;
        (root.querySelector('#pref-show-coords') as HTMLInputElement).checked = this.prefs.showCoordinates;
        (root.querySelector('#pref-grid-res') as HTMLInputElement).value = String(this.prefs.gridResolution);
        (root.querySelector('#pref-export-fmt') as HTMLSelectElement).value = this.prefs.exportFormat;
        (root.querySelector('#pref-autosave') as HTMLInputElement).checked = this.prefs.autoSave;
        (root.querySelector('#pref-notifications') as HTMLInputElement).checked = this.prefs.notifications;
    }

    private _collectValues(root: HTMLElement): void {
        this.prefs.theme = (root.querySelector('#pref-theme') as HTMLSelectElement).value as any;
        this.prefs.animationsEnabled = (root.querySelector('#pref-animations') as HTMLInputElement).checked;
        this.prefs.showCoordinates = (root.querySelector('#pref-show-coords') as HTMLInputElement).checked;
        this.prefs.gridResolution = parseInt((root.querySelector('#pref-grid-res') as HTMLInputElement).value, 10) || 100;
        this.prefs.exportFormat = (root.querySelector('#pref-export-fmt') as HTMLSelectElement).value as any;
        this.prefs.autoSave = (root.querySelector('#pref-autosave') as HTMLInputElement).checked;
        this.prefs.notifications = (root.querySelector('#pref-notifications') as HTMLInputElement).checked;
    }

    /** 静态方法：获取当前偏好 */
    static getCurrent(): UserPreferences {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            return saved ? { ...DEFAULT_PREFS, ...JSON.parse(saved) } : { ...DEFAULT_PREFS };
        } catch {
            return { ...DEFAULT_PREFS };
        }
    }
}
