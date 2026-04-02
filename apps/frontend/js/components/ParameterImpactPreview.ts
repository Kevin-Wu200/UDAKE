/**
 * 参数影响预览组件
 * 用于快速对比参数配置对精度、耗时和内存的影响
 */

export interface KrigingPreviewConfig {
    'grid-resolution': number;
    nlags: number;
    nugget: number;
    sill: number;
    range: number;
    method?: 'ordinary' | 'universal' | 'block';
    variogramModel?: 'spherical' | 'exponential' | 'gaussian';
}

export interface PreviewMetrics {
    estimatedTimeMs: number;
    estimatedMemoryMb: number;
    qualityScore: number;
}

export interface PreviewData {
    id: string;
    label: string;
    config: KrigingPreviewConfig;
    metrics: PreviewMetrics;
    imageDataUrl: string;
    createdAt: string;
}

export interface ComparisonResult {
    fastestId: string | null;
    bestQualityId: string | null;
    lowestMemoryId: string | null;
}

export class ParameterImpactPreview {
    private container: HTMLElement;
    private cardsContainer: HTMLElement;
    private summaryContainer: HTMLElement;
    private previewResults: Map<string, PreviewData> = new Map();

    public constructor(container: HTMLElement) {
        this.container = container;
        this.container.innerHTML = '';
        this.container.className = 'parameter-impact-preview';

        const toolbar = document.createElement('div');
        toolbar.className = 'parameter-impact-toolbar';

        const title = document.createElement('span');
        title.className = 'parameter-impact-title';
        title.textContent = '参数影响预览';

        const exportBtn = document.createElement('button');
        exportBtn.type = 'button';
        exportBtn.className = 'btn btn-secondary parameter-impact-export';
        exportBtn.textContent = '导出预览图';
        exportBtn.addEventListener('click', () => this.exportLatestPreviewImage());

        toolbar.appendChild(title);
        toolbar.appendChild(exportBtn);

        this.cardsContainer = document.createElement('div');
        this.cardsContainer.className = 'parameter-impact-cards';

        this.summaryContainer = document.createElement('div');
        this.summaryContainer.className = 'parameter-impact-summary';

        this.container.appendChild(toolbar);
        this.container.appendChild(this.cardsContainer);
        this.container.appendChild(this.summaryContainer);
    }

    public async generatePreview(config: KrigingPreviewConfig, label: string = '当前配置'): Promise<PreviewData> {
        const metrics = this.estimateMetrics(config);
        const imageDataUrl = this.generatePreviewImage(config, metrics);
        const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;

        const result: PreviewData = {
            id,
            label,
            config,
            metrics,
            imageDataUrl,
            createdAt: new Date().toISOString()
        };

        this.previewResults.set(id, result);
        if (this.previewResults.size > 6) {
            const oldest = Array.from(this.previewResults.keys())[0];
            if (oldest) {
                this.previewResults.delete(oldest);
            }
        }

        this.render();
        return result;
    }

    public comparePreviews(configs: KrigingPreviewConfig[]): ComparisonResult {
        const items = configs.map((config) => this.estimateMetrics(config));
        if (items.length === 0) {
            return {
                fastestId: null,
                bestQualityId: null,
                lowestMemoryId: null
            };
        }

        const fastestIndex = items.reduce((best, item, index, list) => (item.estimatedTimeMs < list[best].estimatedTimeMs ? index : best), 0);
        const bestQualityIndex = items.reduce((best, item, index, list) => (item.qualityScore > list[best].qualityScore ? index : best), 0);
        const lowestMemoryIndex = items.reduce((best, item, index, list) => (item.estimatedMemoryMb < list[best].estimatedMemoryMb ? index : best), 0);

        return {
            fastestId: `配置${fastestIndex + 1}`,
            bestQualityId: `配置${bestQualityIndex + 1}`,
            lowestMemoryId: `配置${lowestMemoryIndex + 1}`
        };
    }

    public clear(): void {
        this.previewResults.clear();
        this.render();
    }

    public getLatest(): PreviewData | null {
        const values = Array.from(this.previewResults.values());
        if (values.length === 0) {
            return null;
        }
        return values[values.length - 1];
    }

