import type { IAPIService } from '../../types/api';

/**
 * 异常检测子面板
 */
export class AnomalyDetectionPanel {
    private container: HTMLElement;
    private apiService: IAPIService;
    private lastResult: unknown = null;

    constructor(container: HTMLElement, apiService: IAPIService) {
        this.container = container;
        this.apiService = apiService;
        this.render();
        this.bindEvents();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="dl-module-card">
                <div class="dl-module-header">
                    <h4>异常检测</h4>
                    <p>检测采样数据中的异常点</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-anomaly-model" class="select">
                            <option value="vae">VAE</option>
                            <option value="gcae">GCAE</option>
                            <option value="gan">GAN</option>
                            <option value="contrastive">Contrastive</option>
                            <option value="fusion">Fusion(仅预测)</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>阈值方法</span>
                        <select id="dl-anomaly-threshold" class="select">
                            <option value="percentile">Percentile</option>
                            <option value="statistical">Statistical</option>
                            <option value="adaptive">Adaptive</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-anomaly-epochs" class="input" type="number" min="1" max="300" value="30">
                    </label>
                    <label class="dl-field">
                        <span>Percentile</span>
                        <input id="dl-anomaly-percentile" class="input" type="number" min="50" max="99.9" step="0.1" value="95">
                    </label>
                    <label class="dl-field">
                        <span>k 值</span>
                        <input id="dl-anomaly-k" class="input" type="number" min="1" max="6" step="0.1" value="2.5">
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>坐标 coords（JSON）</span>
                    <textarea id="dl-anomaly-coords" class="dl-textarea" rows="4">[[0,0],[1,0],[0,1],[1,1],[0.6,0.4],[0.2,0.8]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>数值 values（JSON）</span>
                    <textarea id="dl-anomaly-values" class="dl-textarea" rows="3">[1.1,1.2,1.0,8.8,1.3,1.05]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-anomaly-train" class="btn btn-primary">训练模型</button>
                    <button id="dl-anomaly-predict" class="btn btn-secondary">执行检测</button>
                    <button id="dl-anomaly-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-anomaly-status" class="status-message"></div>
                <pre id="dl-anomaly-result" class="dl-result">暂无结果</pre>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-anomaly-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-anomaly-predict')?.addEventListener('click', () => {
            void this.handlePredict();
        });

        this.container.querySelector('#dl-anomaly-export')?.addEventListener('click', () => {
            this.exportResult();
        });
    }

    private parseJson<T>(inputId: string, fieldName: string): T {
        const input = this.container.querySelector(`#${inputId}`) as HTMLTextAreaElement | null;
        if (!input) {
            throw new Error(`缺少输入项: ${fieldName}`);
        }

        try {
            return JSON.parse(input.value) as T;
        } catch {
            throw new Error(`${fieldName} 不是合法 JSON`);
        }
    }

    private setStatus(message: string, type: 'success' | 'warning' | 'error' | 'loading' = 'success'): void {
        const status = this.container.querySelector('#dl-anomaly-status') as HTMLElement | null;
        if (!status) {
            return;
        }
        status.className = 'status-message';
        if (type !== 'loading') {
            status.classList.add(type);
        }
        status.textContent = message;
    }

    private setResult(data: unknown): void {
        const result = this.container.querySelector('#dl-anomaly-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelName(): 'vae' | 'gcae' | 'gan' | 'contrastive' | 'fusion' {
        const model = (this.container.querySelector('#dl-anomaly-model') as HTMLSelectElement | null)?.value || 'vae';
        if (model === 'gcae' || model === 'gan' || model === 'contrastive' || model === 'fusion') {
            return model;
        }
        return 'vae';
    }

    private async handleTrain(): Promise<void> {
        try {
            const modelName = this.getModelName();
            if (modelName === 'fusion') {
                throw new Error('Fusion 模式仅支持预测，不支持训练');
            }

            this.setStatus('正在训练异常检测模型...', 'loading');
            const epochs = Number((this.container.querySelector('#dl-anomaly-epochs') as HTMLInputElement | null)?.value || 30);
            const coords = this.parseJson<Array<[number, number]>>('dl-anomaly-coords', 'coords');
            const values = this.parseJson<number[]>('dl-anomaly-values', 'values');

            const response = await this.apiService.trainAnomaly({
                model_name: modelName,
                coords,
                values,
                epochs
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('异常检测模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行异常检测...', 'loading');
            const modelName = this.getModelName();
            const thresholdMethod = (this.container.querySelector('#dl-anomaly-threshold') as HTMLSelectElement | null)?.value || 'percentile';
            const percentile = Number((this.container.querySelector('#dl-anomaly-percentile') as HTMLInputElement | null)?.value || 95);
            const k = Number((this.container.querySelector('#dl-anomaly-k') as HTMLInputElement | null)?.value || 2.5);
            const coords = this.parseJson<Array<[number, number]>>('dl-anomaly-coords', 'coords');
            const values = this.parseJson<number[]>('dl-anomaly-values', 'values');

            const response = await this.apiService.predictAnomaly({
                model_name: modelName,
                coords,
                values,
                threshold_method: thresholdMethod as 'statistical' | 'percentile' | 'adaptive',
                percentile,
                k
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('异常检测完成', 'success');
        } catch (error) {
            this.setStatus(`检测失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private exportResult(): void {
        if (!this.lastResult) {
            this.setStatus('没有可导出的结果，请先训练或预测', 'warning');
            return;
        }

        const blob = new Blob([JSON.stringify(this.lastResult, null, 2)], {
            type: 'application/json;charset=utf-8'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `anomaly-result-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        this.setStatus('结果导出成功', 'success');
    }

    public destroy(): void {
        this.container.innerHTML = '';
    }
}
