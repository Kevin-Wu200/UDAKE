/**
 * API 响应类型定义
 * 定义所有 API 响应相关的类型和接口
 */

/**
 * 通用 API 响应
 */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  error?: ApiError;
  timestamp: Date;
  requestId?: string;
}

/**
 * API 错误
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  stack?: string;
}

/**
 * 上传数据响应
 */
export interface UploadDataResponse {
  datasetId: string;
  fileName: string;
  recordCount: number;
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  statistics: {
    count: number;
    min: number;
    max: number;
    mean: number;
    std: number;
  };
}

/**
 * 创建任务响应
 */
export interface CreateTaskResponse {
  taskId: string;
  status: 'pending' | 'queued';
  estimatedDuration?: number;
  createdAt: Date;
}

/**
 * 任务状态响应
 */
export interface TaskStatusResponse {
  taskId: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  stage: string;
  message: string;
  result?: TaskResult;
  error?: ApiError;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  estimatedTimeRemaining?: number;
}

/**
 * 任务结果
 */
export interface TaskResult {
  taskId: string;
  taskType: 'kriging' | 'sampling' | 'analysis' | 'export';
  data: KrigingResult | SamplingResult | AnalysisResult | ExportResult;
  statistics: TaskStatistics;
  generatedAt: Date;
}

/**
 * 任务统计信息
 */
export interface TaskStatistics {
  duration: number;
  memoryUsage?: number;
  cpuUsage?: number;
  success: boolean;
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
  statistics: {
    mean: number;
    std: number;
    min: number;
    max: number;
    variance: number;
  };
  crossValidation?: CrossValidationResult;
}

/**
 * 交叉验证结果
 */
export interface CrossValidationResult {
  observed: number[];
  predicted: number[];
  errors: number[];
  statistics: {
    meanError: number;
    meanSquaredError: number;
    rootMeanSquaredError: number;
    meanAbsoluteError: number;
    coefficientOfDetermination: number;
  };
}

/**
 * 采样结果
 */
export interface SamplingResult {
  points: Array<{
    id: string;
    x: number;
    y: number;
    value?: number;
    uncertainty?: number;
    priority?: number;
  }>;
  statistics: {
    totalPoints: number;
    completedPoints: number;
    pendingPoints: number;
    successRate: number;
  };
}

/**
 * 分析结果
 */
export interface AnalysisResult {
  analysisType: 'uncertainty' | 'risk' | 'anomaly' | 'trend';
  result: UncertaintyAnalysisResult | RiskAnalysisResult | AnomalyAnalysisResult | TrendAnalysisResult;
}

/**
 * 不确定性分析结果
 */
export interface UncertaintyAnalysisResult {
  uncertainty: number[][];
  levels: string[][];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  cellSize: number;
  statistics: {
    mean: number;
    std: number;
    min: number;
    max: number;
  };
}

/**
 * 风险分析结果
 */
export interface RiskAnalysisResult {
  riskIndex: number[][];
  riskLevel: string[][];
  hotspots: Array<{
    x: number;
    y: number;
    radius: number;
    riskLevel: number;
  }>;
  recommendations: string[];
}

/**
 * 异常分析结果
 */
export interface AnomalyAnalysisResult {
  anomalies: Array<{
    id: string;
    x: number;
    y: number;
    value: number;
    score: number;
    severity: string;
  }>;
  statistics: {
    total: number;
    high: number;
    medium: number;
    low: number;
  };
}

/**
 * 趋势分析结果
 */
export interface TrendAnalysisResult {
  trend: 'increasing' | 'decreasing' | 'stable' | 'fluctuating';
  slope: number;
  intercept: number;
  rSquared: number;
  pValue: number;
  confidenceInterval: {
    lower: number;
    upper: number;
  };
}

/**
 * 导出结果
 */
export interface ExportResult {
  fileId: string;
  fileName: string;
  format: string;
  size: number;
  downloadUrl: string;
  expiresAt: Date;
}

/**
 * 查询任务响应
 */
export interface QueryTasksResponse {
  tasks: TaskSummary[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

/**
 * 任务摘要
 */
export interface TaskSummary {
  taskId: string;
  taskType: 'kriging' | 'sampling' | 'analysis' | 'export';
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  duration?: number;
}

/**
 * 更新任务响应
 */
export interface UpdateTaskResponse {
  taskId: string;
  status: string;
  updatedAt: Date;
}

/**
 * 删除任务响应
 */
export interface DeleteTaskResponse {
  deletedTaskIds: string[];
  deletedResultIds: string[];
  count: number;
}

/**
 * 评估采样候选点响应
 */
export interface EvaluateSamplingCandidatesResponse {
  taskId: string;
  candidates: Array<{
    x: number;
    y: number;
    score: number;
    uncertainty: number;
    variance: number;
    impact: number;
    priority: number;
  }>;
  statistics: {
    meanScore: number;
    maxScore: number;
    minScore: number;
  };
}

/**
 * 推荐优化采样点响应
 */
export interface RecommendOptimalPointsResponse {
  taskId: string;
  recommendations: Array<{
    x: number;
    y: number;
    expectedUncertainty: number;
    uncertaintyReduction: number;
    variance: number;
    priority: number;
    reason: string;
  }>;
  expectedImprovement: number;
  uncertaintyReduction: number;
  cost: number;
}

/**
 * 批量模拟采样响应
 */
export interface BatchSimulateSamplingResponse {
  taskId: string;
  results: Array<{
    planId: string;
    points: Array<{
      x: number;
      y: number;
    }>;
    uncertainty: number[][];
    statistics: {
      meanUncertainty: number;
      maxUncertainty: number;
      minUncertainty: number;
    };
  }>;
  comparison: {
    bestPlanId: string;
    rankings: Array<{
      planId: string;
      rank: number;
      score: number;
    }>;
  };
}

/**
 * 插值响应
 */
export interface InterpolationResponse {
  taskId: string;
  grid: number[][];
  variance: number[][];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  cellSize: number;
  statistics: {
    mean: number;
    std: number;
    min: number;
    max: number;
  };
}

/**
 * 生成采样点响应
 */
export interface GenerateSamplingPointsResponse {
  taskId: string;
  points: Array<{
    x: number;
    y: number;
    uncertainty?: number;
    priority?: number;
  }>;
  count: number;
}

/**
 * 执行分析响应
 */
export interface PerformAnalysisResponse {
  taskId: string;
  analysisType: string;
  result: unknown;
  generatedAt: Date;
}

/**
 * 导出数据响应
 */
export interface ExportDataResponse {
  fileId: string;
  fileName: string;
  format: string;
  size: number;
  downloadUrl: string;
  expiresAt: Date;
  recordCount?: number;
}

/**
 * 导入数据响应
 */
export interface ImportDataResponse {
  datasetId: string;
  fileName: string;
  recordCount: number;
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
  statistics: {
    count: number;
    min: number;
    max: number;
    mean: number;
    std: number;
  };
  validation?: ValidationResult;
}

/**
 * 验证结果
 */
export interface ValidationResult {
  valid: boolean;
  errors: Array<{
    field: string;
    message: string;
    value: unknown;
  }>;
  warnings: Array<{
    field: string;
    message: string;
    value: unknown;
    severity: string;
  }>;
}

/**
 * 批量响应
 */
export interface BatchResponse<T = unknown> {
  successes: Array<{
    id: string;
    data: T;
  }>;
  failures: Array<{
    id: string;
    error: ApiError;
  }>;
  total: number;
  successCount: number;
  failureCount: number;
}