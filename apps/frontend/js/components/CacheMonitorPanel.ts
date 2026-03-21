/**
 * 缓存监控面板
 * 实时显示缓存统计信息和健康状态
 */

import { APIService } from '../services/API封装';

export interface CacheMonitorData {
  timestamp: number;
  memory: {
    hits: number;
    misses: number;
    size: number;
    hitRate: number;
  };
  disk: {
    hits: number;
    misses: number;
    size: number;
    hitRate: number;
  };
  total: {
    hits: number;
    misses: number;
    size: number;
    hitRate: number;
    avgResponseTime: number;
  };
  promotionCount: number;
}

export class CacheMonitorPanel {
  private panel: HTMLElement;
  private apiService: APIService;
  private updateInterval: number | null = null;
  private history: CacheMonitorData[] = [];
  private maxHistory = 60; // 保留60秒的历史数据

  constructor(apiService: APIService) {
    this.apiService = apiService;
    this.panel = this.createPanel();
    this.attachEventListeners();
  }

  private createPanel(): HTMLElement {
    const panel = document.createElement('div');
    panel.id = 'cache-monitor-panel';
    panel.className = 'cache-monitor-panel';
    panel.innerHTML = `
      <div class="cache-monitor-header">
        <h2 class="cache-monitor-title">缓存监控</h2>
        <div class="cache-monitor-controls">
          <button class="cache-monitor-btn cache-monitor-btn-primary" id="cache-monitor-refresh">
            刷新
          </button>
          <button class="cache-monitor-btn cache-monitor-btn-secondary" id="cache-monitor-reset">
            重置统计
          </button>
          <button class="cache-monitor-btn cache-monitor-btn-close" id="cache-monitor-close">
            ×
          </button>
        </div>
      </div>

      <div class="cache-monitor-content">
        <!-- 总体统计 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">总体统计</h3>
          <div class="cache-monitor-stats-grid">
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">总命中率</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-success" id="cache-monitor-hit-rate">
                0%
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">总请求数</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-total-requests">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">缓存大小</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-size">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">平均响应时间</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-response-time">
                0ms
              </div>
            </div>
          </div>
        </div>

        <!-- 内存缓存 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">内存缓存</h3>
          <div class="cache-monitor-stats-grid">
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">命中率</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-success" id="cache-monitor-memory-hit-rate">
                0%
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">命中次数</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-memory-hits">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">未命中次数</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-warning" id="cache-monitor-memory-misses">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">缓存大小</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-memory-size">
                0
              </div>
            </div>
          </div>
        </div>

        <!-- 磁盘缓存 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">磁盘缓存</h3>
          <div class="cache-monitor-stats-grid">
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">命中率</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-success" id="cache-monitor-disk-hit-rate">
                0%
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">命中次数</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-disk-hits">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">未命中次数</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-warning" id="cache-monitor-disk-misses">
                0
              </div>
            </div>
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">缓存大小</div>
              <div class="cache-monitor-stat-value" id="cache-monitor-disk-size">
                0
              </div>
            </div>
          </div>
        </div>

        <!-- 提升统计 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">提升统计</h3>
          <div class="cache-monitor-stats-grid">
            <div class="cache-monitor-stat-card">
              <div class="cache-monitor-stat-label">提升次数</div>
              <div class="cache-monitor-stat-value cache-monitor-stat-value-info" id="cache-monitor-promotion-count">
                0
              </div>
            </div>
          </div>
        </div>

        <!-- 实时图表 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">实时命中率</h3>
          <canvas id="cache-monitor-chart" width="800" height="200"></canvas>
        </div>

        <!-- 健康状态 -->
        <div class="cache-monitor-section">
          <h3 class="cache-monitor-section-title">健康状态</h3>
          <div class="cache-monitor-health" id="cache-monitor-health">
            <div class="cache-monitor-health-status cache-monitor-health-status-unknown">
              检测中...
            </div>
            <div class="cache-monitor-health-recommendations" id="cache-monitor-recommendations">
            </div>
          </div>
        </div>
      </div>
    `;

    return panel;
  }

  private attachEventListeners(): void {
    const refreshBtn = this.panel.querySelector('#cache-monitor-refresh');
    refreshBtn?.addEventListener('click', () => this.refresh());

    const resetBtn = this.panel.querySelector('#cache-monitor-reset');
    resetBtn?.addEventListener('click', () => this.resetStats());

    const closeBtn = this.panel.querySelector('#cache-monitor-close');
    closeBtn?.addEventListener('click', () => this.hide());
  }

  public show(): void {
    document.body.appendChild(this.panel);
    this.refresh();
    this.startAutoUpdate();
  }

  public hide(): void {
    this.stopAutoUpdate();
    if (this.panel.parentElement) {
      this.panel.parentElement.removeChild(this.panel);
    }
  }

  private startAutoUpdate(): void {
    if (this.updateInterval !== null) {
      return;
    }

    this.updateInterval = window.setInterval(() => {
      this.refresh();
    }, 1000); // 每秒更新一次
  }

