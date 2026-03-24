import type { IAPIService } from '../../types/api';

/**
 * 时空预测子面板
 */
export class SpatiotemporalPredictionPanel {
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
                    <h4>时空预测</h4>
                    <p>时空序列训练与预测</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-st-model" class="select">
                            <option value="st_transformer">ST-Transformer</option>
                            <option value="gcn_lstm">GCN-LSTM</option>
                            <option value="convlstm">ConvLSTM</option>
                            <option value="stgcn">STGCN</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>序列长度</span>
                        <input id="dl-st-seq-len" class="input" type="number" min="4" max="256" value="8">
                    </label>
                    <label class="dl-field">
                        <span>预测步长</span>
                        <input id="dl-st-horizon" class="input" type="number" min="1" max="48" value="3">
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-st-epochs" class="input" type="number" min="5" max="300" value="20">
                    </label>
                    <label class="dl-field">
                        <span>融合策略</span>
                        <select id="dl-st-fusion" class="select">
                            <option value="gating">Gating</option>
                            <option value="concat">Concat</option>
                            <option value="add">Add</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>融合比例</span>
                        <input id="dl-st-blend" class="input" type="number" min="0" max="1" step="0.05" value="0.7">
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>坐标 coords（JSON）</span>
                    <textarea id="dl-st-coords" class="dl-textarea" rows="4">[[0,0],[1,0],[0,1]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>时间序列 series（JSON, [n_nodes, seq_len, n_features]）</span>
                    <textarea id="dl-st-series" class="dl-textarea" rows="7">[[[1.0],[1.1],[1.2],[1.3],[1.4],[1.5],[1.6],[1.7]],[[0.8],[0.9],[1.0],[1.1],[1.2],[1.3],[1.4],[1.5]],[[1.3],[1.25],[1.2],[1.22],[1.3],[1.35],[1.4],[1.45]]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>目标值 targets（可选 JSON）</span>
                    <textarea id="dl-st-targets" class="dl-textarea" rows="3" placeholder="可留空"></textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-st-train" class="btn btn-primary">训练模型</button>
                    <button id="dl-st-predict" class="btn btn-secondary">执行预测</button>
                    <button id="dl-st-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-st-status" class="status-message"></div>
                <pre id="dl-st-result" class="dl-result">暂无结果</pre>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-st-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-st-predict')?.addEventListener('click', () => {
            void this.handlePredict();
        });

        this.container.querySelector('#dl-st-export')?.addEventListener('click', () => {
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

    private parseOptionalJson<T>(inputId: string): T | undefined {
        const input = this.container.querySelector(`#${inputId}`) as HTMLTextAreaElement | null;
        if (!input || !input.value.trim()) {
            return undefined;
        }

        try {
            return JSON.parse(input.value) as T;
        } catch {
            throw new Error('targets 不是合法 JSON');
        }
    }

    private setStatus(message: string, type: 'success' | 'warning' | 'error' | 'loading' = 'success'): void {
        const status = this.container.querySelector('#dl-st-status') as HTMLElement | null;
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
        const result = this.container.querySelector('#dl-st-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelType(): 'st_transformer' | 'gcn_lstm' | 'convlstm' | 'stgcn' {
        const model = (this.container.querySelector('#dl-st-model') as HTMLSelectElement | null)?.value || 'st_transformer';
        if (model === 'gcn_lstm' || model === 'convlstm' || model === 'stgcn') {
            return model;
        }
        return 'st_transformer';
    }

    private validateSeriesLength(series: number[][][], expectedSeqLen: number): void {
        const invalid = series.some(node => node.length !== expectedSeqLen);
        if (invalid) {
            throw new Error(`series 的 seq_len 应与输入序列长度一致（当前要求 ${expectedSeqLen}）`);
        }
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练时空预测模型...', 'loading');
            const modelType = this.getModelType();
            const seqLen = Number((this.container.querySelector('#dl-st-seq-len') as HTMLInputElement | null)?.value || 8);
            const predHorizon = Number((this.container.querySelector('#dl-st-horizon') as HTMLInputElement | null)?.value || 3);
            const epochs = Number((this.container.querySelector('#dl-st-epochs') as HTMLInputElement | null)?.value || 20);
            const coords = this.parseJson<Array<[number, number]>>('dl-st-coords', 'coords');
            const series = this.parseJson<number[][][]>('dl-st-series', 'series');
            const targets = this.parseOptionalJson<number[][]>('dl-st-targets');
            this.validateSeriesLength(series, seqLen);

            const response = await this.apiService.trainSpatiotemporal({
                model_type: modelType,
                coords,
                series,
                targets,
                epochs,
                pred_horizon: predHorizon
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('时空预测模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行时空预测...', 'loading');
            const modelType = this.getModelType();
            const seqLen = Number((this.container.querySelector('#dl-st-seq-len') as HTMLInputElement | null)?.value || 8);
            const predHorizon = Number((this.container.querySelector('#dl-st-horizon') as HTMLInputElement | null)?.value || 3);
            const fusionStrategy = (this.container.querySelector('#dl-st-fusion') as HTMLSelectElement | null)?.value || 'gating';
            const blendRatio = Number((this.container.querySelector('#dl-st-blend') as HTMLInputElement | null)?.value || 0.7);
            const coords = this.parseJson<Array<[number, number]>>('dl-st-coords', 'coords');
            const series = this.parseJson<number[][][]>('dl-st-series', 'series');
            const targets = this.parseOptionalJson<number[][]>('dl-st-targets');
            this.validateSeriesLength(series, seqLen);

            const response = await this.apiService.predictSpatiotemporal({
                model_type: modelType,
                coords,
                series,
                pred_horizon: predHorizon,
                fusion_strategy: fusionStrategy as 'concat' | 'add' | 'gating',
                targets,
                blend_ratio: blendRatio,
                uncertainty_method: 'mc_dropout',
                enable_memory_optimization: false,
                enable_gpu_acceleration: false,
                enable_inference_acceleration: true,
                enable_long_sequence_optimization: false,
                long_sequence_chunk: 48
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('时空预测完成', 'success');
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
        link.download = `spatiotemporal-result-${Date.now()}.json`;
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
