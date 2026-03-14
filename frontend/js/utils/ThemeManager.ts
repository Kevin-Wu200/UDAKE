/**
 * 主题管理器
 * 支持浅色/深色/跟随系统三种模式
 * 使用 localStorage 持久化用户偏好
 */

type ThemeValue = 'light' | 'dark' | 'auto';

export class ThemeManager {
    static STORAGE_KEY = 'udake-theme-preference';
    static THEMES: Record<string, ThemeValue> = { LIGHT: 'light', DARK: 'dark', AUTO: 'auto' };

    static _current: ThemeValue | null = null;
    static _mediaQuery: MediaQueryList | { matches: boolean; addEventListener: (...args: any[]) => void } =
        typeof window !== 'undefined' && window.matchMedia
            ? window.matchMedia('(prefers-color-scheme: dark)')
            : { matches: false, addEventListener: () => {} };

    static init(): void {
        const saved = (localStorage.getItem(this.STORAGE_KEY) || 'auto') as ThemeValue;
        this._apply(saved);

        this._mediaQuery.addEventListener('change', () => {
            if (this._current === 'auto') {
                this._updateIcon();
            }
        });
    }

    static toggle(): void {
        const order: ThemeValue[] = ['light', 'dark', 'auto'];
        const idx = order.indexOf(this._current!);
        const next = order[(idx + 1) % order.length];
        this._apply(next);
        localStorage.setItem(this.STORAGE_KEY, next);
    }

    static set(theme: ThemeValue): void {
        this._apply(theme);
        localStorage.setItem(this.STORAGE_KEY, theme);
    }

    static get current(): ThemeValue | null {
        return this._current;
    }

    static get effectiveTheme(): 'light' | 'dark' {
        if (this._current === 'auto') {
            return this._mediaQuery.matches ? 'dark' : 'light';
        }
        return this._current as 'light' | 'dark';
    }

    static _apply(theme: ThemeValue): void {
        this._current = theme;
        const root = document.documentElement;

        root.classList.add('theme-transition');

        if (theme === 'auto') {
            root.removeAttribute('data-theme');
        } else {
            root.setAttribute('data-theme', theme);
        }

        this._updateIcon();

        setTimeout(() => root.classList.remove('theme-transition'), 350);
    }

    static _updateIcon(): void {
        const btn = document.getElementById('theme-toggle-btn');
        if (!btn) return;

        const icon = btn.querySelector('.theme-icon');
        if (!icon) return;

        const icons: Record<ThemeValue, string> = { light: '\u2600\uFE0F', dark: '\uD83C\uDF19', auto: '\uD83D\uDCBB' };
        const titles: Record<ThemeValue, string> = {
            light: '当前：浅色模式（点击切换为深色）',
            dark: '当前：深色模式（点击切换为跟随系统）',
            auto: '当前：跟随系统（点击切换为浅色）',
        };

        icon.textContent = icons[this._current as ThemeValue] || icons.auto;
        btn.title = titles[this._current as ThemeValue] || titles.auto;
    }
}
