/**
 * 采样效果对比图组件
 * 用于比较不同采样策略的效果和效率
 */

import { ChartService, type SamplingEfficiencyData } from '../services/ChartService';
import { I18nDialog } from './I18nDialog.js';

export interface SamplingEfficiencyChartConfig {
  container: HTMLElement;
  data: SamplingEfficiencyData[];
  title?: string;
  showLegend?: boolean;
  enableInteractive?: boolean;
  showEfficiency?: boolean;
  showCostAnalysis?: boolean;
}

export interface SamplingEfficiencyChartData {
  strategies: Map<string, SamplingEfficiencyData[]>;
  optimalPoints: Map<string, SamplingEfficiencyData | null>;
  statistics: {
    bestStrategy: string;
    bestEfficiency: number;
    bestCostEfficiency: number;
  };
}

export class SamplingEfficiencyChart {
  private container: HTMLElement;
  private chart: any;
  private config: SamplingEfficiencyChartConfig;
  private data: SamplingEfficiencyChartData;
  private visibleStrategies: Set<string> = new Set();
  private selectedStrategy: string | null = null;

  constructor(config: SamplingEfficiencyChartConfig) {
    this.container = config.container;
    this.config = config;

    // 处理数据
    this.data = this.processData();

    // 初始化所有策略可见
    this.data.strategies.forEach((_, name) => {
      this.visibleStrategies.add(name);
    });

    // 初始化图表
    this.initializeChart();
  }

  /**
   * 处理数据
   */
  private processData(): SamplingEfficiencyChartData {
    const { data } = this.config;

    // 按策略分组数据
    const strategyMap = new Map<string, SamplingEfficiencyData[]>();

    data.forEach((point) => {
      if (!strategyMap.has(point.strategy)) {
        strategyMap.set(point.strategy, []);
      }
      strategyMap.get(point.strategy)!.push(point);
    });

    // 计算效率指标
    const initialUncertainty = Math.max(...data.map((d) => d.averageUncertainty));

    strategyMap.forEach((points, strategy) => {
      points.sort((a, b) => a.samplingPoints - b.samplingPoints);

      // 计算效率
      points.forEach((point, index) => {
        if (index > 0) {
          const prevUncertainty = points[index - 1].averageUncertainty;
          const reduction = prevUncertainty - point.averageUncertainty;
          const addedPoints = point.samplingPoints - points[index - 1].samplingPoints;

          point.efficiency = reduction / addedPoints;
        } else {
          const reduction = initialUncertainty - point.averageUncertainty;
          point.efficiency = reduction / point.samplingPoints;
        }

        // 计算成本效益
        if (point.cost) {
          const totalCost = point.cost * point.samplingPoints;
          point.efficiency = (initialUncertainty - point.averageUncertainty) / totalCost;
        }
      });
    });

    // 找出每个策略的最优点
    const optimalPoints = new Map<string, SamplingEfficiencyData | null>();
    strategyMap.forEach((points, strategy) => {
      const optimal = ChartService.findOptimalSamplingPoints(points);
      optimalPoints.set(strategy, optimal);
    });

    // 找出最佳策略
    let bestStrategy = '';
    let bestEfficiency = 0;
    let bestCostEfficiency = 0;

    optimalPoints.forEach((point, strategy) => {
      if (point) {
        if (point.efficiency !== undefined && point.efficiency > bestEfficiency) {
          bestEfficiency = point.efficiency;
          bestStrategy = strategy;
        }
      }
    });

    return {
      strategies: strategyMap,
      optimalPoints,
      statistics: {
        bestStrategy,
        bestEfficiency,
        bestCostEfficiency: bestEfficiency,
      },
    };
  }

  /**
   * 初始化图表
   */
  private initializeChart() {
    // 创建图表容器
    const chartContainer = document.createElement('div');
    chartContainer.className = 'sampling-efficiency-chart';
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

    // 添加分析面板
    this.addAnalysisPanel();
  }

