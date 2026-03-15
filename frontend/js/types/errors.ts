/**
 * 错误类型定义
 * 统一错误处理系统的类型定义
 */

export enum ErrorType {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  NOT_FOUND = 'not_found',
  SERVER = 'server',
  PLUGIN = 'plugin',
  CACHE = 'cache',
  UNKNOWN = 'unknown'
}

export enum ErrorSeverity {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface ErrorContext {
  url?: string;
  method?: string;
  status?: number;
  params?: any;
  data?: any;
  stack?: string;
  userAgent?: string;
  timestamp?: Date;
  userId?: string;
}

export interface AppError extends Error {
  type: ErrorType;
  severity: ErrorSeverity;
  code: string;
  message: string;
  details?: any;
  context?: ErrorContext;
  originalError?: Error;
  isOperational: boolean;
}

export interface ErrorResponse {
  success: false;
  error: {
    type: ErrorType;
    code: string;
    message: string;
    details?: any;
    timestamp: string;
  };
}