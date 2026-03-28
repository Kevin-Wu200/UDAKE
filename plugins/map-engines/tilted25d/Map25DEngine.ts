/**
 * 2.5D 地图引擎插件
 * 提供轻量级 2.5D 摄像机控制与热力图渲染配置接口
 */

import type {
    Plugin,
    PluginContext,
    PluginType
} from '../../../apps/frontend/js/types/plugin';

interface CameraOptions {
    rotation: number;
    tilt: number;
    zoom: number;
}

interface HeatmapOptions {
    radius: number;
    intensity: number;
    gradient: 'classic' | 'warm' | 'cool' | 'viridis';
}

interface EngineState {
    mode: '2d' | '2.5d';
    camera: CameraOptions;
    heatmap: HeatmapOptions;
}

export default class Map25DEngine implements Plugin {
    id = 'map25d-engine';
    name = '2.5D 地图引擎';
    version = '1.0.0';
    type: PluginType = 'map-engine' as any;
    description = '支持 2.5D 相机控制与交互式热力图的地图引擎插件';

    private context?: PluginContext;
    private state: EngineState = {
        mode: '2d',
        camera: {
            rotation: 32,
            tilt: 48,
            zoom: 1
        },
        heatmap: {
            radius: 36,
            intensity: 0.9,
            gradient: 'classic'
        }
    };

    async initialize(context: PluginContext): Promise<void> {
        this.context = context;
        context.app.registerService('map-2_5d-engine', this, true);

        context.events.on('map25d:mode', (payload: { mode: '2d' | '2.5d' }) => {
            this.setMode(payload.mode);
        });

        context.events.on('map25d:camera', (payload: Partial<CameraOptions>) => {
            this.updateCamera(payload);
        });

        context.events.on('map25d:heatmap', (payload: Partial<HeatmapOptions>) => {
            this.updateHeatmap(payload);
        });
    }

    async activate(): Promise<void> {
        this.context?.events.emit('plugin:map25d:activated', {
            engine: this.id,
            state: this.getState(),
            timestamp: new Date().toISOString()
        });
    }

    async deactivate(): Promise<void> {
        this.context?.events.emit('plugin:map25d:deactivated', {
            engine: this.id,
            timestamp: new Date().toISOString()
        });
    }

    async destroy(): Promise<void> {
        await this.deactivate();
    }

    setMode(mode: '2d' | '2.5d'): void {
        this.state.mode = mode;
        this.emitStateChanged();
    }

    updateCamera(camera: Partial<CameraOptions>): void {
        this.state.camera = {
            ...this.state.camera,
            ...camera
        };
        this.emitStateChanged();
    }

    updateHeatmap(heatmap: Partial<HeatmapOptions>): void {
        this.state.heatmap = {
            ...this.state.heatmap,
            ...heatmap
        };
        this.emitStateChanged();
    }

    getState(): EngineState {
        return {
            mode: this.state.mode,
            camera: { ...this.state.camera },
            heatmap: { ...this.state.heatmap }
        };
    }

    private emitStateChanged(): void {
        this.context?.events.emit('map25d:state-changed', {
            engine: this.id,
            state: this.getState(),
            timestamp: new Date().toISOString()
        });
    }
}
