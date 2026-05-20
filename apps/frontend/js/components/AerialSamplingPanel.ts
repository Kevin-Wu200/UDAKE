/**
 * 航测像片采样推荐面板
 * ====================
 * 支持上传航测像片、查看反演结果、获取采样推荐。
 * 继承现有SamplingRecommendationPanel的设计模式。
 */
import { APIService, resolveRuntimeApiBaseUrl } from '../services/API封装.js';

/** 航测像片元数据 */
interface AerialMetadata {
    file_name: string;
    file_size_bytes: number;
    image_format: string;
    gps: { latitude: number; longitude: number; altitude: number | null };
    imu: { pitch: number | null; roll: number | null; yaw: number | null };
    camera: { focal_length_mm: number | null; image_width_px: number; image_height_px: number };
    capture_time: string | null;
}

/** 影像质量报告 */
interface QualityReport {
    file_path: string;
    blur_score: number;
    exposure_score: number;
    tilt_angle: number;
    overall_score: number;
    quality_level: string;
    recommendations: string[];
}

/** 反演指标摘要 */
interface IndicatorSummary {
    min: number;
    max: number;
    mean: number;
    std: number;
    unit: string;
}

/** 反演结果摘要 */
interface InversionSummary {
    scenario: string;
    indicators: Record<string, IndicatorSummary>;
}

/** 采样建议项 */
interface Recommendation {
    id: number;
    x: number;
    y: number;
    variance: number;
    priority: string;
    uncertainty_level: number;
    sampling_reason: string;
    expected_benefit: number;
}

/** 全流程响应 */
interface PipelineResponse {
    task_id: string;
    status: string;
    metadata?: Record<string, unknown>;
    quality?: QualityReport;
    inversion_summary?: Record<string, unknown>;
    recommendations?: Recommendation[];
    geo_transform?: number[];
    processing_time_ms: number;
    error?: string;
}

type PanelStep = 'upload' | 'parsing' | 'quality' | 'inverting' | 'recommending' | 'results' | 'error';

export class AerialSamplingPanel {
    private container: HTMLElement;
    private apiService: APIService;
    private currentStep: PanelStep;
    private selectedFile: File | null;
    private taskId: string | null;
    private pipelineResult: PipelineResponse | null;
    private onRecommendationSelect: ((rec: Recommendation) => void) | null;
    private scenario: string;
    private strategy: string;
    private nRecommendations: number;

    constructor(
        container: HTMLElement,
        onRecommendationSelect?: (rec: Recommendation) => void,
    ) {
        this.container = container;
        this.apiService = new APIService(resolveRuntimeApiBaseUrl());
        this.currentStep = 'upload';
        this.selectedFile = null;
        this.taskId = null;
        this.pipelineResult = null;
        this.onRecommendationSelect = onRecommendationSelect || null;
        this.scenario = 'all';
        this.strategy = 'hybrid';
        this.nRecommendations = 20;
        this.render();
    }

    /** 渲染主面板 */
    private render(): void {
        this.container.innerHTML = `
        <div class="aerial-sampling-panel" style="padding: 16px; font-family: system-ui, sans-serif;">
            <div class="panel-header" style="margin-bottom: 16px;">
                <h3 style="margin: 0 0 8px 0; font-size: 16px; color: #1a1a2e;">🛩️ 航测像片采样推荐</h3>
                <p style="margin: 0; font-size: 12px; color: #666;">
                    上传航测像片，自动完成反演计算与采样推荐
                </p>
            </div>
            <div id="aerial-step-content"></div>
            <div id="aerial-status-bar" style="margin-top: 12px; font-size: 11px; color: #999;"></div>
        </div>`;

        this.renderCurrentStep();
    }

