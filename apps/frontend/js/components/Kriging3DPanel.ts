import { I18nDialog } from './I18nDialog.js';
/**
 * 3D克里金插值组件
 * 提供3D数据上传、参数配置、插值执行、结果可视化
 */

export interface Kriging3DConfig {
    method: 'ordinary' | 'universal' | 'indicator';
    variogramModel: 'spherical' | 'exponential' | 'gaussian' | 'linear';
    gridResolutionX: number;
    gridResolutionY: number;
    gridResolutionZ: number;
    nlags: number;
    nClosest: number;
    enableAnisotropy: boolean;
    enableCrossValidation: boolean;
    indicatorThreshold?: number;
    driftTerms?: string[];
}

export interface Kriging3DTaskStatus {
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    gridShape?: number[];
    predictionStats?: Record<string, number>;
    varianceStats?: Record<string, number>;
    variogram?: Record<string, any>;
    error?: string;
}

export interface SliceData {
    axis: string;
    position: number;
    gridX: number[];
    gridY: number[];
    values: number[][];
    variance?: number[][];
}

const API_BASE = '/api';

export class Kriging3DPanel {
    private container: HTMLElement;
    private dataId: string | null = null;
    private taskId: string | null = null;
    private pollTimer: number | null = null;
    private config: Kriging3DConfig;

