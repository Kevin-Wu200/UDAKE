/**
 * 移动端导航组件
 * 实现汉堡菜单、底部导航栏和滑动导航
 */

import './config/主题变量';
import { I18n } from '../utils/I18n';
import VirtualList, { type VirtualListOptions } from './VirtualList';
import { RuntimeLifecycle, type LifecycleScope } from '../utils/RuntimeLifecycle';
import { Logger } from '../utils/Logger';

interface NavItem {
    id: string;
    label: string;
    icon: string;
    action: () => void;
}

interface MobileNavigationOptions {
    navItems: NavItem[];
    enableSwipe: boolean;
    enableHaptic: boolean;
    enableVirtualScroll?: boolean;
}

interface VirtualScrollMountOptions<T> {
    container: HTMLElement;
    items: T[];
    itemHeight?: number;
    overscan?: number;
    estimateHeight?: (item: T, index: number) => number;
    renderItem: (item: T, index: number) => HTMLElement;
    keyExtractor?: (item: T, index: number) => string;
    initialScrollTop?: number;
    scrollMemoryKey?: string;
    onEndReached?: () => void;
}

class MobileNavigation {
    private navItems: NavItem[];
    private enableSwipe: boolean;
    private enableHaptic: boolean;
    private enableVirtualScroll: boolean;
    private isSidebarOpen: boolean = false;
    private currentNavIndex: number = 0;
    private swipeThreshold: number = 50;
    private touchActionDebounceMs: number = 180;
    private lastTouchActionAt: number = 0;
    private touchStartX: number = 0;
    private touchStartY: number = 0;
    private navScrollMemory: Map<string, number> = new Map();
    private activeVirtualLists: Map<string, VirtualList<unknown>> = new Map();
    private lifecycleScope: LifecycleScope;

    private elements: {
        hamburgerMenu: HTMLElement | null;
        sidebar: HTMLElement | null;
        bottomNav: HTMLElement | null;
        overlay: HTMLElement | null;
        mapContainer: HTMLElement | null;
    } = {
        hamburgerMenu: null,
        sidebar: null,
        bottomNav: null,
        overlay: null,
        mapContainer: null,
    };

    constructor(options: MobileNavigationOptions) {
        this.navItems = options.navItems;
        this.enableSwipe = options.enableSwipe;
        this.enableHaptic = options.enableHaptic;
        this.enableVirtualScroll = options.enableVirtualScroll ?? true;
        this.lifecycleScope = RuntimeLifecycle.createScope('MobileNavigation');
        this.init();
    }

    /**
     * 初始化移动端导航
     */
    private init(): void {
        this.updateSwipeThreshold();
        this.createHamburgerMenu();
        this.createBottomNav();
        this.createOverlay();
        this.bindEvents();
        this.setupSwipeNavigation();
        this.lifecycleScope.addEventListener(window, 'resize', () => this.updateSwipeThreshold(), { passive: true });
        this.lifecycleScope.addEventListener(window, 'orientationchange', () => this.updateSwipeThreshold(), { passive: true });
    }

    /**
     * 创建汉堡菜单按钮
     */
    private createHamburgerMenu(): void {
        const headerLeft = document.querySelector('.header-left');
        if (!headerLeft) return;

        const hamburger = document.createElement('button');
        hamburger.className = 'hamburger-menu mobile-only';
        hamburger.innerHTML = `
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
            <span class="hamburger-line"></span>
        `;
        hamburger.setAttribute('aria-label', I18n.t('mobilenavigation.openMenu'));
        hamburger.setAttribute('aria-expanded', 'false');

        headerLeft.appendChild(hamburger);
        this.elements.hamburgerMenu = hamburger;
    }