    /** 渲染当前步骤 */
    private renderCurrentStep(): void {
        const content = this.container.querySelector('#aerial-step-content') as HTMLElement;
        if (!content) return;

        switch (this.currentStep) {
            case 'upload': this.renderUploadStep(content); break;
            case 'parsing': this.renderProgressStep(content, '正在解析影像元数据...'); break;
            case 'quality': this.renderQualityStep(content); break;
            case 'inverting': this.renderProgressStep(content, '正在执行遥感反演计算...'); break;
            case 'recommending': this.renderProgressStep(content, '正在生成采样推荐...'); break;
            case 'results': this.renderResultsStep(content); break;
            case 'error': this.renderErrorStep(content); break;
        }
    }

    /** 上传步骤 */
    private renderUploadStep(container: HTMLElement): void {
        container.innerHTML = `
        <div class="upload-area" style="
            border: 2px dashed #ccc; border-radius: 8px; padding: 32px;
            text-align: center; cursor: pointer; transition: border-color 0.2s;
            margin-bottom: 16px;
        " onmouseover="this.style.borderColor='#4a90d9'" onmouseout="this.style.borderColor='#ccc'">
            <input type="file" id="aerial-file-input" accept=".jpg,.jpeg,.tif,.tiff"
                   style="display:none" />
            <div style="font-size: 32px; margin-bottom: 8px;">📸</div>
            <div style="font-size: 14px; color: #333;">点击或拖拽上传航测像片</div>
            <div style="font-size: 11px; color: #999; margin-top: 4px;">
                支持 JPG, TIFF 格式 (EXIF 2.3+)
            </div>
            <div id="aerial-file-name" style="margin-top: 8px; font-size: 12px; color: #4a90d9;"></div>
        </div>
        <div class="config-section" style="margin-bottom: 12px;">
            <label style="font-size: 12px; color: #666; display: block; margin-bottom: 4px;">
                反演场景
            </label>
            <select id="aerial-scenario" style="width: 100%; padding: 6px; border-radius: 4px; border: 1px solid #ddd;">
                <option value="all">全部 (14项指标)</option>
                <option value="water">水质 (5项)</option>
                <option value="forestry">林业 (5项)</option>
                <option value="environment">环境 (4项)</option>
            </select>
        </div>
        <div class="config-section" style="margin-bottom: 12px;">
            <label style="font-size: 12px; color: #666; display: block; margin-bottom: 4px;">
                采样策略
            </label>
            <select id="aerial-strategy" style="width: 100%; padding: 6px; border-radius: 4px; border: 1px solid #ddd;">
                <option value="hybrid">混合策略 (推荐)</option>
                <option value="variance_based">方差优先</option>
                <option value="spatial_coverage">空间覆盖</option>
            </select>
        </div>
        <div class="config-section" style="margin-bottom: 16px;">
            <label style="font-size: 12px; color: #666; display: block; margin-bottom: 4px;">
                建议点数量: <span id="aerial-n-count">20</span>
            </label>
            <input type="range" id="aerial-n-recommendations" min="5" max="100" value="20"
                   style="width: 100%;" />
        </div>
        <button id="aerial-start-btn" disabled
                style="width: 100%; padding: 10px; background: #4a90d9; color: white;
                       border: none; border-radius: 6px; font-size: 14px; cursor: pointer;
                       opacity: 0.5; transition: opacity 0.2s;">
            🚀 开始全流程处理
        </button>`;

        this.bindUploadEvents();
    }

