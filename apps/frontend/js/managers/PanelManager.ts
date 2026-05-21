/**
 * PanelManager - 可折叠面板管理器
 *
 * 统一管理所有带有 data-collapsible 属性的面板的折叠/展开状态。
 * 功能：
 *   - 基于 localStorage 的状态持久化
 *   - CSS transition 驱动的极简动画
 *   - ARIA 无障碍属性同步更新
 *   - 键盘导航支持 (Enter/Space)
 *   - 快速连续点击防抖保护
 */

const STORAGE_KEY = 'udake_panel_states';

/** 面板状态映射表 */
interface PanelStates {
    [panelId: string]: 'collapsed' | 'expanded';
}

export class PanelManager {
    /** 面板 ID → DOM 元素映射 */
    private panels: Map<string, HTMLElement> = new Map();

    /** 防止快速连续点击导致动画错乱的防抖锁 */
    private animatingPanels: Set<string> = new Set();

    /** 动画完成后解锁的延迟 (ms)，与 CSS transition 时长匹配 */
    private readonly ANIMATION_DURATION = 350;

    constructor() {
        this.init();
    }

    // ==================== 初始化 ====================

    private init(): void {
        const panelElements = document.querySelectorAll<HTMLElement>('[data-collapsible]');

        if (panelElements.length === 0) {
            return;
        }

        panelElements.forEach((panel) => {
            const panelId = panel.getAttribute('data-collapsible');
            if (!panelId) return;

            this.panels.set(panelId, panel);

            // 添加可折叠面板样式类
            panel.classList.add('collapsible-panel');
            panel.classList.add('expanded');

            // 确保面板标题有 chevron 图标
            this.ensureChevron(panel);

            // 绑定标题交互事件
            this.bindTitleEvents(panel, panelId);
        });

        // 恢复面板状态（在绑定事件之后，确保 DOM 已准备好）
        this.restorePanelStates();
    }

    // ==================== Chevron 管理 ====================

    private ensureChevron(panel: HTMLElement): void {
        const title = panel.querySelector<HTMLElement>('.panel-title');
        if (!title) return;

        // 避免重复添加
        let chevron = title.querySelector<HTMLElement>('.panel-title-chevron');
        if (!chevron) {
            chevron = document.createElement('span');
            chevron.className = 'panel-title-chevron';
            chevron.setAttribute('aria-hidden', 'true');
            chevron.textContent = '▾';
            title.appendChild(chevron);
        }
    }

    // ==================== 事件绑定 ====================

    private bindTitleEvents(panel: HTMLElement, panelId: string): void {
        const title = panel.querySelector<HTMLElement>('.panel-title');
        if (!title) return;

        // 防止重复绑定
        if (title.dataset.panelManagerBound === 'true') return;
        title.dataset.panelManagerBound = 'true';

        // 设置 ARIA 按钮角色
        title.setAttribute('role', 'button');
        title.setAttribute('tabindex', '0');

        // 点击事件
        title.addEventListener('click', (e) => {
            // 避免触发内部按钮的默认行为
            if ((e.target as HTMLElement).closest('button, a, input, select, textarea, summary, label')) {
                return;
            }
            this.togglePanel(panelId);
        });

        // 键盘事件
        title.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.togglePanel(panelId);
            }
        });
    }

    // ==================== 面板切换 ====================

    /**
     * 切换面板的折叠/展开状态
     */
    togglePanel(panelId: string): void {
        const panel = this.panels.get(panelId);
        if (!panel) return;

        // 防抖：如果动画正在进行中，忽略快速连续点击
        if (this.animatingPanels.has(panelId)) return;

        const isCollapsed = panel.classList.contains('collapsed');

        // 锁定动画
        this.animatingPanels.add(panelId);
        panel.classList.add('no-transition');
        // 强制重排后移除 no-transition，确保 transition 生效
        void panel.offsetWidth;
        panel.classList.remove('no-transition');

        if (isCollapsed) {
            this.expandPanel(panelId, panel);
        } else {
            this.collapsePanel(panelId, panel);
        }

        // 动画完成后解锁
        setTimeout(() => {
            this.animatingPanels.delete(panelId);
        }, this.ANIMATION_DURATION + 50);
    }

    private expandPanel(panelId: string, panel: HTMLElement): void {
        panel.classList.remove('collapsed');
        panel.classList.add('expanded');

        const title = panel.querySelector<HTMLElement>('.panel-title');
        if (title) {
            title.setAttribute('aria-expanded', 'true');
        }

        this.saveState(panelId, 'expanded');
    }

    private collapsePanel(panelId: string, panel: HTMLElement): void {
        panel.classList.remove('expanded');
        panel.classList.add('collapsed');

        const title = panel.querySelector<HTMLElement>('.panel-title');
        if (title) {
            title.setAttribute('aria-expanded', 'false');
        }

        this.saveState(panelId, 'collapsed');
    }

    // ==================== 状态持久化 ====================

    private saveState(panelId: string, state: 'collapsed' | 'expanded'): void {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            const states: PanelStates = stored ? JSON.parse(stored) : {};
            states[panelId] = state;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(states));
        } catch (e) {
            console.warn('[PanelManager] 无法保存面板状态到 localStorage:', e);
        }
    }

    /**
     * 从 localStorage 恢复所有面板的折叠状态
     * 在页面加载时调用
     */
    restorePanelStates(): void {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (!stored) return;

            const states: PanelStates = JSON.parse(stored);

            Object.entries(states).forEach(([panelId, state]) => {
                const panel = this.panels.get(panelId);
                if (!panel) return;

                // 短暂禁用过渡动画
                panel.classList.add('no-transition');

                if (state === 'collapsed') {
                    panel.classList.add('collapsed');
                    panel.classList.remove('expanded');
                } else {
                    panel.classList.remove('collapsed');
                    panel.classList.add('expanded');
                }

                const title = panel.querySelector<HTMLElement>('.panel-title');
                if (title) {
                    title.setAttribute('aria-expanded', state === 'expanded' ? 'true' : 'false');
                }

                // 恢复过渡
                void panel.offsetWidth;
                panel.classList.remove('no-transition');
            });
        } catch (e) {
            console.warn('[PanelManager] 无法从 localStorage 恢复面板状态:', e);
        }
    }

    /**
     * 获取面板当前状态
     */
    getPanelState(panelId: string): 'collapsed' | 'expanded' | null {
        const panel = this.panels.get(panelId);
        if (!panel) return null;
        return panel.classList.contains('collapsed') ? 'collapsed' : 'expanded';
    }

    /**
     * 销毁 PanelManager，清理事件和状态
     */
    destroy(): void {
        this.panels.forEach((panel) => {
            const title = panel.querySelector<HTMLElement>('.panel-title');
            if (title) {
                title.removeAttribute('role');
                title.removeAttribute('tabindex');
                title.dataset.panelManagerBound = 'false';
                // 注意：事件监听器无法直接移除，但可以通过 cloneNode 或标记忽略
            }
            panel.classList.remove('collapsible-panel', 'collapsed', 'expanded', 'no-transition');
        });
        this.panels.clear();
        this.animatingPanels.clear();
    }
}
