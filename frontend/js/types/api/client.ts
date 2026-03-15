/**
 * API 客户端类型定义
 * 定义 API 客户端配置和请求/响应类型
 */

/**
 * API 客户端配置
 */
export interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
  retryCount?: number;
  retryDelay?: number;
  cacheMaxSize?: number;
  cacheTTL?: number;
  headers?: Record<string, string>;
}

/**
 * 请求配置
 */
export interface RequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  params?: Record<string, unknown>;
  data?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
  cache?: boolean;
  retry?: boolean;
}

/**
 * HTTP 响应
 */
export interface Response<T = unknown> {
  data: T;
  status: number;
  statusText: string;
  headers: Record<string, string>;
}

/**
 * 缓存条目
 */
export interface CacheEntry<T = unknown> {
  data: T;
  timestamp: number;
  expiresAt?: number;
}

/**
 * 请求拦截器
 */
export type RequestInterceptor = (config: RequestConfig) => RequestConfig | Promise<RequestConfig>;

/**
 * 响应拦截器
 */
export type ResponseInterceptor<T = unknown> = (response: Response<T>) => Response<T> | Promise<Response<T>>;

/**
 * 错误拦截器
 */
export type ErrorInterceptor = (error: Error) => Error | Promise<Error>;

/**
 * 进度回调
 */
export type ProgressCallback = (progress: {
  loaded: number;
  total: number;
  percentage: number;
}) => void;

/**
 * 上传配置
 */
export interface UploadConfig {
  file: File;
  field?: string;
  data?: Record<string, unknown>;
  onProgress?: ProgressCallback;
}

/**
 * 下载配置
 */
export interface DownloadConfig {
  url: string;
  filename?: string;
  onProgress?: ProgressCallback;
}

/**
 * API 客户端实例
 */
export interface IApiClient {
  request<T>(config: RequestConfig): Promise<Response<T>>;
  get<T>(url: string, params?: Record<string, unknown>, config?: Partial<RequestConfig>): Promise<Response<T>>;
  post<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<Response<T>>;
  put<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<Response<T>>;
  delete<T>(url: string, config?: Partial<RequestConfig>): Promise<Response<T>>;
  patch<T>(url: string, data?: unknown, config?: Partial<RequestConfig>): Promise<Response<T>>;
  upload<T>(config: UploadConfig): Promise<Response<T>>;
  download(config: DownloadConfig): Promise<void>;
  setBaseURL(url: string): void;
  setHeader(key: string, value: string): void;
  setHeaders(headers: Record<string, string>): void;
  clearCache(): void;
  cancelAll(): void;
  addRequestInterceptor(interceptor: RequestInterceptor): void;
  addResponseInterceptor(interceptor: ResponseInterceptor): void;
  addErrorInterceptor(interceptor: ErrorInterceptor): void;
}