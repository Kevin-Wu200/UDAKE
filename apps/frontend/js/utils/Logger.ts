/**
 * 统一日志管理器
 * - 按环境控制日志级别
 * - 对敏感字段做脱敏
 * - 支持作用域日志前缀
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'silent';

type ConsoleMethod = 'debug' | 'info' | 'warn' | 'error' | 'log';

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

const LOG_LEVEL_ORDER: Record<LogLevel, number> = {
    debug: 10,
    info: 20,
    warn: 30,
    error: 40,
    silent: 100
};

const SENSITIVE_KEYWORDS = [
    'token',
    'password',
    'secret',
    'authorization',
    'cookie',
    'apikey',
    'api_key',
    'session',
    'credential'
];

const ORIGINAL_CONSOLE = {
    debug: console.debug.bind(console),
    info: console.info.bind(console),
    warn: console.warn.bind(console),
    error: console.error.bind(console),
    log: console.log.bind(console)
};

function getEnvFlag(name: string): string | undefined {
    try {
        const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
        if (!env) {
            return undefined;
        }
        return env[name];
    } catch {
        return undefined;
    }
}

function parseLogLevel(level?: string | null): LogLevel {
    if (!level) {
        return 'info';
    }

    const normalized = level.toLowerCase().trim();
    if (normalized === 'debug' || normalized === 'info' || normalized === 'warn' || normalized === 'error' || normalized === 'silent') {
        return normalized;
    }

    return 'info';
}

function isSensitiveKey(key: string): boolean {
    const normalized = key.toLowerCase();
    return SENSITIVE_KEYWORDS.some(keyword => normalized.includes(keyword));
}

function sanitizeValue(value: unknown, depth: number = 0): unknown {
    if (depth > 4) {
        return '[MaxDepth]';
    }

    if (value === null || value === undefined) {
        return value;
    }

    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
        return value;
    }

    if (value instanceof Error) {
        return {
            name: value.name,
            message: value.message,
            stack: value.stack
        };
    }

    if (Array.isArray(value)) {
        return value.map(item => sanitizeValue(item, depth + 1));
    }

    if (typeof value === 'object') {
        const output: Record<string, unknown> = {};
        Object.entries(value as Record<string, unknown>).forEach(([key, raw]) => {
            output[key] = isSensitiveKey(key) ? '[REDACTED]' : sanitizeValue(raw, depth + 1);
        });
        return output;
    }

    return String(value);
}

export class Logger {
    private static level: LogLevel = Logger.detectDefaultLevel();
    private static bootstrapped = false;

    private static detectDefaultLevel(): LogLevel {
        const envLevel = parseLogLevel(getEnvFlag('VITE_LOG_LEVEL'));
        const debugEnabled = getEnvFlag('VITE_ENABLE_DEBUG') === 'true';
        const appEnv = getEnvFlag('VITE_APP_ENV') || 'development';

        if (envLevel !== 'info') {
            return envLevel;
        }

        if (appEnv === 'production') {
            return 'warn';
        }

        return debugEnabled ? 'debug' : 'info';
    }

    static setLevel(level: LogLevel): void {
        this.level = level;
    }

    static getLevel(): LogLevel {
        return this.level;
    }

    static shouldLog(level: Exclude<LogLevel, 'silent'>): boolean {
        return LOG_LEVEL_ORDER[level] >= LOG_LEVEL_ORDER[this.level];
    }

    static bootstrap(): void {
        if (this.bootstrapped) {
            return;
        }

        this.bootstrapped = true;

        const mapLevelToMethod = (level: Exclude<LogLevel, 'silent'>): ConsoleMethod => {
            if (level === 'debug') return 'debug';
            if (level === 'info') return 'info';
            if (level === 'warn') return 'warn';
            return 'error';
        };

        const patchMethod = (level: Exclude<LogLevel, 'silent'>, fallback: ConsoleMethod) => {
            const method = mapLevelToMethod(level);
            const patched = (...args: unknown[]) => {
                if (!Logger.shouldLog(level)) {
                    return;
                }
                const timestamp = new Date().toISOString();
                const sanitized = args.map(item => sanitizeValue(item));
                ORIGINAL_CONSOLE[fallback](`[${timestamp}]`, ...sanitized);
            };
            (console as Record<string, unknown>)[method] = patched;
        };

        patchMethod('debug', 'debug');
        patchMethod('info', 'info');
        patchMethod('warn', 'warn');
        patchMethod('error', 'error');
        (console as Record<string, unknown>).log = (console as Record<string, unknown>).info;
    }

    static debug(scope: string, message: string, payload?: unknown): void {
        this.emit('debug', scope, message, payload);
    }

    static info(scope: string, message: string, payload?: unknown): void {
        this.emit('info', scope, message, payload);
    }

    static warn(scope: string, message: string, payload?: unknown): void {
        this.emit('warn', scope, message, payload);
    }

    static error(scope: string, message: string, payload?: unknown): void {
        this.emit('error', scope, message, payload);
    }

    private static emit(level: Exclude<LogLevel, 'silent'>, scope: string, message: string, payload?: unknown): void {
        if (!this.shouldLog(level)) {
            return;
        }

        const content = `[${scope}] ${message}`;
        if (payload === undefined) {
            console[level](content);
            return;
        }

        console[level](content, sanitizeValue(payload));
    }

    static scoped(scope: string): {
        debug: (message: string, payload?: unknown) => void;
        info: (message: string, payload?: unknown) => void;
        warn: (message: string, payload?: unknown) => void;
        error: (message: string, payload?: unknown) => void;
    } {
        return {
            debug: (message: string, payload?: unknown) => this.debug(scope, message, payload),
            info: (message: string, payload?: unknown) => this.info(scope, message, payload),
            warn: (message: string, payload?: unknown) => this.warn(scope, message, payload),
            error: (message: string, payload?: unknown) => this.error(scope, message, payload)
        };
    }

    static safeJson(value: unknown): JsonValue | string {
        try {
            return JSON.parse(JSON.stringify(sanitizeValue(value))) as JsonValue;
        } catch {
            return '[Unserializable]';
        }
    }
}
