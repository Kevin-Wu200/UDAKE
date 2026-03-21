/**
 * 克里金插值模型类型定义
 * 定义克里金插值相关的类型和接口
 */

/**
 * 克里金方法枚举
 */
export enum KrigingMethod {
  ORDINARY = 'ordinary',
  UNIVERSAL = 'universal',
  BLOCK = 'block',
  SIMPLE = 'simple'
}

/**
 * 变异函数模型枚举
 */
export enum VariogramModel {
  SPHERICAL = 'spherical',
  EXPONENTIAL = 'exponential',
  GAUSSIAN = 'gaussian',
  LINEAR = 'linear',
  POWER = 'power',
  HOLE_EFFECT = 'hole-effect'
}

/**
 * 克里金参数
 */
export interface KrigingParameters {
  method: KrigingMethod;
  variogramModel: VariogramModel;
  nugget: number;
  sill: number;
  range: number;
  lagDistance: number;
  numberOfLags: number;
  anisotropy?: AnisotropyParameters;
  drift?: string[];
}

/**
 * 各向异性参数
 */
export interface AnisotropyParameters {
  angle: number;
  ratio: number;
}

/**
 * 克里金结果
 */
export interface KrigingResult {
  grid: number[][];
  variance: number[][];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  cellSize: number;
  rows: number;
  cols: number;
  statistics: KrigingStatistics;
  parameters: KrigingParameters;
}

/**
 * 克里金统计信息
 */
export interface KrigingStatistics {
  mean: number;
  std: number;
  min: number;
  max: number;
  variance: number;
  rmse?: number; // 均方根误差
  mae?: number;  // 平均绝对误差
  r2?: number;   // 决定系数
}

/**
 * 变异函数点
 */
export interface VariogramPoint {
  lag: number;
  semivariance: number;
  count: number;
}

/**
 * 变异函数拟合结果
 */
export interface VariogramFitResult {
  model: VariogramModel;
  parameters: {
    nugget: number;
    sill: number;
    range: number;
  };
  points: VariogramPoint[];
  fittedPoints: VariogramPoint[];
  r2: number;
  rmse: number;
}

/**
 * 交叉验证结果
 */
export interface CrossValidationResult {
  observed: number[];
  predicted: number[];
  errors: number[];
  statistics: CrossValidationStatistics;
  points: CrossValidationPoint[];
}

/**
 * 交叉验证统计信息
 */
export interface CrossValidationStatistics {
  meanError: number;
  meanSquaredError: number;
  rootMeanSquaredError: number;
  meanAbsoluteError: number;
  standardDeviationOfErrors: number;
  coefficientOfDetermination: number;
}

/**
 * 交叉验证点
 */
export interface CrossValidationPoint {
  x: number;
  y: number;
  observed: number;
  predicted: number;
  error: number;
  standardError: number;
  variance: number;
}

/**
 * 网格配置
 */
export interface GridConfig {
  cellSize: number;
  resolution: number;
  interpolation: 'bilinear' | 'nearest' | 'cubic';
}

/**
 * 克里金任务配置
 */
export interface KrigingTaskConfig {
  parameters: KrigingParameters;
  grid: GridConfig;
  bounds?: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  validation?: CrossValidationConfig;
}

/**
 * 交叉验证配置
 */
export interface CrossValidationConfig {
  method: 'leave-one-out' | 'k-fold';
  k?: number; // 用于 k-fold 交叉验证
  seed?: number; // 随机种子
}

/**
 * 克里金插值进度
 */
export interface KrigingProgress {
  stage: 'preprocessing' | 'computing' | 'postprocessing' | 'completed' | 'failed';
  percentage: number;
  message: string;
  currentStep: number;
  totalSteps: number;
}

/**
 * 克里金错误
 */
export interface KrigingError {
  code: string;
  message: string;
  stage?: string;
  details?: Record<string, unknown>;
}

/**
 * 采样优化建议
 */
export interface SamplingOptimization {
  suggestedPoints: OptimizedSamplingPoint[];
  expectedImprovement: number;
  uncertaintyReduction: number;
  cost: number;
  priority: 'high' | 'medium' | 'low';
}

/**
 * 优化的采样点
 */
export interface OptimizedSamplingPoint {
  x: number;
  y: number;
  expectedUncertainty: number;
  uncertaintyReduction: number;
  variance: number;
  priority: number;
  reason: string;
}

/**
 * 不确定性分析结果
 */
export interface UncertaintyAnalysisResult {
  variance: number[][];
  standardDeviation: number[][];
  confidenceInterval: {
    lower: number[][];
    upper: number[][];
  };
  statistics: {
    meanUncertainty: number;
    maxUncertainty: number;
    minUncertainty: number;
  };
}