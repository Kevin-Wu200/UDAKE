/**
 * API 请求类型定义
 * 定义所有 API 请求相关的类型和接口
 */

/**
 * 上传数据请求
 */
export interface UploadDataRequest {
  file: File;
  format: 'geojson' | 'csv' | 'shapefile' | 'json';
  options?: {
    encoding?: string;
    skipInvalid?: boolean;
    validate?: boolean;
    transform?: {
      sourceCRS: string;
      targetCRS: string;
    };
  };
}

/**
 * 创建任务请求
 */
export interface CreateTaskRequest {
  datasetId: string;
  taskType: 'kriging' | 'sampling' | 'analysis' | 'export';
  parameters: KrigingTaskParameters | SamplingTaskParameters | AnalysisTaskParameters | ExportTaskParameters;
  options?: TaskOptions;
}

/**
 * 克里金任务参数
 */
export interface KrigingTaskParameters {
  method: 'ordinary' | 'universal' | 'block';
  variogramModel: 'spherical' | 'exponential' | 'gaussian' | 'linear';
  nugget: number;
  sill: number;
  range: number;
  lagDistance: number;
  numberOfLags: number;
  gridResolution: number;
  bounds?: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
}

/**
 * 采样任务参数
 */
export interface SamplingTaskParameters {
  method: 'free' | 'region' | 'grid' | 'stratified' | 'adaptive';
  strategy: 'random' | 'systematic' | 'stratified' | 'adaptive' | 'optimal';
  constraints?: {
    minDistance?: number;
    maxDistance?: number;
    minPoints?: number;
    maxPoints?: number;
  };
  parameters?: {
    gridSize?: number;
    initialPoints?: number;
    maxPoints?: number;
    uncertaintyThreshold?: number;
  };
}

/**
 * 分析任务参数
 */
export interface AnalysisTaskParameters {
  analysisType: 'uncertainty' | 'risk' | 'anomaly' | 'trend';
  parameters: Record<string, unknown>;
}

/**
 * 导出任务参数
 */
export interface ExportTaskParameters {
  format: 'geojson' | 'csv' | 'json' | 'shapefile';
  includeMetadata?: boolean;
  precision?: number;
  filters?: DataFilter[];
}

/**
 * 任务选项
 */
export interface TaskOptions {
  priority: 'urgent' | 'high' | 'medium' | 'low';
  timeout?: number;
  retryCount?: number;
  notifyOnComplete?: boolean;
  callbackUrl?: string;
}

/**
 * 数据过滤条件
 */
export interface DataFilter {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'lt' | 'gte' | 'lte' | 'in' | 'nin' | 'between';
  value: unknown;
  value2?: unknown;
}

/**
 * 更新任务请求
 */
export interface UpdateTaskRequest {
  taskId: string;
  status?: 'pending' | 'running' | 'paused' | 'cancelled' | 'completed' | 'failed';
  parameters?: Record<string, unknown>;
  options?: Partial<TaskOptions>;
}

/**
 * 查询任务请求
 */
export interface QueryTasksRequest {
  status?: string[];
  taskType?: string[];
  datasetId?: string;
  dateRange?: {
    start: Date;
    end: Date;
  };
  pagination?: {
    page: number;
    pageSize: number;
  };
  sort?: {
    field: string;
    order: 'asc' | 'desc';
  };
}

/**
 * 删除任务请求
 */
export interface DeleteTaskRequest {
  taskIds: string[];
  deleteResults?: boolean;
}

/**
 * 评估采样候选点请求
 */
export interface EvaluateSamplingCandidatesRequest {
  taskId: string;
  candidatePoints: Array<{ x: number; y: number }>;
  strategy: 'uncertainty' | 'variance' | 'impact_optimized';
  gridResolution: number;
}

/**
 * 推荐优化采样点请求
 */
export interface RecommendOptimalPointsRequest {
  taskId: string;
  nRecommendations: number;
  strategy: 'uncertainty' | 'variance' | 'impact_optimized';
  constraints?: {
    boundary?: GeoJSONGeometry;
    minDistance?: number;
    maxDistance?: number;
  };
}

/**
 * 批量模拟采样请求
 */
export interface BatchSimulateSamplingRequest {
  taskId: string;
  samplingPlans: Array<{
    points: Array<{ x: number; y: number }>;
    parameters: Record<string, unknown>;
  }>;
  gridResolution: number;
}

/**
 * 插值请求
 */
export interface InterpolationRequest {
  data: {
    points: Array<{
      x: number;
      y: number;
      value: number;
    }>;
    bounds?: {
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
    };
  };
  parameters: KrigingTaskParameters;
}

/**
 * 生成采样点请求
 */
export interface GenerateSamplingPointsRequest {
  data: {
    bounds?: {
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
    };
    existingPoints?: Array<{
      x: number;
      y: number;
      value: number;
    }>;
  };
  parameters: SamplingTaskParameters;
}

/**
 * 执行分析请求
 */
export interface PerformAnalysisRequest {
  data: {
    datasetId?: string;
    grid?: number[][];
    bounds?: {
      minX: number;
      minY: number;
      maxX: number;
      maxY: number;
    };
    variance?: number[][];
  };
  parameters: AnalysisTaskParameters;
}

/**
 * 导出数据请求
 */
export interface ExportDataRequest {
  data: {
    taskId?: string;
    datasetId?: string;
    format: 'geojson' | 'csv' | 'json' | 'shapefile';
  };
  options?: {
    includeMetadata?: boolean;
    precision?: number;
    filters?: DataFilter[];
  };
}

/**
 * 导入数据请求
 */
export interface ImportDataRequest {
  data: {
    file?: File;
    url?: string;
    content?: string;
    format: 'geojson' | 'csv' | 'shapefile' | 'json';
  };
  options?: {
    encoding?: string;
    skipInvalid?: boolean;
    validate?: boolean;
    transform?: {
      sourceCRS: string;
      targetCRS: string;
    };
  };
}

/**
 * 验证数据请求
 */
export interface ValidateDataRequest {
  data: {
    points: Array<{
      x: number;
      y: number;
      value: number;
      metadata?: Record<string, unknown>;
    }>;
  };
  rules?: ValidationRule[];
}

/**
 * 验证规则
 */
export interface ValidationRule {
  field: string;
  type: 'range' | 'regex' | 'enum' | 'custom';
  constraints: {
    min?: number;
    max?: number;
    pattern?: string;
    values?: unknown[];
    custom?: (value: unknown) => boolean;
  };
  message?: string;
}

/**
 * GeoJSON 几何对象
 */
export interface GeoJSONGeometry {
  type: 'Point' | 'LineString' | 'Polygon' | 'MultiPoint' | 'MultiLineString' | 'MultiPolygon';
  coordinates: number[] | number[][] | number[][][] | number[][][][];
}