  /**
   * 使用 ECharts 初始化图表
   */
  private initECharts(container: HTMLElement) {
    const echarts = (window as any).echarts;
    this.chart = echarts.init(container);

    const { title, showLegend, showEfficiency = true } = this.config;

    // 生成系列数据
    const series: any[] = [];

    this.data.strategies.forEach((points, strategy) => {
      if (!this.visibleStrategies.has(strategy)) return;

      const isSelected = strategy === this.selectedStrategy;
      const optimal = this.data.optimalPoints.get(strategy);

      // 排序数据点
      const sortedPoints = [...points].sort((a, b) => a.samplingPoints - b.samplingPoints);

      // 主曲线
      series.push({
        name: strategy,
        type: 'line',
        data: sortedPoints.map((point) => [point.samplingPoints, point.averageUncertainty]),
        lineStyle: {
          color: this.getStrategyColor(strategy),
          width: isSelected ? 3 : 2,
          type: isSelected ? 'solid' : 'dashed',
        },
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          opacity: 0.8,
        },
        emphasis: {
          focus: 'series',
          itemStyle: {
            opacity: 1,
            borderColor: '#000',
            borderWidth: 2,
          },
        },
      });

      // 标记最优点
      if (optimal) {
        series.push({
          name: `${strategy} - 最优点`,
          type: 'scatter',
          data: [[optimal.samplingPoints, optimal.averageUncertainty]],
          symbolSize: 12,
          itemStyle: {
            color: this.getStrategyColor(strategy),
            borderColor: '#000',
            borderWidth: 2,
          },
          z: 10,
        });
      }
    });

    // 添加效率曲线（如果启用）
    if (showEfficiency) {
      this.data.strategies.forEach((points, strategy) => {
        if (!this.visibleStrategies.has(strategy)) return;

        const sortedPoints = [...points].sort((a, b) => a.samplingPoints - b.samplingPoints);

        series.push({
          name: `${strategy} - 效率`,
          type: 'line',
          yAxisIndex: 1,
          data: sortedPoints.map((point) => [point.samplingPoints, point.efficiency || 0]),
          lineStyle: {
            color: this.getStrategyColor(strategy),
            width: 1,
            type: 'dotted',
          },
          symbol: 'none',
          showSymbol: false,
        });
      });
    }

