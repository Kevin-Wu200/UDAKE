import type { IAPIService } from '../../types/api';

/**
 * 空间插值神经网络子面板
 */
export class SpatialInterpolationPanel {
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
                    <h4>空间插值神经网络</h4>
                    <p>训练并预测空间连续变量</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-spatial-model" class="select">
                            <option value="gnn">GNN</option>
                            <option value="attention">Attention</option>
                            <option value="residual">Residual</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-spatial-epochs" class="input" type="number" min="1" max="200" value="30">
                    </label>
                    <label class="dl-field">
                        <span>融合比例</span>
                        <input id="dl-spatial-blend" class="input" type="number" min="0" max="1" step="0.05" value="0.6">
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>训练样本 samples（JSON）</span>
                    <textarea id="dl-spatial-samples" class="dl-textarea" rows="5">[[0,0,1.2],[1,0,1.8],[0,1,2.3],[1,1,2.9],[0.5,0.7,2.1]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>预测点 queries（JSON）</span>
                    <textarea id="dl-spatial-queries" class="dl-textarea" rows="3">[[0.2,0.2],[0.8,0.5],[0.3,0.9]]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-spatial-train" class="btn btn-primary">训练模型</button>
                    <button id="dl-spatial-predict" class="btn btn-secondary">执行预测</button>
                    <button id="dl-spatial-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-spatial-status" class="status-message"></div>
                <pre id="dl-spatial-result" class="dl-result">暂无结果</pre>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-spatial-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-spatial-predict')?.addEventListener('click', () => {
            void this.handlePredict();
        });

        this.container.querySelector('#dl-spatial-export')?.addEventListener('click', () => {
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
        const status = this.container.querySelector('#dl-spatial-status') as HTMLElement | null;
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
        const result = this.container.querySelector('#dl-spatial-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelType(): 'gnn' | 'attention' | 'residual' {
        const model = (this.container.querySelector('#dl-spatial-model') as HTMLSelectElement | null)?.value || 'gnn';
        if (model === 'attention' || model === 'residual') {
            return model;
        }
        return 'gnn';
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练空间插值模型...', 'loading');
            const modelType = this.getModelType();
            const epochs = Number((this.container.querySelector('#dl-spatial-epochs') as HTMLInputElement | null)?.value || 30);
            const samples = this.parseJson<Array<[number, number, number]>>('dl-spatial-samples', 'samples');

            const response = await this.apiService.trainSpatial({
                model_type: modelType,
                samples,
                epochs
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('空间插值模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行空间预测...', 'loading');
            const modelType = this.getModelType();
            const blendRatio = Number((this.container.querySelector('#dl-spatial-blend') as HTMLInputElement | null)?.value || 0.6);
            const samples = this.parseJson<Array<[number, number, number]>>('dl-spatial-samples', 'samples');
            const queries = this.parseJson<Array<[number, number]>>('dl-spatial-queries', 'queries');

            const response = await this.apiService.predictSpatial({
                model_type: modelType,
                samples,
                queries,
                blend_ratio: blendRatio
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('空间预测完成', 'success');
        } catch (error) {
            this.setStatus(`预测失败：${error instanceof Error ? error.message : String(error)}`, 'error');
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
        link.download = `spatial-result-${Date.now()}.json`;
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
