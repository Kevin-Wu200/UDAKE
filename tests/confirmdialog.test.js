import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ConfirmDialog } from '../apps/frontend/js/components/ConfirmDialog.js';

describe('ConfirmDialog', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
    });

    it('应该创建对话框 DOM', async () => {
        // 不 await，先检查 DOM
        const promise = ConfirmDialog.confirm({
            title: '测试标题',
            message: '测试消息'
        });

        // 等待 requestAnimationFrame
        await new Promise(r => setTimeout(r, 50));

        const overlay = document.querySelector('.confirm-dialog-overlay');
        expect(overlay).not.toBeNull();
        expect(overlay.querySelector('#confirm-dialog-title').textContent).toBe('测试标题');
        expect(overlay.querySelector('#confirm-dialog-message').textContent).toBe('测试消息');

        // 点击取消关闭
        overlay.querySelector('#confirm-cancel').click();
        const result = await promise;
        expect(result).toBe(false);
    });

    it('点击确认应该返回 true', async () => {
        const promise = ConfirmDialog.confirm({
            title: '确认',
            message: '确定吗？'
        });

        await new Promise(r => setTimeout(r, 50));
        document.querySelector('#confirm-ok').click();
        const result = await promise;
        expect(result).toBe(true);
    });

    it('点击遮罩应该返回 false', async () => {
        const promise = ConfirmDialog.confirm({
            title: '确认',
            message: '确定吗？'
        });

        await new Promise(r => setTimeout(r, 50));
        const overlay = document.querySelector('.confirm-dialog-overlay');
        overlay.click();
        const result = await promise;
        expect(result).toBe(false);
    });

    it('danger 模式应该使用红色按钮', async () => {
        const promise = ConfirmDialog.confirm({
            title: '删除',
            message: '确定删除？',
            danger: true
        });

        await new Promise(r => setTimeout(r, 50));
        const confirmBtn = document.querySelector('#confirm-ok');
        expect(confirmBtn.classList.contains('btn-danger')).toBe(true);

        confirmBtn.click();
        await promise;
    });

    it('confirmDanger 应该等同于 danger: true', async () => {
        const promise = ConfirmDialog.confirmDanger({
            title: '删除',
            message: '确定？'
        });

        await new Promise(r => setTimeout(r, 50));
        const confirmBtn = document.querySelector('#confirm-ok');
        expect(confirmBtn.classList.contains('btn-danger')).toBe(true);

        confirmBtn.click();
        await promise;
    });

    it('自定义按钮文本应该生效', async () => {
        const promise = ConfirmDialog.confirm({
            title: '确认',
            message: '确定？',
            confirmText: '是的',
            cancelText: '不了'
        });

        await new Promise(r => setTimeout(r, 50));
        expect(document.querySelector('#confirm-ok').textContent).toBe('是的');
        expect(document.querySelector('#confirm-cancel').textContent).toBe('不了');

        document.querySelector('#confirm-cancel').click();
        await promise;
    });

    it('应该设置正确的 ARIA 属性', async () => {
        const promise = ConfirmDialog.confirm({
            title: '确认',
            message: '确定？'
        });

        await new Promise(r => setTimeout(r, 50));
        const overlay = document.querySelector('.confirm-dialog-overlay');
        expect(overlay.getAttribute('role')).toBe('alertdialog');
        expect(overlay.getAttribute('aria-modal')).toBe('true');

        document.querySelector('#confirm-cancel').click();
        await promise;
    });
});
