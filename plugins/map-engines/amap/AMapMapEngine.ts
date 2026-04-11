import type {
  Plugin,
  PluginContext,
  PluginType
} from '../../../apps/frontend/js/types/plugin';

/**
 * 高德地图引擎插件
 * 目前复用前端主工程中的 AMapEngine 实现。
 */
export default class AMapMapEngine implements Plugin {
  id = 'amap-engine';
  name = '高德地图引擎';
  version = '1.0.0';
  type: PluginType = 'map-engine' as any;
  description = '高德地图引擎插件，负责注册 AMap 能力到插件系统';

  private context?: PluginContext;

  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    context.app.registerService('map-engine:amap', {
      provider: 'amap',
      label: '高德',
      createEngine: async () => {
        const mod = await import('../../../apps/frontend/js/map/core/AMapEngine');
        return new mod.AMapEngine();
      }
    });
  }

  async activate(): Promise<void> {
    this.context?.events.emit('plugin:map-engine:activated', {
      engine: this.id,
      provider: 'amap',
      timestamp: new Date()
    });
  }

  async deactivate(): Promise<void> {
    this.context?.events.emit('plugin:map-engine:deactivated', {
      engine: this.id,
      provider: 'amap',
      timestamp: new Date()
    });
  }

  async destroy(): Promise<void> {
    await this.deactivate();
  }
}
