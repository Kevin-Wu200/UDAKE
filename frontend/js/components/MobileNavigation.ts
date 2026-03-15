/**
 * 移动端导航组件
 * 实现汉堡菜单、底部导航栏和滑动导航
 */

import './config/主题变量';

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
}

class MobileNavigation {
    private navItems: NavItem[];
    private enableSwipe: boolean;
    private enableHaptic: boolean;
    private isSidebarOpen: boolean = false;
    private currentNavIndex: number = 0;
    private swipeThreshold: number = 50;

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
        this.init();
    }

    /**
     * 初始化移动端导航
     */
    private init(): void {
        this.createHamburgerMenu();
        this.createBottomNav();
        this.createOverlay();
        this.bindEvents();
        this.setupSwipeNavigation();
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
        hamburger.setAttribute('aria-label', '打开菜单');
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

            navItem.addEventListener('click', () => {
                this.selectNavItem(index);
                item.action();
                this.hapticFeedback();
            });

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

        overlay.addEventListener('click', () => {
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
            this.elements.hamburgerMenu.addEventListener('click', () => {
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
    }

    /**
     * 设置滑动导航
     */
    private setupSwipeNavigation(): void {
        if (!this.enableSwipe) return;

        const mapContainer = document.querySelector('.map-container');
        if (!mapContainer) return;

        let touchStartX = 0;
        let touchStartY = 0;

        mapContainer.addEventListener('touchstart', (e: Event) => {
            touchStartX = (e as TouchEvent).touches[0].clientX;
            touchStartY = (e as TouchEvent).touches[0].clientY;
        }, { passive: true });

        mapContainer.addEventListener('touchend', (e: Event) => {
            const touchEndX = (e as TouchEvent).changedTouches[0].clientX;
            const touchEndY = (e as TouchEvent).changedTouches[0].clientY;

            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;

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

    /**
     * 处理向左滑动
     */
    private handleSwipeLeft(): void {
        const nextIndex = (this.currentNavIndex + 1) % this.navItems.length;
        this.selectNavItem(nextIndex);
        this.navItems[nextIndex].action();
        this.hapticFeedback();
    }

    /**
     * 处理向右滑动
     */
    private handleSwipeRight(): void {
        const prevIndex = (this.currentNavIndex - 1 + this.navItems.length) % this.navItems.length;
        this.selectNavItem(prevIndex);
        this.navItems[prevIndex].action();
        this.hapticFeedback();
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