    /** 绑定上传区域事件 */
    private bindUploadEvents(): void {
        const uploadArea = this.container.querySelector('.upload-area') as HTMLElement;
        const fileInput = this.container.querySelector('#aerial-file-input') as HTMLInputElement;
        const fileName = this.container.querySelector('#aerial-file-name') as HTMLElement;
        const startBtn = this.container.querySelector('#aerial-start-btn') as HTMLButtonElement;
        const scenarioSel = this.container.querySelector('#aerial-scenario') as HTMLSelectElement;
        const strategySel = this.container.querySelector('#aerial-strategy') as HTMLSelectElement;
        const nSlider = this.container.querySelector('#aerial-n-recommendations') as HTMLInputElement;
        const nCount = this.container.querySelector('#aerial-n-count') as HTMLElement;

        uploadArea?.addEventListener('click', () => fileInput?.click());

        // 拖拽支持
        uploadArea?.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#4a90d9';
            uploadArea.style.background = '#f0f7ff';
        });
        uploadArea?.addEventListener('dragleave', () => {
            uploadArea.style.borderColor = '#ccc';
            uploadArea.style.background = '';
        });
        uploadArea?.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.borderColor = '#ccc';
            uploadArea.style.background = '';
            const files = e.dataTransfer?.files;
            if (files && files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });

        fileInput?.addEventListener('change', () => {
            const files = fileInput.files;
            if (files && files.length > 0) {
                this.handleFileSelect(files[0]);
            }
        });

        // 配置变更
        scenarioSel?.addEventListener('change', () => { this.scenario = scenarioSel.value; });
        strategySel?.addEventListener('change', () => { this.strategy = strategySel.value; });
        nSlider?.addEventListener('input', () => {
            this.nRecommendations = parseInt(nSlider.value);
            if (nCount) nCount.textContent = nSlider.value;
        });

        // 开始处理
        startBtn?.addEventListener('click', () => this.startFullPipeline());

        this.handleFileSelect = (file: File) => {
            this.selectedFile = file;
            if (fileName) fileName.textContent = `📎 ${file.name} (${this.formatFileSize(file.size)})`;
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.style.opacity = '1';
            }
        };
    }

    /** 进度步骤 */
    private renderProgressStep(container: HTMLElement, message: string): void {
        container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div class="spinner" style="
                display: inline-block; width: 36px; height: 36px;
                border: 3px solid #e0e0e0; border-top-color: #4a90d9;
                border-radius: 50%; animation: spin 0.8s linear infinite;
            "></div>
            <div style="margin-top: 16px; font-size: 14px; color: #333;">${message}</div>
            <div style="margin-top: 8px; font-size: 12px; color: #999;">请稍候...</div>
        </div>
        <style>
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>`;
    }

    /** 质量评估结果 */
    private renderQualityStep(container: HTMLElement): void {
        const q = this.pipelineResult?.quality;
        if (!q) return;

        const levelColors: Record<string, string> = {
            excellent: '#2ecc71',
            good: '#27ae60',
            acceptable: '#f39c12',
            poor: '#e67e22',
            rejected: '#e74c3c',
        };

        const levelLabels: Record<string, string> = {
            excellent: '优秀',
            good: '良好',
            acceptable: '可接受',
            poor: '较差',
            rejected: '不合格',
        };

        const color = levelColors[q.quality_level] || '#999';
        const label = levelLabels[q.quality_level] || q.quality_level;

        container.innerHTML = `
        <div style="padding: 8px;">
            <div style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">📊 影像质量评估</div>
            <div style="display: flex; justify-content: space-around; margin-bottom: 12px;">
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #4a90d9;">${q.blur_score.toFixed(1)}</div>
                    <div style="font-size: 11px; color: #999;">清晰度</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #4a90d9;">${q.exposure_score.toFixed(1)}</div>
                    <div style="font-size: 11px; color: #999;">曝光</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #4a90d9;">${q.tilt_angle.toFixed(1)}°</div>
                    <div style="font-size: 11px; color: #999;">倾斜角</div>
                </div>
            </div>
            <div style="text-align: center; margin-bottom: 12px;">
                <span style="font-size: 28px; font-weight: bold; color: ${color};">${q.overall_score.toFixed(1)}</span>
                <span style="margin-left: 8px; padding: 2px 8px; border-radius: 4px;
                    background: ${color}; color: white; font-size: 12px;">${label}</span>
            </div>
            ${q.recommendations.length > 0 ? `
            <div style="background: #fff3cd; padding: 8px; border-radius: 4px; font-size: 11px;">
                ${q.recommendations.map(r => `• ${r}`).join('<br>')}
            </div>` : ''}
        </div>`;
    }

    /** 结果步骤 */
    private renderResultsStep(container: HTMLElement): void {
        const result = this.pipelineResult;
        if (!result) return;

        const recs = result.recommendations || [];
        const summary = result.inversion_summary || {};

        let summaryHTML = '';
        for (const [scenario, indicators] of Object.entries(summary)) {
            const indMap = indicators as Record<string, IndicatorSummary>;
            summaryHTML += `
            <div style="margin-bottom: 8px;">
                <div style="font-size: 13px; font-weight: 600; color: #1a1a2e;">
                    ${this.getScenarioLabel(scenario)}
                </div>`;
            for (const [name, info] of Object.entries(indMap)) {
                if (!info || typeof info.mean === 'undefined') continue;
                summaryHTML += `
                <div style="display: flex; justify-content: space-between; font-size: 11px;
                            padding: 2px 8px; color: #555;">
                    <span>${name}</span>
                    <span>${info.mean.toFixed(2)} ${info.unit || ''}</span>
                </div>`;
            }
            summaryHTML += '</div>';
        }

        let recHTML = '';
        if (recs.length > 0) {
            recHTML = `
            <div style="margin-top: 12px;">
                <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px;">
                    📍 采样建议 (${recs.length}个点)
                </div>
                <div style="max-height: 300px; overflow-y: auto;">`;
            for (const rec of recs.slice(0, 20)) {
                const pColor = rec.priority === 'high' ? '#e74c3c' :
                              rec.priority === 'medium' ? '#f39c12' : '#27ae60';
                recHTML += `
                <div class="rec-item" data-rec-id="${rec.id}"
                     style="padding: 6px 8px; margin-bottom: 4px; border-radius: 4px;
                            background: #f8f9fa; cursor: pointer; font-size: 11px;
                            border-left: 3px solid ${pColor};"
                     onmouseover="this.style.background='#e8f0fe'"
                     onmouseout="this.style.background='#f8f9fa'">
                    <div style="display: flex; justify-content: space-between;">
                        <span>📍 (${rec.x.toFixed(5)}, ${rec.y.toFixed(5)})</span>
                        <span style="color: ${pColor}; font-weight: 600;">${rec.priority}</span>
                    </div>
                    <div style="color: #999; margin-top: 2px;">${rec.sampling_reason}</div>
                </div>`;
            }
            recHTML += '</div></div>';
        }

        container.innerHTML = `
        <div style="padding: 8px;">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 20px; margin-right: 8px;">✅</span>
                <div>
                    <div style="font-size: 14px; font-weight: 600;">处理完成</div>
                    <div style="font-size: 11px; color: #999;">
                        任务ID: ${result.task_id} | 耗时: ${(result.processing_time_ms / 1000).toFixed(1)}s
                    </div>
                </div>
            </div>
            ${summaryHTML}
            ${recHTML}
            <button id="aerial-reset-btn" style="
                width: 100%; margin-top: 12px; padding: 8px;
                background: #f0f0f0; border: 1px solid #ddd; border-radius: 6px;
                font-size: 13px; cursor: pointer;">
                🔄 重新处理
            </button>
        </div>`;

        // 绑定推荐点点击事件
        const recItems = container.querySelectorAll('.rec-item');
        recItems.forEach(item => {
            item.addEventListener('click', () => {
                const recId = parseInt((item as HTMLElement).dataset.recId || '0');
                const rec = recs.find(r => r.id === recId);
                if (rec && this.onRecommendationSelect) {
                    this.onRecommendationSelect(rec);
                }
            });
        });

        // 绑定重置按钮
        const resetBtn = container.querySelector('#aerial-reset-btn');
        resetBtn?.addEventListener('click', () => {
            this.currentStep = 'upload';
            this.pipelineResult = null;
            this.selectedFile = null;
            this.taskId = null;
            this.render();
        });
    }

    /** 错误步骤 */
    private renderErrorStep(container: HTMLElement): void {
        const error = this.pipelineResult?.error || '未知错误';
        container.innerHTML = `
        <div style="text-align: center; padding: 24px;">
            <div style="font-size: 32px; margin-bottom: 8px;">❌</div>
            <div style="font-size: 14px; color: #e74c3c; margin-bottom: 8px;">处理失败</div>
            <div style="font-size: 12px; color: #999; margin-bottom: 16px;">${error}</div>
            <button id="aerial-retry-btn" style="
                padding: 8px 20px; background: #4a90d9; color: white;
                border: none; border-radius: 6px; font-size: 13px; cursor: pointer;">
                🔄 重试
            </button>
        </div>`;

        const retryBtn = container.querySelector('#aerial-retry-btn');
        retryBtn?.addEventListener('click', () => {
            this.currentStep = 'upload';
            this.render();
        });
    }

    /** 启动全流程处理 */
    private async startFullPipeline(): Promise<void> {
        if (!this.selectedFile) return;

        this.currentStep = 'parsing';
        this.renderCurrentStep();
        this.updateStatusBar('正在上传并解析...');

        try {
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('scenario', this.scenario);
            formData.append('strategy', this.strategy);
            formData.append('n_recommendations', String(this.nRecommendations));

            // 步骤1-2: 先解析元数据和评估质量
            this.updateStatusBar('解析EXIF元数据...');

            // 全流程API调用 (上传+解析+反演+推荐)
            const baseUrl = resolveRuntimeApiBaseUrl();
            const response = await fetch(`${baseUrl}/api/aerial/full-pipeline`, {
                method: 'POST',
                body: formData,
            });

            const result: PipelineResponse = await response.json();

            if (!response.ok || result.status === 'rejected' || result.status === 'failed') {
                this.pipelineResult = result;
                this.currentStep = result.status === 'rejected' ? 'quality' : 'error';
                if (result.status === 'rejected') {
                    this.renderCurrentStep();
                    setTimeout(() => { this.currentStep = 'upload'; this.render(); }, 3000);
                } else {
                    this.renderCurrentStep();
                }
                return;
            }

            this.pipelineResult = result;
            this.taskId = result.task_id;

            // 如果包含质量信息，先展示
            if (result.quality) {
                this.currentStep = 'quality';
                this.renderCurrentStep();
                await this.sleep(1500);
            }

            // 展示反演进度
            this.currentStep = 'inverting';
            this.renderCurrentStep();
            this.updateStatusBar('执行遥感反演...');
            await this.sleep(500);

            // 展示采样推荐进度
            this.currentStep = 'recommending';
            this.renderCurrentStep();
            this.updateStatusBar('生成采样推荐...');
            await this.sleep(500);

            // 显示结果
            this.currentStep = 'results';
            this.renderCurrentStep();
            this.updateStatusBar(`完成 | 推荐点: ${result.recommendations?.length || 0} | 耗时: ${(result.processing_time_ms / 1000).toFixed(1)}s`);

        } catch (err) {
            this.pipelineResult = {
                task_id: '',
                status: 'error',
                error: `网络请求失败: ${(err as Error).message}`,
                processing_time_ms: 0,
            };
            this.currentStep = 'error';
            this.renderCurrentStep();
            this.updateStatusBar('处理失败');
        }
    }

    /** 更新状态栏 */
    private updateStatusBar(message: string): void {
        const bar = this.container.querySelector('#aerial-status-bar');
        if (bar) bar.textContent = message;
    }

    /** 获取场景中文标签 */
    private getScenarioLabel(scenario: string): string {
        const labels: Record<string, string> = {
            water: '💧 水质指标',
            forestry: '🌲 林业指标',
            environment: '🌍 环境指标',
            all: '📋 综合指标',
        };
        return labels[scenario] || scenario;
    }

    /** 格式化文件大小 */
    private formatFileSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    /** 延时 */
    private sleep(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /** 销毁 */
    public destroy(): void {
        this.container.innerHTML = '';
    }
}
