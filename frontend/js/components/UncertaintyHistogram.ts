/**
 * 不确定性分布直方图组件
 * 用于可视化不确定性值的分布情况
 */

import { ChartService, type HistogramBin } from '../services/ChartService';

export interface UncertaintyHistogramConfig {
  container: HTMLElement;
  data: number[];
  binCount?: number;
  title?: string;
  showNormalFit?: boolean;
  enableInteractive?: boolean;
  uncertaintyThresholds?: {
    low: number;
    medium: number;
    high: number;
  };
}

export interface HistogramData {
  bins: HistogramBin[];
  statistics: {
    mean: number;
    stdDev: number;
    median: number;
    quantiles: number[];
    min: number;
    max: number;
  };
  normalFit?: {
    mean: number;
    stdDev: number;
    goodnessOfFit: number;
    skewness: number;
    kurtosis: number;
  };
}

export class UncertaintyHistogram {
  private container: HTMLElement;
  private chart: any;
  private config: UncertaintyHistogramConfig;
  private data: HistogramData;
  private selectedBinIndex: number = -1;

  constructor(config: UncertaintyHistogramConfig) {
    this.container = config.container;
    this.config = config;

    // 处理数据
    this.data = this.processData();

    // 初始化图表
    this.initializeChart();
  }

  /**
   * 处理数据
   */
  private processData(): HistogramData {
    const { data: rawdata, binCount = 20, showNormalFit = true } = this.config;

    // 生成直方图 bins
    const bins = ChartService.generateHistogramBins(rawdata, binCount);

    // 计算统计信息
    const sorted = [...rawdata].sort((a, b) => a - b);
    const n = sorted.length;

    const mean = sorted.reduce((sum, d) => sum + d, 0) / n;
    const median = n % 2 === 0
      ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2
      : sorted[Math.floor(n / 2)];

    const variance = sorted.reduce((sum, d) => sum + Math.pow(d - mean, 2), 0) / (n - 1);
    const stdDev = Math.sqrt(variance);

    const quantiles = ChartService.calculateQuantiles(sorted, [0.25, 0.5, 0.75]);

    const statistics = {
      mean,
      stdDev,
      median,
      quantiles,
      min: sorted[0],
      max: sorted[n - 1],
    };

    // 正态分布拟合
    let normalFit;
    if (showNormalFit) {
      normalFit = ChartService.fitNormalDistribution(rawdata);
    }

    return {
      bins,
      statistics,
      normalFit,
    };
  }

