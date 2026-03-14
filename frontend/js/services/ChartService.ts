/**
 * 图表服务层
 * 提供图表配置、数据处理和图表初始化功能
 */

export interface ChartConfig {
  type: 'scatter' | 'line' | 'histogram' | 'multi-line';
  title: string;
  xAxis: {
    name: string;
    unit?: string;
    min?: number;
    max?: number;
  };
  yAxis: {
    name: string;
    unit?: string;
    min?: number;
    max?: number;
  };
  legend?: boolean;
  zoom?: boolean;
  data: any[];
}

export interface ScatterDataPoint {
  x: number;
  y: number;
  label?: string;
  metadata?: Record<string, any>;
}

export interface VariogramModel {
  name: string;
  type: 'spherical' | 'exponential' | 'gaussian' | 'linear';
  nugget: number;
  sill: number;
  range: number;
  fitScore?: number;
}

export interface HistogramBin {
  min: number;
  max: number;
  count: number;
  frequency: number;
  percentage: number;
}

export interface SamplingEfficiencyData {
  samplingPoints: number;
  averageUncertainty: number;
  strategy: string;
  efficiency?: number;
  cost?: number;
}

export class ChartService {
  /**
   * 计算统计指标
   */
  static calculateStatistics(actual: number[], predicted: number[]) {
    if (actual.length !== predicted.length || actual.length === 0) {
      throw new Error('Invalid data for statistics calculation');
    }

    const n = actual.length;
    let sumActual = 0;
    let sumPredicted = 0;
    let sumSquaredError = 0;
    let sumAbsError = 0;
    let sumActualSquared = 0;
    let sumPredictedSquared = 0;
    let sumActualPredicted = 0;

    for (let i = 0; i < n; i++) {
      const a = actual[i];
      const p = predicted[i];
      const error = p - a;

      sumActual += a;
      sumPredicted += p;
      sumSquaredError += error * error;
      sumAbsError += Math.abs(error);
      sumActualSquared += a * a;
      sumPredictedSquared += p * p;
      sumActualPredicted += a * p;
    }

    const meanActual = sumActual / n;
    const meanPredicted = sumPredicted / n;
    const mse = sumSquaredError / n;
    const rmse = Math.sqrt(mse);
    const mae = sumAbsError / n;
    const bias = meanPredicted - meanActual;

    // 计算 R²
    let ssRes = 0;
    let ssTot = 0;
    for (let i = 0; i < n; i++) {
      ssRes += Math.pow(actual[i] - predicted[i], 2);
      ssTot += Math.pow(actual[i] - meanActual, 2);
    }
    const r2 = ssTot !== 0 ? 1 - (ssRes / ssTot) : 0;

    return {
      rmse,
      mae,
      r2,
      bias,
      n,
    };
  }

  /**
   * 计算置信区间
   */
  static calculateConfidenceInterval(
    actual: number[],
    predicted: number[],
    confidence: number = 0.95
  ) {
    const n = actual.length;
    const errors = predicted.map((p, i) => p - actual[i]);
    const meanError = errors.reduce((sum, e) => sum + e, 0) / n;
    const variance = errors.reduce((sum, e) => sum + Math.pow(e - meanError, 2), 0) / (n - 1);
    const stdError = Math.sqrt(variance);

    // 计算置信区间（使用 t 分布）
    const tValue = this.getTValue(n - 1, confidence);
    const margin = tValue * stdError;

    return {
      lower: meanError - margin,
      upper: meanError + margin,
      stdError,
    };
  }

  /**
   * 获取 t 分布的临界值
   */
  private static getTValue(df: number, confidence: number): number {
    // 简化版 t 值查表
    const tTable: Record<number, number> = {
      1: 12.706,
      2: 4.303,
      5: 2.571,
      10: 2.228,
      20: 2.086,
      30: 2.042,
      40: 2.021,
      50: 2.009,
      60: 2.000,
      80: 1.990,
      100: 1.984,
      120: 1.980,
      150: 1.976,
      200: 1.972,
      Infinity: 1.960,
    };

    // 查找最接近的自由度
    const degrees = Object.keys(tTable)
      .map(Number)
      .filter((d) => d <= df || d === Infinity);
    const closestDegree = Math.max(...degrees);

    return tTable[closestDegree] || 1.96;
  }

  /**
   * 生成直方图 bin
   */
  static generateHistogramBins(
    data: number[],
    binCount: number = 20
  ): HistogramBin[] {
    if (data.length === 0) return [];

    const min = Math.min(...data);
    const max = Math.max(...data);
    const binWidth = (max - min) / binCount;

    const bins: HistogramBin[] = [];
    for (let i = 0; i < binCount; i++) {
      bins.push({
        min: min + i * binWidth,
        max: min + (i + 1) * binWidth,
        count: 0,
        frequency: 0,
        percentage: 0,
      });
    }

    // 统计数据点
    data.forEach((value) => {
      let binIndex = Math.floor((value - min) / binWidth);
      if (binIndex >= binCount) binIndex = binCount - 1;
      if (binIndex < 0) binIndex = 0;
      bins[binIndex].count++;
    });

    // 计算频率和百分比
    const totalCount = data.length;
    bins.forEach((bin) => {
      bin.frequency = bin.count / totalCount;
      bin.percentage = (bin.count / totalCount) * 100;
    });

    return bins;
  }

