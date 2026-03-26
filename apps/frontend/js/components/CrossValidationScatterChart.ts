/**
 * 交叉验证散点图组件
 * 用于可视化预测值与实际值的对比，评估模型性能
 */

import { ChartService, type ScatterDataPoint } from '../services/ChartService';
import { I18nDialog } from './I18nDialog.js';

export interface CrossValidationScatterChartConfig {
  container: HTMLElement;
  actual: number[];
  predicted: number[];
  labels?: string[];
  metadata?: Record<string, any>[];
  title?: string;
  showLegend?: boolean;
  enableZoom?: boolean;
  threshold?: number;
  confidenceLevel?: number;
}

export interface ScatterChartData {
  data: ScatterDataPoint[];
  statistics: {
    rmse: number;
    mae: number;
    r2: number;
    bias: number;
    n: number;
  };
  confidenceInterval: {
    lower: number;
    upper: number;
    stdError: number;
  };
}

export class CrossValidationScatterChart {
  private container: HTMLElement;
  private chart: any;
  private config: CrossValidationScatterChartConfig;
  private data: ScatterChartData;
  private highlightedPoints: Set<number> = new Set();
  private filteredPoints: Set<number> = new Set();

  constructor(config: CrossValidationScatterChartConfig) {
    this.container = config.container;
    this.config = config;

    // 计算统计信息
    this.data = this.processData();

    // 初始化图表
    this.initializeChart();
  }

  /**
   * 处理数据
   */
  private processData(): ScatterChartData {
    const { actual, predicted, labels, metadata } = this.config;

    // 计算统计信息
    const statistics = ChartService.calculateStatistics(actual, predicted);

    // 计算置信区间
    const confidenceLevel = this.config.confidenceLevel || 0.95;
    const confidenceInterval = ChartService.calculateConfidenceInterval(
      actual,
      predicted,
      confidenceLevel
    );

    // 创建数据点
    const data: ScatterDataPoint[] = actual.map((a, i) => ({
      x: a,
      y: predicted[i],
      label: labels?.[i],
      metadata: metadata?.[i],
    }));

    return {
      data,
      statistics,
      confidenceInterval,
    };
  }

  /**
   * 初始化图表
   */
  private initializeChart() {
    // 创建图表容器
    const chartContainer = document.createElement('div');
    chartContainer.className = 'cross-validation-scatter-chart';
    chartContainer.style.width = '100%';
    chartContainer.style.height = '100%';
    this.container.innerHTML = '';
    this.container.appendChild(chartContainer);

    // 初始化 ECharts（如果可用）
    if (typeof window !== 'undefined' && (window as any).echarts) {
      this.initECharts(chartContainer);
    } else {
      this.initHTMLChart(chartContainer);
    }

    // 添加统计信息面板
    this.addStatisticsPanel();
  }

  /**
   * 使用 ECharts 初始化图表
   */
  private initECharts(container: HTMLElement) {
    const echarts = (window as any).echarts;
    this.chart = echarts.init(container);

    const { actual, predicted, title, showLegend, enableZoom } = this.config;

    // 生成数据
    const scatterData = this.data.data.map((point, index) => ({
      value: [point.x, point.y],
      name: point.label || `Point ${index}`,
      itemStyle: {
        color: this.getPointColor(index),
      },
    }));

    // 生成理想拟合线
    const minVal = Math.min(...actual, ...predicted);
    const maxVal = Math.max(...actual, ...predicted);
    const lineData = [
      [minVal, minVal],
      [maxVal, maxVal],
    ];

    // 生成置信区间
    const { lower, upper } = this.data.confidenceInterval;
    const lowerLineData = [
      [minVal, minVal + lower],
      [maxVal, maxVal + lower],
    ];
    const upperLineData = [
      [minVal, minVal + upper],
      [maxVal, maxVal + upper],
    ];

    const option: any = {
      title: {
        text: title || '交叉验证散点图',
        left: 'center',
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const index = params.dataIndex;
          const point = this.data.data[index];
          const error = point.y - point.x;
          return `
            <div>
              <strong>${point.label || `Point ${index}`}</strong><br/>
              实际值: ${point.x.toFixed(4)}<br/>
              预测值: ${point.y.toFixed(4)}<br/>
              误差: ${error.toFixed(4)}<br/>
              相对误差: ${((error / point.x) * 100).toFixed(2)}%
            </div>
          `;
        },
      },
      legend: showLegend !== false ? {
        bottom: 10,
        data: ['数据点', '理想拟合线', '置信区间'],
      } : undefined,
      grid: {
        left: '10%',
        right: '10%',
        bottom: showLegend !== false ? '15%' : '10%',
        top: '15%',
        containLabel: true,
      },
      toolbox: {
        feature: {
          saveAsImage: {
            title: '保存为图片',
          },
          dataZoom: enableZoom !== false ? {
            title: {
              zoom: '区域缩放',
              back: '还原缩放',
            },
          } : undefined,
        },
      },
      xAxis: {
        type: 'value',
        name: '实际值',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
      },
      yAxis: {
        type: 'value',
        name: '预测值',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
      },
      series: [
        {
          name: '数据点',
          type: 'scatter',
          data: scatterData,
          symbolSize: 8,
          itemStyle: {
            opacity: 0.7,
          },
          emphasis: {
            focus: 'series',
            itemStyle: {
              opacity: 1,
              borderColor: '#000',
              borderWidth: 2,
            },
          },
        },
        {
          name: '理想拟合线',
          type: 'line',
          data: lineData,
          lineStyle: {
            type: 'dashed',
            color: '#999',
            width: 2,
          },
          symbol: 'none',
          smooth: false,
        },
        {
          name: '置信区间',
          type: 'line',
          data: lowerLineData,
          lineStyle: {
            type: 'dotted',
            color: '#ccc',
            width: 1,
          },
          symbol: 'none',
        },
        {
          name: '置信区间',
          type: 'line',
          data: upperLineData,
          lineStyle: {
            type: 'dotted',
            color: '#ccc',
            width: 1,
          },
          symbol: 'none',
          areaStyle: {
            color: 'rgba(200, 200, 200, 0.1)',
          },
        },
      ],
    };

