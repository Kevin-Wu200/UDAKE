/**
 * 可拖拽面板组件
 * 支持面板拖拽、位置调整、大小调整和显示/隐藏功能
 */

import { appStore } from '../store/Store';
import type { PanelInfo } from '../../types/core';
import { I18nDialog } from './I18nDialog.js';

export class DraggablePanel {
    private panelId: string;
    private element: HTMLElement;
    private header!: HTMLElement;
    private content!: HTMLElement;
    private isDragging: boolean = false;
    private isResizing: boolean = false;
    private dragOffset = { x: 0, y: 0 };
    private resizeDirection: string = '';

    constructor(panelId: string, element: HTMLElement) {
        this.panelId = panelId;
        this.element = element;
        
        // 创建面板结构
        this.createPanelStructure();
        
        // 初始化拖拽和调整大小功能
        this.initializeDrag();
        this.initializeResize();
        
        // 监听面板状态变化
        this.subscribeToPanelState();
    }

    private createPanelStructure(): void {
        // 创建面板头部
        this.header = document.createElement('div');
        this.header.className = 'draggable-panel-header';
        this.header.innerHTML = `
            <span class="panel-title">${this.getPanelTitle()}</span>
            <div class="panel-controls">
                <button class="panel-btn panel-collapse-btn" title="折叠/展开">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="2" fill="none"/>
                    </svg>
                </button>
                <button class="panel-btn panel-hide-btn" title="隐藏">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2"/>
                    </svg>
                </button>
            </div>
        `;

        // 创建面板内容容器
        this.content = document.createElement('div');
        this.content.className = 'draggable-panel-content';
        
        // 移动现有内容到新的内容容器
        while (this.element.firstChild) {
            this.content.appendChild(this.element.firstChild);
        }

        // 添加头部和内容到面板
        this.element.appendChild(this.header);
        this.element.appendChild(this.content);

        // 添加面板类
        this.element.classList.add('draggable-panel');
        this.element.dataset.panelId = this.panelId;

        // 绑定按钮事件
        this.bindControlEvents();
    }

    private getPanelTitle(): string {
        const titles: Record<string, string> = {
            'parameter': '参数面板',
            'sampling': '采样面板',
            'legend': '图例',
            'tools': '工具栏'
        };
        return titles[this.panelId] || '面板';
    }

    private bindControlEvents(): void {
        const collapseBtn = this.header.querySelector('.panel-collapse-btn') as HTMLElement;
        const hideBtn = this.header.querySelector('.panel-hide-btn') as HTMLElement;

        collapseBtn?.addEventListener('click', () => this.toggleCollapse());
        hideBtn?.addEventListener('click', () => this.hidePanel());
    }

    private initializeDrag(): void {
        this.header.style.cursor = 'move';

        this.header.addEventListener('mousedown', (e) => {
            if ((e.target as HTMLElement).closest('.panel-controls')) return;
            
            this.isDragging = true;
            const rect = this.element.getBoundingClientRect();
            this.dragOffset = {
                x: e.clientX - rect.left,
                y: e.clientY - rect.top
            };

            this.element.style.position = 'absolute';
            this.element.style.zIndex = '1000';
            this.element.classList.add('dragging');

            document.addEventListener('mousemove', this.onDrag);
            document.addEventListener('mouseup', this.stopDrag);
        });
    }

    private onDrag = (e: MouseEvent): void => {
        if (!this.isDragging) return;

        const x = e.clientX - this.dragOffset.x;
        const y = e.clientY - this.dragOffset.y;

        this.element.style.left = `${x}px`;
        this.element.style.top = `${y}px`;

        // 检测吸附区域
        this.checkSnapPosition(e.clientX, e.clientY);
    };

    private stopDrag = (): void => {
        if (!this.isDragging) return;

        this.isDragging = false;
        this.element.classList.remove('dragging');
        this.element.style.zIndex = '';

        document.removeEventListener('mousemove', this.onDrag);
        document.removeEventListener('mouseup', this.stopDrag);

        // 更新面板位置状态
        this.updatePanelPosition();
    };

