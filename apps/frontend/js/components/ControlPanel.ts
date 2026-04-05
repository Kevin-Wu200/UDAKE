import type { PollutantDefinition } from '../../types/pollutant';

export interface ControlPanelEvents {
    onPollutantsChange?: (pollutantIds: string[]) => void;
    onTimeSpeedChange?: (speed: number) => void;
    onViewAction?: (action: 'rotate-left' | 'rotate-right' | 'zoom-in' | 'zoom-out' | 'pan-left' | 'pan-right' | 'save' | 'restore') => void;
}

export class ControlPanel {
    private readonly container: HTMLElement;
    private readonly pollutants: PollutantDefinition[];
    private readonly events: ControlPanelEvents;

    constructor(container: HTMLElement, pollutants: PollutantDefinition[], events: ControlPanelEvents = {}) {
        this.container = container;
        this.pollutants = pollutants;
        this.events = events;
        this.render();
        this.bindEvents();
    }

    private render(): void {
        const pollutantOptions = this.pollutants.map(item => `
            <label>
                <input type="checkbox" class="st-control-pollutant" value="${item.id}" checked>
                ${item.name}
            </label>
        `).join('');

        this.container.innerHTML = `
            <div class="st-control-panel">
                <section>
                    <h4>污染物选择</h4>
                    <div class="st-control-pollutants">${pollutantOptions}</div>
                </section>
                <section>
                    <h4>时间速度</h4>
                    <select id="st-control-speed">
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1x</option>
                        <option value="2">2x</option>
                        <option value="4">4x</option>
                    </select>
                </section>
                <section>
                    <h4>视角控制</h4>
                    <div class="st-control-view-actions">
                        <button data-action="rotate-left" type="button">左旋</button>
                        <button data-action="rotate-right" type="button">右旋</button>
                        <button data-action="zoom-in" type="button">放大</button>
                        <button data-action="zoom-out" type="button">缩小</button>
                        <button data-action="pan-left" type="button">左移</button>
                        <button data-action="pan-right" type="button">右移</button>
                        <button data-action="save" type="button">保存视角</button>
                        <button data-action="restore" type="button">恢复视角</button>
                    </div>
                </section>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelectorAll('.st-control-pollutant').forEach(input => {
            input.addEventListener('change', () => {
                const selected = Array.from(this.container.querySelectorAll('.st-control-pollutant'))
                    .filter(node => (node as HTMLInputElement).checked)
                    .map(node => (node as HTMLInputElement).value);
                this.events.onPollutantsChange?.(selected);
            });
        });

        const speedSelect = this.container.querySelector('#st-control-speed') as HTMLSelectElement | null;
        speedSelect?.addEventListener('change', () => {
            this.events.onTimeSpeedChange?.(Number(speedSelect.value));
        });

        this.container.querySelectorAll('[data-action]').forEach(button => {
            button.addEventListener('click', () => {
                const action = button.getAttribute('data-action') as
                    | 'rotate-left'
                    | 'rotate-right'
                    | 'zoom-in'
                    | 'zoom-out'
                    | 'pan-left'
                    | 'pan-right'
                    | 'save'
                    | 'restore';
                if (action) {
                    this.events.onViewAction?.(action);
                }
            });
        });
    }

    destroy(): void {
        this.container.innerHTML = '';
    }
}
