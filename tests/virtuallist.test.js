import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { VirtualList } from '../apps/frontend/js/components/VirtualList.ts';

describe('VirtualList', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        Object.defineProperty(container, 'clientHeight', {
            configurable: true,
            get: () => 320,
        });
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    it('只渲染可视区附近元素', () => {
        const items = Array.from({ length: 10000 }, (_, i) => ({ id: i, text: `item-${i}` }));

        const list = new VirtualList({
            container,
            items,
            itemHeight: 40,
            overscan: 4,
            renderItem: (item) => {
                const el = document.createElement('div');
                el.textContent = item.text;
                return el;
            },
        });

        const renderedCount = container.querySelectorAll('[data-virtual-key]').length;
        expect(renderedCount).toBeLessThan(80);

        list.destroy();
    });

    it('支持滚动到指定索引', () => {
        const items = Array.from({ length: 500 }, (_, i) => ({ id: i, text: `row-${i}` }));

        const list = new VirtualList({
            container,
            items,
            itemHeight: 50,
            renderItem: (item) => {
                const el = document.createElement('div');
                el.textContent = item.text;
                return el;
            },
        });

        list.scrollToIndex(120);
        expect(container.scrollTop).toBeGreaterThan(0);

        list.destroy();
    });
});
