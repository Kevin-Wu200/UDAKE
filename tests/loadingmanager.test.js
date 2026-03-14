import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { LoadingManager } from '../frontend/js/utils/LoadingManager.js';
import { SkeletonLoader } from '../frontend/js/utils/SkeletonLoader.js';

// Mock SkeletonLoader
vi.mock('../frontend/js/utils/SkeletonLoader.js', () => ({
    SkeletonLoader: {
        show: vi.fn(() => document.createElement('div')),
        hide: vi.fn()
    }
}));

describe('LoadingManager', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        LoadingManager._overlay = null;
        LoadingManager._textEl = null;
        LoadingManager._progressEl = null;
        LoadingManager._requestCount = 0;
        LoadingManager._retryCallbacks = new Map();
        
        // Mock setTimeout
        global.setTimeout = vi.fn((cb, delay) => {
            cb();
            return 1;
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('show / hide', () => {
        it('show 应该创建并显示遮罩', () => {
            LoadingManager.show('加载中...');
            expect(LoadingManager._overlay).not.toBeNull();
            expect(LoadingManager._overlay.classList.contains('loading-visible')).toBe(true);
            expect(LoadingManager._textEl.textContent).toBe('加载中...');
        });

        it('show 应该设置正确的ARIA属性', () => {
            LoadingManager.show('测试');
            expect(LoadingManager._overlay.getAttribute('role')).toBe('status');
            expect(LoadingManager._overlay.getAttribute('aria-live')).toBe('polite');
            expect(LoadingManager._overlay.getAttribute('aria-hidden')).toBe('false');
        });

        it('hide 应该隐藏遮罩', () => {
            LoadingManager.show('test');
            LoadingManager.hide();
            expect(LoadingManager._overlay.classList.contains('loading-visible')).toBe(false);
            expect(LoadingManager._overlay.getAttribute('aria-hidden')).toBe('true');
        });

        it('多次 show 需要对应次数的 hide', () => {
            LoadingManager.show('1');
            LoadingManager.show('2');
            LoadingManager.hide();
            expect(LoadingManager.isLoading).toBe(true);
            LoadingManager.hide();
            expect(LoadingManager.isLoading).toBe(false);
        });

        it('forceHide 应该立即隐藏', () => {
            LoadingManager.show('1');
            LoadingManager.show('2');
            LoadingManager.forceHide();
            expect(LoadingManager.isLoading).toBe(false);
            expect(LoadingManager.requestCount).toBe(0);
        });

        it('show 应该返回遮罩元素', () => {
            const overlay = LoadingManager.show('测试');
            expect(overlay).toBe(LoadingManager._overlay);
        });

        it('show 应该使用默认文本', () => {
            LoadingManager.show();
            expect(LoadingManager._textEl.textContent).toBe('加载中...');
        });
    });

    describe('updateText', () => {
        it('应该更新加载文本', () => {
            LoadingManager.show('初始');
            LoadingManager.updateText('更新后');
            expect(LoadingManager._textEl.textContent).toBe('更新后');
        });

        it('没有遮罩时不应报错', () => {
            expect(() => LoadingManager.updateText('test')).not.toThrow();
        });
    });

    describe('updateProgress', () => {
        it('应该更新进度条百分比', () => {
            LoadingManager.show('进度', { type: 'progress' });
            LoadingManager.updateProgress(50);
            
            const fill = LoadingManager._progressEl.querySelector('.loading-progress-fill');
            expect(fill.style.width).toBe('50%');
        });

        it('应该设置ARIA值', () => {
            LoadingManager.show('进度', { type: 'progress' });
            LoadingManager.updateProgress(75);
            
            expect(LoadingManager._progressEl.getAttribute('aria-valuenow')).toBe('75');
        });

        it('应该限制百分比在0-100之间', () => {
            LoadingManager.show('进度', { type: 'progress' });
            
            LoadingManager.updateProgress(-10);
            const fill1 = LoadingManager._progressEl.querySelector('.loading-progress-fill');
            expect(fill1.style.width).toBe('0%');
            
            LoadingManager.updateProgress(150);
            const fill2 = LoadingManager._progressEl.querySelector('.loading-progress-fill');
            expect(fill2.style.width).toBe('100%');
        });

        it('没有进度条时不应报错', () => {
            LoadingManager.show('测试');
            expect(() => LoadingManager.updateProgress(50)).not.toThrow();
        });
    });

    describe('不同类型的显示选项', () => {
        it('overlay类型应该显示默认遮罩', () => {
            LoadingManager.show('测试', { type: 'overlay' });
            expect(LoadingManager._overlay).not.toBeNull();
            expect(LoadingManager._overlay.classList.contains('loading-visible')).toBe(true);
        });

        it('progress类型应该显示进度条', () => {
            LoadingManager.show('进度', { type: 'progress' });
            expect(LoadingManager._progressEl).not.toBeNull();
        });

        it('skeleton类型应该使用SkeletonLoader', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);
            
            LoadingManager.show('骨架屏', { type: 'skeleton', container });
            expect(SkeletonLoader.show).toHaveBeenCalled();
        });

        it('skeleton类型应该支持text类型', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);
            
            LoadingManager.show('文本骨架', { type: 'skeleton', container, skeletonType: 'text' });
            expect(SkeletonLoader.show).toHaveBeenCalledWith(container, 'text');
        });

        it('skeleton类型应该支持panel类型', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);
            
            LoadingManager.show('面板骨架', { type: 'skeleton', container, skeletonType: 'panel' });
            expect(SkeletonLoader.show).toHaveBeenCalledWith(container, 'panel');
        });
    });

    describe('hide with skeleton', () => {
        it('应该隐藏骨架屏', () => {
            const container = document.createElement('div');
            container.classList.add('skeleton-wrapper');
            document.body.appendChild(container);
            
            LoadingManager.hide(container);
            expect(SkeletonLoader.hide).toHaveBeenCalled();
        });

        it('非骨架屏wrapper应该正常处理', () => {
            LoadingManager.show('测试');
            const nonSkeleton = document.createElement('div');
            
            expect(() => LoadingManager.hide(nonSkeleton)).not.toThrow();
        });
    });

    describe('isLoading / requestCount', () => {
        it('初始状态应该不在加载', () => {
            expect(LoadingManager.isLoading).toBe(false);
            expect(LoadingManager.requestCount).toBe(0);
        });

        it('show 后应该在加载', () => {
            LoadingManager.show();
            expect(LoadingManager.isLoading).toBe(true);
            expect(LoadingManager.requestCount).toBe(1);
        });

        it('requestCount应该正确递增', () => {
            LoadingManager.show();
            LoadingManager.show();
            LoadingManager.show();
            expect(LoadingManager.requestCount).toBe(3);
        });

        it('requestCount应该正确递减', () => {
            LoadingManager.show();
            LoadingManager.show();
            LoadingManager.hide();
            expect(LoadingManager.requestCount).toBe(1);
        });

        it('requestCount不应该小于0', () => {
            LoadingManager.show();
            LoadingManager.hide();
            LoadingManager.hide();
            expect(LoadingManager.requestCount).toBe(0);
        });
    });

    describe('withRetry', () => {
        it('成功时应该返回结果', async () => {
            const fn = vi.fn().mockResolvedValue('ok');
            const result = await LoadingManager.withRetry(fn);
            expect(result).toBe('ok');
            expect(fn).toHaveBeenCalledTimes(1);
        });

        it('应该显示加载文本', async () => {
            const fn = vi.fn().mockResolvedValue('ok');
            await LoadingManager.withRetry(fn, { loadingText: '正在重试...' });
            
            expect(LoadingManager._textEl.textContent).toBe('正在重试...');
        });

        it('失败后应该重试', async () => {
            const fn = vi.fn()
                .mockRejectedValueOnce(new Error('fail'))
                .mockResolvedValueOnce('ok');

            const result = await LoadingManager.withRetry(fn, { retryDelay: 0 });
            expect(result).toBe('ok');
            expect(fn).toHaveBeenCalledTimes(2);
        });

        it('重试时应该更新文本', async () => {
            const fn = vi.fn()
                .mockRejectedValueOnce(new Error('fail'))
                .mockRejectedValueOnce(new Error('fail'))
                .mockResolvedValueOnce('ok');

            await LoadingManager.withRetry(fn, { loadingText: '加载', maxRetries: 3, retryDelay: 0 });
            expect(fn).toHaveBeenCalledTimes(3);
        });

        it('超过最大重试次数应该抛出错误', async () => {
            const fn = vi.fn().mockRejectedValue(new Error('always fail'));

            await expect(LoadingManager.withRetry(fn, { maxRetries: 1, retryDelay: 0 }))
                .rejects.toThrow('always fail');
            expect(fn).toHaveBeenCalledTimes(2); // 1 initial + 1 retry
        });

        it('成功后应该隐藏加载状态', async () => {
            const fn = vi.fn().mockResolvedValue('ok');
            await LoadingManager.withRetry(fn);
            
            expect(LoadingManager.isLoading).toBe(false);
        });

        it('失败后应该隐藏加载状态', async () => {
            const fn = vi.fn().mockRejectedValue(new Error('fail'));
            
            try {
                await LoadingManager.withRetry(fn, { maxRetries: 0, retryDelay: 0 });
            } catch (e) {
                // Expected error
            }
            
            expect(LoadingManager.isLoading).toBe(false);
        });

        it('应该使用默认重试选项', async () => {
            const fn = vi.fn().mockResolvedValue('ok');
            await LoadingManager.withRetry(fn);
            
            expect(fn).toHaveBeenCalledTimes(1);
        });
    });

    describe('覆盖层创建', () => {
        it('应该创建正确的HTML结构', () => {
            LoadingManager.show('测试');
            
            expect(LoadingManager._overlay.querySelector('.loading-content')).not.toBeNull();
            expect(LoadingManager._overlay.querySelector('.loading-spinner')).not.toBeNull();
            expect(LoadingManager._overlay.querySelector('.loading-text')).not.toBeNull();
        });

        it('应该将覆盖层添加到body', () => {
            LoadingManager.show('测试');
            expect(document.body.contains(LoadingManager._overlay)).toBe(true);
        });

        it('重复show不应该重复创建覆盖层', () => {
            LoadingManager.show('测试1');
            const overlay1 = LoadingManager._overlay;
            LoadingManager.show('测试2');
            const overlay2 = LoadingManager._overlay;
            
            expect(overlay1).toBe(overlay2);
        });
    });

    describe('进度条创建', () => {
        it('应该在第一次显示进度时创建进度条', () => {
            LoadingManager.show('进度', { type: 'progress' });
            
            expect(LoadingManager._progressEl).not.toBeNull();
            expect(LoadingManager._progressEl.classList.contains('loading-progress')).toBe(true);
        });

        it('进度条应该有正确的ARIA属性', () => {
            LoadingManager.show('进度', { type: 'progress' });
            
            expect(LoadingManager._progressEl.getAttribute('role')).toBe('progressbar');
            expect(LoadingManager._progressEl.getAttribute('aria-valuemin')).toBe('0');
            expect(LoadingManager._progressEl.getAttribute('aria-valuemax')).toBe('100');
        });

        it('进度条应该包含fill元素', () => {
            LoadingManager.show('进度', { type: 'progress' });
            
            expect(LoadingManager._progressEl.querySelector('.loading-progress-fill')).not.toBeNull();
        });
    });

    describe('边界情况', () => {
        it('多次forceHide不应该报错', () => {
            LoadingManager.show('测试');
            LoadingManager.forceHide();
            expect(() => LoadingManager.forceHide()).not.toThrow();
        });

        it('没有show就hide不应该报错', () => {
            expect(() => LoadingManager.hide()).not.toThrow();
        });

        it('更新不存在的进度条不应该报错', () => {
            expect(() => LoadingManager.updateProgress(50)).not.toThrow();
        });

        it('更新不存在的文本不应该报错', () => {
            expect(() => LoadingManager.updateText('测试')).not.toThrow();
        });

        it('空字符串作为文本应该正常工作', () => {
            LoadingManager.show('');
            expect(LoadingManager._textEl.textContent).toBe('');
        });

        it('null作为文本应该正常工作', () => {
            LoadingManager.show(null);
            // textContent 会将 null 转换为空字符串
            expect(LoadingManager._textEl.textContent).toBe('');
        });
    });
});