    private checkSnapPosition(clientX: number, clientY: number): void {
        const snapThreshold = 50;
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        // 检测左侧吸附
        if (clientX < snapThreshold) {
            this.element.classList.add('snap-left');
        } else {
            this.element.classList.remove('snap-left');
        }

        // 检测右侧吸附
        if (clientX > windowWidth - snapThreshold) {
            this.element.classList.add('snap-right');
        } else {
            this.element.classList.remove('snap-right');
        }

        // 检测顶部吸附
        if (clientY < snapThreshold) {
            this.element.classList.add('snap-top');
        } else {
            this.element.classList.remove('snap-top');
        }

        // 检测底部吸附
        if (clientY > windowHeight - snapThreshold) {
            this.element.classList.add('snap-bottom');
        } else {
            this.element.classList.remove('snap-bottom');
        }
    }

    private updatePanelPosition(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const panelInfo = panels[this.panelId];
        
        if (panelInfo) {
            const rect = this.element.getBoundingClientRect();
            panelInfo.x = rect.left;
            panelInfo.y = rect.top;

            // 确定面板位置
            if (this.element.classList.contains('snap-left')) {
                panelInfo.position = 'left';
            } else if (this.element.classList.contains('snap-right')) {
                panelInfo.position = 'right';
            } else if (this.element.classList.contains('snap-top')) {
                panelInfo.position = 'top';
            } else if (this.element.classList.contains('snap-bottom')) {
                panelInfo.position = 'bottom';
            } else {
                panelInfo.position = 'floating';
            }

            appStore.set(`layout.panels.${this.panelId}`, panelInfo);
        }
    }