    constructor(containerId: string) {
        const el = document.getElementById(containerId);
        if (!el) throw new Error(`容器 ${containerId} 不存在`);
        this.container = el;
        this.config = {
            method: 'ordinary',
            variogramModel: 'spherical',
            gridResolutionX: 50,
            gridResolutionY: 50,
            gridResolutionZ: 20,
            nlags: 12,
            nClosest: 16,
            enableAnisotropy: false,
            enableCrossValidation: true,
        };
        this.render();
        this.bindEvents();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="kriging3d-panel">
                <div class="panel">
                    <h2 class="panel-title">3D数据上传</h2>
                    <div class="panel-content">
                        <div class="file-picker" id="file-picker-3d">
                            <span id="file-name-3d">选择3D数据文件 (GeoJSON/CSV/钻孔数据)</span>
                            <input type="file" id="file-input-3d" accept=".geojson,.json,.csv" class="file-input">
                        </div>
                        <button id="upload-btn-3d" class="btn btn-primary">上传3D数据</button>
                        <div id="upload-status-3d" class="status-message"></div>
                        <div id="data-stats-3d" style="display:none;"></div>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">3D插值参数</h2>
                    <div class="panel-content">
                        <div class="form-group">
                            <label>克里金方法</label>
                            <select id="kriging3d-method" class="select">
                                <option value="ordinary">普通克里金</option>
                                <option value="universal">泛克里金</option>
                                <option value="indicator">指示克里金</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>变异函数模型</label>
                            <select id="kriging3d-variogram" class="select">
                                <option value="spherical">球状模型</option>
                                <option value="exponential">指数模型</option>
                                <option value="gaussian">高斯模型</option>
                                <option value="linear">线性模型</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>X分辨率 <span id="res-x-val">${this.config.gridResolutionX}</span></label>
                            <input type="range" id="kriging3d-res-x" class="slider" min="10" max="100" value="${this.config.gridResolutionX}" step="5">
                        </div>
                        <div class="form-group slider-group">
                            <label>Y分辨率 <span id="res-y-val">${this.config.gridResolutionY}</span></label>
                            <input type="range" id="kriging3d-res-y" class="slider" min="10" max="100" value="${this.config.gridResolutionY}" step="5">
                        </div>
                        <div class="form-group slider-group">
                            <label>Z分辨率 <span id="res-z-val">${this.config.gridResolutionZ}</span></label>
                            <input type="range" id="kriging3d-res-z" class="slider" min="5" max="50" value="${this.config.gridResolutionZ}" step="1">
                        </div>
                        <div class="form-group slider-group">
                            <label>滞后数 <span id="nlags3d-val">${this.config.nlags}</span></label>
                            <input type="range" id="kriging3d-nlags" class="slider" min="6" max="24" value="${this.config.nlags}" step="1">
                        </div>
                        <div class="form-group slider-group">
                            <label>搜索邻点数 <span id="nclosest-val">${this.config.nClosest}</span></label>
                            <input type="range" id="kriging3d-nclosest" class="slider" min="8" max="32" value="${this.config.nClosest}" step="1">
                        </div>
                        <div class="form-group" id="indicator-threshold-group" style="display:none;">
                            <label>指示阈值</label>
                            <input type="number" id="kriging3d-threshold" class="input" value="0" step="0.1">
                        </div>
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="kriging3d-anisotropy">
                                <span>启用各向异性</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="kriging3d-cv" checked>
                                <span>启用交叉验证</span>
                            </label>
                        </div>
                        <button id="start-kriging3d-btn" class="btn btn-primary" disabled>开始3D插值</button>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">3D任务状态</h2>
                    <div class="panel-content">
                        <div id="task-status-3d">暂无任务</div>
                        <div id="progress-bar-3d" class="progress-bar" style="display:none;">
                            <div class="progress-fill" id="progress-fill-3d"></div>
                        </div>
                    </div>
                </div>

                <div class="panel" id="result-panel-3d" style="display:none;">
                    <h2 class="panel-title">3D结果查看</h2>
                    <div class="panel-content">
                        <div id="result-stats-3d"></div>
                        <div class="form-group">
                            <label>切片轴</label>
                            <select id="slice-axis" class="select">
                                <option value="z">Z轴（水平切片）</option>
                                <option value="x">X轴（纵向切片）</option>
                                <option value="y">Y轴（横向切片）</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>切片位置 <span id="slice-pos-val">0</span></label>
                            <input type="range" id="slice-position" class="slider" min="0" max="100" value="50" step="1">
                        </div>
                        <button id="get-slice-btn" class="btn btn-secondary">获取切片</button>
                        <div id="slice-container-3d"></div>
                        <div class="export-buttons" style="margin-top:8px;">
                            <button class="btn btn-export" id="export-3d-json">导出JSON</button>
                            <button class="btn btn-export" id="export-3d-npz">导出NPZ</button>
                        </div>
                    </div>
                </div>

                <div class="panel" id="viz-panel-3d" style="display:none;">
                    <h2 class="panel-title">3D可视化</h2>
                    <div class="panel-content">
                        <div id="threejs-container" style="width:100%;height:400px;background:#1a1a2e;border-radius:8px;"></div>
                        <div class="form-group" style="margin-top:8px;">
                            <label>显示模式</label>
                            <select id="viz-mode-3d" class="select">
                                <option value="points">点云</option>
                                <option value="isosurface">等值面</option>
                                <option value="volume">体渲染</option>
                                <option value="slice">切片</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>透明度 <span id="opacity-val">0.8</span></label>
                            <input type="range" id="viz-opacity" class="slider" min="0" max="1" value="0.8" step="0.05">
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    private bindEvents(): void {
        // 文件选择
        const fileInput = this.container.querySelector('#file-input-3d') as HTMLInputElement;
        const filePicker = this.container.querySelector('#file-picker-3d');
        filePicker?.addEventListener('click', () => fileInput?.click());
        fileInput?.addEventListener('change', () => {
            const name = fileInput.files?.[0]?.name || '选择3D数据文件';
            const span = this.container.querySelector('#file-name-3d');
            if (span) span.textContent = name;
        });

        // 上传
        this.container.querySelector('#upload-btn-3d')?.addEventListener('click', () => this.uploadData());

        // 滑块同步
        this.bindSlider('kriging3d-res-x', 'res-x-val', (v) => { this.config.gridResolutionX = v; });
        this.bindSlider('kriging3d-res-y', 'res-y-val', (v) => { this.config.gridResolutionY = v; });
        this.bindSlider('kriging3d-res-z', 'res-z-val', (v) => { this.config.gridResolutionZ = v; });
        this.bindSlider('kriging3d-nlags', 'nlags3d-val', (v) => { this.config.nlags = v; });
        this.bindSlider('kriging3d-nclosest', 'nclosest-val', (v) => { this.config.nClosest = v; });
        this.bindSlider('viz-opacity', 'opacity-val', () => {});

        // 方法切换
        this.container.querySelector('#kriging3d-method')?.addEventListener('change', (e) => {
            const val = (e.target as HTMLSelectElement).value as Kriging3DConfig['method'];
            this.config.method = val;
            const thresholdGroup = this.container.querySelector('#indicator-threshold-group') as HTMLElement;
            if (thresholdGroup) thresholdGroup.style.display = val === 'indicator' ? 'block' : 'none';
        });

        this.container.querySelector('#kriging3d-variogram')?.addEventListener('change', (e) => {
            this.config.variogramModel = (e.target as HTMLSelectElement).value as Kriging3DConfig['variogramModel'];
        });

        this.container.querySelector('#kriging3d-anisotropy')?.addEventListener('change', (e) => {
            this.config.enableAnisotropy = (e.target as HTMLInputElement).checked;
        });

        this.container.querySelector('#kriging3d-cv')?.addEventListener('change', (e) => {
            this.config.enableCrossValidation = (e.target as HTMLInputElement).checked;
        });

        // 开始插值
        this.container.querySelector('#start-kriging3d-btn')?.addEventListener('click', () => this.startKriging());

        // 切片
        this.container.querySelector('#get-slice-btn')?.addEventListener('click', () => this.getSlice());
        this.bindSlider('slice-position', 'slice-pos-val', () => {});

        // 导出
        this.container.querySelector('#export-3d-json')?.addEventListener('click', () => this.exportResult('json'));
        this.container.querySelector('#export-3d-npz')?.addEventListener('click', () => this.exportResult('npz'));
    }

    private bindSlider(sliderId: string, valId: string, callback: (v: number) => void): void {
        const slider = this.container.querySelector(`#${sliderId}`) as HTMLInputElement;
        const valSpan = this.container.querySelector(`#${valId}`);
        slider?.addEventListener('input', () => {
            if (valSpan) valSpan.textContent = slider.value;
            callback(Number(slider.value));
        });
    }

    private async uploadData(): Promise<void> {
        const fileInput = this.container.querySelector('#file-input-3d') as HTMLInputElement;
        const statusEl = this.container.querySelector('#upload-status-3d') as HTMLElement;
        const file = fileInput?.files?.[0];
        if (!file) {
            if (statusEl) statusEl.textContent = '请先选择文件';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            if (statusEl) statusEl.textContent = '上传中...';
            const resp = await fetch(`${API_BASE}/kriging3d/upload`, { method: 'POST', body: formData });
            if (!resp.ok) throw new Error(`上传失败: ${resp.status}`);
            const data = await resp.json();
            this.dataId = data.data_id;
            if (statusEl) statusEl.textContent = `上传成功: ${data.point_count} 个3D点`;

            // 显示统计信息
            const statsResp = await fetch(`${API_BASE}/kriging3d/data/${this.dataId}/stats`);
            if (statsResp.ok) {
                const stats = await statsResp.json();
                const statsEl = this.container.querySelector('#data-stats-3d') as HTMLElement;
                if (statsEl) {
                    statsEl.style.display = 'block';
                    statsEl.innerHTML = `
                        <div class="stats-grid">
                            <div>点数: ${stats.point_count}</div>
                            <div>X: [${stats.x_range[0].toFixed(2)}, ${stats.x_range[1].toFixed(2)}]</div>
                            <div>Y: [${stats.y_range[0].toFixed(2)}, ${stats.y_range[1].toFixed(2)}]</div>
                            <div>Z: [${stats.z_range[0].toFixed(2)}, ${stats.z_range[1].toFixed(2)}]</div>
                            <div>值: ${stats.value_stats.min.toFixed(2)} ~ ${stats.value_stats.max.toFixed(2)}</div>
                            <div>均值: ${stats.value_stats.mean.toFixed(2)}, 标准差: ${stats.value_stats.std.toFixed(2)}</div>
                        </div>
                    `;
                }
            }

            const startBtn = this.container.querySelector('#start-kriging3d-btn') as HTMLButtonElement;
            if (startBtn) startBtn.disabled = false;
        } catch (err: any) {
            if (statusEl) statusEl.textContent = `上传失败: ${err.message}`;
        }
    }

    private async startKriging(): Promise<void> {
        if (!this.dataId) return;
        const statusEl = this.container.querySelector('#task-status-3d') as HTMLElement;
        const progressBar = this.container.querySelector('#progress-bar-3d') as HTMLElement;

        const body: Record<string, any> = {
            data_id: this.dataId,
            method: this.config.method,
            variogram_model: this.config.variogramModel,
            grid_resolution_x: this.config.gridResolutionX,
            grid_resolution_y: this.config.gridResolutionY,
            grid_resolution_z: this.config.gridResolutionZ,
            nlags: this.config.nlags,
            n_closest: this.config.nClosest,
            enable_anisotropy: this.config.enableAnisotropy,
            enable_cross_validation: this.config.enableCrossValidation,
        };

        if (this.config.method === 'indicator') {
            const thresholdInput = this.container.querySelector('#kriging3d-threshold') as HTMLInputElement;
            body.indicator_threshold = Number(thresholdInput?.value || 0);
        }

        try {
            if (statusEl) statusEl.textContent = '启动中...';
            if (progressBar) progressBar.style.display = 'block';

            const resp = await fetch(`${API_BASE}/kriging3d/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!resp.ok) throw new Error(`启动失败: ${resp.status}`);
            const data = await resp.json();
            this.taskId = data.task_id;
            if (statusEl) statusEl.textContent = `任务已启动: ${this.taskId?.slice(0, 8)}...`;
            this.startPolling();
        } catch (err: any) {
            if (statusEl) statusEl.textContent = `启动失败: ${err.message}`;
        }
    }

    private startPolling(): void {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.pollTimer = window.setInterval(() => this.pollStatus(), 2000);
    }

    private async pollStatus(): Promise<void> {
        if (!this.taskId) return;
        try {
            const resp = await fetch(`${API_BASE}/kriging3d/status/${this.taskId}`);
            if (!resp.ok) return;
            const status: Kriging3DTaskStatus = await resp.json();

            const statusEl = this.container.querySelector('#task-status-3d') as HTMLElement;
            const progressFill = this.container.querySelector('#progress-fill-3d') as HTMLElement;

            if (progressFill) progressFill.style.width = `${status.progress || 0}%`;

            if (status.status === 'completed') {
                if (this.pollTimer) clearInterval(this.pollTimer);
                if (statusEl) statusEl.textContent = '3D插值完成';
                this.showResults(status);
            } else if (status.status === 'failed') {
                if (this.pollTimer) clearInterval(this.pollTimer);
                if (statusEl) statusEl.textContent = `失败: ${status.error || '未知错误'}`;
            } else {
                if (statusEl) statusEl.textContent = `计算中... ${(status.progress || 0).toFixed(1)}%`;
            }
        } catch { /* ignore polling errors */ }
    }

    private showResults(status: Kriging3DTaskStatus): void {
        const resultPanel = this.container.querySelector('#result-panel-3d') as HTMLElement;
        const vizPanel = this.container.querySelector('#viz-panel-3d') as HTMLElement;
        if (resultPanel) resultPanel.style.display = 'block';
        if (vizPanel) vizPanel.style.display = 'block';

        const statsEl = this.container.querySelector('#result-stats-3d') as HTMLElement;
        if (statsEl && status.predictionStats) {
            const ps = status.predictionStats;
            const vs = status.varianceStats || {};
            statsEl.innerHTML = `
                <div class="stats-grid">
                    <div><strong>网格:</strong> ${status.gridShape?.join(' x ')}</div>
                    <div><strong>预测均值:</strong> ${(ps.mean || 0).toFixed(4)}</div>
                    <div><strong>预测范围:</strong> ${(ps.min || 0).toFixed(4)} ~ ${(ps.max || 0).toFixed(4)}</div>
                    <div><strong>方差均值:</strong> ${(vs.mean || 0).toFixed(4)}</div>
                </div>
            `;
        }

        this.init3DVisualization();
    }

    private async getSlice(): Promise<void> {
        if (!this.taskId) return;
        const axis = (this.container.querySelector('#slice-axis') as HTMLSelectElement)?.value || 'z';
        const posSlider = this.container.querySelector('#slice-position') as HTMLInputElement;
        const position = Number(posSlider?.value || 50);

        try {
            const resp = await fetch(`${API_BASE}/kriging3d/slice/${this.taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ axis, position, resolution: 100 }),
            });
            if (!resp.ok) throw new Error('获取切片失败');
            const slice: SliceData = await resp.json();
            this.renderSlice(slice);
        } catch (err: any) {
            const container = this.container.querySelector('#slice-container-3d');
            if (container) container.innerHTML = `<p style="color:red;">${err.message}</p>`;
        }
    }

    private renderSlice(slice: SliceData): void {
        const container = this.container.querySelector('#slice-container-3d') as HTMLElement;
        if (!container) return;

        const width = 300;
        const height = 300;
        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = '100%';
        canvas.style.borderRadius = '4px';
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const values = slice.values;
        const rows = values.length;
        const cols = values[0]?.length || 0;
        if (rows === 0 || cols === 0) return;

        let vmin = Infinity, vmax = -Infinity;
        for (const row of values) {
            for (const v of row) {
                if (v < vmin) vmin = v;
                if (v > vmax) vmax = v;
            }
        }
        const range = vmax - vmin || 1;

        const cellW = width / cols;
        const cellH = height / rows;

        for (let i = 0; i < rows; i++) {
            for (let j = 0; j < cols; j++) {
                const t = (values[i][j] - vmin) / range;
                const r = Math.round(255 * Math.min(1, 2 * t));
                const g = Math.round(255 * Math.min(1, 2 * (1 - t)));
                const b = Math.round(100 * (1 - t));
                ctx.fillStyle = `rgb(${r},${g},${b})`;
                ctx.fillRect(j * cellW, i * cellH, cellW + 1, cellH + 1);
            }
        }

        container.innerHTML = `<p style="font-size:12px;color:#888;">${slice.axis.toUpperCase()}轴切片 @ ${slice.position.toFixed(2)}</p>`;
        container.appendChild(canvas);
    }

    private async exportResult(format: string): Promise<void> {
        if (!this.taskId) return;
        try {
            const resp = await fetch(`${API_BASE}/kriging3d/export/${this.taskId}?format=${format}`);
            if (!resp.ok) throw new Error('导出失败');
            const data = await resp.json();
            I18nDialog.alert(`导出成功: ${data.path}`);
        } catch (err: any) {
            I18nDialog.alert(`导出失败: ${err.message}`);
        }
    }

    private init3DVisualization(): void {
        const container = this.container.querySelector('#threejs-container') as HTMLElement;
        if (!container) return;
        // Three.js 3D可视化占位 - 实际项目中集成Three.js
        container.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#8888aa;flex-direction:column;">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                <p style="margin-top:12px;">3D可视化区域</p>
                <p style="font-size:12px;opacity:0.6;">使用切片功能查看2D截面</p>
            </div>
        `;
    }

    public destroy(): void {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.container.innerHTML = '';
    }
}

