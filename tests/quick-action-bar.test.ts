import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QuickActionBar } from '../apps/frontend/js/components/QuickActionBar.js';
import { KeyboardManager } from '../apps/frontend/js/utils/KeyboardManager.js';

describe('QuickActionBar', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div class="map-container"></div>';
        localStorage.clear();
        KeyboardManager._shortcuts = [];
        KeyboardManager._shortcutPanel = null;
        KeyboardManager._focusTrapStack = [];
    });

    it('应渲染默认快捷操作按钮', () => {
        const container = document.querySelector('.map-container') as HTMLElement;
        const bar = new QuickActionBar();
        bar.mount(container);

        const buttons = container.querySelectorAll('.quick-action-btn');
        expect(buttons.length).toBeGreaterThan(6);
    });

    it('应支持显示/隐藏操作项', () => {
        const container = document.querySelector('.map-container') as HTMLElement;
        const bar = new QuickActionBar();
        bar.mount(container);

        const settingsBtn = container.querySelector('.quick-action-settings-btn') as HTMLButtonElement;
        settingsBtn.click();

        const toggle = container.querySelector('input[data-action-toggle="new-project"]') as HTMLInputElement;
        expect(toggle).toBeTruthy();

        toggle.checked = false;
        toggle.dispatchEvent(new Event('change', { bubbles: true }));

        const newProjectBtn = container.querySelector('.quick-action-btn[data-action-id="new-project"]');
        expect(newProjectBtn).toBeNull();
    });

    it('应支持拖拽排序并持久化', () => {
        const container = document.querySelector('.map-container') as HTMLElement;
        const bar = new QuickActionBar();
        bar.mount(container);

        const barAny = bar as any;
        barAny.reorder('wizard-center', 'new-project');

        const saved = localStorage.getItem('udake_quick_action_bar_state_v1');
        expect(saved).toContain('wizard-center');

        const first = container.querySelector('.quick-action-btn') as HTMLElement;
        expect(first.dataset.actionId).toBe('wizard-center');
    });

    it('推荐点击应转发为快捷操作请求事件', () => {
        const container = document.querySelector('.map-container') as HTMLElement;
        const bar = new QuickActionBar();
        bar.mount(container);

        const handler = vi.fn();
        document.addEventListener('quick-action-request', handler);

        document.dispatchEvent(new CustomEvent('recommendation-action', {
            detail: { actionId: 'new-project' }
        }));

        expect(handler).toHaveBeenCalled();
        const matched = handler.mock.calls.some((call) => call[0]?.detail?.actionId === 'new-project');
        expect(matched).toBe(true);
    });
});
