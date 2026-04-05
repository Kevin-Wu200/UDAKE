import type { PollutantDefinition } from '../../types/pollutant';
import type { STPredictionSnapshot, STSeriesInput } from '../../types/spatiotemporal';
import { SpatiotemporalService } from '../services/SpatiotemporalService';
import { SpatiotemporalVisualizer } from './SpatiotemporalVisualizer';

export interface STKrigingPanelOptions {
    pollutants: PollutantDefinition[];
    baseURL?: string;
}

export class STKrigingPanel {
    private readonly container: HTMLElement;
    private readonly service: SpatiotemporalService;
    private readonly visualizer: SpatiotemporalVisualizer;

    constructor(container: HTMLElement, options: STKrigingPanelOptions) {
        this.container = container;
        this.service = new SpatiotemporalService(options.baseURL);

        this.container.innerHTML = `
            <section class="st-kriging-panel">
                <header class="st-kriging-header">
                    <h3>时空克里金分析</h3>
                    <div class="st-kriging-actions">
                        <button id="st-train-btn" type="button">训练模型</button>
                        <button id="st-predict-btn" type="button">执行预测</button>
                    </div>
                </header>
                <div id="st-kriging-status">等待操作</div>
                <div id="st-visualizer-root"></div>
            </section>
        `;

        const root = this.container.querySelector('#st-visualizer-root') as HTMLElement | null;
        if (!root) {
            throw new Error('缺少可视化挂载节点');
        }
        this.visualizer = new SpatiotemporalVisualizer(root, {
            pollutants: options.pollutants
        });

        this.bindEvents();
    }

    private bindEvents(): void {
        this.container.querySelector('#st-train-btn')?.addEventListener('click', () => {
            void this.handleTrain();
        });

        this.container.querySelector('#st-predict-btn')?.addEventListener('click', () => {
            void this.handlePredict();
        });
    }

    private setStatus(message: string): void {
        const status = this.container.querySelector('#st-kriging-status') as HTMLElement | null;
        if (status) {
            status.textContent = message;
        }
    }

    private buildDemoSeries(): STSeriesInput {
        return {
            x: [0, 10, 20, 30],
            y: [0, 5, 10, 15],
            z: [0, 1, 2, 1],
            t: [1, 2, 3, 4],
            value: [30, 45, 35, 60]
        };
    }

    private async handleTrain(): Promise<void> {
        try {
            this.setStatus('正在训练时空克里金模型...');
            const response = await this.service.train({
                data: this.buildDemoSeries(),
                model_type: 'separated',
                options: {
                    variogram_model: 'spherical'
                }
            });
            const modelId = String((response.data as Record<string, unknown>).model_id || 'unknown');
            this.setStatus(`训练完成，模型ID: ${modelId}`);
        } catch (error) {
            this.setStatus(`训练失败: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    private async handlePredict(): Promise<void> {
        try {
            this.setStatus('正在执行预测...');
            const response = await this.service.predict({
                model_id: 'latest',
                target_positions: {
                    x: [2, 8, 16],
                    y: [2, 7, 14],
                    z: [0, 1, 1]
                },
                target_times: [5, 6, 7],
                prediction_days: 7
            });

            const snapshots = this.toSnapshots(response.data as Record<string, unknown>);
            if (snapshots.length === 0) {
                this.setStatus('预测完成，但无可视化数据');
                return;
            }

            await this.visualizer.loadSnapshots(snapshots);
            this.setStatus(`预测完成，加载 ${snapshots.length} 个时刻`);
        } catch (error) {
            this.setStatus(`预测失败: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    private toSnapshots(data: Record<string, unknown>): STPredictionSnapshot[] {
        const points = (data.points as Array<Record<string, unknown>> | undefined) || [];
        return points.map((point, index) => ({
            timestamp: String(point.timestamp || `T${index + 1}`),
            location: {
                x: Number(point.x || 0),
                y: Number(point.y || 0),
                z: Number(point.z || 0)
            },
            concentrations: [
                {
                    pollutantId: 'pm25',
                    value: Number(point.value || 0),
                    unit: 'ug/m3',
                    level: 'medium'
                }
            ],
            uncertainty: Number(point.uncertainty || 0.12),
            decayRate: {
                day1: 5,
                day7: 15,
                day15: 30
            }
        }));
    }

    destroy(): void {
        this.visualizer.destroy();
        this.container.innerHTML = '';
    }
}
