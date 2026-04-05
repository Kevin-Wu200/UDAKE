import type { PollutantConcentration } from '../../types/pollutant';
import type { STPredictionSnapshot } from '../../types/spatiotemporal';

export interface SelectionStats {
    count: number;
    mean: number;
    min: number;
    max: number;
}

export class InfoPanel {
    private readonly container: HTMLElement;

    constructor(container: HTMLElement) {
        this.container = container;
        this.render();
    }

    private render(): void {
        this.container.innerHTML = `
            <div class="st-info-panel">
                <div><strong>当前时刻:</strong> <span id="st-info-time">--</span></div>
                <div><strong>预测值:</strong> <span id="st-info-prediction">--</span></div>
                <div><strong>不确定性:</strong> <span id="st-info-uncertainty">--</span></div>
                <div><strong>精度衰减:</strong> <span id="st-info-decay">--</span></div>
                <div><strong>悬停信息:</strong> <span id="st-info-hover">--</span></div>
                <div><strong>区域统计:</strong> <span id="st-info-selection">--</span></div>
            </div>
        `;
    }

    update(snapshot: STPredictionSnapshot): void {
        this.setText('st-info-time', snapshot.timestamp);
        this.setText('st-info-prediction', this.formatConcentrations(snapshot.concentrations));
        this.setText('st-info-uncertainty', `±${(snapshot.uncertainty * 100).toFixed(1)}%`);
        this.setText(
            'st-info-decay',
            `1天 ${snapshot.decayRate.day1}%, 7天 ${snapshot.decayRate.day7}%, 15天 ${snapshot.decayRate.day15}%`
        );
    }

    updateHover(text: string): void {
        this.setText('st-info-hover', text || '--');
    }

    updateSelectionStats(stats: SelectionStats): void {
        this.setText(
            'st-info-selection',
            `数量 ${stats.count}, 均值 ${stats.mean.toFixed(2)}, 最小 ${stats.min.toFixed(2)}, 最大 ${stats.max.toFixed(2)}`
        );
    }

    private formatConcentrations(concentrations: PollutantConcentration[]): string {
        if (!concentrations.length) {
            return '--';
        }
        return concentrations.map(item => `${item.pollutantId}: ${item.value.toFixed(2)} ${item.unit}`).join('; ');
    }

    private setText(id: string, value: string): void {
        const element = this.container.querySelector(`#${id}`) as HTMLElement | null;
        if (element) {
            element.textContent = value;
        }
    }

    destroy(): void {
        this.container.innerHTML = '';
    }
}