    /**
     * 创建底部导航栏
     */
    private createBottomNav(): void {
        const existingBottomNav = document.querySelector('.bottom-nav');
        if (existingBottomNav) {
            this.elements.bottomNav = existingBottomNav as HTMLElement;
            return;
        }

        const bottomNav = document.createElement('nav');
        bottomNav.className = 'bottom-nav mobile-only';
        bottomNav.style.paddingBottom = 'env(safe-area-inset-bottom, 0px)';

        this.navItems.forEach((item, index) => {
            const navItem = document.createElement('button');
            navItem.className = `bottom-nav-item ${index === 0 ? 'active' : ''}`;
            navItem.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${item.icon}
                </svg>
                <span>${item.label}</span>
            `;
            navItem.setAttribute('aria-label', item.label);
            navItem.setAttribute('aria-current', index === 0 ? 'page' : 'false');
            this.bindTouchAwareNavEvents(navItem, item, index);

            bottomNav.appendChild(navItem);
        });

        document.body.appendChild(bottomNav);
        this.elements.bottomNav = bottomNav;

        // 调整地图容器高度
        const mapContainer = document.querySelector('.map-container');
        if (mapContainer) {
            mapContainer.classList.add('with-bottom-nav');
            this.elements.mapContainer = mapContainer as HTMLElement;
        }
    }

    /**
     * 创建遮罩层
     */
    private createOverlay(): void {
        const existingOverlay = document.querySelector('.overlay');
        if (existingOverlay) {
            this.elements.overlay = existingOverlay as HTMLElement;
            return;
        }

        const overlay = document.createElement('div');
        overlay.className = 'overlay';
        overlay.setAttribute('aria-hidden', 'true');

        this.lifecycleScope.addEventListener(overlay, 'click', () => {
            this.closeSidebar();
        });

        document.body.appendChild(overlay);
        this.elements.overlay = overlay;
    }

    /**
     * 绑定事件
     */
    private bindEvents(): void {
        if (this.elements.hamburgerMenu) {
            this.lifecycleScope.addEventListener(this.elements.hamburgerMenu, 'click', () => {
                this.toggleSidebar();
                this.hapticFeedback();
            });
        }
    }

    /**
     * 切换侧边栏
     */
    private toggleSidebar(): void {
        const sidebar = document.querySelector('.sidebar') as HTMLElement;
        const overlay = this.elements.overlay;
        const hamburger = this.elements.hamburgerMenu;

        if (!sidebar || !overlay || !hamburger) return;

        this.isSidebarOpen = !this.isSidebarOpen;

        if (this.isSidebarOpen) {
            sidebar.classList.add('active');
            overlay.classList.add('active');
            hamburger.classList.add('active');
            hamburger.setAttribute('aria-expanded', 'true');
            document.body.style.overflow = 'hidden';
        } else {
            this.closeSidebar();
        }
    }

    /**
     * 关闭侧边栏
     */
    private closeSidebar(): void {
        const sidebar = document.querySelector('.sidebar') as HTMLElement;
        const overlay = this.elements.overlay;
        const hamburger = this.elements.hamburgerMenu;

        if (!sidebar || !overlay || !hamburger) return;

        this.isSidebarOpen = false;
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
        hamburger.classList.remove('active');
        hamburger.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
    }

    /**
     * 选择底部导航项
     */
    private selectNavItem(index: number): void {
        this.saveCurrentScrollPosition();

        const navItems = this.elements.bottomNav?.querySelectorAll('.bottom-nav-item');
        if (!navItems) return;

        navItems.forEach((item, i) => {
            if (i === index) {
                item.classList.add('active');
                item.setAttribute('aria-current', 'page');
            } else {
                item.classList.remove('active');
                item.setAttribute('aria-current', 'false');
            }
        });

        this.currentNavIndex = index;
        this.restoreCurrentScrollPosition();
    }

    /**
     * 设置滑动导航
     */
    private setupSwipeNavigation(): void {
        if (!this.enableSwipe) return;

        const mapContainer = document.querySelector('.map-container');
        if (!mapContainer) return;

        this.lifecycleScope.addEventListener(mapContainer, 'touchstart', (e: Event) => {
            const touch = (e as TouchEvent).touches[0];
            this.touchStartX = touch.clientX;
            this.touchStartY = touch.clientY;
        }, { passive: true });

        this.lifecycleScope.addEventListener(mapContainer, 'touchend', (e: Event) => {
            const touchEndX = (e as TouchEvent).changedTouches[0].clientX;
            const touchEndY = (e as TouchEvent).changedTouches[0].clientY;

            const deltaX = touchEndX - this.touchStartX;
            const deltaY = touchEndY - this.touchStartY;

            // 水平滑动
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > this.swipeThreshold) {
                if (deltaX > 0) {
                    // 向右滑动
                    this.handleSwipeRight();
                } else {
                    // 向左滑动
                    this.handleSwipeLeft();
                }
            }
        }, { passive: true });
    }

    private updateSwipeThreshold(): void {
        if (typeof window === 'undefined') {
            return;
        }
        const viewportWidth = window.innerWidth;
        this.swipeThreshold = Math.max(28, Math.floor(viewportWidth * 0.08));
        Logger.debug('MobileNavigation', `滑动阈值更新为 ${this.swipeThreshold}px`);
    }

    /**
     * 处理向左滑动
     */
    private handleSwipeLeft(): void {
        if (!this.shouldHandleTouchAction()) {
            return;
        }
        const nextIndex = (this.currentNavIndex + 1) % this.navItems.length;
        this.selectNavItem(nextIndex);
        this.navItems[nextIndex].action();
        this.hapticFeedback();
    }

    /**
     * 处理向右滑动
     */
    private handleSwipeRight(): void {
        if (!this.shouldHandleTouchAction()) {
            return;
        }
        const prevIndex = (this.currentNavIndex - 1 + this.navItems.length) % this.navItems.length;
        this.selectNavItem(prevIndex);
        this.navItems[prevIndex].action();
        this.hapticFeedback();
    }

    private shouldHandleTouchAction(): boolean {
        const now = Date.now();
        if ((now - this.lastTouchActionAt) < this.touchActionDebounceMs) {
            return false;
        }
        this.lastTouchActionAt = now;
        return true;
    }

    private bindTouchAwareNavEvents(navItem: HTMLElement, item: NavItem, index: number): void {
        let touchStartAt = 0;
        let longPressTimer: number | null = null;
        let lastTapAt = 0;

        const selectItem = () => {
            if (!this.shouldHandleTouchAction()) {
                return;
            }
            this.selectNavItem(index);
            item.action();
            this.hapticFeedback();
        };

        this.lifecycleScope.addEventListener(navItem, 'click', () => {
            selectItem();
        });

        this.lifecycleScope.addEventListener(navItem, 'touchstart', () => {
            touchStartAt = Date.now();
            longPressTimer = window.setTimeout(() => {
                navItem.dispatchEvent(new CustomEvent('mobile-nav-longpress', {
                    bubbles: true,
                    detail: { id: item.id, index }
                }));
            }, 500);
        }, { passive: true });

        this.lifecycleScope.addEventListener(navItem, 'touchend', () => {
            if (longPressTimer !== null) {
                window.clearTimeout(longPressTimer);
                longPressTimer = null;
            }

            const now = Date.now();
            const touchDuration = now - touchStartAt;
            if (touchDuration > 450) {
                return;
            }

            if ((now - lastTapAt) <= 280) {
                navItem.dispatchEvent(new CustomEvent('mobile-nav-doubletap', {
                    bubbles: true,
                    detail: { id: item.id, index }
                }));
            }
            lastTapAt = now;
        }, { passive: true });
    }

    /**
     * 触觉反馈
     */
    private hapticFeedback(): void {
        if (!this.enableHaptic) return;

        if ('vibrate' in navigator) {
            navigator.vibrate(10);
        }
    }

    private saveCurrentScrollPosition(): void {
        const currentNav = this.navItems[this.currentNavIndex];
        const mapContainer = this.elements.mapContainer;
        if (!currentNav || !mapContainer) {
            return;
        }
        this.navScrollMemory.set(currentNav.id, mapContainer.scrollTop);
    }

    private restoreCurrentScrollPosition(): void {
        const currentNav = this.navItems[this.currentNavIndex];
        const mapContainer = this.elements.mapContainer;
        if (!currentNav || !mapContainer) {
            return;
        }
        mapContainer.scrollTop = this.navScrollMemory.get(currentNav.id) || 0;
    }

    private isMobileViewport(): boolean {
        return typeof window !== 'undefined' && window.matchMedia('(max-width: 1024px)').matches;
    }

    public mountVirtualList<T>(options: VirtualScrollMountOptions<T>): VirtualList<T> | null {
        if (!this.enableVirtualScroll || !this.isMobileViewport()) {
            return null;
        }

        const memoryKey = options.scrollMemoryKey || 'default';
        const initialScrollTop = options.initialScrollTop ?? this.navScrollMemory.get(memoryKey) ?? 0;
        const virtualOptions: VirtualListOptions<T> = {
            container: options.container,
            items: options.items,
            itemHeight: options.itemHeight,
            overscan: options.overscan,
            estimateHeight: options.estimateHeight,
            renderItem: options.renderItem,
            keyExtractor: options.keyExtractor,
            initialScrollTop,
            onEndReached: options.onEndReached,
        };

        const list = new VirtualList(virtualOptions);
        this.activeVirtualLists.set(memoryKey, list as VirtualList<unknown>);
        return list;
    }

    public rememberVirtualListScroll(key: string): void {
        const list = this.activeVirtualLists.get(key);
        if (!list) {
            return;
        }
        this.navScrollMemory.set(key, list.getScrollTop());
    }

    /**
     * 更新导航项
     */
    public updateNavItems(items: NavItem[]): void {
        this.navItems = items;
        const bottomNav = this.elements.bottomNav;
        if (bottomNav) {
            bottomNav.innerHTML = '';
            this.createBottomNav();
        }
    }

    /**
     * 销毁导航
     */
    public destroy(): void {
        this.activeVirtualLists.forEach(list => list.destroy());
        this.activeVirtualLists.clear();
        this.lifecycleScope.cleanup();

        if (this.elements.hamburgerMenu) {
            this.elements.hamburgerMenu.remove();
        }
        if (this.elements.bottomNav) {
            this.elements.bottomNav.remove();
        }
        if (this.elements.overlay) {
            this.elements.overlay.remove();
        }
        if (this.elements.mapContainer) {
            this.elements.mapContainer.classList.remove('with-bottom-nav');
        }
    }
}

// 导出
export default MobileNavigation;
