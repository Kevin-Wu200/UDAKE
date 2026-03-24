import type { IAPIService } from '../../types/api';

/**
 * 强化学习采样优化子面板
 */
export class SamplingRLPanel {
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
                    <h4>强化学习采样优化</h4>
                    <p>根据不确定性分布推荐高价值采样点</p>
                </div>

                <div class="dl-form-grid">
                    <label class="dl-field">
                        <span>模型类型</span>
                        <select id="dl-rl-model" class="select">
                            <option value="ppo">PPO</option>
                            <option value="dqn">DQN</option>
                            <option value="a2c">A2C</option>
                            <option value="a3c">A3C</option>
                        </select>
                    </label>
                    <label class="dl-field">
                        <span>训练轮数</span>
                        <input id="dl-rl-episodes" class="input" type="number" min="5" max="500" value="30">
                    </label>
                    <label class="dl-field">
                        <span>采样预算</span>
                        <input id="dl-rl-budget" class="input" type="number" min="8" max="200" value="20">
                    </label>
                    <label class="dl-field">
                        <span>推荐点数量</span>
                        <input id="dl-rl-count" class="input" type="number" min="1" max="100" value="10">
                    </label>
                    <label class="dl-field">
                        <span>融合策略</span>
                        <select id="dl-rl-strategy" class="select">
                            <option value="hybrid">Hybrid</option>
                            <option value="rl_only">RL Only</option>
                            <option value="rule_only">Rule Only</option>
                        </select>
                    </label>
                </div>

                <label class="dl-field dl-field-full">
                    <span>不确定性矩阵 uncertainty_map（JSON）</span>
                    <textarea id="dl-rl-map" class="dl-textarea" rows="5">[[0.2,0.4,0.8],[0.3,0.9,0.6],[0.1,0.5,0.7]]</textarea>
                </label>

                <label class="dl-field dl-field-full">
                    <span>已有采样点 existing_points（JSON）</span>
                    <textarea id="dl-rl-points" class="dl-textarea" rows="3">[[0,0],[1,1]]</textarea>
                </label>

                <div class="dl-actions">
                    <button id="dl-rl-train" class="btn btn-primary">训练策略</button>
                    <button id="dl-rl-recommend" class="btn btn-secondary">生成推荐</button>
                    <button id="dl-rl-export" class="btn btn-export">导出结果</button>
                </div>

                <div id="dl-rl-status" class="status-message"></div>
                <pre id="dl-rl-result" class="dl-result">暂无结果</pre>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelector('#dl-rl-train')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#dl-rl-recommend')?.addEventListener('click', () => {
            void this.handleRecommend();
        });

        this.container.querySelector('#dl-rl-export')?.addEventListener('click', () => {
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
        const status = this.container.querySelector('#dl-rl-status') as HTMLElement | null;
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
        const result = this.container.querySelector('#dl-rl-result') as HTMLElement | null;
        if (!result) {
            return;
        }
        result.textContent = JSON.stringify(data, null, 2);
    }

    private getModelName(): 'ppo' | 'dqn' | 'a2c' | 'a3c' {
        const model = (this.container.querySelector('#dl-rl-model') as HTMLSelectElement | null)?.value || 'ppo';
        if (model === 'dqn' || model === 'a2c' || model === 'a3c') {
            return model;
        }
        return 'ppo';
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练强化学习采样模型...', 'loading');
            const modelName = this.getModelName();
            const episodes = Number((this.container.querySelector('#dl-rl-episodes') as HTMLInputElement | null)?.value || 30);
            const budget = Number((this.container.querySelector('#dl-rl-budget') as HTMLInputElement | null)?.value || 20);
            const uncertaintyMap = this.parseJson<number[][]>('dl-rl-map', 'uncertainty_map');
            const existingPoints = this.parseJson<Array<[number, number]>>('dl-rl-points', 'existing_points');

            const response = await this.apiService.trainSamplingRL({
                model_name: modelName,
                uncertainty_map: uncertaintyMap,
                existing_points: existingPoints,
                episodes,
                budget
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('强化学习采样模型训练完成', 'success');
        } catch (error) {
            this.setStatus(`训练失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private async handleRecommend(): Promise<void> {
        try {
            this.setStatus('正在生成采样推荐...', 'loading');
            const modelName = this.getModelName();
            const recommendCount = Number((this.container.querySelector('#dl-rl-count') as HTMLInputElement | null)?.value || 10);
            const fusionStrategy = (this.container.querySelector('#dl-rl-strategy') as HTMLSelectElement | null)?.value || 'hybrid';
            const uncertaintyMap = this.parseJson<number[][]>('dl-rl-map', 'uncertainty_map');
            const existingPoints = this.parseJson<Array<[number, number]>>('dl-rl-points', 'existing_points');

            const response = await this.apiService.recommendSamplingRL({
                model_name: modelName,
                uncertainty_map: uncertaintyMap,
                existing_points: existingPoints,
                n_recommendations: recommendCount,
                fusion_strategy: fusionStrategy as 'rl_only' | 'rule_only' | 'hybrid',
                realtime: true
            });

            this.lastResult = response;
            this.setResult(response);
            this.setStatus('采样推荐生成完成', 'success');
        } catch (error) {
            this.setStatus(`推荐失败：${error instanceof Error ? error.message : String(error)}`, 'error');
        }
    }

    private exportResult(): void {
        if (!this.lastResult) {
            this.setStatus('没有可导出的结果，请先训练或推荐', 'warning');
            return;
        }

        const blob = new Blob([JSON.stringify(this.lastResult, null, 2)], {
            type: 'application/json;charset=utf-8'
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `sampling-rl-result-${Date.now()}.json`;
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
