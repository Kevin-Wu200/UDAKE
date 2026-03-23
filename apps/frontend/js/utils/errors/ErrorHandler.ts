/**
 * 错误处理器
 * 提供统一的错误处理机制
 */

import type { AppError } from '../../types/errors';
import { ErrorType, ErrorSeverity } from '../../types/errors';
import { ApplicationError, NetworkError, ValidationError, AuthenticationError, AuthorizationError, NotFoundError, ServerError, PluginError, CacheError } from './AppError';
import i18n from '../../i18n/config';
import { Logger } from '../Logger';

export interface ErrorHandlerConfig {
  enableLogging: boolean;
  enableReporting: boolean;
  enableUserNotification: boolean;
  logLevel: ErrorSeverity;
  reporter?: (error: AppError, payload: SerializedAppError) => void;
  notifier?: (message: string, error: AppError) => void;
}

interface SerializedAppError {
  type: ErrorType;
  code: string;
  message: string;
  severity: ErrorSeverity;
  details?: unknown;
  context?: unknown;
  stack?: string;
}

declare global {
  interface Window {
    Sentry?: {
      captureException?: (error: Error, context?: Record<string, unknown>) => void;
    };
  }
}

export class ErrorHandler {
  private config: ErrorHandlerConfig;
  private errorHandlers: Map<ErrorType, (error: AppError) => void>;
  private globalHandlers: Array<(error: AppError) => void>;

  constructor(config: Partial<ErrorHandlerConfig> = {}) {
    this.config = {
      enableLogging: true,
      enableReporting: true,
      enableUserNotification: true,
      logLevel: ErrorSeverity.MEDIUM,
      ...config
    };

    this.errorHandlers = new Map();
    this.globalHandlers = [];

    this.initializeDefaultHandlers();
    this.setupGlobalErrorHandlers();
  }

  private initializeDefaultHandlers(): void {
    this.errorHandlers.set(ErrorType.NETWORK, this.handleNetworkError.bind(this));
    this.errorHandlers.set(ErrorType.VALIDATION, this.handleValidationError.bind(this));
    this.errorHandlers.set(ErrorType.AUTHENTICATION, this.handleAuthenticationError.bind(this));
    this.errorHandlers.set(ErrorType.AUTHORIZATION, this.handleAuthorizationError.bind(this));
    this.errorHandlers.set(ErrorType.NOT_FOUND, this.handleNotFoundError.bind(this));
    this.errorHandlers.set(ErrorType.SERVER, this.handleServerError.bind(this));
    this.errorHandlers.set(ErrorType.PLUGIN, this.handlePluginError.bind(this));
    this.errorHandlers.set(ErrorType.CACHE, this.handleCacheError.bind(this));
  }

  private setupGlobalErrorHandlers(): void {
    // 捕获未处理的 Promise 拒绝
    window.addEventListener('unhandledrejection', (event) => {
      this.handle(
        new ApplicationError(
          ErrorType.UNKNOWN,
          'UNHANDLED_PROMISE_REJECTION',
          '未处理的 Promise 拒绝',
          ErrorSeverity.HIGH,
          { reason: event.reason }
        )
      );
    });

    // 捕获全局错误
    window.addEventListener('error', (event) => {
      this.handle(
        new ApplicationError(
          ErrorType.UNKNOWN,
          'GLOBAL_ERROR',
          event.message,
          ErrorSeverity.HIGH,
          { filename: event.filename, lineno: event.lineno },
          event.error
        )
      );
    });
  }

  handle(error: Error | AppError): void {
    let appError: AppError;

    // 转换为 AppError
    if (error instanceof ApplicationError) {
      appError = error;
    } else {
      appError = this.convertToAppError(error);
    }

    // 记录错误
    if (this.shouldLog(appError)) {
      this.logError(appError);
    }

    // 报告错误
    if (this.shouldReport(appError)) {
      this.reportError(appError);
    }

    // 通知用户
    if (this.shouldNotifyUser(appError)) {
      this.notifyUser(appError);
    }

    // 调用特定类型的处理器
    const handler = this.errorHandlers.get(appError.type);
    if (handler) {
      handler(appError);
    }

    // 调用全局处理器
    this.globalHandlers.forEach(handler => handler(appError));
  }

  private convertToAppError(error: Error): AppError {
    // 根据错误信息推断错误类型
    const message = error.message.toLowerCase();
    let type = ErrorType.UNKNOWN;

    if (message.includes('network') || message.includes('fetch')) {
      type = ErrorType.NETWORK;
    } else if (message.includes('validation') || message.includes('invalid')) {
      type = ErrorType.VALIDATION;
    } else if (message.includes('authentication') || message.includes('unauthorized')) {
      type = ErrorType.AUTHENTICATION;
    } else if (message.includes('not found') || message.includes('404')) {
      type = ErrorType.NOT_FOUND;
    }

    return new ApplicationError(
      type,
      'UNKNOWN_ERROR',
      error.message,
      ErrorSeverity.MEDIUM,
      undefined,
      undefined,
      error
    );
  }

  private shouldLog(error: AppError): boolean {
    return this.config.enableLogging &&
           this.compareSeverity(error.severity, this.config.logLevel) >= 0;
  }

  private shouldReport(error: AppError): boolean {
    return this.config.enableReporting &&
           error.isOperational &&
           this.compareSeverity(error.severity, ErrorSeverity.HIGH) >= 0;
  }

