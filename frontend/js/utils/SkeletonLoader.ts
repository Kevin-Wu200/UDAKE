/**
 * 骨架屏工具
 * 在内容加载时显示占位动画
 */

export type SkeletonType = 'text' | 'panel';

export class SkeletonLoader {
    static createTextSkeleton(lines: number = 3): string {
        return Array.from({ length: lines }, (_, i) =>
            `<div class="skeleton skeleton-text" style="width: ${80 - i * 10}%"></div>`
        ).join('');
    }

    static createPanelSkeleton(): string {
        return `
            <div style="padding: 20px;">
                <div class="skeleton skeleton-text" style="width: 40%; height: 18px; margin-bottom: 16px;"></div>
                <div class="skeleton skeleton-rect" style="margin-bottom: 12px;"></div>
                <div class="skeleton skeleton-text" style="width: 70%;"></div>
                <div class="skeleton skeleton-text" style="width: 50%;"></div>
            </div>
        `;
    }

    static show(container: HTMLElement, type: SkeletonType = 'text'): HTMLDivElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'skeleton-wrapper';
        wrapper.innerHTML = type === 'panel'
            ? this.createPanelSkeleton()
            : this.createTextSkeleton();
        container.appendChild(wrapper);
        return wrapper;
    }

    static hide(wrapper: HTMLDivElement | null): void {
        if (wrapper) {
            wrapper.style.opacity = '0';
            wrapper.style.transition = 'opacity 200ms ease';
            setTimeout(() => wrapper.remove(), 200);
        }
    }
}
