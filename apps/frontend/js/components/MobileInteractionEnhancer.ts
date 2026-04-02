interface MobileInteractionEnhancerOptions {
    container: HTMLElement;
    onRefresh?: () => Promise<void> | void;
    onLoadMore?: () => Promise<void> | void;
    onSearch?: (keyword: string) => void;
    searchPlaceholder?: string;
    refreshThreshold?: number;
    loadMoreOffset?: number;
    refreshCooldownMs?: number;
}

class MobileInteractionEnhancer {
    private readonly container: HTMLElement;
    private readonly onRefresh?: () => Promise<void> | void;
    private readonly onLoadMore?: () => Promise<void> | void;
    private readonly onSearch?: (keyword: string) => void;
    private readonly searchPlaceholder: string;
    private readonly refreshThreshold: number;
    private readonly loadMoreOffset: number;
    private readonly refreshCooldownMs: number;

    private searchWrapper: HTMLElement | null = null;
    private searchInput: HTMLInputElement | null = null;
    private pullIndicator: HTMLElement | null = null;
    private loadMoreIndicator: HTMLElement | null = null;

    private startY = 0;
    private pullDistance = 0;
    private isPulling = false;
    private isRefreshing = false;
    private isLoadingMore = false;
    private lastRefreshAt = 0;

    constructor(options: MobileInteractionEnhancerOptions) {
        this.container = options.container;
        this.onRefresh = options.onRefresh;
        this.onLoadMore = options.onLoadMore;
        this.onSearch = options.onSearch;
        this.searchPlaceholder = options.searchPlaceholder || '搜索';
        this.refreshThreshold = options.refreshThreshold ?? 72;
        this.loadMoreOffset = options.loadMoreOffset ?? 140;
        this.refreshCooldownMs = options.refreshCooldownMs ?? 1200;

        this.init();
    }

    private init(): void {
        if (!this.isMobileViewport()) {
            return;
        }

        this.container.classList.add('mobile-list-shell');
        this.createSearchBar();
        this.createPullIndicator();
        this.createLoadMoreIndicator();
        this.bindEvents();
    }

    private createSearchBar(): void {
        if (!this.onSearch) {
            return;
        }

        const parent = this.container.parentElement;
        if (!parent) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'mobile-search-bar';

        const input = document.createElement('input');
        input.className = 'mobile-search-input';
        input.type = 'search';
        input.placeholder = this.searchPlaceholder;
        input.setAttribute('aria-label', this.searchPlaceholder);

        wrapper.appendChild(input);
        parent.insertBefore(wrapper, this.container);

        this.searchWrapper = wrapper;
        this.searchInput = input;
    }

    private createPullIndicator(): void {
        const indicator = document.createElement('div');
        indicator.className = 'pull-refresh-indicator';
        indicator.textContent = '下拉刷新';
        this.container.insertBefore(indicator, this.container.firstChild);
        this.pullIndicator = indicator;
    }

    private createLoadMoreIndicator(): void {
        if (!this.onLoadMore) {
            return;
        }

        const indicator = document.createElement('div');
        indicator.className = 'infinite-loading-indicator';
        indicator.textContent = '上拉加载更多';
        this.container.appendChild(indicator);
        this.loadMoreIndicator = indicator;
    }

    private bindEvents(): void {
        this.container.addEventListener('touchstart', this.handleTouchStart, { passive: true });
        this.container.addEventListener('touchmove', this.handleTouchMove, { passive: false });
        this.container.addEventListener('touchend', this.handleTouchEnd, { passive: true });
        this.container.addEventListener('scroll', this.handleScroll, { passive: true });

        if (this.searchInput) {
            this.searchInput.addEventListener('input', this.handleSearchInput);
        }
    }

    private readonly handleSearchInput = (event: Event): void => {
        if (!this.onSearch) {
            return;
        }
        const keyword = (event.target as HTMLInputElement).value.trim();
        this.onSearch(keyword);
    };

    private readonly handleTouchStart = (event: TouchEvent): void => {
        if (event.touches.length !== 1 || this.container.scrollTop > 0 || this.isRefreshing) {
            this.isPulling = false;
            return;
        }

        this.startY = event.touches[0].clientY;
        this.pullDistance = 0;
        this.isPulling = true;
    };