  /**
   * 初始化图表
   */
  private initializeChart() {
    // 创建图表容器
    const chartContainer = document.createElement('div');
    chartContainer.className = 'uncertainty-histogram';
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

    const { title, showNormalFit = true } = this.config;

    // 生成直方图数据
    const histogramData = this.data.bins.map((bin, index) => ({
      value: [
        bin.min,
        bin.max,
        bin.count,
        index,
      ],
      itemStyle: {
        color: this.getBinColor(bin.min, bin.max),
      },
    }));

    const series: any[] = [
      {
        name: '不确定性分布',
        type: 'bar',
        data: histogramData,
        barWidth: '90%',
        itemStyle: {
          borderRadius: [2, 2, 0, 0],
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
    ];

    // 添加正态分布拟合曲线
    if (showNormalFit && this.data.normalFit) {
      const { mean, stdDev } = this.data.normalFit;
      const { min, max } = this.data.statistics;
      const range = max - min;

      const curveData = Array.from({ length: 100 }, (_, i) => {
        const x = min + (range * i) / 99;
        const z = (x - mean) / stdDev;
        const pdf = (1 / (stdDev * Math.sqrt(2 * Math.PI))) *
                    Math.exp(-0.5 * z * z);
        const scaledValue = pdf * this.config.data.length * (range / this.data.bins.length);
        return [x, scaledValue];
      });

      series.push({
        name: '正态分布拟合',
        type: 'line',
        data: curveData,
        lineStyle: {
          color: '#ff5722',
          width: 2,
        },
        symbol: 'none',
        smooth: true,
      });
    }

    // 添加统计线
    const { mean, median, quantiles } = this.data.statistics;

    series.push(
      {
        name: '平均值',
        type: 'line',
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: mean }],
          lineStyle: {
            color: '#2196f3',
            type: 'solid',
            width: 2,
          },
          label: {
            formatter: '平均值',
            position: 'end',
          },
        },
      },
      {
        name: '中位数',
        type: 'line',
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ xAxis: median }],
          lineStyle: {
            color: '#4caf50',
            type: 'dashed',
            width: 2,
          },
          label: {
            formatter: '中位数',
            position: 'end',
          },
        },
      },
      {
        name: '四分位数',
        type: 'line',
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            { xAxis: quantiles[0] },
            { xAxis: quantiles[1] },
            { xAxis: quantiles[2] },
          ],
          lineStyle: {
            color: '#ff9800',
            type: 'dotted',
            width: 1,
          },
          label: {
            formatter: (params: any) => {
              const values = ['Q1', 'Q2', 'Q3'];
              return values[params.dataIndex] || '';
            },
            position: 'end',
          },
        },
      }
    );

    const option: any = {
      title: {
        text: title || '不确定性分布直方图',
        left: 'center',
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.componentType === 'series' && params.seriesType === 'bar') {
            const index = params.value[3];
            const bin = this.data.bins[index];
            return `
              <div>
                <strong>不确定性区间</strong><br/>
                范围: [${bin.min.toFixed(4)}, ${bin.max.toFixed(4)}]<br/>
                频数: ${bin.count}<br/>
                频率: ${(bin.frequency * 100).toFixed(2)}%<br/>
                百分比: ${bin.percentage.toFixed(2)}%
              </div>
            `;
          }
          return '';
        },
      },
      grid: {
        left: '10%',
        right: '10%',
        bottom: '10%',
        top: '15%',
        containLabel: true,
      },
      toolbox: {
        feature: {
          saveAsImage: {
            title: '保存为图片',
          },
          dataZoom: {
            title: {
              zoom: '区域缩放',
              back: '还原缩放',
            },
          },
        },
      },
      xAxis: {
        type: 'value',
        name: '不确定性值',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
      },
      yAxis: {
        type: 'value',
        name: '频数',
        nameLocation: 'middle',
        nameGap: 30,
        minInterval: 1,
      },
      series,
    };

    this.chart.setOption(option);

    // 添加事件监听
    this.chart.on('click', (params: any) => {
      if (params.componentType === 'series' && params.seriesType === 'bar') {
        this.selectBin(params.value[3]);
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
    chartDiv.className = 'html-histogram-chart';
    chartDiv.innerHTML = `
      <div class="chart-header">
        <h3>${this.config.title || '不确定性分布直方图'}</h3>
      </div>
      <div class="chart-content">
        <canvas id="histogram-canvas"></canvas>
      </div>
      <div class="chart-controls">
        <label>
          Bin 数量:
          <input type="number" id="bin-count" value="${this.config.binCount || 20}" min="5" max="100">
        </label>
        <button id="update-chart" class="btn btn-sm">更新</button>
        <button id="export-png" class="btn btn-sm">导出 PNG</button>
      </div>
    `;

    container.appendChild(chartDiv);

    // 绑定事件
    const canvas = chartDiv.querySelector('#histogram-canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      this.drawHTMLChart(canvas, ctx);
    }

    // 更新按钮
    const updateBtn = chartDiv.querySelector('#update-chart');
    if (updateBtn) {
      updateBtn.addEventListener('click', () => {
        const binCountInput = chartDiv.querySelector('#bin-count') as HTMLInputElement;
        const newBinCount = parseInt(binCountInput.value, 10);
        if (newBinCount >= 5 && newBinCount <= 100) {
          this.config.binCount = newBinCount;
          this.data = this.processData();
          if (ctx) this.drawHTMLChart(canvas, ctx);
          this.addStatisticsPanel();
        }
      });
    }

    // 导出按钮
    const exportPngBtn = chartDiv.querySelector('#export-png');
    if (exportPngBtn) {
      exportPngBtn.addEventListener('click', () => {
        this.exportAsImage('png');
      });
    }
  }

  /**
   * 绘制 HTML 版本的直方图
   */
  private drawHTMLChart(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D) {
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;

    canvas.width = rect.width;
    canvas.height = rect.height;

    const padding = { top: 40, right: 40, bottom: 60, left: 70 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    // 计算数据范围
    const { min, max } = this.data.statistics;
    const maxCount = Math.max(...this.data.bins.map((b) => b.count));

    const rangeX = max - min || 1;
    const rangeY = maxCount || 1;

    // 转换坐标函数
    const scaleX = (x: number) => padding.left + ((x - min) / rangeX) * chartWidth;
    const scaleY = (y: number) => canvas.height - padding.bottom - (y / rangeY) * chartHeight;

    // 绘制背景
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制网格
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    // 绘制直方图
    const barWidth = chartWidth / this.data.bins.length;

    this.data.bins.forEach((bin, index) => {
      const x = scaleX(bin.min);
      const y = scaleY(bin.count);
      const width = barWidth * 0.9;
      const height = canvas.height - padding.bottom - y;

      ctx.fillStyle = this.getBinColor(bin.min, bin.max);
      ctx.globalAlpha = this.selectedBinIndex === index ? 1 : 0.7;
      ctx.fillRect(x, y, width, height);
      ctx.globalAlpha = 1;

      // 高亮选中的 bin
      if (this.selectedBinIndex === index) {
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, width, height);
      }
    });

    // 绘制正态分布拟合曲线
    if (this.config.showNormalFit && this.data.normalFit) {
      const { mean, stdDev } = this.data.normalFit;

      ctx.beginPath();
      ctx.strokeStyle = '#ff5722';
      ctx.lineWidth = 2;

      const range = max - min;
      for (let i = 0; i < 100; i++) {
        const x = min + (range * i) / 99;
        const z = (x - mean) / stdDev;
        const pdf = (1 / (stdDev * Math.sqrt(2 * Math.PI))) *
                    Math.exp(-0.5 * z * z);
        const scaledValue = pdf * this.config.data.length * (range / this.data.bins.length);

        const canvasX = scaleX(x);
        const canvasY = scaleY(scaledValue);

        if (i === 0) {
          ctx.moveTo(canvasX, canvasY);
        } else {
          ctx.lineTo(canvasX, canvasY);
        }
      }

      ctx.stroke();
    }

    // 绘制统计线
    const { mean, median, quantiles } = this.data.statistics;

    // 平均值线
    ctx.beginPath();
    ctx.strokeStyle = '#2196f3';
    ctx.lineWidth = 2;
    ctx.moveTo(scaleX(mean), padding.top);
    ctx.lineTo(scaleX(mean), canvas.height - padding.bottom);
    ctx.stroke();

    // 中位数线
    ctx.beginPath();
    ctx.strokeStyle = '#4caf50';
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 2;
    ctx.moveTo(scaleX(median), padding.top);
    ctx.lineTo(scaleX(median), canvas.height - padding.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    // 四分位数线
    ctx.beginPath();
    ctx.strokeStyle = '#ff9800';
    ctx.setLineDash([2, 2]);
    ctx.lineWidth = 1;
    quantiles.forEach((q) => {
      ctx.moveTo(scaleX(q), padding.top);
      ctx.lineTo(scaleX(q), canvas.height - padding.bottom);
    });
    ctx.stroke();
    ctx.setLineDash([]);

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
    ctx.fillText('不确定性值', canvas.width / 2, canvas.height - 10);

    // Y 轴标签
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('频数', 0, 0);
    ctx.restore();

    // 绘制刻度
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = min + (rangeX * i) / 5;
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
      const value = (rangeY * i) / 5;
      const y = scaleY(value);
      const x = padding.left - 10;

      ctx.fillText(Math.round(value).toString(), x, y);

      // Y 轴刻度线
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left - 5, y);
      ctx.stroke();
    }
  }

  /**
   * 获取 bin 颜色
   */
  private getBinColor(min: number, max: number): string {
    const thresholds = this.config.uncertaintyThresholds || {
      low: 0.1,
      medium: 0.3,
      high: 0.5,
    };

    const avg = (min + max) / 2;

    if (avg < thresholds.low) {
      return '#4caf50'; // 绿色：低不确定性
    } else if (avg < thresholds.medium) {
      return '#ff9800'; // 橙色：中等不确定性
    } else {
      return '#f44336'; // 红色：高不确定性
    }
  }

  /**
   * 选择 bin
   */
  public selectBin(index: number) {
    if (this.selectedBinIndex === index) {
      this.selectedBinIndex = -1;
    } else {
      this.selectedBinIndex = index;
    }

    // 更新图表
    if (this.chart) {
      this.chart.setOption({
        series: [{
          data: this.data.bins.map((bin, i) => ({
            ...bin,
            itemStyle: {
              color: this.getBinColor(bin.min, bin.max),
              opacity: this.selectedBinIndex === i ? 1 : 0.7,
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
        <span class="stat-label">平均值:</span>
        <span class="stat-value">${this.data.statistics.mean.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">标准差:</span>
        <span class="stat-value">${this.data.statistics.stdDev.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">中位数:</span>
        <span class="stat-value">${this.data.statistics.median.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Q1:</span>
        <span class="stat-value">${this.data.statistics.quantiles[0].toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Q2:</span>
        <span class="stat-value">${this.data.statistics.quantiles[1].toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Q3:</span>
        <span class="stat-value">${this.data.statistics.quantiles[2].toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最小值:</span>
        <span class="stat-value">${this.data.statistics.min.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">最大值:</span>
        <span class="stat-value">${this.data.statistics.max.toFixed(4)}</span>
      </div>
    `;

    // 添加正态分布拟合信息
    if (this.data.normalFit) {
      const fitInfo = document.createElement('div');
      fitInfo.className = 'fit-info';
      fitInfo.innerHTML = `
        <div class="stat-item">
          <span class="stat-label">偏度:</span>
          <span class="stat-value">${this.data.normalFit.skewness.toFixed(4)}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">峰度:</span>
          <span class="stat-value">${this.data.normalFit.kurtosis.toFixed(4)}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">拟合优度:</span>
          <span class="stat-value">${this.data.normalFit.goodnessOfFit.toFixed(4)}</span>
        </div>
      `;
      statsPanel.appendChild(fitInfo);
    }

    this.container.appendChild(statsPanel);
  }

  /**
   * 更新 bin 数量
   */
  public updateBinCount(binCount: number) {
    if (binCount >= 5 && binCount <= 100) {
      this.config.binCount = binCount;
      this.data = this.processData();
      this.initializeChart();
    }
  }

  /**
   * 导出图表为图片
   */
  public async exportAsImage(format: 'png' | 'svg' | 'pdf' = 'png') {
    try {
      const blob = await ChartService.exportChartAsImage(
        this.container,
        format,
        `uncertainty-histogram.${format}`
      );

      ChartService.downloadFile(blob, `uncertainty-histogram.${format}`);
    } catch (error) {
      console.error('导出图表失败:', error);
      alert('导出图表失败，请重试');
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
   * 获取正态分布拟合信息
   */
  public getNormalFit() {
    return this.data.normalFit;
  }
}