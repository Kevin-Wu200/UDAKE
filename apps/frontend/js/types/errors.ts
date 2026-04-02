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

export enum ErrorLevel {
  INFO = 'INFO',
  WARNING = 'WARNING',
  SEVERE = 'SEVERE',
  FATAL = 'FATAL'
}

export interface ErrorAction {
  key: 'retry' | 'refresh' | 'open_help' | 'dismiss' | string;
  labelKey: string;
  fallbackLabel: string;
  primary?: boolean;
}

export interface ErrorContext {
  source?: string;
  url?: string;
  method?: string;
  status?: number;
  params?: unknown;
  data?: unknown;
  stack?: string;
  userAgent?: string;
  timestamp?: Date;
  userId?: string;
}

export interface AppError extends Error {
  type: ErrorType;
  severity: ErrorSeverity;
  level: ErrorLevel;
  code: string;
  message: string;
  userMessage?: string;
  solutions?: string[];
  actions?: ErrorAction[];
  helpLink?: string;
  details?: unknown;
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
    details?: unknown;
    timestamp: string;
  };
}
