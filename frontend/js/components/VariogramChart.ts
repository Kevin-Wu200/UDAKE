/**
 * 变异函数曲线图组件
 * 用于显示经验变异函数和拟合的变异函数模型
 */

import { ChartService, type VariogramModel } from '../services/ChartService';

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

export class VariogramChart {
  private container: HTMLElement;
  private chart: any;
  private config: VariogramChartConfig;
  private data: VariogramChartData;
  private selectedModel: string | null = null;
  private visibleModels: Set<string> = new Set();

  constructor(config: VariogramChartConfig) {
    this.container = config.container;
    this.config = config;

    // 处理数据
    this.data = this.processData();

    // 设置默认选中的模型
    if (this.config.selectedModel) {
      this.selectedModel = this.config.selectedModel;
    } else if (this.data.models.size > 0) {
      this.selectedModel = this.data.models.keys().next().value;
    }

    // 初始化所有模型可见
    this.data.models.forEach((_, name) => {
      this.visibleModels.add(name);
    });

    // 初始化图表
    this.initializeChart();
  }

  /**
   * 处理数据
   */
  private processData(): VariogramChartData {
    const { empiricalData, models } = this.config;

    // 生成模型曲线
    const modelMap = new Map<string, { model: VariogramModel; curve: number[] }>();

    if (models) {
      const maxDistance = Math.max(...empiricalData.map((d) => d.distance));
      const distance = Array.from({ length: 100 }, (_, i) => (maxDistance * i) / 99);

      models.forEach((model) => {
        const curve = ChartService.generateVariogramCurve(model, distance);
        modelMap.set(model.name, { model, curve });
      });

      // 找出最佳模型
      if (models.length > 0) {
        const bestModel = models.reduce((best, current) => {
          const currentScore = current.fitScore || 0;
          const bestScore = best.fitScore || 0;
          return currentScore > bestScore ? current : best;
        });
        this.data.bestModel = bestModel;
      }
    }

    return {
      empirical: empiricalData,
      models: modelMap,
    };
  }

  /**
   * 初始化图表
   */
  private initializeChart() {
    // 创建图表容器
    const chartContainer = document.createElement('div');
    chartContainer.className = 'variogram-chart';
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

    // 添加模型参数面板
    if (this.config.models && this.config.models.length > 0) {
      this.addModelParametersPanel();
    }
  }

