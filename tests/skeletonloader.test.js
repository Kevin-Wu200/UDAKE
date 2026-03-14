import { describe, it, expect, beforeEach } from 'vitest';
import { SkeletonLoader } from '../frontend/js/utils/SkeletonLoader.js';

describe('SkeletonLoader', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    describe('createTextSkeleton', () => {
        it('应该创建指定行数的骨架屏', () => {
            const html = SkeletonLoader.createTextSkeleton(3);
            const div = document.createElement('div');
            div.innerHTML = html;
            expect(div.querySelectorAll('.skeleton-text').length).toBe(3);
        });

        it('默认应该创建 3 行', () => {
            const html = SkeletonLoader.createTextSkeleton();
            const div = document.createElement('div');
            div.innerHTML = html;
            expect(div.querySelectorAll('.skeleton-text').length).toBe(3);
        });

        it('每行宽度应该递减', () => {
            const html = SkeletonLoader.createTextSkeleton(3);
            const div = document.createElement('div');
            div.innerHTML = html;
            const lines = div.querySelectorAll('.skeleton-text');
            expect(lines[0].style.width).toBe('80%');
            expect(lines[1].style.width).toBe('70%');
            expect(lines[2].style.width).toBe('60%');
        });
    });

    describe('createPanelSkeleton', () => {
        it('应该创建面板骨架屏', () => {
            const html = SkeletonLoader.createPanelSkeleton();
            const div = document.createElement('div');
            div.innerHTML = html;
            expect(div.querySelectorAll('.skeleton').length).toBeGreaterThan(0);
        });
    });

    describe('show', () => {
        it('应该在容器中添加骨架屏', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);

            const wrapper = SkeletonLoader.show(container, 'text');
            expect(wrapper.classList.contains('skeleton-wrapper')).toBe(true);
            expect(container.contains(wrapper)).toBe(true);
        });

        it('panel 类型应该创建面板骨架屏', () => {
            const container = document.createElement('div');
            document.body.appendChild(container);

            const wrapper = SkeletonLoader.show(container, 'panel');
            expect(wrapper.querySelector('.skeleton-rect')).not.toBeNull();
        });
    });

    describe('hide', () => {
        it('应该移除骨架屏', async () => {
            const container = document.createElement('div');
            document.body.appendChild(container);

            const wrapper = SkeletonLoader.show(container);
            SkeletonLoader.hide(wrapper);

            expect(wrapper.style.opacity).toBe('0');
            // 等待 setTimeout 移除
            await new Promise(r => setTimeout(r, 250));
            expect(container.contains(wrapper)).toBe(false);
        });

        it('传入 null 不应报错', () => {
            expect(() => SkeletonLoader.hide(null)).not.toThrow();
        });
    });
});
