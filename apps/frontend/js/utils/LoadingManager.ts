/**
 * 全局加载状态管理器
 * 统一管理加载指示器、请求计数、加载文本、失败重试
 */
import { SkeletonLoader } from './SkeletonLoader.js';

interface ShowOptions {
    type?: 'overlay' | 'progress' | 'skeleton';
    container?: HTMLElement;
    skeletonType?: 'text' | 'panel';
}

interface RetryOptions {
    loadingText?: string;
    maxRetries?: number;
    retryDelay?: number;
}

export class LoadingManager {
    static _instance: LoadingManager | null = null;
    static _requestCount: number = 0;
    static _overlay: HTMLDivElement | null = null;
    static _textEl: HTMLSpanElement | null = null;
    static _progressEl: HTMLDivElement | null = null;
    static _retryCallbacks: Map<string, () => void> = new Map();

    /**
     * 显示全局加载遮罩
     * @param text - 加载提示文本
     * @param options - 加载选项
     */
    static show(text: string = '加载中...', options: ShowOptions = {}): HTMLDivElement {
        LoadingManager._requestCount++;
        const type = options.type || 'overlay';

        if (type === 'skeleton' && options.container) {
            return SkeletonLoader.show(options.container, options.skeletonType || 'panel') as HTMLDivElement;
        }

        if (type === 'progress') {
            return LoadingManager._showProgress(text);
        }

        // overlay 类型
        if (!LoadingManager._overlay) {
            LoadingManager._createOverlay();
        }

        LoadingManager._textEl!.textContent = text;
        LoadingManager._overlay!.classList.add('loading-visible');
        LoadingManager._overlay!.setAttribute('aria-hidden', 'false');
        return LoadingManager._overlay!;
    }

    /**
     * 更新加载文本
     */
    static updateText(text: string): void {
        if (LoadingManager._textEl) {
            LoadingManager._textEl.textContent = text;
        }
    }

    /**
     * 更新进度条
     * @param percent - 0~100
     */
    static updateProgress(percent: number): void {
        if (LoadingManager._progressEl) {
            const fill = LoadingManager._progressEl.querySelector('.loading-progress-fill') as HTMLElement | null;
            if (fill) {
                fill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
                LoadingManager._progressEl.setAttribute('aria-valuenow', String(percent));
            }
        }
    }

    /**
     * 隐藏加载状态
     * @param skeletonWrapper - 骨架屏 wrapper（由 show 返回）
     */
    static hide(skeletonWrapper?: HTMLElement | null): void {
        LoadingManager._requestCount = Math.max(0, LoadingManager._requestCount - 1);

        if (skeletonWrapper && skeletonWrapper.classList?.contains('skeleton-wrapper')) {
            SkeletonLoader.hide(skeletonWrapper as HTMLDivElement);
            return;
        }

        if (LoadingManager._requestCount === 0 && LoadingManager._overlay) {
            LoadingManager._overlay.classList.remove('loading-visible');
            LoadingManager._overlay.setAttribute('aria-hidden', 'true');
        }
    }

    /**
     * 强制隐藏所有加载状态
     */
    static forceHide(): void {
        LoadingManager._requestCount = 0;
        if (LoadingManager._overlay) {
            LoadingManager._overlay.classList.remove('loading-visible');
            LoadingManager._overlay.setAttribute('aria-hidden', 'true');
        }
    }

    /**
     * 带重试的异步操作包装
     * @param asyncFn - 异步函数
     * @param options - 重试选项
     */
    static async withRetry<T>(asyncFn: () => Promise<T>, options: RetryOptions = {}): Promise<T> {
        const { loadingText = '加载中...', maxRetries = 3, retryDelay = 1000 } = options;
        let lastError: unknown;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const text = attempt > 0
                    ? `${loadingText}（第 ${attempt} 次重试）`
                    : loadingText;
                LoadingManager.show(text);
                const result = await asyncFn();
                LoadingManager.hide();
                return result;
            } catch (error) {
                lastError = error;
                LoadingManager.hide();
                if (attempt < maxRetries) {
                    await new Promise<void>(r => setTimeout(r, retryDelay * (attempt + 1)));
                }
            }
        }
        throw lastError;
    }

    /** 当前是否正在加载 */
    static get isLoading(): boolean {
        return LoadingManager._requestCount > 0;
    }

    /** 当前请求计数 */
    static get requestCount(): number {
        return LoadingManager._requestCount;
    }

    // --- 内部方法 ---

    static _createOverlay(): void {
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.setAttribute('role', 'status');
        overlay.setAttribute('aria-live', 'polite');
        overlay.setAttribute('aria-hidden', 'true');

        overlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <span class="loading-text">加载中...</span>
            </div>
        `;

        document.body.appendChild(overlay);
        LoadingManager._overlay = overlay;
        LoadingManager._textEl = overlay.querySelector('.loading-text');
    }

    static _showProgress(text: string): HTMLDivElement {
        if (!LoadingManager._overlay) {
            LoadingManager._createOverlay();
        }

        const content = LoadingManager._overlay!.querySelector('.loading-content')!;
        let progressBar = content.querySelector('.loading-progress') as HTMLDivElement | null;
        if (!progressBar) {
            progressBar = document.createElement('div');
            progressBar.className = 'loading-progress';
            progressBar.setAttribute('role', 'progressbar');
            progressBar.setAttribute('aria-valuemin', '0');
            progressBar.setAttribute('aria-valuemax', '100');
            progressBar.setAttribute('aria-valuenow', '0');
            progressBar.innerHTML = '<div class="loading-progress-fill"></div>';
            content.appendChild(progressBar);
        }

        LoadingManager._progressEl = progressBar;
        LoadingManager._textEl!.textContent = text;
        LoadingManager._overlay!.classList.add('loading-visible');
        LoadingManager._overlay!.setAttribute('aria-hidden', 'false');
        return LoadingManager._overlay!;
    }
}