  /**
   * 使用 ECharts 初始化图表
   */
  private initECharts(container: HTMLElement) {
    const echarts = (window as any).echarts;
    this.chart = echarts.init(container);

    const { title, showLegend } = this.config;

    // 生成经验数据
    const empiricalData = this.data.empirical.map((point) => ({
      value: [point.distance, point.semivariance],
      name: `h=${point.distance.toFixed(2)}, N=${point.count}`,
    }));

    // 生成模型曲线
    const series: any[] = [
      {
        name: '经验变异函数',
        type: 'scatter',
        data: empiricalData,
        symbolSize: (data: any) => {
          const point = this.data.empirical.find(
            (p) => p.distance === data.value[0]
          );
          return Math.min(20, Math.max(5, Math.sqrt(point?.count || 1) * 2));
        },
        itemStyle: {
          color: '#333',
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
    ];

    // 添加模型曲线
    this.data.models.forEach((data, name) => {
      if (this.visibleModels.has(name)) {
        const isSelected = name === this.selectedModel;
        const model = data.model;

        const maxDistance = Math.max(...this.data.empirical.map((d) => d.distance));
        const distance = Array.from({ length: 100 }, (_, i) => (maxDistance * i) / 99);

        series.push({
          name: name,
          type: 'line',
          data: distance.map((d, i) => [d, data.curve[i]]),
          lineStyle: {
            color: this.getModelColor(name),
            width: isSelected ? 3 : 2,
            type: isSelected ? 'solid' : 'dashed',
          },
          symbol: 'none',
          smooth: false,
        });
      }
    });

    const option: any = {
      title: {
        text: title || '变异函数曲线',
        left: 'center',
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.seriesName === '经验变异函数') {
            const point = this.data.empirical[params.dataIndex];
            return `
              <div>
                <strong>经验变异函数</strong><br/>
                距离: ${point.distance.toFixed(4)}<br/>
                半方差: ${point.semivariance.toFixed(4)}<br/>
                样本对数: ${point.count}
              </div>
            `;
          } else {
            const modelData = this.data.models.get(params.seriesName);
            if (modelData) {
              const model = modelData.model;
              return `
                <div>
                  <strong>${params.seriesName}</strong><br/>
                  距离: ${params.value[0].toFixed(4)}<br/>
                  半方差: ${params.value[1].toFixed(4)}<br/>
                  模型: ${model.type}<br/>
                  变差值: ${model.nugget.toFixed(4)}<br/>
                  基台值: ${model.sill.toFixed(4)}<br/>
                  范围值: ${model.range.toFixed(4)}
                </div>
              `;
            }
          }
          return '';
        },
      },
      legend: showLegend !== false ? {
        bottom: 10,
        data: ['经验变异函数', ...Array.from(this.data.models.keys())],
        selected: {
          '经验变异函数': true,
          ...Object.fromEntries(
            Array.from(this.data.models.keys()).map((name) => [
              name,
              this.visibleModels.has(name),
            ])
          ),
        },
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
        name: '距离 (h)',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
      },
      yAxis: {
        type: 'value',
        name: '半方差 γ(h)',
        nameLocation: 'middle',
        nameGap: 30,
        scale: true,
        min: 0,
      },
      series,
    };

    this.chart.setOption(option);

    // 添加事件监听
    this.chart.on('click', (params: any) => {
      if (params.componentType === 'legend') {
        this.toggleModel(params.name);
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

    // 绑定事件
    const canvas = chartDiv.querySelector('#variogram-canvas') as HTMLCanvasElement;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      this.drawHTMLChart(canvas, ctx);
    }

    // 生成模型图例
    const legendDiv = chartDiv.querySelector('#model-legend');
    if (legendDiv) {
      this.data.models.forEach((_, name) => {
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item';
        legendItem.innerHTML = `
          <input type="checkbox" id="model-${name}" checked>
          <label for="model-${name}" style="color: ${this.getModelColor(name)}">
            ${name}
          </label>
        `;
        legendDiv.appendChild(legendItem);

        const checkbox = legendItem.querySelector(`#model-${name}`) as HTMLInputElement;
        checkbox.addEventListener('change', (e) => {
          this.toggleModel(name, (e.target as HTMLInputElement).checked);
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
   * 绘制 HTML 版本的变异函数图
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
    const allValues = [
      ...this.data.empirical.map((d) => d.distance),
      ...this.data.empirical.map((d) => d.semivariance),
    ];
    const minX = 0;
    const maxX = Math.max(...this.data.empirical.map((d) => d.distance));
    const minY = 0;
    const maxY = Math.max(...this.data.empirical.map((d) => d.semivariance));

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    // 转换坐标函数
    const scaleX = (x: number) => padding.left + ((x - minX) / rangeX) * chartWidth;
    const scaleY = (y: number) => canvas.height - padding.bottom - ((y - minY) / rangeY) * chartHeight;

    // 绘制背景
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 绘制网格
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    // 绘制模型曲线
    this.data.models.forEach((data, name) => {
      if (this.visibleModels.has(name)) {
        const isSelected = name === this.selectedModel;

        ctx.beginPath();
        ctx.strokeStyle = this.getModelColor(name);
        ctx.lineWidth = isSelected ? 3 : 2;
        if (!isSelected) {
          ctx.setLineDash([5, 5]);
        } else {
          ctx.setLineDash([]);
        }

        const maxDistance = Math.max(...this.data.empirical.map((d) => d.distance));
        const distance = Array.from({ length: 100 }, (_, i) => (maxDistance * i) / 99);

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
      }
    });

    // 绘制经验数据点
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

      // 绘制误差线
      ctx.strokeStyle = '#666';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, y - size);
      ctx.lineTo(x, y + size);
      ctx.moveTo(x - size, y);
      ctx.lineTo(x + size, y);
      ctx.stroke();
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
    ctx.fillText('距离 (h)', canvas.width / 2, canvas.height - 10);

    // Y 轴标签
    ctx.save();
    ctx.translate(15, canvas.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('半方差 γ(h)', 0, 0);
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
      const value = minY + (rangeY * i) / 5;
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
   * 获取模型颜色
   */
  private getModelColor(name: string): string {
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
    } else {
      if (this.visibleModels.has(name)) {
        this.visibleModels.delete(name);
      } else {
        this.visibleModels.add(name);
      }
    }

    // 更新图表
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
   * 更新图表
   */
  private updateChart() {
    if (this.chart) {
      this.chart.setOption({
        series: this.chart.getOption().series.map((s: any) => {
          if (s.name !== '经验变异函数') {
            s.lineStyle = {
              ...s.lineStyle,
              width: s.name === this.selectedModel ? 3 : 2,
              type: s.name === this.selectedModel ? 'solid' : 'dashed',
            };
          }
          return s;
        }),
      });
    }
  }

  /**
   * 添加模型参数面板
   */
  private addModelParametersPanel() {
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

    this.container.appendChild(paramsPanel);
  }

  /**
   * 获取模型类型名称
   */
  private getModelTypeName(type: string): string {
    const typeNames: Record<string, string> = {
      spherical: '球状模型',
      exponential: '指数模型',
      gaussian: '高斯模型',
      linear: '线性模型',
    };
    return typeNames[type] || type;
  }

  /**
   * 调整模型参数
   */
  public adjustModelParameter(
    modelName: string,
    parameter: 'nugget' | 'sill' | 'range',
    value: number
  ) {
    const modelData = this.data.models.get(modelName);
    if (modelData) {
      modelData.model[parameter] = value;

      // 重新生成曲线
      const maxDistance = Math.max(...this.data.empirical.map((d) => d.distance));
      const distance = Array.from({ length: 100 }, (_, i) => (maxDistance * i) / 99);
      modelData.curve = ChartService.generateVariogramCurve(modelData.model, distance);

      // 更新图表
      this.updateChart();
      this.addModelParametersPanel();
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
        `variogram-chart.${format}`
      );

      ChartService.downloadFile(blob, `variogram-chart.${format}`);
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
}