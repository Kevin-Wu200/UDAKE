import type { PollutantDefinition, PollutantLayerState } from '../../types/pollutant';

export interface PollutantLayerManagerEvents {
    onLayerVisibilityChange?: (layerId: string, visible: boolean) => void;
    onLayerOpacityChange?: (layerId: string, opacity: number) => void;
    onLayerOrderChange?: (layers: PollutantLayerState[]) => void;
    onLegendExport?: (json: string) => void;
}

export class PollutantLayerManager {
    private readonly container: HTMLElement;
    private readonly events: PollutantLayerManagerEvents;
    private readonly definitions: PollutantDefinition[];
    private states: PollutantLayerState[];

    constructor(container: HTMLElement, definitions: PollutantDefinition[], events: PollutantLayerManagerEvents = {}) {
        this.container = container;
        this.events = events;
        this.definitions = definitions;
        this.states = definitions.map((definition, index) => ({
            pollutantId: definition.id,
            visible: true,
            opacity: 0.8,
            order: index
        }));

        this.render();
        this.bindEvents();
    }

    getStates(): PollutantLayerState[] {
        return [...this.states].sort((a, b) => a.order - b.order);
    }

    setLayerVisibility(layerId: string, visible: boolean): void {
        this.states = this.states.map(state => state.pollutantId === layerId ? { ...state, visible } : state);
        this.render();
        this.bindEvents();
        this.events.onLayerVisibilityChange?.(layerId, visible);
    }

    setLayerOpacity(layerId: string, opacity: number): void {
        const normalized = Math.max(0, Math.min(1, opacity));
        this.states = this.states.map(state => state.pollutantId === layerId ? { ...state, opacity: normalized } : state);
        this.render();
        this.bindEvents();
        this.events.onLayerOpacityChange?.(layerId, normalized);
    }

    moveLayer(layerId: string, direction: 'up' | 'down'): void {
        const ordered = this.getStates();
        const index = ordered.findIndex(item => item.pollutantId === layerId);
        if (index < 0) {
            return;
        }

        const targetIndex = direction === 'up' ? index - 1 : index + 1;
        if (targetIndex < 0 || targetIndex >= ordered.length) {
            return;
        }

        const tmp = ordered[index];
        ordered[index] = ordered[targetIndex];
        ordered[targetIndex] = tmp;
        this.states = ordered.map((item, idx) => ({ ...item, order: idx }));

        this.render();
        this.bindEvents();
        this.events.onLayerOrderChange?.(this.getStates());
    }

    exportLegend(): string {
        const legend = this.definitions.map(definition => ({
            pollutantId: definition.id,
            pollutantName: definition.name,
            unit: definition.unit,
            thresholds: definition.thresholds,
            colors: definition.colorStops
        }));
        const json = JSON.stringify(legend, null, 2);
        this.events.onLegendExport?.(json);
        return json;
    }

    private render(): void {
        const rows = this.getStates().map(state => {
            const definition = this.definitions.find(item => item.id === state.pollutantId);
            const name = definition?.name || state.pollutantId;
            return `
                <div class="st-layer-row" data-layer-id="${state.pollutantId}">
                    <label>
                        <input class="st-layer-visible" type="checkbox" ${state.visible ? 'checked' : ''}>
                        ${name}
                    </label>
                    <input class="st-layer-opacity" type="range" min="0" max="1" step="0.05" value="${state.opacity}">
                    <button class="st-layer-up" type="button">↑</button>
                    <button class="st-layer-down" type="button">↓</button>
                </div>
            `;
        }).join('');

        this.container.innerHTML = `
            <div class="st-layer-manager">
                <div class="st-layer-header">
                    <strong>图层管理</strong>
                    <button id="st-export-legend" type="button">导出图例</button>
                </div>
                <div class="st-layer-list">${rows}</div>
            </div>
        `;
    }

    private bindEvents(): void {
        this.container.querySelectorAll('.st-layer-row').forEach(row => {
            const layerId = row.getAttribute('data-layer-id');
            if (!layerId) {
                return;
            }

            const visibleInput = row.querySelector('.st-layer-visible') as HTMLInputElement | null;
            visibleInput?.addEventListener('change', () => this.setLayerVisibility(layerId, visibleInput.checked));

            const opacityInput = row.querySelector('.st-layer-opacity') as HTMLInputElement | null;
            opacityInput?.addEventListener('input', () => this.setLayerOpacity(layerId, Number(opacityInput.value)));

            row.querySelector('.st-layer-up')?.addEventListener('click', () => this.moveLayer(layerId, 'up'));
            row.querySelector('.st-layer-down')?.addEventListener('click', () => this.moveLayer(layerId, 'down'));
        });

        this.container.querySelector('#st-export-legend')?.addEventListener('click', () => {
            this.exportLegend();
        });
    }

    destroy(): void {
        this.container.innerHTML = '';
    }
}
