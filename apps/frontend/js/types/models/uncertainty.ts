/**
 * 不确定性模型类型定义
 * 定义不确定性分析相关的类型和接口
 */

import type { Geometry } from 'geojson';

/**
 * 不确定性类型
 */
export enum UncertaintyType {
  MEASUREMENT = 'measurement',
  SPATIAL = 'spatial',
  TEMPORAL = 'temporal',
  MODEL = 'model',
  INTERPOLATION = 'interpolation'
}

/**
 * 不确定性等级
 */
export enum UncertaintyLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  VERY_HIGH = 'very_high'
}

/**
 * 不确定性值
 */
export interface UncertaintyValue {
  value: number;
  variance?: number;
  standardDeviation?: number;
  confidenceInterval?: {
    lower: number;
    upper: number;
  };
  level: UncertaintyLevel;
  type: UncertaintyType;
}

/**
 * 不确定性分布
 */
export enum UncertaintyDistribution {
  NORMAL = 'normal',
  LOG_NORMAL = 'log_normal',
  UNIFORM = 'uniform',
  TRIANGULAR = 'triangular',
  BETA = 'beta',
  CUSTOM = 'custom'
}

/**
 * 不确定性参数
 */
export interface UncertaintyParameters {
  distribution: UncertaintyDistribution;
  mean: number;
  variance?: number;
  std?: number;
  parameters?: Record<string, number>;
}

/**
 * 不确定性网格
 */
export interface UncertaintyGrid {
  data: UncertaintyValue[][];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  cellSize: number;
  rows: number;
  cols: number;
  crs?: string;
}

/**
 * 不确定性统计信息
 */
export interface UncertaintyStatistics {
  mean: number;
  std: number;
  min: number;
  max: number;
  variance: number;
  median: number;
  percentile25: number;
  percentile75: number;
  skewness?: number;
  kurtosis?: number;
}

/**
 * 不确定性分类结果
 */
export interface UncertaintyClassification {
  grid: UncertaintyLevel[][];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  cellSize: number;
  rows: number;
  cols: number;
  thresholds: {
    low: number;
    medium: number;
    high: number;
  };
  statistics: UncertaintyLevelStatistics;
}

/**
 * 不确定性等级统计
 */
export interface UncertaintyLevelStatistics {
  low: number;
  medium: number;
  high: number;
  veryHigh: number;
  total: number;
  percentages: {
    low: number;
    medium: number;
    high: number;
    veryHigh: number;
  };
}

/**
 * 风险指数
 */
export interface RiskIndex {
  value: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  factors: RiskFactor[];
  timestamp: Date;
}

/**
 * 风险因子
 */
export interface RiskFactor {
  name: string;
  weight: number;
  value: number;
  description: string;
}

/**
 * 决策阈值
 */
export interface DecisionThreshold {
  name: string;
  value: number;
  operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte';
  action: string;
  priority: number;
}

/**
 * 决策建议
 */
export interface DecisionRecommendation {
  recommendation: string;
  confidence: number;
  reasoning: string[];
  alternatives: string[];
  riskLevel: RiskIndex;
  uncertainty: UncertaintyValue;
}

/**
 * 空间风险报告
 */
export interface SpatialRiskReport {
  id: string;
  title: string;
  description?: string;
  generatedAt: Date;
  studyArea: Geometry;
  riskIndices: RiskIndex[];
  uncertaintyLevels: UncertaintyClassification;
  hotspots: RiskHotspot[];
  recommendations: DecisionRecommendation[];
  metadata: Record<string, unknown>;
}

/**
 * 风险热点
 */
export interface RiskHotspot {
  id: string;
  location: { x: number; y: number };
  radius: number;
  riskLevel: number;
  uncertaintyLevel: UncertaintyLevel;
  factors: RiskFactor[];
  priority: 'high' | 'medium' | 'low';
}

/**
 * 不确定性传播模型
 */
export interface UncertaintyPropagation {
  inputUncertainties: UncertaintyValue[];
  propagationMethod: 'monte_carlo' | 'analytical' | 'fuzzy';
  outputUncertainty: UncertaintyValue;
  sensitivity: SensitivityAnalysis;
}

/**
 * 敏感性分析
 */
export interface SensitivityAnalysis {
  parameters: SensitivityParameter[];
  method: 'sobol' | 'morris' | 'local';
}

/**
 * 敏感性参数
 */
export interface SensitivityParameter {
  name: string;
  sensitivity: number;
  contribution: number;
  rank: number;
}

/**
 * 不确定性可视化配置
 */
export interface UncertaintyVisualizationConfig {
  type: 'heatmap' | 'contour' | 'scatter' | 'bar' | 'histogram';
  colorScale: {
    low: string;
    medium: string;
    high: string;
    veryHigh: string;
  };
  opacity: number;
  showContours: boolean;
  showLabels: boolean;
  legend: boolean;
}

/**
 * 异常检测结果
 */
export interface AnomalyDetectionResult {
  anomalies: AnomalyPoint[];
  statistics: AnomalyStatistics;
  confidence: number;
  method: string;
}

/**
 * 异常点
 */
export interface AnomalyPoint {
  id: string;
  x: number;
  y: number;
  value: number;
  score: number;
  severity: 'low' | 'medium' | 'high';
  reason: string;
  context: Record<string, unknown>;
}

/**
 * 异常统计
 */
export interface AnomalyStatistics {
  total: number;
  low: number;
  medium: number;
  high: number;
  percentage: number;
}