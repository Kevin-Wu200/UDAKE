export interface DecayPoint {
    day: number;
    value: number;
}

export interface DecaySummary {
    day1: number;
    day7: number;
    day15: number;
}

export class PrecisionDecayIndicator {
    private readonly container: HTMLElement;

    constructor(container: HTMLElement) {
        this.container = container;
        this.render({ day1: 1, day7: 1, day15: 1 });
    }

    render(summary: DecaySummary): void {
        const points: DecayPoint[] = [
            { day: 1, value: summary.day1 },
            { day: 7, value: summary.day7 },
            { day: 15, value: summary.day15 }
        ];

        const rows = points.map((point) => {
            const percent = `${Math.max(0, Math.min(100, point.value * 100)).toFixed(1)}%`;
            return `<li data-day="${point.day}">D${point.day}: ${percent}</li>`;
        }).join('');

        this.container.innerHTML = `
            <section class="st-precision-decay">
                <h4>精度衰减</h4>
                <ul>${rows}</ul>
            </section>
        `;
    }

    destroy(): void {
        this.container.innerHTML = '';
    }
}
