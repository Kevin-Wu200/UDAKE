/**
 * 错误类型定义
 */

/** 错误类型枚举 */
export enum ErrorType {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  NOT_FOUND = 'not_found',
  SERVER = 'server',
  PLUGIN = 'plugin',
  CACHE = 'cache'
}

/** 错误严重程度枚举 */
export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

/** 错误上下文 */
export interface ErrorContext {
  timestamp?: Date;
  userId?: string;
  sessionId?: string;
  requestId?: string;
  url?: string;
  method?: string;
  userAgent?: string;
  [key: string]: any;
}

/** 应用错误接口 */
export interface AppError {
  type: ErrorType;
  code: string;
  message: string;
  severity: ErrorSeverity;
  details?: any;
  context?: ErrorContext;
  originalError?: Error;
  isOperational: boolean;
  toJSON?(): any;
}