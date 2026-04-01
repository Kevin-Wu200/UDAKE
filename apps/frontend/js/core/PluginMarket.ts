/**
 * 插件市场
 * 提供插件的注册、发现、安装和更新功能
 */

import type { PluginManifest, PluginType } from '../types/plugin';

/**
 * 插件市场信息
 */
export interface PluginMarketInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  type: PluginType;
  downloadUrl: string;
  homepage?: string;
  repository?: string;
  license?: string;
  keywords?: string[];
  rating?: number;
  downloads?: number;
  updatedAt?: string;
  screenshot?: string;
  minAppVersion?: string;
  dependencies?: string[];
}

/**
 * 插件搜索结果
 */
export interface PluginSearchResult {
  plugins: PluginMarketInfo[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * 插件安装结果
 */
export interface PluginInstallResult {
  success: boolean;
  pluginId?: string;
  error?: string;
}

/**
 * 插件市场类
 */
export class PluginMarket {
  private baseUrl: string;
  private cache: Map<string, PluginMarketInfo> = new Map();
  private cacheTimeout: number = 5 * 60 * 1000; // 5分钟

  constructor(baseUrl: string = `${import.meta.env.VITE_OFFICIAL_WEB}/api/plugins`) {
    this.baseUrl = baseUrl;
  }

  /**
   * 搜索插件
   * @param query 搜索关键词
   * @param type 插件类型（可选）
   * @param page 页码
   * @param pageSize 每页数量
   * @returns 搜索结果
   */
  async searchPlugins(
    query: string,
    type?: PluginType,
    page: number = 1,
    pageSize: number = 20
  ): Promise<PluginSearchResult> {
    console.log(`[PluginMarket] 搜索插件: ${query}`);

    try {
      const params = new URLSearchParams({
        q: query,
        page: page.toString(),
        pageSize: pageSize.toString()
      });

      if (type) {
        params.append('type', type);
      }

      const url = `${this.baseUrl}/plugins/search?${params}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`搜索插件失败: ${response.statusText}`);
      }

      const result: PluginSearchResult = await response.json();

      // 缓存结果
      result.plugins.forEach(plugin => {
        this.cache.set(plugin.id, plugin);
      });

      return result;

    } catch (error) {
      console.error('[PluginMarket] 搜索插件失败:', error);
      throw error;
    }
  }

  /**
   * 获取插件详情
   * @param pluginId 插件ID
   * @returns 插件信息
   */
  async getPluginInfo(pluginId: string): Promise<PluginMarketInfo> {
    console.log(`[PluginMarket] 获取插件详情: ${pluginId}`);

    // 检查缓存
    const cached = this.cache.get(pluginId);
    if (cached) {
      return cached;
    }

    try {
      const url = `${this.baseUrl}/plugins/${pluginId}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取插件详情失败: ${response.statusText}`);
      }

      const info: PluginMarketInfo = await response.json();

      // 缓存结果
      this.cache.set(pluginId, info);

      return info;

    } catch (error) {
      console.error('[PluginMarket] 获取插件详情失败:', error);
      throw error;
    }
  }

  /**
   * 获取插件列表
   * @param type 插件类型（可选）
   * @param page 页码
   * @param pageSize 每页数量
   * @returns 插件列表
   */
  async getPlugins(
    type?: PluginType,
    page: number = 1,
    pageSize: number = 20
  ): Promise<PluginSearchResult> {
    console.log(`[PluginMarket] 获取插件列表`);

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        pageSize: pageSize.toString()
      });

      if (type) {
        params.append('type', type);
      }

      const url = `${this.baseUrl}/plugins?${params}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取插件列表失败: ${response.statusText}`);
      }

      const result: PluginSearchResult = await response.json();

      // 缓存结果
      result.plugins.forEach(plugin => {
        this.cache.set(plugin.id, plugin);
      });

      return result;

    } catch (error) {
      console.error('[PluginMarket] 获取插件列表失败:', error);
      throw error;
    }
  }

  /**
   * 获取热门插件
   * @param limit 数量限制
   * @returns 插件列表
   */
  async getPopularPlugins(limit: number = 10): Promise<PluginMarketInfo[]> {
    console.log(`[PluginMarket] 获取热门插件`);

    try {
      const url = `${this.baseUrl}/plugins/popular?limit=${limit}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取热门插件失败: ${response.statusText}`);
      }

      const plugins: PluginMarketInfo[] = await response.json();

      // 缓存结果
      plugins.forEach(plugin => {
        this.cache.set(plugin.id, plugin);
      });

      return plugins;

    } catch (error) {
      console.error('[PluginMarket] 获取热门插件失败:', error);
      throw error;
    }
  }

  /**
   * 获取最新插件
   * @param limit 数量限制
   * @returns 插件列表
   */
  async getLatestPlugins(limit: number = 10): Promise<PluginMarketInfo[]> {
    console.log(`[PluginMarket] 获取最新插件`);

    try {
      const url = `${this.baseUrl}/plugins/latest?limit=${limit}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取最新插件失败: ${response.statusText}`);
      }

      const plugins: PluginMarketInfo[] = await response.json();

      // 缓存结果
      plugins.forEach(plugin => {
        this.cache.set(plugin.id, plugin);
      });

      return plugins;

    } catch (error) {
      console.error('[PluginMarket] 获取最新插件失败:', error);
      throw error;
    }
  }

  /**
   * 获取插件分类
   * @returns 分类列表
   */
  async getCategories(): Promise<string[]> {
    console.log(`[PluginMarket] 获取插件分类`);

    try {
      const url = `${this.baseUrl}/categories`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取插件分类失败: ${response.statusText}`);
      }

      const categories: string[] = await response.json();

      return categories;

    } catch (error) {
      console.error('[PluginMarket] 获取插件分类失败:', error);
      throw error;
    }
  }

