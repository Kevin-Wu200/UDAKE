import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ThemeManager } from '../apps/frontend/js/utils/ThemeManager.js';

// Mock localStorage
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: vi.fn(key => store[key] ?? null),
        setItem: vi.fn((key, value) => { store[key] = String(value); }),
        removeItem: vi.fn(key => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; })
    };
})();
vi.stubGlobal('localStorage', localStorageMock);

describe('ThemeManager', () => {
    let mockMatchMedia;

    beforeEach(() => {
        document.documentElement.removeAttribute('data-theme');
        document.body.innerHTML = `
            <button id="theme-toggle-btn">
                <span class="theme-icon"></span>
            </button>
        `;
        localStorageMock.clear();
        localStorageMock.getItem.mockClear();
        localStorageMock.setItem.mockClear();

        // Mock matchMedia
        mockMatchMedia = { matches: false, addEventListener: vi.fn() };
        ThemeManager._mediaQuery = mockMatchMedia;
        ThemeManager._current = null;
    });

    describe('init', () => {
        it('无保存偏好时应该使用 auto', () => {
            ThemeManager.init();
            expect(ThemeManager.current).toBe('auto');
            expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
        });

        it('应该恢复保存的偏好', () => {
            localStorage.setItem('udake-theme-preference', 'dark');
            ThemeManager.init();
            expect(ThemeManager.current).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it('应该监听系统主题变化', () => {
            ThemeManager.init();
            expect(mockMatchMedia.addEventListener).toHaveBeenCalledWith('change', expect.any(Function));
        });
    });

    describe('toggle', () => {
        it('应该按 light -> dark -> auto 循环', () => {
            ThemeManager._apply('light');
            ThemeManager._current = 'light';

            ThemeManager.toggle();
            expect(ThemeManager.current).toBe('dark');

            ThemeManager.toggle();
            expect(ThemeManager.current).toBe('auto');

            ThemeManager.toggle();
            expect(ThemeManager.current).toBe('light');
        });

        it('应该持久化到 localStorage', () => {
            ThemeManager._apply('light');
            ThemeManager._current = 'light';
            ThemeManager.toggle();
            expect(localStorage.getItem('udake-theme-preference')).toBe('dark');
        });
    });

    describe('set', () => {
        it('应该设置指定主题', () => {
            ThemeManager.set('dark');
            expect(ThemeManager.current).toBe('dark');
            expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        });

        it('auto 应该移除 data-theme 属性', () => {
            ThemeManager.set('dark');
            ThemeManager.set('auto');
            expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
        });
    });

    describe('effectiveTheme', () => {
        it('手动设置时应该返回设置值', () => {
            ThemeManager.set('dark');
            expect(ThemeManager.effectiveTheme).toBe('dark');
        });

        it('auto 模式下应该根据系统偏好返回', () => {
            mockMatchMedia.matches = true;
            ThemeManager.set('auto');
            expect(ThemeManager.effectiveTheme).toBe('dark');

            mockMatchMedia.matches = false;
            expect(ThemeManager.effectiveTheme).toBe('light');
        });
    });

    describe('图标更新', () => {
        it('应该根据主题更新图标', () => {
            ThemeManager.set('dark');
            const icon = document.querySelector('.theme-icon');
            expect(icon.textContent).toBe('\uD83C\uDF19');
        });

        it('auto 模式应该显示电脑图标', () => {
            ThemeManager.set('auto');
            const icon = document.querySelector('.theme-icon');
            expect(icon.textContent).toBe('\uD83D\uDCBB');
        });
    });
});