    private estimateMetrics(config: KrigingPreviewConfig): PreviewMetrics {
        const grid = config['grid-resolution'];
        const lags = config.nlags;
        const nuggetPenalty = Math.max(0, config.nugget - config.sill * 0.4);

        const estimatedTimeMs = Math.max(120, Math.round(grid * 8 + lags * 35 + config.range * 12 + nuggetPenalty * 300));
        const estimatedMemoryMb = Math.max(40, Math.round(grid * 0.85 + lags * 2.8 + config.range * 0.9));

        const smoothness = 100 - Math.min(45, config.nugget * 100);
        const detail = Math.min(100, 35 + grid * 0.28 + lags * 1.8);
        const balance = Math.max(0, 100 - Math.abs(config.sill - 1.2) * 20 - Math.abs(config.range - 35) * 0.8);
        const qualityScore = Math.round((smoothness * 0.25 + detail * 0.45 + balance * 0.3) * 10) / 10;

        return {
            estimatedTimeMs,
            estimatedMemoryMb,
            qualityScore: Math.max(0, Math.min(100, qualityScore))
        };
    }

    private generatePreviewImage(config: KrigingPreviewConfig, metrics: PreviewMetrics): string {
        const canvas = document.createElement('canvas');
        canvas.width = 180;
        canvas.height = 120;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            return '';
        }

        const seed = this.calculateSeed(config);
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, `hsl(${(seed * 17) % 360}, 72%, 66%)`);
        gradient.addColorStop(1, `hsl(${(seed * 37 + 60) % 360}, 68%, 42%)`);
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < 5; i++) {
            const alpha = 0.15 + ((seed + i) % 7) * 0.03;
            ctx.fillStyle = `rgba(255,255,255,${Math.min(0.45, alpha)})`;
            const x = ((seed * (i + 3)) % 140) + i * 8;
            const y = ((seed * (i + 5)) % 80) + i * 6;
            const radius = 14 + ((seed + i * 11) % 18);
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fill();
        }

        ctx.fillStyle = 'rgba(0,0,0,0.45)';
        ctx.fillRect(0, canvas.height - 32, canvas.width, 32);
        ctx.fillStyle = '#fff';
        ctx.font = '11px sans-serif';
        ctx.fillText(`Q:${metrics.qualityScore.toFixed(1)} T:${(metrics.estimatedTimeMs / 1000).toFixed(2)}s`, 8, canvas.height - 12);

        return canvas.toDataURL('image/png');
    }

    private render(): void {
        const previews = Array.from(this.previewResults.values());
        this.cardsContainer.innerHTML = '';

        previews.forEach((preview) => {
            const card = document.createElement('article');
            card.className = 'parameter-impact-card';
            card.innerHTML = `
                <div class="parameter-impact-card-header">
                    <strong>${preview.label}</strong>
                    <span>${new Date(preview.createdAt).toLocaleTimeString('zh-CN', { hour12: false })}</span>
                </div>
                <img src="${preview.imageDataUrl}" alt="${preview.label} 预览图" class="parameter-impact-image" />
                <div class="parameter-impact-metrics">
                    <span>预计耗时: ${(preview.metrics.estimatedTimeMs / 1000).toFixed(2)}s</span>
                    <span>预计内存: ${preview.metrics.estimatedMemoryMb}MB</span>
                    <span>质量评分: ${preview.metrics.qualityScore.toFixed(1)}</span>
                </div>
            `;
            this.cardsContainer.appendChild(card);
        });

        const latest = this.getLatest();
        if (!latest) {
            this.summaryContainer.innerHTML = '<span class="parameter-impact-empty">点击“生成预览”查看参数影响对比</span>';
            return;
        }

        const normalizedSpeed = Math.max(0, Math.min(100, 120 - latest.metrics.estimatedTimeMs / 35));
        const normalizedMemory = Math.max(0, Math.min(100, 120 - latest.metrics.estimatedMemoryMb / 3));

        this.summaryContainer.innerHTML = `
            <div class="parameter-impact-score-row"><span>质量</span><div class="bar"><i style="width:${latest.metrics.qualityScore}%"></i></div><strong>${latest.metrics.qualityScore.toFixed(1)}%</strong></div>
            <div class="parameter-impact-score-row"><span>速度</span><div class="bar"><i style="width:${normalizedSpeed}%"></i></div><strong>${normalizedSpeed.toFixed(1)}%</strong></div>
            <div class="parameter-impact-score-row"><span>内存友好</span><div class="bar"><i style="width:${normalizedMemory}%"></i></div><strong>${normalizedMemory.toFixed(1)}%</strong></div>
        `;
    }

    private exportLatestPreviewImage(): void {
        const latest = this.getLatest();
        if (!latest || !latest.imageDataUrl) {
            return;
        }

        const anchor = document.createElement('a');
        anchor.href = latest.imageDataUrl;
        anchor.download = `kriging-preview-${Date.now()}.png`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
    }

    private calculateSeed(config: KrigingPreviewConfig): number {
        return Math.round(
            config['grid-resolution'] * 0.7 +
            config.nlags * 13 +
            config.nugget * 100 +
            config.sill * 17 +
            config.range * 9
        );
    }
}
