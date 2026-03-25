/**
 * 启动加载组件
 * 用于状态文字轮播与启动阶段文案管理。
 */

export interface StartupLoaderOptions {
    statuses?: string[];
    rotateIntervalMs?: number;
    onStatusChange?: (status: string, index: number) => void;
}

const DEFAULT_STATUSES = [
    '正在加载配置...',
    '正在连接服务器...',
    '正在准备地图数据...',
    '即将完成...'
];

export class StartupLoader {
    private statuses: string[];
    private rotateIntervalMs: number;
    private currentIndex: number = 0;
    private timerId: number | null = null;
    private onStatusChange?: (status: string, index: number) => void;

    constructor(options: StartupLoaderOptions = {}) {
        this.statuses = options.statuses?.length ? options.statuses : DEFAULT_STATUSES;
        this.rotateIntervalMs = this.normalizeInterval(options.rotateIntervalMs ?? 1400);
        this.onStatusChange = options.onStatusChange;
    }

    public start(): void {
        if (this.timerId !== null) {
            return;
        }
        this.emitCurrentStatus();
        this.timerId = window.setInterval(() => {
            this.currentIndex = (this.currentIndex + 1) % this.statuses.length;
            this.emitCurrentStatus();
        }, this.rotateIntervalMs);
    }

    public stop(finalStatus?: string): void {
        if (this.timerId !== null) {
            clearInterval(this.timerId);
            this.timerId = null;
        }
        if (finalStatus) {
            this.onStatusChange?.(finalStatus, this.currentIndex);
        }
    }

    public reset(): void {
        this.currentIndex = 0;
    }

    public getCurrentStatus(): string {
        return this.statuses[this.currentIndex] ?? DEFAULT_STATUSES[0];
    }

    private emitCurrentStatus(): void {
        this.onStatusChange?.(this.getCurrentStatus(), this.currentIndex);
    }

    private normalizeInterval(value: number): number {
        if (!Number.isFinite(value)) {
            return 1400;
        }
        return Math.min(2000, Math.max(1000, Math.round(value)));
    }
}