  private stopAutoUpdate(): void {
    if (this.updateInterval !== null) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }
  }

  private refresh(): void {
    const stats = this.apiService.getCacheStats();

    // 更新总体统计
    this.updateElement('cache-monitor-hit-rate', `${(stats.total.hitRate * 100).toFixed(2)}%`);
    this.updateElement('cache-monitor-total-requests', stats.total.totalRequests.toLocaleString());
    this.updateElement('cache-monitor-size', stats.total.size.toLocaleString());
    this.updateElement('cache-monitor-response-time', `${stats.total.avgResponseTime.toFixed(2)}ms`);

    // 更新内存缓存统计
    this.updateElement('cache-monitor-memory-hit-rate', `${(stats.memory.hitRate * 100).toFixed(2)}%`);
    this.updateElement('cache-monitor-memory-hits', stats.memory.hits.toLocaleString());
    this.updateElement('cache-monitor-memory-misses', stats.memory.misses.toLocaleString());
    this.updateElement('cache-monitor-memory-size', stats.memory.size.toLocaleString());

    // 更新磁盘缓存统计
    this.updateElement('cache-monitor-disk-hit-rate', `${(stats.disk.hitRate * 100).toFixed(2)}%`);
    this.updateElement('cache-monitor-disk-hits', stats.disk.hits.toLocaleString());
    this.updateElement('cache-monitor-disk-misses', stats.disk.misses.toLocaleString());
    this.updateElement('cache-monitor-disk-size', stats.disk.size.toLocaleString());

    // 更新提升统计
    this.updateElement('cache-monitor-promotion-count', stats.promotionCount.toLocaleString());

    // 添加到历史记录
    this.addToHistory(stats);

    // 更新图表
    this.updateChart();

    // 更新健康状态
    this.updateHealthStatus();
  }

  private updateElement(id: string, value: string): void {
    const element = this.panel.querySelector(`#${id}`);
    if (element) {
      element.textContent = value;
    }
  }

  private addToHistory(stats: any): void {
    const data: CacheMonitorData = {
      timestamp: Date.now(),
      memory: {
        hits: stats.memory.hits,
        misses: stats.memory.misses,
        size: stats.memory.size,
        hitRate: stats.memory.hitRate
      },
      disk: {
        hits: stats.disk.hits,
        misses: stats.disk.misses,
        size: stats.disk.size,
        hitRate: stats.disk.hitRate
      },
      total: {
        hits: stats.total.hits,
        misses: stats.total.misses,
        size: stats.total.size,
        hitRate: stats.total.hitRate,
        avgResponseTime: stats.total.avgResponseTime
      },
      promotionCount: stats.promotionCount
    };

    this.history.push(data);

    // 保留最近60秒的数据
    const now = Date.now();
    this.history = this.history.filter(item => now - item.timestamp < 60000);
  }

  private updateChart(): void {
    const canvas = this.panel.querySelector('#cache-monitor-chart') as HTMLCanvasElement;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // 清空画布
    ctx.clearRect(0, 0, width, height);

    // 绘制背景
    ctx.fillStyle = '#f5f5f5';
    ctx.fillRect(0, 0, width, height);

    // 绘制网格线
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 10; i++) {
      const y = (height / 10) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // 绘制命中率曲线
    if (this.history.length > 1) {
      // 内存缓存命中率
      ctx.strokeStyle = '#4caf50';
      ctx.lineWidth = 2;
      ctx.beginPath();

      this.history.forEach((item, index) => {
        const x = (index / (this.history.length - 1)) * width;
        const y = height - (item.memory.hitRate * height);
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();

      // 磁盘缓存命中率
      ctx.strokeStyle = '#2196f3';
      ctx.beginPath();

      this.history.forEach((item, index) => {
        const x = (index / (this.history.length - 1)) * width;
        const y = height - (item.disk.hitRate * height);
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();

      // 总命中率
      ctx.strokeStyle = '#ff9800';
      ctx.lineWidth = 3;
      ctx.beginPath();

      this.history.forEach((item, index) => {
        const x = (index / (this.history.length - 1)) * width;
        const y = height - (item.total.hitRate * height);
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
    }

    // 绘制图例
    ctx.font = '12px Arial';
    ctx.fillStyle = '#4caf50';
    ctx.fillText('内存缓存', 10, 20);
    ctx.fillStyle = '#2196f3';
    ctx.fillText('磁盘缓存', 80, 20);
    ctx.fillStyle = '#ff9800';
    ctx.fillText('总命中率', 150, 20);
  }

  private updateHealthStatus(): void {
    const stats = this.apiService.getCacheStats();
    const healthDiv = this.panel.querySelector('#cache-monitor-health-status');
    const recommendationsDiv = this.panel.querySelector('#cache-monitor-recommendations');

    if (!healthDiv || !recommendationsDiv) return;

    const hitRate = stats.total.hitRate;
    const sizeRate = stats.total.size / 1000; // 假设最大大小为1000

    let status: 'healthy' | 'warning' | 'critical';
    let statusText: string;

    if (hitRate > 0.7 && sizeRate < 0.9) {
      status = 'healthy';
      statusText = '健康';
    } else if (hitRate > 0.5 && sizeRate < 0.95) {
      status = 'warning';
      statusText = '警告';
    } else {
      status = 'critical';
      statusText = '严重';
    }

    healthDiv.className = `cache-monitor-health-status cache-monitor-health-status-${status}`;
    healthDiv.textContent = statusText;

    // 生成建议
    const recommendations: string[] = [];

    if (hitRate < 0.5) {
      recommendations.push('缓存命中率较低，建议增加TTL或调整缓存大小');
    }

    if (sizeRate > 0.9) {
      recommendations.push('缓存使用率过高，建议增加缓存大小');
    }

    if (stats.memory.hitRate < stats.disk.hitRate) {
      recommendations.push('内存缓存命中率较低，考虑优化热门数据识别');
    }

    if (stats.promotionCount > stats.total.hits * 0.1) {
      recommendations.push('提升频率较高，考虑调整内存缓存大小');
    }

    recommendationsDiv.innerHTML = recommendations.map(rec => `<div class="cache-monitor-recommendation">${rec}</div>`).join('');
  }

  private resetStats(): void {
    this.apiService.resetCacheStats();
    this.history = [];
    this.refresh();
  }

  public destroy(): void {
    this.stopAutoUpdate();
    if (this.panel.parentElement) {
      this.panel.parentElement.removeChild(this.panel);
    }
  }
}