  /**
   * 计算分位数
   */
  static calculateQuantiles(data: number[], quantiles: number[] = [0.25, 0.5, 0.75]) {
    const sorted = [...data].sort((a, b) => a - b);
    const n = sorted.length;

    return quantiles.map((q) => {
      const index = q * (n - 1);
      const lower = Math.floor(index);
      const upper = Math.ceil(index);
      const weight = index - lower;

      if (lower === upper) {
        return sorted[lower];
      }
      return sorted[lower] * (1 - weight) + sorted[upper] * weight;
    });
  }

  /**
   * 计算正态分布参数
   */
  static fitNormalDistribution(data: number[]) {
    const n = data.length;
    if (n === 0) return { mean: 0, stdDev: 0, goodnessOfFit: 0 };

    const mean = data.reduce((sum, d) => sum + d, 0) / n;
    const variance = data.reduce((sum, d) => sum + Math.pow(d - mean, 2), 0) / (n - 1);
    const stdDev = Math.sqrt(variance);

    // 简单的拟合优度检查（偏度和峰度）
    const skewness = data.reduce((sum, d) => sum + Math.pow((d - mean) / stdDev, 3), 0) / n;
    const kurtosis = data.reduce((sum, d) => sum + Math.pow((d - mean) / stdDev, 4), 0) / n - 3;

    const goodnessOfFit = Math.exp(-(Math.abs(skewness) + Math.abs(kurtosis)) / 2);

    return { mean, stdDev, skewness, kurtosis, goodnessOfFit };
  }

  /**
   * 生成变异函数曲线数据
   */
  static generateVariogramCurve(
    model: VariogramModel,
    distance: number[]
  ) {
    const { type, nugget, sill, range } = model;
    const curve = distance.map((d) => {
      let value = nugget;
      const diff = sill - nugget;

      switch (type) {
        case 'spherical':
          if (d < range) {
            value = nugget + diff * (1.5 * (d / range) - 0.5 * Math.pow(d / range, 3));
          } else {
            value = sill;
          }
          break;

        case 'exponential':
          value = nugget + diff * (1 - Math.exp(-3 * d / range));
          break;

        case 'gaussian':
          value = nugget + diff * (1 - Math.exp(-3 * Math.pow(d / range, 2)));
          break;

        case 'linear':
          if (d < range) {
            value = nugget + diff * (d / range);
          } else {
            value = sill;
          }
          break;
      }

      return value;
    });

    return curve;
  }

  /**
   * 计算采样效率
   */
  static calculateSamplingEfficiency(
    initialUncertainty: number,
    finalUncertainty: number,
    samplingPoints: number,
    cost: number = 1
  ) {
    const uncertaintyReduction = initialUncertainty - finalUncertainty;
    const efficiency = uncertaintyReduction / samplingPoints;
    const costEfficiency = uncertaintyReduction / cost;

    return {
      uncertaintyReduction,
      efficiency,
      costEfficiency,
    };
  }

  /**
   * 查找最优采样点数量
   */
  static findOptimalSamplingPoints(
    data: SamplingEfficiencyData[],
    efficiencyThreshold: number = 0.01
  ) {
    if (data.length < 2) return null;

    // 查找效率降低的点
    for (let i = 1; i < data.length; i++) {
      const prevEfficiency = data[i - 1].efficiency || 0;
      const currentEfficiency = data[i].efficiency || 0;
      const improvement = currentEfficiency - prevEfficiency;

      if (improvement < efficiencyThreshold) {
        return data[i - 1];
      }
    }

    // 如果没有找到，返回最后一个点
    return data[data.length - 1];
  }

  /**
   * 导出图表为图片
   */
  static async exportChartAsImage(
    chartElement: HTMLElement,
    format: 'png' | 'svg' | 'pdf' = 'png',
    filename?: string
  ): Promise<Blob> {
    // 使用 Canvas API 或 html2canvas 库
    // 这里先返回一个 Promise，实际实现需要根据使用的图表库调整
    return new Promise((resolve, reject) => {
      try {
        // 创建 canvas
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        // 设置 canvas 大小
        const rect = chartElement.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;

        // 转换为 blob
        canvas.toBlob(
          (blob) => {
            if (blob) {
              resolve(blob);
            } else {
              reject(new Error('Failed to create blob'));
            }
          },
          `image/${format}`,
          1.0
        );
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 下载文件
   */
  static downloadFile(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}