/**
 * 变异函数曲线图组件
 * 用于显示经验变异函数和拟合的变异函数模型
 */

import { ChartService, type VariogramModel } from '../services/ChartService';
import { I18nDialog } from './I18nDialog.js';
import { I18n } from '../utils/I18n';

export interface VariogramChartConfig {
  container: HTMLElement;
  empiricalData: { distance: number; semivariance: number; count: number }[];
  models?: VariogramModel[];
  selectedModel?: string;
  title?: string;
  showLegend?: boolean;
  enableInteractive?: boolean;
}

export interface VariogramChartData {
  empirical: { distance: number; semivariance: number; count: number }[];
  models: Map<string, { model: VariogramModel; curve: number[] }>;
  bestModel?: VariogramModel;
}

export interface VariogramParams {
  modelType: 'spherical' | 'exponential' | 'gaussian' | 'linear';
  nugget: number;
  sill: number;
  range: number;
}

export interface FitQuality {
  r2: number;
  rmse: number;
  recommendation: string;
}

export interface VariogramFit {
  model: VariogramModel;
  curve: number[];
  quality: FitQuality;
}

export class VariogramChart {
  private container: HTMLElement;
  private chart: any;
  private config: VariogramChartConfig;
  private data: VariogramChartData;
  private selectedModel: string | null = null;
  private visibleModels: Set<string> = new Set();
  private chartHost: HTMLElement | null = null;
  private qualityPanel: HTMLElement | null = null;
  private currentFit: VariogramFit | null = null;

  constructor(config: VariogramChartConfig) {
    this.container = config.container;
    this.config = config;

    this.data = this.processData();

    if (this.config.selectedModel) {
      this.selectedModel = this.config.selectedModel;
    } else if (this.data.models.size > 0) {
      const firstModel = this.data.models.keys().next().value;
      this.selectedModel = firstModel !== undefined ? firstModel : null;
    }

    this.data.models.forEach((_, name) => {
      this.visibleModels.add(name);
    });

    this.initializeChart();
    this.refreshFitQuality();
  }

  /**
   * 处理数据
   */
  private processData(): VariogramChartData {
    const { empiricalData, models } = this.config;
    const modelMap = new Map<string, { model: VariogramModel; curve: number[] }>();

    let bestModel: VariogramModel | undefined;

    if (models && models.length > 0) {
      const distance = this.buildDistanceAxis();

      models.forEach((model) => {
        const curve = ChartService.generateVariogramCurve(model, distance);
        modelMap.set(model.name, { model, curve });
      });

      bestModel = models.reduce((best, current) => {
        const currentScore = current.fitScore || 0;
        const bestScore = best.fitScore || 0;
        return currentScore > bestScore ? current : best;
      });
    }

    return {
      empirical: empiricalData,
      models: modelMap,
      bestModel
    };
  }

  /**
   * 初始化图表
   */
  private initializeChart() {
    const wrapper = document.createElement('div');
    wrapper.className = 'variogram-chart';
    wrapper.style.width = '100%';
    wrapper.style.height = '100%';
    this.container.innerHTML = '';
    this.container.appendChild(wrapper);

    this.chartHost = document.createElement('div');
    this.chartHost.className = 'variogram-chart-host';
    this.chartHost.style.minHeight = '250px';
    wrapper.appendChild(this.chartHost);

    if (typeof window !== 'undefined' && (window as any).echarts) {
      this.initECharts(this.chartHost);
    } else {
      this.initHTMLChart(this.chartHost);
    }

    this.qualityPanel = document.createElement('div');
    this.qualityPanel.className = 'variogram-quality-panel';
    wrapper.appendChild(this.qualityPanel);

    this.addModelParametersPanel();
  }

  /**
   * 使用 ECharts 初始化图表
   */
  private initECharts(container: HTMLElement) {
    const echarts = (window as any).echarts;
    this.chart = echarts.init(container);
    this.chart.setOption(this.buildEChartsOption());

    this.chart.on('click', (params: any) => {
      if (params.componentType === 'legend') {
        this.toggleModel(params.name);
      }
    });

    window.addEventListener('resize', () => {
      this.chart?.resize();
    });
  }

