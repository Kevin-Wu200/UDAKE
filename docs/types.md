# TypeScript 类型定义文档

本文档描述了 UDAKE 项目中使用的所有 TypeScript 类型定义。

## 目录

- [数据模型](#数据模型)
- [克里金模型](#克里金模型)
- [采样模型](#采样模型)
- [不确定性模型](#不确定性模型)
- [API 请求类型](#api-请求类型)
- [API 响应类型](#api-响应类型)
- [API 客户端类型](#api-客户端类型)

## 数据模型

### 基本类型

#### GeoJSONGeometry
GeoJSON 几何对象类型。

```typescript
type GeoJSONGeometryType = 'Point' | 'LineString' | 'Polygon' | 'MultiPoint' | 'MultiLineString' | 'MultiPolygon';

interface GeoJSONGeometry {
  type: GeoJSONGeometryType;
  coordinates: number[] | number[][] | number[][][] | number[][][][];
}
```

#### SamplePoint
采样点数据结构。

```typescript
interface SamplePoint {
  id: string;
  x: number;
  y: number;
  value: number;
  timestamp?: Date;
  metadata?: Record<string, unknown>;
  properties?: GeoJSONProperties;
}
```

#### Dataset
数据集结构。

```typescript
interface Dataset {
  id: string;
  name: string;
  description?: string;
  points: SamplePoint[];
  bounds: BoundingBox;
  crs?: CRSInfo;
  createdAt: Date;
  updatedAt: Date;
  metadata?: Record<string, unknown>;
}
```

### 统计类型

#### DatasetStatistics
数据集统计信息。

```typescript
interface DatasetStatistics {
  count: number;
  min: number;
  max: number;
  mean: number;
  std: number;
  variance: number;
  range: number;
}
```

## 克里金模型

### 方法枚举

#### KrigingMethod
克里金插值方法。

```typescript
enum KrigingMethod {
  ORDINARY = 'ordinary',
  UNIVERSAL = 'universal',
  BLOCK = 'block',
  SIMPLE = 'simple'
}
```

#### VariogramModel
变异函数模型。

```typescript
enum VariogramModel {
  SPHERICAL = 'spherical',
  EXPONENTIAL = 'exponential',
  GAUSSIAN = 'gaussian',
  LINEAR = 'linear',
  POWER = 'power',
  HOLE_EFFECT = 'hole-effect'
}
```

### 核心类型

#### KrigingParameters
克里金插值参数。

```typescript
interface KrigingParameters {
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
```

#### KrigingResult
克里金插值结果。

```typescript
interface KrigingResult {
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
```

#### CrossValidationResult
交叉验证结果。

```typescript
interface CrossValidationResult {
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
  points: CrossValidationPoint[];
}
```

## 采样模型

### 方法枚举

#### SamplingMethod
采样方法。

```typescript
enum SamplingMethod {
  FREE = 'free',
  REGION = 'region',
  GRID = 'grid',
  STRATIFIED = 'stratified',
  ADAPTIVE = 'adaptive',
  RANDOM = 'random'
}
```

#### SamplingStrategy
采样策略。

```typescript
enum SamplingStrategy {
  RANDOM = 'random',
  SYSTEMATIC = 'systematic',
  STRATIFIED = 'stratified',
  CLUSTER = 'cluster',
  ADAPTIVE = 'adaptive',
  OPTIMAL = 'optimal',
  IMPACT_OPTIMIZED = 'impact_optimized',
  UNCERTAINTY_REDUCTION = 'uncertainty_reduction'
}
```

### 核心类型

#### SamplingConfig
采样配置。

```typescript
interface SamplingConfig {
  method: SamplingMethod;
  mode: SamplingMode;
  constraints?: SamplingConstraints;
  parameters?: SamplingParameters;
  validation?: SamplingValidation;
}
```

#### SamplingResult
采样结果。

```typescript
interface SamplingResult {
  points: SamplingPoint[];
  statistics: SamplingStatistics;
  metadata: Record<string, unknown>;
  timestamp: Date;
}
```

#### SamplingRecommendation
采样推荐。

```typescript
interface SamplingRecommendation {
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
```

## 不确定性模型

### 类型枚举

#### UncertaintyType
不确定性类型。

```typescript
enum UncertaintyType {
  MEASUREMENT = 'measurement',
  SPATIAL = 'spatial',
  TEMPORAL = 'temporal',
  MODEL = 'model',
  INTERPOLATION = 'interpolation'
}
```

#### UncertaintyLevel
不确定性等级。

```typescript
enum UncertaintyLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  VERY_HIGH = 'very_high'
}
```

### 核心类型

#### UncertaintyValue
不确定性值。

```typescript
interface UncertaintyValue {
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
```

#### UncertaintyClassification
不确定性分类结果。

```typescript
interface UncertaintyClassification {
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
```

#### RiskIndex
风险指数。

```typescript
interface RiskIndex {
  value: number;
  level: 'low' | 'medium' | 'high' | 'critical';
  factors: RiskFactor[];
  timestamp: Date;
}
```

#### SpatialRiskReport
空间风险报告。

```typescript
interface SpatialRiskReport {
  id: string;
  title: string;
  description?: string;
  generatedAt: Date;
  studyArea: GeoJSONGeometry;
  riskIndices: RiskIndex[];
  uncertaintyLevels: UncertaintyClassification;
  hotspots: RiskHotspot[];
  recommendations: DecisionRecommendation[];
  metadata: Record<string, unknown>;
}
```

## API 请求类型

### 数据操作

#### UploadDataRequest
上传数据请求。

```typescript
interface UploadDataRequest {
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
```

#### ImportDataRequest
导入数据请求。

```typescript
interface ImportDataRequest {
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
```

### 任务操作

#### CreateTaskRequest
创建任务请求。

```typescript
interface CreateTaskRequest {
  datasetId: string;
  taskType: 'kriging' | 'sampling' | 'analysis' | 'export';
  parameters: KrigingTaskParameters | SamplingTaskParameters | AnalysisTaskParameters | ExportTaskParameters;
  options?: TaskOptions;
}
```

#### QueryTasksRequest
查询任务请求。

```typescript
interface QueryTasksRequest {
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
```

### 分析操作

#### EvaluateSamplingCandidatesRequest
评估采样候选点请求。

```typescript
interface EvaluateSamplingCandidatesRequest {
  taskId: string;
  candidatePoints: Array<{ x: number; y: number }>;
  strategy: 'uncertainty' | 'variance' | 'impact_optimized';
  gridResolution: number;
}
```

#### RecommendOptimalPointsRequest
推荐优化采样点请求。

```typescript
interface RecommendOptimalPointsRequest {
  taskId: string;
  nRecommendations: number;
  strategy: 'uncertainty' | 'variance' | 'impact_optimized';
  constraints?: {
    boundary?: GeoJSONGeometry;
    minDistance?: number;
    maxDistance?: number;
  };
}
```

## API 响应类型

### 通用响应

#### ApiResponse
通用 API 响应结构。

```typescript
interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  error?: ApiError;
  timestamp: Date;
  requestId?: string;
}
```

#### ApiError
API 错误结构。

```typescript
interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  stack?: string;
}
```

### 任务响应

#### TaskStatusResponse
任务状态响应。

```typescript
interface TaskStatusResponse {
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
```

#### QueryTasksResponse
查询任务响应。

```typescript
interface QueryTasksResponse {
  tasks: TaskSummary[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}
```

### 分析响应

#### EvaluateSamplingCandidatesResponse
评估采样候选点响应。

```typescript
interface EvaluateSamplingCandidatesResponse {
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
```

#### RecommendOptimalPointsResponse
推荐优化采样点响应。

```typescript
interface RecommendOptimalPointsResponse {
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
```

## API 客户端类型

### 配置类型

#### ApiClientConfig
API 客户端配置。

```typescript
interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
  retryCount?: number;
  retryDelay?: number;
  cacheMaxSize?: number;
  cacheTTL?: number;
  headers?: Record<string, string>;
}
```

#### RequestConfig
请求配置。

```typescript
interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
  cache?: boolean;
  retry?: boolean;
}
```

### 响应类型

#### Response
HTTP 响应。

```typescript
interface Response<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}
```

#### CacheEntry
缓存条目。

```typescript
interface CacheEntry<T = unknown> {
  data: T;
  timestamp: number;
  expiresAt?: number;
}
```

### 拦截器类型

#### RequestInterceptor
请求拦截器。

```typescript
type RequestInterceptor = (config: RequestConfig) => RequestConfig | Promise<RequestConfig>;
```

#### ResponseInterceptor
响应拦截器。

```typescript
type ResponseInterceptor<T = unknown> = (response: Response<T>) => Response<T> | Promise<Response<T>>;
```

#### ErrorInterceptor
错误拦截器。

```typescript
type ErrorInterceptor = (error: Error) => Error | Promise<Error>;
```

## 类型使用示例

### 使用数据模型

```typescript
import type { SamplePoint, Dataset, DatasetStatistics } from '../types/models/data';

// 创建采样点
const point: SamplePoint = {
  id: '1',
  x: 100.5,
  y: 200.3,
  value: 15.7,
  timestamp: new Date(),
  metadata: {
    quality: 'high',
    source: 'manual'
  }
};

// 创建数据集
const dataset: Dataset = {
  id: 'dataset-1',
  name: '环境监测数据',
  description: '某地区的环境监测采样数据',
  points: [point],
  bounds: {
    minX: 100,
    minY: 200,
    maxX: 101,
    maxY: 201
  },
  createdAt: new Date(),
  updatedAt: new Date()
};
```

### 使用 API 客户端

```typescript
import { APIService } from '../services/API封装';
import type { UploadDataRequest, UploadDataResponse } from '../types/api';

const api = new APIService('http://localhost:8000');

// 上传数据
const uploadRequest: UploadDataRequest = {
  file: new File([''], 'data.csv'),
  format: 'csv',
  options: {
    skipInvalid: true,
    validate: true
  }
};

const response = await api.uploadData(uploadRequest.file);
```

### 使用克里金类型

```typescript
import type { KrigingParameters, KrigingMethod, VariogramModel } from '../types/models/kriging';

// 配置克里金参数
const params: KrigingParameters = {
  method: KrigingMethod.ORDINARY,
  variogramModel: VariogramModel.SPHERICAL,
  nugget: 0.1,
  sill: 1.0,
  range: 100,
  lagDistance: 10,
  numberOfLags: 20,
  anisotropy: {
    angle: 0,
    ratio: 1
  }
};
```

### 使用采样类型

```typescript
import type { SamplingConfig, SamplingMethod, SamplingStrategy } from '../types/models/sampling';

// 配置采样
const config: SamplingConfig = {
  method: SamplingMethod.ADAPTIVE,
  mode: 'automatic',
  constraints: {
    minDistance: 10,
    maxDistance: 100,
    maxPoints: 50
  },
  parameters: {
    initialPoints: 10,
    maxPoints: 50,
    uncertaintyThreshold: 0.5,
    strategy: SamplingStrategy.UNCERTAINTY_REDUCTION
  }
};
```

## 类型安全最佳实践

1. **避免使用 `any` 类型**：始终使用具体的类型定义
2. **使用泛型**：对于通用函数和组件，使用泛型提高类型安全性
3. **使用类型守卫**：在运行时验证数据类型
4. **使用 `unknown` 替代 `any`**：在确实需要动态类型时使用 `unknown`
5. **定义完整的接口**：为所有数据结构定义完整的接口
6. **使用联合类型**：对于有限的选择，使用联合类型而非字符串
7. **使用枚举**：对于固定的常量集合，使用枚举

## 相关文档

- [Any 类型使用清单](./any-types-analysis.md)
- [开发指南](./开发指南.md)
- [API 文档](./API文档.md)