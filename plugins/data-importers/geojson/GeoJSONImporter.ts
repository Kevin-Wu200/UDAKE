/**
 * GeoJSON 数据导入插件
 * 支持导入和解析 GeoJSON 格式的地理空间数据
 */

import type {
  Plugin,
  PluginContext,
  PluginType
} from '../../../apps/frontend/js/types/plugin';

/**
 * 导入配置
 */
interface ImportConfig {
  maxFileSize: number;
  supportedFeatures: string[];
}

/**
 * 导入结果
 */
interface ImportResult {
  success: boolean;
  data?: any;
  error?: string;
  features?: number;
  fileType?: string;
  fileSize?: number;
}

/**
 * GeoJSON 数据导入插件类
 */
export default class GeoJSONImporter implements Plugin {
  id = 'geojson-importer';
  name = 'GeoJSON 数据导入插件';
  version = '1.0.0';
  type: PluginType = 'data-importer' as any;
  description = '支持导入和解析 GeoJSON 格式的地理空间数据';

  private context?: PluginContext;
  private config?: ImportConfig;

  /**
   * 初始化插件
   */
  async initialize(context: PluginContext): Promise<void> {
    this.context = context;
    this.config = context.config as ImportConfig;

    console.log('[GeoJSONImporter] 初始化 GeoJSON 数据导入插件');

    // 注册数据导入服务
    context.app.registerService('data-importer', this, true);

    // 监听数据导入事件
    context.events.on('data:import', this.onDataImport.bind(this));
  }

  /**
   * 激活插件
   */
  async activate(): Promise<void> {
    console.log('[GeoJSONImporter] 激活 GeoJSON 数据导入插件');

    // 发射激活事件
    this.context?.events.emit('plugin:data-importer:activated', {
      importer: this.id,
      timestamp: new Date()
    });
  }

  /**
   * 停用插件
   */
  async deactivate(): Promise<void> {
    console.log('[GeoJSONImporter] 停用 GeoJSON 数据导入插件');

    // 发射停用事件
    this.context?.events.emit('plugin:data-importer:deactivated', {
      importer: this.id,
      timestamp: new Date()
    });
  }

  /**
   * 销毁插件
   */
  async destroy(): Promise<void> {
    console.log('[GeoJSONImporter] 销毁 GeoJSON 数据导入插件');

    await this.deactivate();
  }

  /**
   * 导入 GeoJSON 数据
   * @param file 文件对象
   * @returns 导入结果
   */
  async import(file: File): Promise<ImportResult> {
    console.log('[GeoJSONImporter] 开始导入文件', file.name);

    try {
      // 检查文件大小
      if (file.size > (this.config?.maxFileSize || 10485760)) {
        throw new Error(`文件大小超过限制 (${this.config?.maxFileSize || 10485760} bytes)`);
      }

      // 检查文件类型
      if (!file.name.endsWith('.json') && !file.name.endsWith('.geojson')) {
        throw new Error('不支持的文件类型，仅支持 .json 和 .geojson 文件');
      }

      // 读取文件内容
      const content = await this.readFile(file);

      // 解析 JSON
      const data = JSON.parse(content);

      // 验证 GeoJSON 格式
      this.validateGeoJSON(data);

      // 获取要素数量
      const features = this.countFeatures(data);

      const result: ImportResult = {
        success: true,
        data,
        features,
        fileType: 'geojson',
        fileSize: file.size
      };

      // 发射导入成功事件
      this.context?.events.emit('data:imported', {
        importer: this.id,
        result,
        timestamp: new Date()
      });

      console.log('[GeoJSONImporter] 文件导入成功', result);
      return result;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      const result: ImportResult = {
        success: false,
        error: errorMessage
      };

      // 发射导入失败事件
      this.context?.events.emit('data:import:failed', {
        importer: this.id,
        error: errorMessage,
        timestamp: new Date()
      });

      console.error('[GeoJSONImporter] 文件导入失败', error);
      return result;
    }
  }

