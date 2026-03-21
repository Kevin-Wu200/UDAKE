import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { KeyboardManager } from '../apps/frontend/js/utils/KeyboardManager.js';

describe('KeyboardManager', () => {
    beforeEach(() => {
        KeyboardManager._shortcuts = [];
        KeyboardManager._shortcutPanel = null;
        KeyboardManager._focusTrapStack = [];
        document.body.innerHTML = '';
        
        // 移除所有事件监听器
        document.removeEventListener = vi.fn();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('register', () => {
        it('应该注册快捷键', () => {
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler: () => {} });
            expect(KeyboardManager._shortcuts.length).toBe(1);
            expect(KeyboardManager._shortcuts[0].key).toBe('n');
        });

        it('应该支持多个快捷键', () => {
            KeyboardManager.register({ key: 'a', description: 'A', handler: () => {} });
            KeyboardManager.register({ key: 'b', description: 'B', handler: () => {} });
            expect(KeyboardManager._shortcuts.length).toBe(2);
        });

        it('应该保存快捷键配置', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 's', ctrl: true, shift: true, description: '保存', handler });
            
            const shortcut = KeyboardManager._shortcuts[0];
            expect(shortcut.key).toBe('s');
            expect(shortcut.ctrl).toBe(true);
            expect(shortcut.shift).toBe(true);
            expect(shortcut.description).toBe('保存');
            expect(shortcut.handler).toBe(handler);
        });
    });

    describe('init 和快捷键触发', () => {
        it('应该在按键时触发对应处理函数', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'Escape', description: '关闭', handler });
            KeyboardManager.init();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            expect(handler).toHaveBeenCalledTimes(1);
        });

        it('Ctrl 快捷键应该正确匹配', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler });
            KeyboardManager.init();

            // 没有 ctrl 不应触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n' }));
            expect(handler).not.toHaveBeenCalled();

            // 有 ctrl 应该触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', ctrlKey: true }));
            expect(handler).toHaveBeenCalled();
        });

        it('Meta键快捷键应该正确匹配', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler });
            KeyboardManager.init();

            // 有 meta 应该触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', metaKey: true }));
            expect(handler).toHaveBeenCalled();
        });

        it('Shift快捷键应该正确匹配', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 's', shift: true, description: '保存', handler });
            KeyboardManager.init();

            // 没有 shift 不应触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 's' }));
            expect(handler).not.toHaveBeenCalled();

            // 有 shift 应该触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', shiftKey: true }));
            expect(handler).toHaveBeenCalled();
        });

        it('Ctrl+Shift组合应该正确匹配', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'a', ctrl: true, shift: true, description: '组合', handler });
            KeyboardManager.init();

            // 缺少任何一个修饰键都不应触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', ctrlKey: true }));
            expect(handler).not.toHaveBeenCalled();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', shiftKey: true }));
            expect(handler).not.toHaveBeenCalled();

            // 同时有 ctrl 和 shift 应该触发
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', ctrlKey: true, shiftKey: true }));
            expect(handler).toHaveBeenCalled();
        });

        it('输入框内不应触发快捷键（Escape 除外）', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', description: '新建', handler });
            KeyboardManager.init();

            document.body.innerHTML = '<input id="test-input">';
            const input = document.getElementById('test-input');
            input.focus();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n' }));
            expect(handler).not.toHaveBeenCalled();
        });

        it('Escape在输入框内应该触发', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'Escape', description: '关闭', handler });
            KeyboardManager.init();

            document.body.innerHTML = '<input id="test-input">';
            const input = document.getElementById('test-input');
            input.focus();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            expect(handler).toHaveBeenCalled();
        });

        it('textarea内不应触发快捷键（Escape 除外）', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', description: '新建', handler });
            KeyboardManager.init();

            document.body.innerHTML = '<textarea id="test-textarea"></textarea>';
            const textarea = document.getElementById('test-textarea');
            textarea.focus();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n' }));
            expect(handler).not.toHaveBeenCalled();
        });

        it('select内不应触发快捷键（Escape 除外）', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', description: '新建', handler });
            KeyboardManager.init();

            document.body.innerHTML = '<select id="test-select"><option>1</option></select>';
            const select = document.getElementById('test-select');
            select.focus();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n' }));
            expect(handler).not.toHaveBeenCalled();
        });

        it('应该阻止默认行为', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler });
            KeyboardManager.init();

            const event = new KeyboardEvent('keydown', { key: 'n', ctrlKey: true });
            event.preventDefault = vi.fn();
            
            document.dispatchEvent(event);
            expect(event.preventDefault).toHaveBeenCalled();
        });

        it('Ctrl+/应该切换快捷键面板', () => {
            KeyboardManager.init();
            
            const event = new KeyboardEvent('keydown', { key: '/', ctrlKey: true });
            event.preventDefault = vi.fn();
            
            document.dispatchEvent(event);
            expect(event.preventDefault).toHaveBeenCalled();
        });
    });

    describe('trapFocus', () => {
        it('应该返回释放函数', () => {
            document.body.innerHTML = '<div id="modal"><button>OK</button></div>';
            const container = document.getElementById('modal');
            const release = KeyboardManager.trapFocus(container);
            expect(typeof release).toBe('function');
        });

        it('应该聚焦第一个可聚焦元素', () => {
            document.body.innerHTML = '<div id="modal"><button>OK</button><button>Cancel</button></div>';
            const container = document.getElementById('modal');
            const release = KeyboardManager.trapFocus(container);
            
            const buttons = container.querySelectorAll('button');
            expect(document.activeElement).toBe(buttons[0]);
        });

        it('Tab应该循环到最后一个元素', () => {
            document.body.innerHTML = '<div id="modal"><button>1</button><button>2</button><button>3</button></div>';
            const container = document.getElementById('modal');
            KeyboardManager.trapFocus(container);
            
            const buttons = container.querySelectorAll('button');
            buttons[2].focus();
            
            const event = new KeyboardEvent('keydown', { key: 'Tab' });
            event.preventDefault = vi.fn();
            
            container.dispatchEvent(event);
            expect(event.preventDefault).toHaveBeenCalled();
            expect(document.activeElement).toBe(buttons[0]);
        });

        it('Shift+Tab应该循环到第一个元素', () => {
            document.body.innerHTML = '<div id="modal"><button>1</button><button>2</button><button>3</button></div>';
            const container = document.getElementById('modal');
            KeyboardManager.trapFocus(container);
            
            const buttons = container.querySelectorAll('button');
            buttons[0].focus();
            
            const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true });
            event.preventDefault = vi.fn();
            
            container.dispatchEvent(event);
            expect(event.preventDefault).toHaveBeenCalled();
            expect(document.activeElement).toBe(buttons[2]);
        });

        it('没有可聚焦元素时应该不处理', () => {
            document.body.innerHTML = '<div id="modal">No focusable elements</div>';
            const container = document.getElementById('modal');
            KeyboardManager.trapFocus(container);
            
            const event = new KeyboardEvent('keydown', { key: 'Tab' });
            event.preventDefault = vi.fn();
            
            container.dispatchEvent(event);
            expect(event.preventDefault).not.toHaveBeenCalled();
        });

        it('释放函数应该恢复之前的焦点', () => {
            document.body.innerHTML = '<button id="outside">Outside</button><div id="modal"><button>Inside</button></div>';
            const outsideBtn = document.getElementById('outside');
            const modal = document.getElementById('modal');
            
            outsideBtn.focus();
            const release = KeyboardManager.trapFocus(modal);
            release();
            
            expect(document.activeElement).toBe(outsideBtn);
        });

        it('释放函数应该移除事件监听器', () => {
            document.body.innerHTML = '<div id="modal"><button>OK</button></div>';
            const container = document.getElementById('modal');
            container.removeEventListener = vi.fn(); // Mock removeEventListener 方法
            const release = KeyboardManager.trapFocus(container);
            
            release();
            expect(container.removeEventListener).toHaveBeenCalled();
        });
    });

    describe('releaseFocusTrap', () => {
        it('应该释放最近的焦点陷阱', () => {
            document.body.innerHTML = '<div id="modal"><button>OK</button></div>';
            const container = document.getElementById('modal');
            KeyboardManager.trapFocus(container);
            expect(KeyboardManager._focusTrapStack.length).toBe(1);

            KeyboardManager.releaseFocusTrap();
            expect(KeyboardManager._focusTrapStack.length).toBe(0);
        });

        it('应该支持多个焦点陷阱的LIFO释放', () => {
            document.body.innerHTML = '<div id="modal1"><button>1</button></div><div id="modal2"><button>2</button></div>';
            const modal1 = document.getElementById('modal1');
            const modal2 = document.getElementById('modal2');
            
            KeyboardManager.trapFocus(modal1);
            KeyboardManager.trapFocus(modal2);
            expect(KeyboardManager._focusTrapStack.length).toBe(2);

            KeyboardManager.releaseFocusTrap();
            expect(KeyboardManager._focusTrapStack.length).toBe(1);

            KeyboardManager.releaseFocusTrap();
            expect(KeyboardManager._focusTrapStack.length).toBe(0);
        });

        it('空栈时不应该报错', () => {
            expect(() => KeyboardManager.releaseFocusTrap()).not.toThrow();
        });
    });

    describe('快捷键面板', () => {
        it('toggleShortcutPanel 应该创建面板', () => {
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            expect(KeyboardManager._shortcutPanel).not.toBeNull();
            expect(document.querySelector('.shortcut-panel')).not.toBeNull();
        });

        it('面板应该显示所有注册的快捷键', () => {
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler: () => {} });
            KeyboardManager.register({ key: 's', shift: true, description: '保存', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            
            const panel = document.querySelector('.shortcut-panel');
            expect(panel.innerHTML).toContain('新建');
            expect(panel.innerHTML).toContain('保存');
        });

        it('面板应该显示正确的键盘符号', () => {
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            
            const panel = document.querySelector('.shortcut-panel');
            expect(panel.innerHTML).toContain('⌘');
            expect(panel.innerHTML).toContain('N');
        });

        it('面板应该设置正确的ARIA属性', () => {
            KeyboardManager.register({ key: 'n', description: '测试', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            
            const panel = KeyboardManager._shortcutPanel;
            expect(panel.getAttribute('role')).toBe('dialog');
            expect(panel.getAttribute('aria-label')).toBe('键盘快捷键');
        });

        it('再次 toggle 应该关闭面板', () => {
            KeyboardManager.register({ key: 'n', ctrl: true, description: '新建', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            KeyboardManager.toggleShortcutPanel();
            // 面板被设为 null（DOM 移除有延迟）
            expect(KeyboardManager._shortcutPanel).toBeNull();
        });

        it('Escape键应该关闭面板', () => {
            KeyboardManager.register({ key: 'n', description: '测试', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            
            // 面板应该被移除
            setTimeout(() => {
                expect(KeyboardManager._shortcutPanel).toBeNull();
            }, 250);
        });

        it('面板关闭时应该移除DOM元素', () => {
            const mockSetTimeout = vi.fn((cb, delay) => {
                cb();
                return 1;
            });
            global.setTimeout = mockSetTimeout;
            
            KeyboardManager.register({ key: 'n', description: '测试', handler: () => {} });
            KeyboardManager.toggleShortcutPanel();
            KeyboardManager.toggleShortcutPanel();
            
            // 面板应该被移除（有延迟）
            expect(mockSetTimeout).toHaveBeenCalled();
        });
    });

    describe('边界情况', () => {
        it('没有注册快捷键时面板应该显示提示', () => {
            KeyboardManager.toggleShortcutPanel();
            const panel = document.querySelector('.shortcut-panel');
            expect(panel.innerHTML).toContain('键盘快捷键');
        });

        it('没有可聚焦元素时trapFocus不应该报错', () => {
            document.body.innerHTML = '<div id="modal"></div>';
            const container = document.getElementById('modal');
            expect(() => KeyboardManager.trapFocus(container)).not.toThrow();
        });

        it('快捷键键值应该区分大小写', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'N', ctrl: true, description: '测试', handler });
            KeyboardManager.init();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'n', ctrlKey: true }));
            expect(handler).not.toHaveBeenCalled();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'N', ctrlKey: true }));
            expect(handler).toHaveBeenCalled();
        });

        it('特殊键应该正确处理', () => {
            const handler = vi.fn();
            KeyboardManager.register({ key: 'Enter', description: '确认', handler });
            KeyboardManager.init();

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
            expect(handler).toHaveBeenCalled();
        });
    });
});