    private initializeResize(): void {
        // 创建调整大小的手柄
        ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'].forEach(direction => {
            const handle = document.createElement('div');
            handle.className = `resize-handle resize-${direction}`;
            handle.dataset.direction = direction;
            this.element.appendChild(handle);
        });

        // 绑定调整大小事件
        this.element.addEventListener('mousedown', (e) => {
            const target = e.target as HTMLElement;
            if (target.classList.contains('resize-handle')) {
                this.startResize(e, target.dataset.direction!);
            }
        });
    }

    private startResize(e: MouseEvent, direction: string): void {
        e.stopPropagation();

        this.isResizing = true;
        this.resizeDirection = direction;

        const rect = this.element.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        this.element.classList.add('resizing');

        document.addEventListener('mousemove', this.onResize);
        document.addEventListener('mouseup', this.stopResize);
    }

    private onResize = (e: MouseEvent): void => {
        if (!this.isResizing || !this.resizeDirection) return;

        const rect = this.element.getBoundingClientRect();
        const minWidth = 200;
        const minHeight = 100;

        let newWidth = rect.width;
        let newHeight = rect.height;
        let newX = rect.left;
        let newY = rect.top;

        if (this.resizeDirection.includes('e')) {
            newWidth = e.clientX - rect.left;
        }
        if (this.resizeDirection.includes('w')) {
            newWidth = rect.right - e.clientX;
            newX = e.clientX;
        }
        if (this.resizeDirection.includes('s')) {
            newHeight = e.clientY - rect.top;
        }
        if (this.resizeDirection.includes('n')) {
            newHeight = rect.bottom - e.clientY;
            newY = e.clientY;
        }

        // 应用最小尺寸限制
        if (newWidth >= minWidth) {
            this.element.style.width = `${newWidth}px`;
            if (this.resizeDirection.includes('w')) {
                this.element.style.left = `${newX}px`;
            }
        }

        if (newHeight >= minHeight) {
            this.element.style.height = `${newHeight}px`;
            if (this.resizeDirection.includes('n')) {
                this.element.style.top = `${newY}px`;
            }
        }

        // 显示尺寸提示
        this.showSizeTooltip(newWidth, newHeight, e.clientX, e.clientY);
    };

    private stopResize = (): void => {
        if (!this.isResizing) return;

        this.isResizing = false;
        this.element.classList.remove('resizing');
        this.resizeDirection = '';

        // 隐藏尺寸提示
        this.hideSizeTooltip();

        // 更新面板尺寸状态
        this.updatePanelSize();

        document.removeEventListener('mousemove', this.onResize);
        document.removeEventListener('mouseup', this.stopResize);
    };

    private updatePanelSize(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const panelInfo = panels[this.panelId];
        
        if (panelInfo) {
            const rect = this.element.getBoundingClientRect();
            panelInfo.width = rect.width;
            panelInfo.height = rect.height;

            appStore.set(`layout.panels.${this.panelId}`, panelInfo);
        }
    }

    private showSizeTooltip(width: number, height: number, x: number, y: number): void {
        let tooltip = document.getElementById('resize-tooltip');
        
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'resize-tooltip';
            tooltip.className = 'resize-tooltip';
            document.body.appendChild(tooltip);
        }

        tooltip.textContent = `${Math.round(width)} × ${Math.round(height)}`;
        tooltip.style.left = `${x + 15}px`;
        tooltip.style.top = `${y + 15}px`;
        tooltip.style.display = 'block';
    }

    private hideSizeTooltip(): void {
        const tooltip = document.getElementById('resize-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }

    private toggleCollapse(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const panelInfo = panels[this.panelId];
        
        if (panelInfo) {
            panelInfo.collapsed = !panelInfo.collapsed;
            this.element.classList.toggle('collapsed', panelInfo.collapsed);
            this.content.style.display = panelInfo.collapsed ? 'none' : 'block';
            
            appStore.set(`layout.panels.${this.panelId}`, panelInfo);
        }
    }

    private hidePanel(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const panelInfo = panels[this.panelId];

        if (panelInfo) {
            panelInfo.visible = false;
            this.element.style.display = 'none';

            appStore.set(`layout.panels.${this.panelId}`, panelInfo);
        }
    }

    public showPanel(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const panelInfo = panels[this.panelId];
        
        if (panelInfo) {
            panelInfo.visible = true;
            this.element.style.display = 'block';
            
            appStore.set(`layout.panels.${this.panelId}`, panelInfo);
        }
    }

    private subscribeToPanelState(): void {
        appStore.subscribe(`layout.panels.${this.panelId}`, (panelInfo: PanelInfo) => {
            // 更新面板可见性
            this.element.style.display = panelInfo.visible ? 'block' : 'none';
            
            // 更新面板折叠状态
            this.element.classList.toggle('collapsed', panelInfo.collapsed || false);
            this.content.style.display = panelInfo.collapsed ? 'none' : 'block';
            
            // 更新面板位置
            if (panelInfo.position === 'floating' && panelInfo.x !== undefined && panelInfo.y !== undefined) {
                this.element.style.position = 'absolute';
                this.element.style.left = `${panelInfo.x}px`;
                this.element.style.top = `${panelInfo.y}px`;
            }
            
            // 更新面板尺寸
            if (panelInfo.width !== undefined) {
                this.element.style.width = `${panelInfo.width}px`;
            }
            if (panelInfo.height !== undefined) {
                this.element.style.height = `${panelInfo.height}px`;
            }
        });
    }

    public destroy(): void {
        // 清理事件监听器
        document.removeEventListener('mousemove', this.onDrag);
        document.removeEventListener('mouseup', this.stopDrag);
        document.removeEventListener('mousemove', this.onResize);
        document.removeEventListener('mouseup', this.stopResize);
        
        // 移除面板元素
        this.element.remove();
    }
}

/**
 * 布局管理器
 * 管理所有可拖拽面板和布局配置
 */
export class LayoutManager {
    private panels: Map<string, DraggablePanel> = new Map();

    constructor() {
        this.initializePanels();
        this.createLayoutControls();
    }

    private initializePanels(): void {
        const panels = appStore.get('layout.panels') as Record<string, PanelInfo>;

        for (const [panelId, _panelInfo] of Object.entries(panels)) {
            const element = document.querySelector(`[data-panel-id="${panelId}"]`) as HTMLElement;

            if (element) {
                const draggablePanel = new DraggablePanel(panelId, element);
                this.panels.set(panelId, draggablePanel);
            }
        }
    }

    private createLayoutControls(): void {
        // 创建布局控制面板
        const controls = document.createElement('div');
        controls.className = 'layout-controls';
        controls.innerHTML = `
            <button class="layout-btn" data-action="save">保存布局</button>
            <button class="layout-btn" data-action="load">加载布局</button>
            <button class="layout-btn" data-action="reset">重置布局</button>
            <div class="layout-saved-list"></div>
        `;
        
        document.body.appendChild(controls);
        
        // 绑定控制按钮事件
        controls.querySelectorAll('.layout-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = (e.target as HTMLElement).dataset.action;
                this.handleLayoutAction(action!);
            });
        });
        
        // 更新已保存布局列表
        this.updateSavedLayoutsList();
    }

    private handleLayoutAction(action: string): void {
        switch (action) {
            case 'save':
                this.saveLayout();
                break;
            case 'load':
                this.loadLayout();
                break;
            case 'reset':
                this.resetLayout();
                break;
        }
    }

    public saveLayout(name?: string): void {
        if (!name) {
            const inputName = I18nDialog.prompt(
                'dialog.layout.name.prompt',
                'dialog.layout.defaultName',
                undefined,
                { date: new Date().toLocaleDateString() }
            );
            if (!inputName) return;
            name = inputName;
        }

        const currentPanels = appStore.get('layout.panels') as Record<string, PanelInfo>;
        const savedLayouts = appStore.get('layout.savedLayouts') as Record<string, Record<string, PanelInfo>>;

        savedLayouts[name] = JSON.parse(JSON.stringify(currentPanels));

        appStore.set('layout.savedLayouts', savedLayouts);
        appStore.set('layout.activeLayout', name);
        
        this.updateSavedLayoutsList();
        
        I18nDialog.alert('dialog.layout.saved', { name });
    }

    public loadLayout(name?: string): void {
        if (!name) {
            const savedLayouts = appStore.get('layout.savedLayouts') as Record<string, Record<string, PanelInfo>>;
            const layoutNames = Object.keys(savedLayouts);

            if (layoutNames.length === 0) {
                I18nDialog.alert('dialog.layout.none');
                return;
            }

            const inputName = I18nDialog.prompt('dialog.layout.selectToLoad', layoutNames[0], {
                names: layoutNames.join('\n')
            });
            if (!inputName || !savedLayouts[inputName]) {
                I18nDialog.alert('dialog.layout.notFound');
                return;
            }
            name = inputName;
        }

        const savedLayouts = appStore.get('layout.savedLayouts') as Record<string, Record<string, PanelInfo>>;
        const layout = savedLayouts[name];
        
        if (layout) {
            appStore.set('layout.panels', layout);
            appStore.set('layout.activeLayout', name);
            I18nDialog.alert('dialog.layout.loaded', { name });
        }
    }

    public resetLayout(): void {
        if (I18nDialog.confirm('dialog.layout.resetConfirm')) {
            // 恢复默认布局
            const defaultPanels = {
                'parameter': { id: 'parameter', visible: true, position: 'left', width: 300 },
                'sampling': { id: 'sampling', visible: true, position: 'right', width: 350 },
                'legend': { id: 'legend', visible: true, position: 'bottom', height: 200 },
                'tools': { id: 'tools', visible: true, position: 'top', height: 60 }
            };
            
            appStore.set('layout.panels', defaultPanels);
            appStore.set('layout.activeLayout', 'default');
            
            I18nDialog.alert('dialog.layout.resetDone');
        }
    }

    private updateSavedLayoutsList(): void {
        const savedLayouts = appStore.get('layout.savedLayouts') as Record<string, Record<string, PanelInfo>>;
        const listElement = document.querySelector('.layout-saved-list');

        if (listElement) {
            const activeLayout = appStore.get('layout.activeLayout');
            listElement.innerHTML = Object.entries(savedLayouts).map(([name, _layout]) => `
                <div class="layout-item ${name === activeLayout ? 'active' : ''}" data-layout="${name}">
                    <span class="layout-name">${name}</span>
                    <button class="layout-delete" title="删除">✕</button>
                </div>
            `).join('');
            
            // 绑定布局项事件
            listElement.querySelectorAll('.layout-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    if ((e.target as HTMLElement).classList.contains('layout-delete')) {
                        this.deleteLayout((item as HTMLElement).dataset.layout!);
                    } else {
                        this.loadLayout((item as HTMLElement).dataset.layout!);
                    }
                });
            });
        }
    }

    private deleteLayout(name: string): void {
        if (I18nDialog.confirm('dialog.layout.deleteConfirm', { name })) {
            const savedLayouts = appStore.get('layout.savedLayouts') as Record<string, Record<string, PanelInfo>>;
            delete savedLayouts[name];
            
            appStore.set('layout.savedLayouts', savedLayouts);
            
            if (appStore.get('layout.activeLayout') === name) {
                appStore.set('layout.activeLayout', 'default');
            }
            
            this.updateSavedLayoutsList();
        }
    }

    public destroy(): void {
        // 清理所有面板
        this.panels.forEach(panel => panel.destroy());
        this.panels.clear();
        
        // 移除布局控制面板
        const controls = document.querySelector('.layout-controls');
        if (controls) {
            controls.remove();
        }
    }
}
