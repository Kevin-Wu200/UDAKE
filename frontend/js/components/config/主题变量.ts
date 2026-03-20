/**
 * 手势设置面板主题变量（测试环境兼容）
 * 仅在页面中注入一次基础 CSS 变量，避免重复导入报错。
 */

const STYLE_ID = 'gesture-theme-variables';

if (typeof document !== 'undefined' && !document.getElementById(STYLE_ID)) {
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
        :root {
            --gesture-panel-bg: #ffffff;
            --gesture-panel-text: #111827;
            --gesture-panel-border: #d1d5db;
            --gesture-accent: #2563eb;
        }
    `;
    document.head.appendChild(style);
}

export {};