  /**
   * 检查插件更新
   * @param pluginId 插件ID
   * @param currentVersion 当前版本
   * @returns 是否有更新
   */
  async checkUpdate(pluginId: string, currentVersion: string): Promise<{
    hasUpdate: boolean;
    latestVersion?: string;
    downloadUrl?: string;
  }> {
    console.log(`[PluginMarket] 检查插件更新: ${pluginId}`);

    try {
      const info = await this.getPluginInfo(pluginId);

      const hasUpdate = this.compareVersions(info.version, currentVersion) > 0;

      return {
        hasUpdate,
        latestVersion: hasUpdate ? info.version : undefined,
        downloadUrl: hasUpdate ? info.downloadUrl : undefined
      };

    } catch (error) {
      console.error('[PluginMarket] 检查插件更新失败:', error);
      return { hasUpdate: false };
    }
  }

  /**
   * 下载插件
   * @param pluginId 插件ID
   * @returns 插件内容
   */
  async downloadPlugin(pluginId: string): Promise<Blob> {
    console.log(`[PluginMarket] 下载插件: ${pluginId}`);

    try {
      const info = await this.getPluginInfo(pluginId);
      const response = await fetch(info.downloadUrl);

      if (!response.ok) {
        throw new Error(`下载插件失败: ${response.statusText}`);
      }

      return await response.blob();

    } catch (error) {
      console.error('[PluginMarket] 下载插件失败:', error);
      throw error;
    }
  }

  /**
   * 上报插件使用情况
   * @param pluginId 插件ID
   * @param version 插件版本
   */
  async reportUsage(pluginId: string, version: string): Promise<void> {
    console.log(`[PluginMarket] 上报插件使用: ${pluginId}`);

    try {
      const url = `${this.baseUrl}/plugins/${pluginId}/usage`;
      await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ version })
      });

    } catch (error) {
      console.error('[PluginMarket] 上报插件使用失败:', error);
      // 静默失败，不影响用户体验
    }
  }

  /**
   * 提交插件评分
   * @param pluginId 插件ID
   * @param rating 评分（1-5）
   * @param comment 评论（可选）
   */
  async submitRating(
    pluginId: string,
    rating: number,
    comment?: string
  ): Promise<void> {
    console.log(`[PluginMarket] 提交插件评分: ${pluginId}`);

    if (rating < 1 || rating > 5) {
      throw new Error('评分必须在1-5之间');
    }

    try {
      const url = `${this.baseUrl}/plugins/${pluginId}/rating`;
      await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ rating, comment })
      });

    } catch (error) {
      console.error('[PluginMarket] 提交插件评分失败:', error);
      throw error;
    }
  }

  /**
   * 获取插件评论
   * @param pluginId 插件ID
   * @param page 页码
   * @param pageSize 每页数量
   * @returns 评论列表
   */
  async getReviews(
    pluginId: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<any[]> {
    console.log(`[PluginMarket] 获取插件评论: ${pluginId}`);

    try {
      const params = new URLSearchParams({
        page: page.toString(),
        pageSize: pageSize.toString()
      });

      const url = `${this.baseUrl}/plugins/${pluginId}/reviews?${params}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`获取插件评论失败: ${response.statusText}`);
      }

      return await response.json();

    } catch (error) {
      console.error('[PluginMarket] 获取插件评论失败:', error);
      throw error;
    }
  }

  /**
   * 比较版本号
   * @param version1 版本1
   * @param version2 版本2
   * @returns 比较结果（1: version1 > version2, -1: version1 < version2, 0: 相等）
   */
  private compareVersions(version1: string, version2: string): number {
    const v1 = version1.split('.').map(Number);
    const v2 = version2.split('.').map(Number);

    for (let i = 0; i < Math.max(v1.length, v2.length); i++) {
      const n1 = v1[i] || 0;
      const n2 = v2[i] || 0;

      if (n1 > n2) return 1;
      if (n1 < n2) return -1;
    }

    return 0;
  }

  /**
   * 清除缓存
   */
  clearCache(): void {
    this.cache.clear();
    console.log('[PluginMarket] 缓存已清除');
  }

  /**
   * 获取缓存大小
   * @returns 缓存中的插件数量
   */
  getCacheSize(): number {
    return this.cache.size;
  }

  /**
   * 设置基础URL
   * @param baseUrl 基础URL
   */
  setBaseUrl(baseUrl: string): void {
    this.baseUrl = baseUrl;
    console.log(`[PluginMarket] 基础URL已设置为: ${baseUrl}`);
  }

  /**
   * 获取基础URL
   * @returns 基础URL
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }
}