  /**
   * 使用纯 HTML 初始化图表（后备方案）
   */
  private initHTMLChart(container: HTMLElement) {
    const chartDiv = document.createElement('div');
    chartDiv.className = 'html-variogram-chart';
    chartDiv.innerHTML = `
      <div class="chart-header">
        <h3>${this.config.title || '变异函数曲线'}</h3>
      </div>
      <div class="chart-content">
        <canvas id="variogram-canvas"></canvas>
      </div>
      <div class="chart-controls">
        <button id="reset-zoom" class="btn btn-sm">重置视图</button>
        <button id="export-png" class="btn btn-sm">导出 PNG</button>
      </div>
      <div class="model-legend" id="model-legend"></div>
    `;

    container.appendChild(chartDiv);

    const canvas = chartDiv.querySelector('#variogram-canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      this.drawHTMLChart(canvas, ctx);
    }

    const legendDiv = chartDiv.querySelector('#model-legend');
    if (legendDiv) {
      legendDiv.innerHTML = '';
      this.data.models.forEach((_, name) => {
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';
        legendItem.innerHTML = `
          <input type="checkbox" id="model-${name}" checked>
          <label for="model-${name}" style="color: ${this.getModelColor(name)}">${name}</label>
        `;
        legendDiv.appendChild(legendItem);

        const checkbox = legendItem.querySelector(`#model-${name}`) as HTMLInputElement;
        checkbox.addEventListener('change', (e) => {
          this.toggleModel(name, (e.target as HTMLInputElement).checked);
          if (ctx) {
            this.drawHTMLChart(canvas, ctx);
          }
        });
      });
    }

    const resetBtn = chartDiv.querySelector('#reset-zoom');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (ctx) {
          this.drawHTMLChart(canvas, ctx);
        }
      });
    }

    const exportPngBtn = chartDiv.querySelector('#export-png');
    if (exportPngBtn) {
      exportPngBtn.addEventListener('click', () => {
        this.exportAsImage('png');
      });
    }
  }

  /**
   * 绘制 HTML 版本的变异函数图
   */
  private drawHTMLChart(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D) {
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) {
      return;
    }

    canvas.width = rect.width;
    canvas.height = rect.height;

    const padding = { top: 40, right: 40, bottom: 60, left: 70 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    const minX = 0;
    const maxX = Math.max(...this.data.empirical.map((d) => d.distance), 1);
    const minY = 0;
    const maxY = Math.max(...this.data.empirical.map((d) => d.semivariance), 1);

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    const scaleX = (x: number) => padding.left + ((x - minX) / rangeX) * chartWidth;
    const scaleY = (y: number) => canvas.height - padding.bottom - ((y - minY) / rangeY) * chartHeight;

    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    this.data.models.forEach((data, name) => {
      if (!this.visibleModels.has(name)) {
        return;
      }

      const isSelected = name === this.selectedModel;

      ctx.beginPath();
      ctx.strokeStyle = this.getModelColor(name);
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.setLineDash(isSelected ? [] : [5, 5]);

      const distance = this.buildDistanceAxis();
      distance.forEach((d, i) => {
        const x = scaleX(d);
        const y = scaleY(data.curve[i]);
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
      ctx.setLineDash([]);
    });

    this.data.empirical.forEach((point) => {
      const x = scaleX(point.distance);
      const y = scaleY(point.semivariance);
      const size = Math.min(20, Math.max(5, Math.sqrt(point.count) * 2));

      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fillStyle = '#333';
      ctx.globalAlpha = 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;

      ctx.strokeStyle = '#666';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y - size);
      ctx.lineTo(x, y + size);
      ctx.moveTo(x - size, y);
      ctx.lineTo(x + size, y);
      ctx.stroke();
    });

    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, canvas.height - padding.bottom);
    ctx.lineTo(canvas.width - padding.right, canvas.height - padding.bottom);
    ctx.stroke();

    ctx.fillStyle = '#333';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';

    ctx.fillText('距离 (h)', canvas.width / 2, canvas.height - 10);

    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('半方差 γ(h)', 0, 0);
    ctx.restore();

    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = minX + (rangeX * i) / 5;
      const x = scaleX(value);
      const y = canvas.height - padding.bottom + 15;

      ctx.fillText(value.toFixed(2), x, y);
      ctx.beginPath();
      ctx.moveTo(x, canvas.height - padding.bottom);
      ctx.lineTo(x, canvas.height - padding.bottom + 5);
      ctx.stroke();
    }

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      const value = minY + (rangeY * i) / 5;
      const y = scaleY(value);
      const x = padding.left - 10;

      ctx.fillText(value.toFixed(2), x, y);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left - 5, y);
      ctx.stroke();
    }
  }

  /**
   * 获取模型颜色
   */
  private getModelColor(name: string): string {
    const colors = ['#2196f3', '#4caf50', '#ff9800', '#9c27b0', '#f44336', '#00bcd4', '#8bc34a', '#ffc107'];
    const index = Array.from(this.data.models.keys()).indexOf(name);
    return colors[index % colors.length];
  }

  /**
   * 切换模型显示
   */
  public toggleModel(name: string, visible?: boolean) {
    if (visible !== undefined) {
      if (visible) {
        this.visibleModels.add(name);
      } else {
        this.visibleModels.delete(name);
      }
    } else if (this.visibleModels.has(name)) {
      this.visibleModels.delete(name);
    } else {
      this.visibleModels.add(name);
    }

    this.updateChart();
  }

  /**
   * 选择模型
   */
  public selectModel(name: string) {
    this.selectedModel = name;
    this.updateChart();
  }

  /**
   * 根据参数实时更新拟合曲线
   */
  public updateFitting(params: VariogramParams): void {
    const selectedName = this.selectedModel || `${params.modelType}-实时拟合`;

    const model: VariogramModel = {
      name: selectedName,
      type: params.modelType,
      nugget: params.nugget,
      sill: Math.max(params.sill, params.nugget + 0.001),
      range: Math.max(0.001, params.range)
    };

    const curve = ChartService.generateVariogramCurve(model, this.buildDistanceAxis());

    this.data.models.set(selectedName, { model, curve });
    this.visibleModels.add(selectedName);
    this.selectedModel = selectedName;

    this.refreshFitQuality();
    this.updateChart();
  }

  /**
   * 计算拟合质量指标
   */
  public calculateFitQuality(
    empirical: { distance: number; semivariance: number }[],
    fitted: { distance: number; semivariance: number }[]
  ): FitQuality {
    if (empirical.length === 0 || fitted.length === 0) {
      return {
        r2: 0,
        rmse: 0,
        recommendation: '缺少经验点，建议先加载采样数据后再评估拟合质量'
      };
    }

    const fittedAtEmpirical = empirical.map((point) => {
      const nearest = fitted.reduce((best, item) => {
        const bestDiff = Math.abs(best.distance - point.distance);
        const currentDiff = Math.abs(item.distance - point.distance);
        return currentDiff < bestDiff ? item : best;
      }, fitted[0]);
      return nearest.semivariance;
    });

    const actual = empirical.map((item) => item.semivariance);
    const stats = ChartService.calculateStatistics(actual, fittedAtEmpirical);

    return {
      r2: stats.r2,
      rmse: stats.rmse,
      recommendation: this.generateRecommendation(stats.r2, stats.rmse)
    };
  }

  /**
   * 更新图表
   */
  private updateChart() {
    if (this.chart) {
      this.chart.setOption(this.buildEChartsOption(), true);
    } else {
      const canvas = this.container.querySelector('#variogram-canvas') as HTMLCanvasElement | null;
      const ctx = canvas?.getContext('2d');
      if (canvas && ctx) {
        this.drawHTMLChart(canvas, ctx);
      }
    }

    this.addModelParametersPanel();
    this.refreshFitQuality();
  }

  /**
   * 添加模型参数面板
   */
  private addModelParametersPanel() {
    const host = this.container.querySelector('.variogram-chart');
    if (!host) {
      return;
    }

    const existing = host.querySelector('.model-parameters-panel');
    if (existing) {
      existing.remove();
    }

    if (this.data.models.size === 0) {
      return;
    }

    const paramsPanel = document.createElement('div');
    paramsPanel.className = 'model-parameters-panel';

    this.data.models.forEach((data, name) => {
      const model = data.model;
      const isSelected = name === this.selectedModel;
      const isBest = this.data.bestModel?.name === name;

      const modelDiv = document.createElement('div');
      modelDiv.className = `model-param-item ${isSelected ? 'selected' : ''}`;
      modelDiv.innerHTML = `
        <div class="model-header">
          <strong>${name}</strong>
          ${isBest ? '<span class="best-model-badge">最佳</span>' : ''}
          ${model.fitScore !== undefined ? `<span class="fit-score">拟合: ${model.fitScore.toFixed(4)}</span>` : ''}
        </div>
        <div class="model-details">
          <div>模型: ${this.getModelTypeName(model.type)}</div>
          <div>变差值 (C0): ${model.nugget.toFixed(4)}</div>
          <div>基台值 (C): ${model.sill.toFixed(4)}</div>
          <div>范围值 (a): ${model.range.toFixed(4)}</div>
        </div>
      `;

      modelDiv.addEventListener('click', () => {
        this.selectModel(name);
      });

      paramsPanel.appendChild(modelDiv);
    });

    host.appendChild(paramsPanel);
  }

  /**
   * 获取模型类型名称
   */
  private getModelTypeName(type: string): string {
    const typeNames: Record<string, string> = {
      spherical: '球状模型',
      exponential: '指数模型',
      gaussian: '高斯模型',
      linear: '线性模型'
    };
    return typeNames[type] || type;
  }

  /**
   * 调整模型参数
   */
  public adjustModelParameter(modelName: string, parameter: 'nugget' | 'sill' | 'range', value: number) {
    const modelData = this.data.models.get(modelName);
    if (!modelData) {
      return;
    }

    modelData.model[parameter] = value;
    modelData.curve = ChartService.generateVariogramCurve(modelData.model, this.buildDistanceAxis());

    this.updateChart();
  }

  /**
   * 导出图表为图片
   */
  public async exportAsImage(format: 'png' | 'svg' | 'pdf' = 'png') {
    try {
      const blob = await ChartService.exportChartAsImage(this.container, format, `variogram-chart.${format}`);
      ChartService.downloadFile(blob, `variogram-chart.${format}`);
    } catch (error) {
      console.error('导出图表失败:', error);
      I18nDialog.alert('dialog.chart.exportFailed');
    }
  }

  /**
   * 调整图表大小
   */
  public resize() {
    if (this.chart) {
      this.chart.resize();
    }
  }

  /**
   * 销毁图表
   */
  public destroy() {
    if (this.chart) {
      this.chart.dispose();
    }
    this.container.innerHTML = '';
  }

  /**
   * 获取选中的模型
   */
  public getSelectedModel(): VariogramModel | null {
    if (this.selectedModel) {
      const modelData = this.data.models.get(this.selectedModel);
      return modelData?.model || null;
    }
    return null;
  }

  /**
   * 获取所有模型
   */
  public getModels(): VariogramModel[] {
    return Array.from(this.data.models.values()).map((data) => data.model);
  }

  private buildDistanceAxis(): number[] {
    const maxDistance = Math.max(...this.data?.empirical.map((d) => d.distance) || this.config.empiricalData.map((d) => d.distance), 1);
    return Array.from({ length: 100 }, (_, i) => (maxDistance * i) / 99);
  }

  private buildEChartsOption(): any {
    const { title, showLegend } = this.config;

    const empiricalData = this.data.empirical.map((point) => ({
      value: [point.distance, point.semivariance],
      name: `h=${point.distance.toFixed(2)}, N=${point.count}`
    }));

    const distance = this.buildDistanceAxis();
    const series: any[] = [
      {
        name: '经验变异函数',
        type: 'scatter',
        data: empiricalData,
        symbolSize: (data: any) => {
          const point = this.data.empirical.find((p) => p.distance === data.value[0]);
          return Math.min(20, Math.max(5, Math.sqrt(point?.count || 1) * 2));
        },
        itemStyle: {
          color: '#333',
          opacity: 0.7
        }
      }
    ];

    this.data.models.forEach((item, name) => {
      if (!this.visibleModels.has(name)) {
        return;
      }

      const isSelected = name === this.selectedModel;
      series.push({
        name,
        type: 'line',
        data: distance.map((d, i) => [d, item.curve[i]]),
        lineStyle: {
          color: this.getModelColor(name),
          width: isSelected ? 3 : 2,
          type: isSelected ? 'solid' : 'dashed'
        },
        symbol: 'none',
        smooth: false
      });
    });

    return {
      title: {
        text: title || '变异函数曲线',
        left: 'center'
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.seriesName === '经验变异函数') {
            const point = this.data.empirical[params.dataIndex];
            return `<div><strong>经验变异函数</strong><br/>距离: ${point.distance.toFixed(4)}<br/>半方差: ${point.semivariance.toFixed(4)}<br/>样本对数: ${point.count}</div>`;
          }

          const modelData = this.data.models.get(params.seriesName);
          if (!modelData) {
            return '';
          }

          const model = modelData.model;
          return `<div><strong>${params.seriesName}</strong><br/>距离: ${params.value[0].toFixed(4)}<br/>半方差: ${params.value[1].toFixed(4)}<br/>模型: ${model.type}<br/>变差值: ${model.nugget.toFixed(4)}<br/>基台值: ${model.sill.toFixed(4)}<br/>范围值: ${model.range.toFixed(4)}</div>`;
        }
      },
      legend: showLegend !== false ? {
        bottom: 10,
        data: ['经验变异函数', ...Array.from(this.data.models.keys())],
        selected: {
          '经验变异函数': true,
          ...Object.fromEntries(Array.from(this.data.models.keys()).map((name) => [name, this.visibleModels.has(name)]))
        }
      } : undefined,
      grid: {
        left: '10%',
        right: '10%',
        bottom: showLegend !== false ? '15%' : '10%',
        top: '15%',
        containLabel: true
      },
      toolbox: {
        feature: {
          saveAsImage: {
            title: '保存为图片'
          },
          dataZoom: {
            title: {
              zoom: '区域缩放',
              back: '还原缩放'
            }
          }
        }
      },
      xAxis: {
        type: 'value',
        name: '距离 (h)',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true
      },
      yAxis: {
        type: 'value',
        name: '半方差 γ(h)',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
        min: 0
      },
      series
    };
  }

  private refreshFitQuality(): void {
    if (!this.qualityPanel) {
      return;
    }

    const selected = this.selectedModel ? this.data.models.get(this.selectedModel) : null;
    if (!selected) {
      this.qualityPanel.innerHTML = '<span>' + I18n.t('variogram.fitQualityNoModel') + '</span>';
      return;
    }

    const fittedPoints = this.buildDistanceAxis().map((distance, index) => ({
      distance,
      semivariance: selected.curve[index]
    }));
    const empiricalPoints = this.data.empirical.map((point) => ({
      distance: point.distance,
      semivariance: point.semivariance
    }));

    const quality = this.calculateFitQuality(empiricalPoints, fittedPoints);
    this.currentFit = {
      model: selected.model,
      curve: selected.curve,
      quality
    };

    this.qualityPanel.innerHTML = `
      <div class="variogram-quality-metrics">
        <span>R²: ${quality.r2.toFixed(3)}</span>
        <span>RMSE: ${quality.rmse.toFixed(4)}</span>
      </div>
      <div class="variogram-quality-recommendation">建议：${quality.recommendation}</div>
    `;
  }

  private generateRecommendation(r2: number, rmse: number): string {
    if (r2 >= 0.85 && rmse < 0.15) {
      return '拟合表现良好，可保持当前参数进行插值';
    }
    if (r2 < 0.6) {
      return '拟合偏弱，建议优先增大 range 或切换变异函数模型';
    }
    if (rmse > 0.3) {
      return '误差偏高，可适当减小 nugget 并增加 nlags';
    }
    return '拟合中等，建议微调 sill 与 range 观察曲线变化';
  }
}