    const option: any = {
      title: {
        text: title || '采样效果对比',
        left: 'center',
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.seriesName.includes('最优点')) {
            const strategy = params.seriesName.replace(' - 最优点', '');
            const optimal = this.data.optimalPoints.get(strategy);
            if (optimal) {
              return `
                <div>
                  <strong>${strategy} - 最优点</strong><br/>
                  采样点数: ${optimal.samplingPoints}<br/>
                  平均不确定性: ${optimal.averageUncertainty.toFixed(4)}<br/>
                  效率: ${optimal.efficiency?.toFixed(6) || 'N/A'}<br/>
                  成本: ${optimal.cost || 'N/A'}
                </div>
              `;
            }
          } else if (params.seriesName.includes('效率')) {
            const strategy = params.seriesName.replace(' - 效率', '');
            return `
              <div>
                <strong>${strategy} - 效率</strong><br/>
                采样点数: ${params.value[0]}<br/>
                效率: ${params.value[1].toFixed(6)}
              </div>
            `;
          } else {
            return `
              <div>
                <strong>${params.seriesName}</strong><br/>
                采样点数: ${params.value[0]}<br/>
                平均不确定性: ${params.value[1].toFixed(4)}
              </div>
            `;
          }
          return '';
        },
      },
      legend: showLegend !== false ? {
        bottom: 10,
        data: Array.from(this.data.strategies.keys()),
        selected: Object.fromEntries(
          Array.from(this.data.strategies.keys()).map((name) => [
            name,
            this.visibleStrategies.has(name),
          ])
        ),
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
        name: '采样点数量',
        nameLocation: 'middle',
        nameGap: 30,
        minInterval: 1,
      },
      yAxis: [
        {
          type: 'value',
          name: '平均不确定性',
          nameLocation: 'middle',
          nameGap: 30,
          position: 'left',
        },
        {
          type: 'value',
          name: '效率',
          nameLocation: 'middle',
          nameGap: 30,
          position: 'right',
          show: showEfficiency,
        },
      ],
      series,
    };

    this.chart.setOption(option);

    // 添加事件监听
    this.chart.on('click', (params: any) => {
      if (params.componentType === 'legend') {
        this.toggleStrategy(params.name);
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
    chartDiv.className = 'html-efficiency-chart';
    chartDiv.innerHTML = `
      <div class="chart-header">
        <h3>${this.config.title || '采样效果对比'}</h3>
      </div>
      <div class="chart-content">
        <canvas id="efficiency-canvas"></canvas>
      </div>
      <div class="chart-controls">
        <button id="reset-zoom" class="btn btn-sm">重置视图</button>
        <button id="export-png" class="btn btn-sm">导出 PNG</button>
      </div>
      <div class="strategy-legend" id="strategy-legend"></div>
    `;

    container.appendChild(chartDiv);

    // 绑定事件
    const canvas = chartDiv.querySelector('#efficiency-canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      console.error('无法获取 2D 上下文');
      return;
    }

    this.drawHTMLChart(canvas, ctx);

    // 生成策略图例
    const legendDiv = chartDiv.querySelector('#strategy-legend');
    if (legendDiv) {
      this.data.strategies.forEach((_, name) => {
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';
        legendItem.innerHTML = `
          <input type="checkbox" id="strategy-${name}" checked>
          <label for="strategy-${name}" style="color: ${this.getStrategyColor(name)}">
            ${name}
          </label>
        `;
        legendDiv.appendChild(legendItem);

        const checkbox = legendItem.querySelector(`#strategy-${name}`) as HTMLInputElement;
        checkbox.addEventListener('change', (e) => {
          this.toggleStrategy(name, (e.target as HTMLInputElement).checked);
          this.drawHTMLChart(canvas, ctx);
        });
      });
    }

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
  }

  /**
   * 绘制 HTML 版本的采样效果对比图
   */
  private drawHTMLChart(canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D) {
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (!rect) return;

    canvas.width = rect.width;
    canvas.height = rect.height;

    const padding = { top: 40, right: 40, bottom: 60, left: 70 };
    const chartWidth = canvas.width - padding.left - padding.right;
    const chartHeight = canvas.height - padding.top - padding.bottom;

    // 收集所有数据点
    const allPoints: SamplingEfficiencyData[] = [];
    this.data.strategies.forEach((points) => {
      allPoints.push(...points);
    });

    // 计算数据范围
    const maxPoints = Math.max(...allPoints.map((d) => d.samplingPoints));
    const maxUncertainty = Math.max(...allPoints.map((d) => d.averageUncertainty));
    const minUncertainty = Math.min(...allPoints.map((d) => d.averageUncertainty));

    const rangeX = maxPoints || 1;
    const rangeY = maxUncertainty - minUncertainty || 1;

    // 转换坐标函数
    const scaleX = (x: number) => padding.left + (x / rangeX) * chartWidth;
    const scaleY = (y: number) => canvas.height - padding.bottom - ((y - minUncertainty) / rangeY) * chartHeight;

    // 绘制背景
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制网格
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    // 绘制策略曲线
    this.data.strategies.forEach((points, strategy) => {
      if (!this.visibleStrategies.has(strategy)) return;

      const isSelected = strategy === this.selectedStrategy;
      const optimal = this.data.optimalPoints.get(strategy);

      // 排序数据点
      const sortedPoints = [...points].sort((a, b) => a.samplingPoints - b.samplingPoints);

      // 绘制曲线
      ctx.beginPath();
      ctx.strokeStyle = this.getStrategyColor(strategy);
      ctx.lineWidth = isSelected ? 3 : 2;
      if (!isSelected) {
        ctx.setLineDash([5, 5]);
      } else {
        ctx.setLineDash([]);
      }

      sortedPoints.forEach((point, index) => {
        const x = scaleX(point.samplingPoints);
        const y = scaleY(point.averageUncertainty);

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
      ctx.setLineDash([]);

      // 绘制数据点
      sortedPoints.forEach((point) => {
        const x = scaleX(point.samplingPoints);
        const y = scaleY(point.averageUncertainty);

        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = this.getStrategyColor(strategy);
        ctx.globalAlpha = 0.8;
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // 标记最优点
      if (optimal) {
        const x = scaleX(optimal.samplingPoints);
        const y = scaleY(optimal.averageUncertainty);

        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.fillStyle = this.getStrategyColor(strategy);
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.fill();
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
    ctx.fillText('采样点数量', canvas.width / 2, canvas.height - 10);

    // Y 轴标签
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('平均不确定性', 0, 0);
    ctx.restore();

    // 绘制刻度
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = (rangeX * i) / 5;
      const x = scaleX(value);
      const y = canvas.height - padding.bottom + 15;

      ctx.fillText(Math.round(value).toString(), x, y);

      // X 轴刻度线
      ctx.beginPath();
      ctx.moveTo(x, canvas.height - padding.bottom);
      ctx.lineTo(x, canvas.height - padding.bottom + 5);
      ctx.stroke();
    }

    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 5; i++) {
      const value = minUncertainty + (rangeY * i) / 5;
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
   * 获取策略颜色
   */
  private getStrategyColor(strategy: string): string {
    const colors = [
      '#2196f3',
      '#4caf50',
      '#ff9800',
      '#9c27b0',
      '#f44336',
      '#00bcd4',
      '#8bc34a',
      '#ffc107',
    ];
    const index = Array.from(this.data.strategies.keys()).indexOf(strategy);
    return colors[index % colors.length];
  }

  /**
   * 切换策略显示
   */
  public toggleStrategy(strategy: string, visible?: boolean) {
    if (visible !== undefined) {
      if (visible) {
        this.visibleStrategies.add(strategy);
      } else {
        this.visibleStrategies.delete(strategy);
      }
    } else {
      if (this.visibleStrategies.has(strategy)) {
        this.visibleStrategies.delete(strategy);
      } else {
        this.visibleStrategies.add(strategy);
      }
    }

    // 更新图表
    this.updateChart();
  }

  /**
   * 选择策略
   */
  public selectStrategy(strategy: string) {
    this.selectedStrategy = strategy;
    this.updateChart();
  }

  /**
   * 更新图表
   */
  private updateChart() {
    if (this.chart) {
      this.chart.setOption({
        series: this.chart.getOption().series.map((s: any) => {
          const strategyName = s.name.replace(' - 最优点', '').replace(' - 效率', '');
          if (strategyName) {
            s.lineStyle = {
              ...s.lineStyle,
              width: strategyName === this.selectedStrategy ? 3 : 2,
              type: strategyName === this.selectedStrategy ? 'solid' : 'dashed',
            };
          }
          return s;
        }),
      });
    }
  }

  /**
   * 添加分析面板
   */
  private addAnalysisPanel() {
    const analysisPanel = document.createElement('div');
    analysisPanel.className = 'analysis-panel';

    // 最佳策略
    const bestStrategyDiv = document.createElement('div');
    bestStrategyDiv.className = 'best-strategy';
    bestStrategyDiv.innerHTML = `
      <h4>最佳策略</h4>
      <div>策略: ${this.data.statistics.bestStrategy}</div>
      <div>最高效率: ${this.data.statistics.bestEfficiency.toFixed(6)}</div>
    `;
    analysisPanel.appendChild(bestStrategyDiv);

    // 各策略的最优点
    const optimalPointsDiv = document.createElement('div');
    optimalPointsDiv.className = 'optimal-points';
    optimalPointsDiv.innerHTML = '<h4>最优采样点数量</h4>';

    this.data.optimalPoints.forEach((point, strategy) => {
      if (point) {
        const pointDiv = document.createElement('div');
        pointDiv.className = 'optimal-point-item';
        pointDiv.innerHTML = `
          <div style="color: ${this.getStrategyColor(strategy)}">
            <strong>${strategy}</strong>
          </div>
          <div>采样点数: ${point.samplingPoints}</div>
          <div>不确定性: ${point.averageUncertainty.toFixed(4)}</div>
          <div>效率: ${point.efficiency?.toFixed(6) || 'N/A'}</div>
        `;
        pointDiv.addEventListener('click', () => {
          this.selectStrategy(strategy);
        });
        optimalPointsDiv.appendChild(pointDiv);
      }
    });

    analysisPanel.appendChild(optimalPointsDiv);

    // 采样模拟输入
    const simulationDiv = document.createElement('div');
    simulationDiv.className = 'simulation-panel';
    simulationDiv.innerHTML = `
      <h4>采样模拟</h4>
      <label>
        采样点数量:
        <input type="number" id="simulation-points" min="1" value="10">
      </label>
      <button id="simulate" class="btn btn-sm">模拟</button>
      <div id="simulation-result"></div>
    `;

    const simulateBtn = simulationDiv.querySelector('#simulate');
    if (simulateBtn) {
      simulateBtn.addEventListener('click', () => {
        const pointsInput = simulationDiv.querySelector('#simulation-points') as HTMLInputElement;
        const points = parseInt(pointsInput.value, 10);
        this.simulateSampling(points, simulationDiv.querySelector('#simulation-result') as HTMLElement);
      });
    }

    analysisPanel.appendChild(simulationDiv);

    this.container.appendChild(analysisPanel);
  }

  /**
   * 模拟采样
   */
  private simulateSampling(points: number, resultDiv: HTMLElement) {
    const results: { strategy: string; expectedUncertainty: number; cost: number }[] = [];

    this.data.strategies.forEach((dataPoints, strategy) => {
      // 找到最接近的采样点数量
      const closest = dataPoints.reduce((prev, curr) => {
        return Math.abs(curr.samplingPoints - points) < Math.abs(prev.samplingPoints - points)
          ? curr
          : prev;
      });

      // 使用线性插值估算不确定性
      let expectedUncertainty = closest.averageUncertainty;

      if (dataPoints.length > 1) {
        const sorted = [...dataPoints].sort((a, b) => a.samplingPoints - b.samplingPoints);
        const index = sorted.findIndex((p) => p.samplingPoints >= points);

        if (index > 0) {
          const lower = sorted[index - 1];
          const upper = sorted[index];
          const t = (points - lower.samplingPoints) / (upper.samplingPoints - lower.samplingPoints);
          expectedUncertainty = lower.averageUncertainty + t * (upper.averageUncertainty - lower.averageUncertainty);
        }
      }

      results.push({
        strategy,
        expectedUncertainty,
        cost: closest.cost || points,
      });
    });

    // 显示结果
    resultDiv.innerHTML = `
      <h5>预期不确定性:</h5>
      ${results.map((r) => `
        <div style="color: ${this.getStrategyColor(r.strategy)}">
          ${r.strategy}: ${r.expectedUncertainty.toFixed(4)} (成本: ${r.cost})
        </div>
      `).join('')}
    `;
  }

  /**
   * 导出图表为图片
   */
  public async exportAsImage(format: 'png' | 'svg' | 'pdf' = 'png') {
    try {
      const blob = await ChartService.exportChartAsImage(
        this.container,
        format,
        `sampling-efficiency-chart.${format}`
      );

      ChartService.downloadFile(blob, `sampling-efficiency-chart.${format}`);
    } catch (error) {
      console.error('导出图表失败:', error);
      I18nDialog.alert('导出图表失败，请重试');
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
   * 获取所有策略
   */
  public getStrategies(): string[] {
    return Array.from(this.data.strategies.keys());
  }

  /**
   * 获取策略的最优点
   */
  public getOptimalPoint(strategy: string): SamplingEfficiencyData | null {
    return this.data.optimalPoints.get(strategy) || null;
  }
}