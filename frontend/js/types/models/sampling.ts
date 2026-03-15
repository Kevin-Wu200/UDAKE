/**
 * 采样模型类型定义
 * 定义采样相关的类型和接口
 */

/**
 * 采样方法枚举
 */
export enum SamplingMethod {
  FREE = 'free',
  REGION = 'region',
  GRID = 'grid',
  STRATIFIED = 'stratified',
  ADAPTIVE = 'adaptive',
  RANDOM = 'random'
}

/**
 * 采样模式
 */
export enum SamplingMode {
  SINGLE = 'single',
  BATCH = 'batch',
  AUTOMATIC = 'automatic'
}

/**
 * 采样点
 */
export interface SamplingPoint {
  id: string;
  x: number;
  y: number;
  value?: number;
  timestamp?: Date;
  method: SamplingMethod;
  status: 'pending' | 'sampling' | 'completed' | 'failed';
  metadata?: Record<string, unknown>;
}

/**
 * 采样配置
 */
export interface SamplingConfig {
  method: SamplingMethod;
  mode: SamplingMode;
  constraints?: SamplingConstraints;
  parameters?: SamplingParameters;
  validation?: SamplingValidation;
}

/**
 * 采样约束
 */
export interface SamplingConstraints {
  minDistance?: number;
  maxDistance?: number;
  boundary?: GeoJSONGeometry;
  minPoints?: number;
  maxPoints?: number;
  allowedAreas?: GeoJSONGeometry[];
  forbiddenAreas?: GeoJSONGeometry[];
}

/**
 * 采样参数
 */
export interface SamplingParameters {
  gridSize?: number;
  stratification?: StratificationConfig;
  randomSeed?: number;
  adaptiveParameters?: AdaptiveSamplingParameters;
}

/**
 * 分层配置
 */
export interface StratificationConfig {
  strata: StratificationLayer[];
  method: 'equal' | 'proportional' | 'optimal';
}

/**
 * 分层
 */
export interface StratificationLayer {
  id: string;
  name: string;
  geometry: GeoJSONGeometry;
  weight: number;
  targetPoints?: number;
}

/**
 * 自适应采样参数
 */
export interface AdaptiveSamplingParameters {
  initialPoints: number;
  maxPoints: number;
  uncertaintyThreshold: number;
  improvementThreshold: number;
  strategy: 'uncertainty' | 'variance' | 'impact';
}

/**
 * 采样验证配置
 */
export interface SamplingValidation {
  checkDuplicates: boolean;
  checkBounds: boolean;
  checkConstraints: boolean;
  validateValues: boolean;
}

/**
 * 采样结果
 */
export interface SamplingResult {
  points: SamplingPoint[];
  statistics: SamplingStatistics;
  metadata: Record<string, unknown>;
  timestamp: Date;
}

/**
 * 采样统计信息
 */
export interface SamplingStatistics {
  totalPoints: number;
  completedPoints: number;
  pendingPoints: number;
  failedPoints: number;
  successRate: number;
  averageValue?: number;
  minValue?: number;
  maxValue?: number;
  stdValue?: number;
}

/**
 * 采样推荐
 */
export interface SamplingRecommendation {
  id: string;
  type: 'point' | 'area' | 'path';
  priority: 'high' | 'medium' | 'low';
  reason: string;
  expectedValue?: number;
  uncertainty?: number;
  geometry?: GeoJSONGeometry;
  point?: { x: number; y: number };
  metadata?: Record<string, unknown>;
}

/**
 * 采样计划
 */
export interface SamplingPlan {
  id: string;
  name: string;
  description?: string;
  config: SamplingConfig;
  recommendations: SamplingRecommendation[];
  status: 'draft' | 'active' | 'completed' | 'cancelled';
  createdAt: Date;
  updatedAt: Date;
}

/**
 * 采样进度
 */
export interface SamplingProgress {
  planId: string;
  stage: 'preparing' | 'sampling' | 'validating' | 'completed' | 'failed';
  percentage: number;
  message: string;
  currentPoint: number;
  totalPoints: number;
  estimatedTimeRemaining?: number;
}

/**
 * 采样策略
 */
export enum SamplingStrategy {
  RANDOM = 'random',
  SYSTEMATIC = 'systematic',
  STRATIFIED = 'stratified',
  CLUSTER = 'cluster',
  ADAPTIVE = 'adaptive',
  OPTIMAL = 'optimal',
  IMPACT_OPTIMIZED = 'impact_optimized',
  UNCERTAINTY_REDUCTION = 'uncertainty_reduction'
}

/**
 * 采样候选点
 */
export interface SamplingCandidate {
  id: string;
  x: number;
  y: number;
  score: number;
  uncertainty: number;
  variance: number;
  impact: number;
  priority: number;
  metadata?: Record<string, unknown>;
}

/**
 * 采样区域
 */
export interface SamplingRegion {
  id: string;
  name: string;
  geometry: GeoJSONGeometry;
  parameters: RegionSamplingParameters;
  status: 'pending' | 'sampling' | 'completed';
  points: SamplingPoint[];
}

/**
 * 区域采样参数
 */
export interface RegionSamplingParameters {
  minPoints: number;
  maxPoints: number;
  minDistance: number;
  maxDistance: number;
  priority: number;
}

/**
 * 采样评估结果
 */
export interface SamplingEvaluation {
  coverage: number;
  density: number;
  efficiency: number;
  cost: number;
  time: number;
  accuracy?: number;
  overallScore: number;
}