    this.chart.setOption(option);

    // 添加事件监听
    this.chart.on('click', (params: any) => {
      if (params.componentType === 'series' && params.seriesName === '数据点') {
        this.highlightPoint(params.dataIndex);
      }
    });

    // 响应式调整
    window.addEventListener('resize', () => {
      this.chart.resize();
    });
  }

  /**
   * 使用纯 HTML 初始化图表（后备方案）
   */
  private initHTMLChart(container: HTMLElement) {
    const chartDiv = document.createElement('div');
    chartDiv.className = 'html-scatter-chart';
    chartDiv.innerHTML = `
      <div class="chart-header">
        <h3>${this.config.title || '交叉验证散点图'}</h3>
      </div>
      <div class="chart-content">
        <canvas id="scatter-canvas"></canvas>
        <div class="chart-overlay" id="chart-tooltip"></div>
      </div>
      <div class="chart-controls">
        <button id="reset-zoom" class="btn btn-sm">重置视图</button>
        <button id="export-png" class="btn btn-sm">导出 PNG</button>
        <button id="export-svg" class="btn btn-sm">导出 SVG</button>
      </div>
    `;

    container.appendChild(chartDiv);

    // 绑定事件
    const canvas = chartDiv.querySelector('#scatter-canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.error('无法获取 2D 上下文');
      return;
    }

    this.drawHTMLChart(canvas, ctx);

    // 按钮事件
    const resetBtn = chartDiv.querySelector('#reset-zoom');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.drawHTMLChart(canvas, ctx);
      });
    }

    const exportPngBtn = chartDiv.querySelector('#export-png');
    if (exportPngBtn) {
      exportPngBtn.addEventListener('click', () => {
        this.exportAsImage('png');
      });
    }

    const exportSvgBtn = chartDiv.querySelector('#export-svg');
    if (exportSvgBtn) {
      exportSvgBtn.addEventListener('click', () => {
        this.exportAsImage('svg');
      });
    }
  }

  /**
   * 绘制 HTML 版本的散点图
   */
  private drawHTMLChart(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D) {
    const { actual, predicted } = this.config;
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;

    canvas.width = rect.width;
    canvas.height = rect.height;

    const padding = { top: 40, right: 40, bottom: 60, left: 70 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    // 计算数据范围
    const minX = Math.min(...actual, ...predicted);
    const maxX = Math.max(...actual, ...predicted);
    const rangeX = maxX - minX || 1;
    const rangeY = rangeX;

    // 转换坐标函数
    const scaleX = (x: number) => padding.left + ((x - minX) / rangeX) * chartWidth;
    const scaleY = (y: number) => canvas.height - padding.bottom - ((y - minX) / rangeY) * chartHeight;

    // 绘制背景
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制网格
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    // 绘制理想拟合线
    ctx.strokeStyle = '#999';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(scaleX(minX), scaleY(minX));
    ctx.lineTo(scaleX(maxX), scaleY(maxX));
    ctx.stroke();
    ctx.setLineDash([]);

    // 绘制置信区间
    const { lower, upper } = this.data.confidenceInterval;
    ctx.fillStyle = 'rgba(200, 200, 200, 0.1)';
    ctx.beginPath();
    ctx.moveTo(scaleX(minX), scaleY(minX + lower));
    ctx.lineTo(scaleX(maxX), scaleY(maxX + lower));
    ctx.lineTo(scaleX(maxX), scaleY(maxX + upper));
    ctx.lineTo(scaleX(minX), scaleY(minX + upper));
    ctx.closePath();
    ctx.fill();

    // 绘制数据点
    this.data.data.forEach((point, index) => {
      const x = scaleX(point.x);
      const y = scaleY(point.y);

      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fillStyle = this.getPointColor(index);
      ctx.globalAlpha = 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;

      // 高亮选中的点
      if (this.highlightedPoints.has(index)) {
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });

    // 绘制坐标轴
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, canvas.height - padding.bottom);
    ctx.lineTo(canvas.width - padding.right, canvas.height - padding.bottom);
    ctx.stroke();

    // 绘制坐标轴标签
    ctx.fillStyle = '#333';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';

    // X 轴标签
    ctx.fillText('实际值', canvas.width / 2, canvas.height - 10);

    // Y 轴标签
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('预测值', 0, 0);
    ctx.restore();

    // 绘制刻度
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = minX + (rangeX * i) / 5;
      const x = scaleX(value);
      const y = canvas.height - padding.bottom + 15;

      ctx.fillText(value.toFixed(2), x, y);

      // X 轴刻度线
      ctx.beginPath();
      ctx.moveTo(x, canvas.height - padding.bottom);
      ctx.lineTo(x, canvas.height - padding.bottom + 5);
      ctx.stroke();
    }

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      const value = minX + (rangeY * i) / 5;
      const y = scaleY(value);
      const x = padding.left - 10;

      ctx.fillText(value.toFixed(2), x, y);

      // Y 轴刻度线
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left - 5, y);
      ctx.stroke();
    }
  }

  /**
   * 获取数据点颜色
   */
  private getPointColor(index: number): string {
    const point = this.data.data[index];
    const error = point.y - point.x;
    const relativeError = Math.abs(error / point.x);

    // 基于相对误差着色
    if (relativeError < 0.1) {
      return '#4caf50'; // 绿色：误差小
    } else if (relativeError < 0.2) {
      return '#ff9800'; // 橙色：误差中等
    } else {
      return '#f44336'; // 红色：误差大
    }
  }

  /**
   * 高亮数据点
   */
  public highlightPoint(index: number) {
    if (this.highlightedPoints.has(index)) {
      this.highlightedPoints.delete(index);
    } else {
      this.highlightedPoints.add(index);
    }

    // 更新图表
    if (this.chart) {
      this.chart.setOption({
        series: [{
          data: this.data.data.map((point, i) => ({
            ...point,
            itemStyle: {
              color: this.highlightedPoints.has(i) ? '#ff0000' : this.getPointColor(i),
              borderWidth: this.highlightedPoints.has(i) ? 3 : 0,
            },
          })),
        }],
      });
    }
  }

  /**
   * 筛选数据点
   */
  public filterPoints(threshold: number) {
    this.filteredPoints.clear();

    this.data.data.forEach((point, index) => {
      const error = Math.abs(point.y - point.x) / point.x;
      if (error > threshold) {
        this.filteredPoints.add(index);
      }
    });

    // 更新图表
    if (this.chart) {
      this.chart.setOption({
        series: [{
          data: this.data.data.map((point, index) => ({
            ...point,
            itemStyle: {
              opacity: this.filteredPoints.has(index) ? 0.3 : 0.7,
            },
          })),
        }],
      });
    }
  }

  /**
   * 添加统计信息面板
   */
  private addStatisticsPanel() {
    const statsPanel = document.createElement('div');
    statsPanel.className = 'statistics-panel';
    statsPanel.innerHTML = `
      <div class="stat-item">
        <span class="stat-label">RMSE:</span>
        <span class="stat-value">${this.data.statistics.rmse.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">MAE:</span>
        <span class="stat-value">${this.data.statistics.mae.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">R²:</span>
        <span class="stat-value">${this.data.statistics.r2.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">偏差:</span>
        <span class="stat-value">${this.data.statistics.bias.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">样本数:</span>
        <span class="stat-value">${this.data.statistics.n}</span>
      </div>
    `;

    this.container.appendChild(statsPanel);
  }

  /**
   * 导出图表为图片
   */
  public async exportAsImage(format: 'png' | 'svg' | 'pdf' = 'png') {
    try {
      const blob = await ChartService.exportChartAsImage(
        this.container,
        format,
        `cross-validation-scatter.${format}`
      );

      ChartService.downloadFile(blob, `cross-validation-scatter.${format}`);
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
   * 获取统计信息
   */
  public getStatistics() {
    return this.data.statistics;
  }

  /**
   * 获取数据
   */
  public getData() {
    return this.data.data;
  }
}
