export interface VirtualListOptions<T> {
    container: HTMLElement;
    items: T[];
    overscan?: number;
    itemHeight?: number;
    estimateHeight?: (item: T, index: number) => number;
    keyExtractor?: (item: T, index: number) => string;
    renderItem: (item: T, index: number) => HTMLElement;
    onEndReached?: () => void;
    endReachedThreshold?: number;
    initialScrollTop?: number;
}

interface RenderRange {
    start: number;
    end: number;
}

/**
 * 轻量虚拟滚动列表，支持移动端大数据量渲染和可变高度。
 */
export class VirtualList<T> {
    private container: HTMLElement;
    private content: HTMLElement;
    private items: T[];
    private overscan: number;
    private fallbackHeight: number;
    private estimateHeight?: (item: T, index: number) => number;
    private keyExtractor: (item: T, index: number) => string;
    private renderItem: (item: T, index: number) => HTMLElement;
    private onEndReached?: () => void;
    private endReachedThreshold: number;

    private elementCache: Map<string, HTMLElement> = new Map();
    private measuredHeights: number[] = [];
    private prefixHeights: number[] = [];
    private totalHeight: number = 0;
    private rafToken: number | null = null;
    private currentRange: RenderRange = { start: -1, end: -1 };

    constructor(options: VirtualListOptions<T>) {
        this.container = options.container;
        this.items = options.items;
        this.overscan = options.overscan ?? 6;
        this.fallbackHeight = options.itemHeight ?? 56;
        this.estimateHeight = options.estimateHeight;
        this.keyExtractor = options.keyExtractor || ((_item, index) => `item_${index}`);
        this.renderItem = options.renderItem;
        this.onEndReached = options.onEndReached;
        this.endReachedThreshold = options.endReachedThreshold ?? 600;

        this.content = document.createElement('div');
        this.content.className = 'virtual-list-content';
        this.content.style.position = 'relative';
        this.content.style.width = '100%';

        this.container.innerHTML = '';
        this.container.style.overflowY = this.container.style.overflowY || 'auto';
        this.container.style.webkitOverflowScrolling = 'touch';
        this.container.appendChild(this.content);

        this.initializeHeights();
        this.bindEvents();

        if (typeof options.initialScrollTop === 'number') {
            this.container.scrollTop = Math.max(0, options.initialScrollTop);
        }

        this.renderVisible();
    }

    public updateItems(items: T[]): void {
        this.items = items;
        this.elementCache.clear();
        this.initializeHeights();
        this.renderVisible();
    }

    public scrollToIndex(index: number): void {
        if (index < 0 || index >= this.items.length) {
            return;
        }
        this.container.scrollTop = this.prefixHeights[index] || 0;
        this.renderVisible();
    }

    public getScrollTop(): number {
        return this.container.scrollTop;
    }

    public destroy(): void {
        this.unbindEvents();
        this.content.remove();
        this.elementCache.clear();
        if (this.rafToken !== null) {
            cancelAnimationFrame(this.rafToken);
            this.rafToken = null;
        }
    }

    private initializeHeights(): void {
        this.measuredHeights = this.items.map((item, index) => this.getEstimatedHeight(item, index));
        this.rebuildPrefixHeights();
    }

    private rebuildPrefixHeights(): void {
        this.prefixHeights = new Array(this.items.length);
        let total = 0;
        for (let i = 0; i < this.items.length; i += 1) {
            this.prefixHeights[i] = total;
            total += this.measuredHeights[i] || this.fallbackHeight;
        }
        this.totalHeight = total;
        this.content.style.height = `${this.totalHeight}px`;
    }

    private getEstimatedHeight(item: T, index: number): number {
        if (this.estimateHeight) {
            const estimated = this.estimateHeight(item, index);
            if (Number.isFinite(estimated) && estimated > 0) {
                return estimated;
            }
        }
        return this.fallbackHeight;
    }

    private bindEvents(): void {
        this.container.addEventListener('scroll', this.handleScroll, { passive: true });
        this.container.addEventListener('touchmove', this.handleScroll, { passive: true });
    }

    private unbindEvents(): void {
        this.container.removeEventListener('scroll', this.handleScroll);
        this.container.removeEventListener('touchmove', this.handleScroll);
    }

    private handleScroll = (): void => {
        if (this.rafToken !== null) {
            return;
        }
        this.rafToken = requestAnimationFrame(() => {
            this.rafToken = null;
            this.renderVisible();
            this.checkEndReached();
        });
    };

    private checkEndReached(): void {
        if (!this.onEndReached) {
            return;
        }
        const distanceToBottom = this.totalHeight - (this.container.scrollTop + this.container.clientHeight);
        if (distanceToBottom <= this.endReachedThreshold) {
            this.onEndReached();
        }
    }

    private findStartIndex(scrollTop: number): number {
        let low = 0;
        let high = this.prefixHeights.length - 1;
        let answer = 0;

        while (low <= high) {
            const mid = Math.floor((low + high) / 2);
            if ((this.prefixHeights[mid] || 0) <= scrollTop) {
                answer = mid;
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }

        return answer;
    }

    private buildRange(scrollTop: number, viewportHeight: number): RenderRange {
        if (this.items.length === 0) {
            return { start: 0, end: -1 };
        }

        const startIndex = this.findStartIndex(scrollTop);
        let endIndex = startIndex;
        const viewportBottom = scrollTop + viewportHeight;

        while (endIndex < this.items.length - 1 && (this.prefixHeights[endIndex] + this.measuredHeights[endIndex]) < viewportBottom) {
            endIndex += 1;
        }

        return {
            start: Math.max(0, startIndex - this.overscan),
            end: Math.min(this.items.length - 1, endIndex + this.overscan),
        };
    }

    private renderVisible(): void {
        const range = this.buildRange(this.container.scrollTop, this.container.clientHeight || 0);
        if (range.start === this.currentRange.start && range.end === this.currentRange.end) {
            return;
        }
        this.currentRange = range;

        this.content.innerHTML = '';

        for (let index = range.start; index <= range.end; index += 1) {
            const item = this.items[index];
            if (typeof item === 'undefined') {
                continue;
            }

            const key = this.keyExtractor(item, index);
            const element = this.renderItem(item, index);
            element.dataset.virtualKey = key;
            element.style.position = 'absolute';
            element.style.top = '0';
            element.style.left = '0';
            element.style.width = '100%';
            element.style.transform = `translateY(${this.prefixHeights[index]}px)`;

            this.content.appendChild(element);
            this.elementCache.set(key, element);

            const measured = element.offsetHeight;
            if (Number.isFinite(measured) && measured > 0 && measured !== this.measuredHeights[index]) {
                this.measuredHeights[index] = measured;
            }
        }

        this.rebuildPrefixHeights();
    }
}

export default VirtualList;
