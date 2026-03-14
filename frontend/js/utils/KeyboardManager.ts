/**
 * 键盘导航与焦点管理工具
 * 焦点陷阱、Tab循环、快捷键面板
 */

interface ShortcutConfig {
    key: string;
    ctrl?: boolean;
    shift?: boolean;
    description: string;
    handler: () => void;
}

export class KeyboardManager {
    static _shortcuts: ShortcutConfig[] = [];
    static _shortcutPanel: HTMLDivElement | null = null;
    static _focusTrapStack: (() => void)[] = [];

    static register(shortcut: ShortcutConfig): void {
        KeyboardManager._shortcuts.push(shortcut);
    }

    static init(): void {
        document.addEventListener('keydown', (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                KeyboardManager.toggleShortcutPanel();
                return;
            }

            const tag = document.activeElement?.tagName;
            const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
            if (isInput && e.key !== 'Escape') return;

            for (const s of KeyboardManager._shortcuts) {
                const ctrlMatch = s.ctrl ? (e.ctrlKey || e.metaKey) : !(e.ctrlKey || e.metaKey);
                const shiftMatch = s.shift ? e.shiftKey : !e.shiftKey;
                if (e.key === s.key && ctrlMatch && shiftMatch) {
                    e.preventDefault();
                    s.handler();
                    return;
                }
            }
        });
    }

    static trapFocus(container: HTMLElement): () => void {
        const previousFocus = document.activeElement;

        const getFocusable = (): NodeListOf<HTMLElement> => container.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );

        const handler = (e: KeyboardEvent): void => {
            if (e.key !== 'Tab') return;

            const focusable = getFocusable();
            if (focusable.length === 0) return;

            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        };

        container.addEventListener('keydown', handler);

        const focusable = getFocusable();
        if (focusable.length > 0) {
            (focusable[0] as HTMLElement).focus();
        }

        const release = (): void => {
            container.removeEventListener('keydown', handler);
            if (previousFocus && (previousFocus as HTMLElement).focus) {
                (previousFocus as HTMLElement).focus();
            }
        };

        KeyboardManager._focusTrapStack.push(release);
        return release;
    }

    static releaseFocusTrap(): void {
        const release = KeyboardManager._focusTrapStack.pop();
        if (release) release();
    }

    static toggleShortcutPanel(): void {
        if (KeyboardManager._shortcutPanel) {
            KeyboardManager._hideShortcutPanel();
        } else {
            KeyboardManager._showShortcutPanel();
        }
    }

    static _showShortcutPanel(): void {
        const panel = document.createElement('div');
        panel.className = 'shortcut-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', '键盘快捷键');

        let html = '<h3 class="shortcut-panel-title">键盘快捷键</h3><div class="shortcut-list">';
        for (const s of KeyboardManager._shortcuts) {
            const keys: string[] = [];
            if (s.ctrl) keys.push('<kbd>⌘</kbd>');
            if (s.shift) keys.push('<kbd>⇧</kbd>');
            keys.push(`<kbd>${s.key.length === 1 ? s.key.toUpperCase() : s.key}</kbd>`);
            html += `<div class="shortcut-item"><span class="shortcut-keys">${keys.join(' + ')}</span><span class="shortcut-desc">${s.description}</span></div>`;
        }
        html += '</div><p class="shortcut-hint">按 <kbd>⌘</kbd> + <kbd>/</kbd> 关闭</p>';
        panel.innerHTML = html;

        document.body.appendChild(panel);
        requestAnimationFrame(() => panel.classList.add('shortcut-panel-visible'));
        KeyboardManager._shortcutPanel = panel as HTMLDivElement;

        const handler = (e: KeyboardEvent): void => {
            if (e.key === 'Escape') {
                KeyboardManager._hideShortcutPanel();
                document.removeEventListener('keydown', handler);
            }
        };
        document.addEventListener('keydown', handler);
    }

    static _hideShortcutPanel(): void {
        const panel = KeyboardManager._shortcutPanel;
        if (!panel) return;
        panel.classList.remove('shortcut-panel-visible');
        setTimeout(() => panel.remove(), 200);
        KeyboardManager._shortcutPanel = null;
    }
}
