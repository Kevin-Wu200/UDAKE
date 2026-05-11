/**
 * 错误处理器
 * 提供统一的错误处理机制
 */

import type { AppError, ErrorAction } from '../../types/errors';
import { ErrorType, ErrorSeverity, ErrorLevel } from '../../types/errors';
import { ApplicationError } from './AppError';
import { I18n } from '../I18n';
import { Logger } from '../Logger';
import { I18nDialog } from '../../components/I18nDialog.js';

export interface ErrorHandlerConfig {
  enableLogging: boolean;
  enableReporting: boolean;
  enableUserNotification: boolean;
  logLevel: ErrorSeverity;
  autoUploadThreshold: number;
  reporter?: (error: AppError, payload: SerializedAppError) => void;
  notifier?: (message: string, error: AppError, guide: ErrorGuide) => void;
}

export interface ErrorProcessingContext {
  source?: string;
  operation?: string;
  userId?: string;
  requestId?: string;
  [key: string]: unknown;
}

interface ErrorStat {
  type: ErrorType;
  code: string;
  level: ErrorLevel;
  count: number;
  lastSeenAt: string;
}

interface ErrorLogRecord {
  type: ErrorType;
  code: string;
  level: ErrorLevel;
  message: string;
  timestamp: string;
  context?: unknown;
  stack?: string;
}

interface ErrorGuide {
  message: string;
  solutions: string[];
  actions: ErrorAction[];
  helpLink?: string;
}

interface MiddlewareContext {
  timestamp: string;
  context: ErrorProcessingContext;
}

interface SerializedAppError {
  type: ErrorType;
  code: string;
  message: string;
  severity: ErrorSeverity;
  level: ErrorLevel;
  userMessage?: string;
  details?: unknown;
  solutions?: string[];
  actions?: ErrorAction[];
  helpLink?: string;
  context?: unknown;
  stack?: string;
  occurrenceCount?: number;
}

