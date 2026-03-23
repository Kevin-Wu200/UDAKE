/**
 * 自定义错误类
 * 提供统一的应用错误处理机制
 */

import type { AppError, ErrorContext } from '../../types/errors';
import { ErrorType, ErrorSeverity } from '../../types/errors';

export class ApplicationError extends Error implements AppError {
  public readonly type: ErrorType;
  public readonly severity: ErrorSeverity;
  public readonly code: string;
  public readonly details?: unknown;
  public readonly context?: ErrorContext;
  public readonly originalError?: Error;
  public readonly isOperational: boolean;

  constructor(
    type: ErrorType,
    code: string,
    message: string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    details?: unknown,
    context?: ErrorContext,
    originalError?: Error
  ) {
    super(message);

    this.name = this.constructor.name;
    this.type = type;
    this.severity = severity;
    this.code = code;
    this.details = details;
    this.context = {
      timestamp: new Date(),
      ...context
    };
    this.originalError = originalError;
    this.isOperational = true;

    // 维护正确的堆栈跟踪（仅在 Node.js 环境中可用）
    if (typeof (Error as { captureStackTrace?: (targetObject: object, constructorOpt?: Function) => void }).captureStackTrace === 'function') {
      (Error as { captureStackTrace?: (targetObject: object, constructorOpt?: Function) => void }).captureStackTrace?.(this, this.constructor);
    }
  }

  toJSON(): Record<string, unknown> {
    return {
      type: this.type,
      code: this.code,
      message: this.message,
      severity: this.severity,
      details: this.details,
      context: this.context,
      originalError: this.originalError?.message,
      stack: this.stack
    };
  }
}

// 具体错误类
export class NetworkError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.NETWORK,
      'NETWORK_ERROR',
      message,
      ErrorSeverity.HIGH,
      details,
      context
    );
  }
}

export class ValidationError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.VALIDATION,
      'VALIDATION_ERROR',
      message,
      ErrorSeverity.MEDIUM,
      details,
      context
    );
  }
}

export class AuthenticationError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.AUTHENTICATION,
      'AUTHENTICATION_ERROR',
      message,
      ErrorSeverity.HIGH,
      details,
      context
    );
  }
}

export class AuthorizationError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.AUTHORIZATION,
      'AUTHORIZATION_ERROR',
      message,
      ErrorSeverity.HIGH,
      details,
      context
    );
  }
}

export class NotFoundError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.NOT_FOUND,
      'NOT_FOUND',
      message,
      ErrorSeverity.MEDIUM,
      details,
      context
    );
  }
}

export class ServerError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.SERVER,
      'SERVER_ERROR',
      message,
      ErrorSeverity.CRITICAL,
      details,
      context
    );
  }
}

export class PluginError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.PLUGIN,
      'PLUGIN_ERROR',
      message,
      ErrorSeverity.HIGH,
      details,
      context
    );
  }
}

export class CacheError extends ApplicationError {
  constructor(message: string, details?: unknown, context?: ErrorContext) {
    super(
      ErrorType.CACHE,
      'CACHE_ERROR',
      message,
      ErrorSeverity.LOW,
      details,
      context
    );
  }
}