    private readonly handleTouchMove = (event: TouchEvent): void => {
        if (!this.isPulling) {
            return;
        }

        const currentY = event.touches[0].clientY;
        const deltaY = Math.max(0, currentY - this.startY);
        this.pullDistance = Math.min(120, deltaY * 0.6);

        if (this.pullDistance <= 0) {
            return;
        }

        event.preventDefault();

        if (this.pullIndicator) {
            this.pullIndicator.classList.add('active');
            this.pullIndicator.style.transform = `translateY(${this.pullDistance - 56}px)`;
            this.pullIndicator.textContent = this.pullDistance >= this.refreshThreshold ? '松开立即刷新' : '下拉刷新';
        }
    };

    private readonly handleTouchEnd = (): void => {
        if (!this.isPulling) {
            return;
        }

        this.isPulling = false;

        if (this.pullIndicator) {
            this.pullIndicator.style.transform = 'translateY(-56px)';
            this.pullIndicator.classList.remove('active');
        }

        if (this.pullDistance >= this.refreshThreshold) {
            void this.triggerRefresh();
        }

        this.pullDistance = 0;
    };

    private readonly handleScroll = (): void => {
        if (!this.onLoadMore || this.isLoadingMore) {
            return;
        }

        const distanceToBottom = this.container.scrollHeight - (this.container.scrollTop + this.container.clientHeight);
        if (distanceToBottom <= this.loadMoreOffset) {
            void this.triggerLoadMore();
        }
    };

    private async triggerRefresh(): Promise<void> {
        if (!this.onRefresh || this.isRefreshing) {
            return;
        }

        const now = Date.now();
        if ((now - this.lastRefreshAt) < this.refreshCooldownMs) {
            return;
        }

        this.isRefreshing = true;
        this.lastRefreshAt = now;

        if (this.pullIndicator) {
            this.pullIndicator.classList.add('active');
            this.pullIndicator.textContent = '正在刷新...';
            this.pullIndicator.style.transform = 'translateY(0)';
        }

        try {
            await this.onRefresh();
            if (this.pullIndicator) {
                this.pullIndicator.textContent = '刷新完成';
            }
        } catch {
            if (this.pullIndicator) {
                this.pullIndicator.textContent = '刷新失败';
            }
        } finally {
            window.setTimeout(() => {
                if (!this.pullIndicator) {
                    return;
                }
                this.pullIndicator.classList.remove('active');
                this.pullIndicator.textContent = '下拉刷新';
                this.pullIndicator.style.transform = 'translateY(-56px)';
            }, 520);
            this.isRefreshing = false;
        }
    }

    private async triggerLoadMore(): Promise<void> {
        if (!this.onLoadMore || this.isLoadingMore) {
            return;
        }

        this.isLoadingMore = true;
        if (this.loadMoreIndicator) {
            this.loadMoreIndicator.classList.add('active');
            this.loadMoreIndicator.textContent = '正在加载更多...';
        }

        try {
            await this.onLoadMore();
            if (this.loadMoreIndicator) {
                this.loadMoreIndicator.textContent = '继续上拉加载';
            }
        } catch {
            if (this.loadMoreIndicator) {
                this.loadMoreIndicator.textContent = '加载失败，请重试';
            }
        } finally {
            window.setTimeout(() => {
                if (this.loadMoreIndicator) {
                    this.loadMoreIndicator.classList.remove('active');
                    this.loadMoreIndicator.textContent = '上拉加载更多';
                }
            }, 380);
            this.isLoadingMore = false;
        }
    }

    private isMobileViewport(): boolean {
        return typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches;
    }

    public destroy(): void {
        this.container.removeEventListener('touchstart', this.handleTouchStart);
        this.container.removeEventListener('touchmove', this.handleTouchMove);
        this.container.removeEventListener('touchend', this.handleTouchEnd);
        this.container.removeEventListener('scroll', this.handleScroll);

        if (this.searchInput) {
            this.searchInput.removeEventListener('input', this.handleSearchInput);
        }

        this.searchWrapper?.remove();
        this.pullIndicator?.remove();
        this.loadMoreIndicator?.remove();
        this.container.classList.remove('mobile-list-shell');

        this.searchWrapper = null;
        this.searchInput = null;
        this.pullIndicator = null;
        this.loadMoreIndicator = null;
    }
}

export default MobileInteractionEnhancer;