type ErrorMiddleware = (
  error: AppError,
  middlewareContext: MiddlewareContext,
  next: () => Promise<void>
) => Promise<void> | void;

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
  private middlewares: ErrorMiddleware[];
  private stats: Map<string, ErrorStat>;
  private errorLogs: ErrorLogRecord[];

  constructor(config: Partial<ErrorHandlerConfig> = {}) {
    this.config = {
      enableLogging: true,
      enableReporting: true,
      enableUserNotification: true,
      logLevel: ErrorSeverity.MEDIUM,
      autoUploadThreshold: 50,
      ...config
    };

    this.errorHandlers = new Map();
    this.globalHandlers = [];
    this.middlewares = [];
    this.stats = new Map();
    this.errorLogs = [];

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
    if (typeof window === 'undefined') {
      return;
    }

    window.addEventListener('unhandledrejection', (event) => {
      // 防止浏览器默认的错误日志
      event.preventDefault();
      this.handle(
        new ApplicationError(
          ErrorType.UNKNOWN,
          'E-SYS-UNHANDLED-REJECTION',
          '应用出现未处理的异步错误，请稍后重试',
          ErrorSeverity.HIGH,
          { reason: event.reason },
          { source: 'global.unhandledrejection' }
        ),
        { source: 'global.unhandledrejection' }
      );
    });

    window.addEventListener('error', (event) => {
      this.handle(
        new ApplicationError(
          ErrorType.UNKNOWN,
          'E-SYS-GLOBAL-ERROR',
          event.message || '应用出现异常错误',
          ErrorSeverity.HIGH,
          { filename: event.filename, lineno: event.lineno },
          { source: 'global.error' },
          event.error
        ),
        { source: 'global.error' }
      );
    });
  }

  handle(error: Error | AppError, context: ErrorProcessingContext = {}): void {
    const appError = error instanceof ApplicationError ? error : this.convertToAppError(error);
    const middlewareContext: MiddlewareContext = {
      timestamp: new Date().toISOString(),
      context
    };

    void this.runMiddlewares(appError, middlewareContext, async () => {
      this.processError(appError, context);
    });
  }

  async withErrorBoundary<T>(
    task: () => Promise<T> | T,
    fallbackValue: T,
    context: ErrorProcessingContext = {}
  ): Promise<T> {
    try {
      return await task();
    } catch (error) {
      this.handle(error instanceof Error ? error : new Error(String(error)), context);
      return fallbackValue;
    }
  }

  registerMiddleware(middleware: ErrorMiddleware): () => void {
    this.middlewares.push(middleware);
    return () => {
      this.middlewares = this.middlewares.filter((item) => item !== middleware);
    };
  }

  clearMiddlewares(): void {
    this.middlewares = [];
  }

  getErrorStats(): ErrorStat[] {
    return Array.from(this.stats.values()).sort((a, b) => b.count - a.count);
  }

  clearErrorStats(): void {
    this.stats.clear();
  }

  getErrorLogs(limit = 100): ErrorLogRecord[] {
    if (limit <= 0) {
      return [];
    }
    return this.errorLogs.slice(-limit);
  }

  clearErrorLogs(): void {
    this.errorLogs = [];
  }

  private async runMiddlewares(
    appError: AppError,
    middlewareContext: MiddlewareContext,
    finalHandler: () => Promise<void>
  ): Promise<void> {
    let index = -1;
    const dispatch = async (currentIndex: number): Promise<void> => {
      if (currentIndex <= index) {
        return;
      }
      index = currentIndex;

      if (currentIndex === this.middlewares.length) {
        await finalHandler();
        return;
      }

      const middleware = this.middlewares[currentIndex];
      await middleware(appError, middlewareContext, () => dispatch(currentIndex + 1));
    };

    await dispatch(0);
  }

  private processError(appError: AppError, context: ErrorProcessingContext): void {
    this.recordStats(appError);
    this.recordErrorLog(appError, context);

    if (this.shouldLog(appError)) {
      this.logError(appError, context);
    }

    if (this.shouldReport(appError)) {
      this.reportError(appError);
    }

    if (this.shouldNotifyUser(appError)) {
      this.notifyUser(appError);
    }

    const handler = this.errorHandlers.get(appError.type);
    if (handler) {
      handler(appError);
    }

    this.globalHandlers.forEach(handlerFn => handlerFn(appError));

    if (this.config.enableReporting && this.errorLogs.length >= this.config.autoUploadThreshold) {
      this.uploadErrorLogs();
    }
  }

  private convertToAppError(error: Error): AppError {
    const message = error.message.toLowerCase();
    let type = ErrorType.UNKNOWN;
    let code = 'E-APP-UNKNOWN';

    if (message.includes('network') || message.includes('fetch')) {
      type = ErrorType.NETWORK;
      code = 'E-NET-REQUEST';
    } else if (message.includes('validation') || message.includes('invalid')) {
      type = ErrorType.VALIDATION;
      code = 'E-VAL-INPUT';
    } else if (message.includes('authentication') || message.includes('unauthorized')) {
      type = ErrorType.AUTHENTICATION;
      code = 'E-AUTH-LOGIN';
    } else if (message.includes('not found') || message.includes('404')) {
      type = ErrorType.NOT_FOUND;
      code = 'E-HTTP-404';
    }

    return new ApplicationError(
      type,
      code,
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

  private recordStats(error: AppError): void {
    const key = `${error.type}:${error.code}`;
    const current = this.stats.get(key);
    const nextCount = current ? current.count + 1 : 1;

    this.stats.set(key, {
      type: error.type,
      code: error.code,
      level: error.level,
      count: nextCount,
      lastSeenAt: new Date().toISOString()
    });
  }

  private recordErrorLog(error: AppError, context: ErrorProcessingContext): void {
    const payload = this.serializeError(error);
    this.errorLogs.push({
      type: payload.type,
      code: payload.code,
      level: payload.level,
      message: payload.userMessage || payload.message,
      timestamp: new Date().toISOString(),
      context: {
        ...(payload.context || {}),
        ...context
      },
      stack: payload.stack
    });

    if (this.errorLogs.length > 500) {
      this.errorLogs.shift();
    }
  }

  private logError(error: AppError, context: ErrorProcessingContext): void {
    const logMethod = this.getLogMethod(error.severity);
    logMethod(
      `[${error.level}] [${error.code}] ${error.message}`,
      {
        details: error.details,
        context: {
          ...(error.context || {}),
          ...context
        },
        solutions: error.solutions,
        helpLink: error.helpLink
      }
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

    if (typeof window !== 'undefined' && window.Sentry?.captureException) {
      window.Sentry.captureException(error, { extra: payload });
      return;
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('app:error:reported', { detail: payload }));
    }
  }

  private notifyUser(error: AppError): void {
    const guide = this.buildErrorGuide(error);
    if (this.config.notifier) {
      this.config.notifier(guide.message, error, guide);
      return;
    }

    const payload = this.serializeError(error);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('app:error:notify', {
          detail: {
            message: guide.message,
            guide,
            error: payload
          }
        })
      );
    }

    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      I18nDialog.alert(`${guide.message}\n${guide.solutions[0] || ''}`.trim());
    }
  }

  private serializeError(error: AppError): SerializedAppError {
    const serializableError = error as AppError & { toJSON?: () => SerializedAppError };
    const basePayload = typeof serializableError.toJSON === 'function'
      ? serializableError.toJSON()
      : {
          type: error.type,
          code: error.code,
          message: error.message,
          severity: error.severity,
          level: error.level,
          userMessage: error.userMessage,
          details: error.details,
          solutions: error.solutions,
          actions: error.actions,
          helpLink: error.helpLink,
          context: error.context,
          stack: error.stack
        };

    const statKey = `${error.type}:${error.code}`;
    const occurrenceCount = this.stats.get(statKey)?.count || 1;
    return {
      ...basePayload,
      occurrenceCount
    };
  }

  private buildErrorGuide(error: AppError): ErrorGuide {
    const rawMessage = (error.userMessage || error.message || '').trim();
    const translatedUnknown = I18n.t('error.common.unknown');
    const isGenericUnknownMessage = !rawMessage ||
      rawMessage === translatedUnknown ||
      rawMessage.toLowerCase() === 'unknown error' ||
      rawMessage.toLowerCase() === '未知错误';

    const defaultGuide = this.getDefaultGuide(error.type);
    const message = isGenericUnknownMessage ? defaultGuide.message : rawMessage;

    return {
      message,
      solutions: error.solutions && error.solutions.length > 0 ? error.solutions : defaultGuide.solutions,
      actions: error.actions && error.actions.length > 0 ? error.actions : defaultGuide.actions,
      helpLink: error.helpLink || defaultGuide.helpLink
    };
  }

  private getDefaultGuide(errorType: ErrorType): ErrorGuide {
    const unknownMessage = I18n.t('error.common.unknown');
    const actionRetry: ErrorAction = {
      key: 'retry',
      labelKey: 'error.common.retryButton',
      fallbackLabel: '重试',
      primary: true
    };

    const actionRefresh: ErrorAction = {
      key: 'refresh',
      labelKey: 'error.common.refreshButton',
      fallbackLabel: '刷新'
    };

    const actionHelp: ErrorAction = {
      key: 'open_help',
      labelKey: 'error.common.helpButton',
      fallbackLabel: '查看帮助'
    };

    const fallback: Record<ErrorType, ErrorGuide> = {
      [ErrorType.NETWORK]: {
        message: I18n.t('error.network_error.message'),
        solutions: [
          I18n.t('error.network_error.suggestion'),
          I18n.t('error.solution.check_network')
        ],
        actions: [actionRetry, actionRefresh, actionHelp],
        helpLink: '/help/network'
      },
      [ErrorType.VALIDATION]: {
        message: I18n.t('error.validation_error.message'),
        solutions: [I18n.t('error.validation_error.suggestion')],
        actions: [actionRefresh],
        helpLink: '/help/data-validation'
      },
      [ErrorType.AUTHENTICATION]: {
        message: I18n.t('error.permission_denied.message'),
        solutions: [I18n.t('error.solution.relogin')],
        actions: [actionRefresh],
        helpLink: '/help/login'
      },
      [ErrorType.AUTHORIZATION]: {
        message: I18n.t('error.permission_denied.message'),
        solutions: [I18n.t('error.solution.request_permission')],
        actions: [actionHelp],
        helpLink: '/help/permission'
      },
      [ErrorType.NOT_FOUND]: {
        message: I18n.t('error.not_found.message'),
        solutions: [I18n.t('error.solution.check_resource_path')],
        actions: [actionRefresh],
        helpLink: '/help/resource'
      },
      [ErrorType.SERVER]: {
        message: I18n.t('error.server_error.message'),
        solutions: [I18n.t('error.server_error.suggestion')],
        actions: [actionRetry, actionHelp],
        helpLink: '/help/server'
      },
      [ErrorType.PLUGIN]: {
        message: I18n.t('error.plugin_error.message'),
        solutions: [I18n.t('error.solution.disable_plugin')],
        actions: [actionRefresh, actionHelp],
        helpLink: '/help/plugin'
      },
      [ErrorType.CACHE]: {
        message: I18n.t('error.cache_error.message'),
        solutions: [I18n.t('error.solution.clear_cache')],
        actions: [actionRefresh],
        helpLink: '/help/cache'
      },
      [ErrorType.UNKNOWN]: {
        message: unknownMessage,
        solutions: [I18n.t('error.solution.try_again_later')],
        actions: [actionRetry, actionHelp],
        helpLink: '/help/general'
      }
    };

    return fallback[errorType] || fallback[ErrorType.UNKNOWN];
  }

  uploadErrorLogs(): void {
    if (this.errorLogs.length === 0 || !this.config.enableReporting) {
      return;
    }

    const payload = {
      generatedAt: new Date().toISOString(),
      logs: this.errorLogs,
      stats: this.getErrorStats()
    };

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('app:error:batch-report', { detail: payload }));
    }
  }

  private handleNetworkError(error: AppError): void {
    Logger.info('ErrorHandler', '处理网络错误', error);
  }

  private handleValidationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理验证错误', error);
  }

  private handleAuthenticationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理认证错误', error);
  }

  private handleAuthorizationError(error: AppError): void {
    Logger.info('ErrorHandler', '处理授权错误', error);
  }

  private handleNotFoundError(error: AppError): void {
    Logger.info('ErrorHandler', '处理未找到错误', error);
  }

  private handleServerError(error: AppError): void {
    Logger.info('ErrorHandler', '处理服务器错误', error);
  }

  private handlePluginError(error: AppError): void {
    Logger.info('ErrorHandler', '处理插件错误', error);
  }

  private handleCacheError(error: AppError): void {
    Logger.info('ErrorHandler', '处理缓存错误', error);
  }

  registerHandler(errorType: ErrorType, handler: (error: AppError) => void): void {
    this.errorHandlers.set(errorType, handler);
  }

  registerGlobalHandler(handler: (error: AppError) => void): () => void {
    this.globalHandlers.push(handler);
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

export const errorHandler = new ErrorHandler();