  private shouldNotifyUser(error: AppError): boolean {
    return this.config.enableUserNotification &&
           this.compareSeverity(error.severity, ErrorSeverity.MEDIUM) >= 0;
  }

  private compareSeverity(severity1: ErrorSeverity, severity2: ErrorSeverity): number {
    const severityOrder = {
      [ErrorSeverity.LOW]: 0,
      [ErrorSeverity.MEDIUM]: 1,
      [ErrorSeverity.HIGH]: 2,
      [ErrorSeverity.CRITICAL]: 3
    };
    return severityOrder[severity1] - severityOrder[severity2];
  }

  private logError(error: AppError): void {
    const logMethod = this.getLogMethod(error.severity);
    logMethod(
      `[${error.type.toUpperCase()}] ${error.code}: ${error.message}`,
      error.details,
      error.context
    );
  }

  private getLogMethod(severity: ErrorSeverity): (...args: unknown[]) => void {
    switch (severity) {
      case ErrorSeverity.LOW:
        return console.debug;
      case ErrorSeverity.MEDIUM:
        return console.info;
      case ErrorSeverity.HIGH:
        return console.warn;
      case ErrorSeverity.CRITICAL:
        return console.error;
      default:
        return console.log;
    }
  }

  private reportError(error: AppError): void {
    const payload = this.serializeError(error);
    Logger.error('ErrorHandler', '捕获到高优先级错误', payload);

    if (this.config.reporter) {
      this.config.reporter(error, payload);
      return;
    }

    if (window.Sentry?.captureException) {
      window.Sentry.captureException(error, { extra: payload });
      return;
    }

    window.dispatchEvent(new CustomEvent('app:error:reported', { detail: payload }));
  }

  private notifyUser(error: AppError): void {
    const message = this.getUserFriendlyMessage(error);
    if (this.config.notifier) {
      this.config.notifier(message, error);
      return;
    }

    const payload = this.serializeError(error);
    window.dispatchEvent(
      new CustomEvent('app:error:notify', {
        detail: {
          message,
          error: payload
        }
      })
    );

    // 在未接入统一通知中心时，回退为基础提示，避免静默失败。
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      alert(message);
    }
  }

  private serializeError(error: AppError): SerializedAppError {
    const serializableError = error as AppError & { toJSON?: () => SerializedAppError };
    if (typeof serializableError.toJSON === 'function') {
      return serializableError.toJSON();
    }

    return {
      type: error.type,
      code: error.code,
      message: error.message,
      severity: error.severity,
      details: error.details,
      context: error.context,
      stack: error.stack
    };
  }

  private getUserFriendlyMessage(error: AppError): string {
    const errorMessages: Record<ErrorType, string> = {
      [ErrorType.NETWORK]: i18n.t('errors.network'),
      [ErrorType.VALIDATION]: i18n.t('errors.validation'),
      [ErrorType.AUTHENTICATION]: i18n.t('errors.authentication'),
      [ErrorType.AUTHORIZATION]: i18n.t('errors.authorization'),
      [ErrorType.NOT_FOUND]: i18n.t('errors.notFound'),
      [ErrorType.SERVER]: i18n.t('errors.server'),
      [ErrorType.PLUGIN]: i18n.t('errors.plugin'),
      [ErrorType.CACHE]: i18n.t('errors.cache'),
      [ErrorType.UNKNOWN]: i18n.t('errors.unknown')
    };

    return errorMessages[error.type] || error.message;
  }

  // 特定类型的错误处理器
  private handleNetworkError(error: AppError): void {
    Logger.info('ErrorHandler', '处理网络错误', error);
    // 可以在这里实现特定的处理逻辑，如重试
  }

  private handleValidationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理验证错误', error);
    // 可以在这里实现表单验证错误的特殊处理
  }

  private handleAuthenticationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理认证错误', error);
    // 可以在这里实现重定向到登录页面
  }

  private handleAuthorizationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理授权错误', error);
    // 可以在这里实现权限提示
  }

  private handleNotFoundError(error: AppError): void {
    Logger.info('ErrorHandler', '处理未找到错误', error);
    // 可以在这里实现404页面
  }

  private handleServerError(error: AppError): void {
    Logger.info('ErrorHandler', '处理服务器错误', error);
    // 可以在这里实现错误页面
  }

  private handlePluginError(error: AppError): void {
    Logger.info('ErrorHandler', '处理插件错误', error);
    // 可以在这里实现插件错误处理
  }

  private handleCacheError(error: AppError): void {
    Logger.info('ErrorHandler', '处理缓存错误', error);
    // 可以在这里实现缓存清理
  }

  registerHandler(errorType: ErrorType, handler: (error: AppError) => void): void {
    this.errorHandlers.set(errorType, handler);
  }

  registerGlobalHandler(handler: (error: AppError) => void): () => void {
    this.globalHandlers.push(handler);
    // 返回取消注册函数
    return () => {
      const index = this.globalHandlers.indexOf(handler);
      if (index > -1) {
        this.globalHandlers.splice(index, 1);
      }
    };
  }

  updateConfig(config: Partial<ErrorHandlerConfig>): void {
    this.config = { ...this.config, ...config };
  }
}

// 导出单例
export const errorHandler = new ErrorHandler();