  /**
   * 从字符串导入 GeoJSON 数据
   * @param content GeoJSON 字符串内容
   * @returns 导入结果
   */
  async importFromString(content: string): Promise<ImportResult> {
    console.log('[GeoJSONImporter] 从字符串导入数据');

    try {
      // 解析 JSON
      const data = JSON.parse(content);

      // 验证 GeoJSON 格式
      this.validateGeoJSON(data);

      // 获取要素数量
      const features = this.countFeatures(data);

      const result: ImportResult = {
        success: true,
        data,
        features,
        fileType: 'geojson'
      };

      // 发射导入成功事件
      this.context?.events.emit('data:imported', {
        importer: this.id,
        result,
        timestamp: new Date()
      });

      console.log('[GeoJSONImporter] 数据导入成功', result);
      return result;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);

      const result: ImportResult = {
        success: false,
        error: errorMessage
      };

      // 发射导入失败事件
      this.context?.events.emit('data:import:failed', {
        importer: this.id,
        error: errorMessage,
        timestamp: new Date()
      });

      console.error('[GeoJSONImporter] 数据导入失败', error);
      return result;
    }
  }

  /**
   * 读取文件内容
   * @param file 文件对象
   * @returns 文件内容
   */
  private readFile(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (event) => {
        resolve(event.target?.result as string);
      };

      reader.onerror = (error) => {
        reject(new Error('文件读取失败'));
      };

      reader.readAsText(file);
    });
  }

  /**
   * 验证 GeoJSON 格式
   * @param data 数据对象
   */
  private validateGeoJSON(data: any): void {
    if (!data || typeof data !== 'object') {
      throw new Error('无效的 GeoJSON 数据');
    }

    if (!data.type) {
      throw new Error('GeoJSON 数据缺少 type 字段');
    }

    const supportedFeatures = this.config?.supportedFeatures || [
      'Point', 'LineString', 'Polygon', 'MultiPoint',
      'MultiLineString', 'MultiPolygon', 'GeometryCollection',
      'Feature', 'FeatureCollection'
    ];

    if (!supportedFeatures.includes(data.type)) {
      throw new Error(`不支持的 GeoJSON 类型: ${data.type}`);
    }

    // 如果是 FeatureCollection，验证 features 字段
    if (data.type === 'FeatureCollection') {
      if (!Array.isArray(data.features)) {
        throw new Error('FeatureCollection 缺少 features 数组');
      }

      // 验证每个要素
      data.features.forEach((feature: any, index: number) => {
        if (!feature.type || feature.type !== 'Feature') {
          throw new Error(`要素 ${index} 不是有效的 Feature 对象`);
        }

        if (!feature.geometry) {
          throw new Error(`要素 ${index} 缺少 geometry 字段`);
        }

        if (!feature.geometry.type) {
          throw new Error(`要素 ${index} 的 geometry 缺少 type 字段`);
        }
      });
    }

    // 如果是 Feature，验证 geometry 字段
    if (data.type === 'Feature') {
      if (!data.geometry) {
        throw new Error('Feature 缺少 geometry 字段');
      }

      if (!data.geometry.type) {
        throw new Error('Feature 的 geometry 缺少 type 字段');
      }
    }
  }

  /**
   * 计算要素数量
   * @param data GeoJSON 数据
   * @returns 要素数量
   */
  private countFeatures(data: any): number {
    if (data.type === 'FeatureCollection') {
      return data.features?.length || 0;
    } else if (data.type === 'Feature') {
      return 1;
    } else {
      return 0;
    }
  }

  /**
   * 处理数据导入事件
   */
  private onDataImport(data: any): void {
    console.log('[GeoJSONImporter] 收到数据导入事件', data);
    // 这里可以根据需要处理数据导入事件
  }

  /**
   * 获取支持的文件格式
   * @returns 支持的文件格式列表
   */
  getSupportedFormats(): string[] {
    return ['.json', '.geojson'];
  }

  /**
   * 获取最大文件大小
   * @returns 最大文件大小（字节）
   */
  getMaxFileSize(): number {
    return this.config?.maxFileSize || 10485760;
  }

  /**
   * 获取支持的要素类型
   * @returns 支持的要素类型列表
   */
  getSupportedFeatures(): string[] {
    return this.config?.supportedFeatures || [];
  }

  /**
   * 导出 GeoJSON 数据
   * @param data 数据对象
   * @returns GeoJSON 字符串
   */
  export(data: any): string {
    console.log('[GeoJSONImporter] 导出 GeoJSON 数据');

    try {
      // 验证数据
      this.validateGeoJSON(data);

      // 转换为 JSON 字符串
      const jsonString = JSON.stringify(data, null, 2);

      // 发射导出事件
      this.context?.events.emit('data:exported', {
        importer: this.id,
        data,
        timestamp: new Date()
      });

      return jsonString;

    } catch (error) {
      console.error('[GeoJSONImporter] 数据导出失败', error);
      throw error;
    }
  }

  /**
   * 下载 GeoJSON 文件
   * @param data 数据对象
   * @param filename 文件名
   */
  download(data: any, filename: string = 'data.geojson'): void {
    console.log('[GeoJSONImporter] 下载 GeoJSON 文件', filename);

    try {
      const content = this.export(data);
      const blob = new Blob([content], { type: 'application/json' });
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();

      URL.revokeObjectURL(url);

      // 发射下载事件
      this.context?.events.emit('data:downloaded', {
        importer: this.id,
        filename,
        timestamp: new Date()
      });

    } catch (error) {
      console.error('[GeoJSONImporter] 文件下载失败', error);
      throw error;
    }
  }

  /**
   * 获取配置
   * @returns 导入配置
   */
  getConfig(): ImportConfig | undefined {
    return this.config;
  }

  /**
   * 更新配置
   * @param config 新配置
   */
  updateConfig(config: Partial<ImportConfig>): void {
    if (this.config) {
      this.config = { ...this.config, ...config };
      console.log('[GeoJSONImporter] 配置已更新', this.config);
    }
  }
}