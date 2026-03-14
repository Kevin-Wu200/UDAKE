/**
 * 操作确认对话框组件
 * 支持普通确认和危险操作二次确认
 */

interface ConfirmOptions {
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    danger?: boolean;
}

export class ConfirmDialog {
    /**
     * 显示确认对话框
     */
    static confirm({
        title,
        message,
        confirmText = '确认',
        cancelText = '取消',
        danger = false,
    }: ConfirmOptions): Promise<boolean> {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay confirm-dialog-overlay';
            overlay.setAttribute('role', 'alertdialog');
            overlay.setAttribute('aria-modal', 'true');
            overlay.setAttribute('aria-labelledby', 'confirm-dialog-title');
            overlay.setAttribute('aria-describedby', 'confirm-dialog-message');

            const dangerClass = danger ? 'btn-danger' : 'btn-primary';

            overlay.innerHTML = `
                <div class="modal-content confirm-dialog">
                    <h2 class="modal-title" id="confirm-dialog-title">${title}</h2>
                    <p class="confirm-dialog-message" id="confirm-dialog-message">${message}</p>
                    <div class="modal-actions">
                        <button class="btn btn-secondary" id="confirm-cancel">${cancelText}</button>
                        <button class="btn ${dangerClass}" id="confirm-ok">${confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            // 触发入场动画
            requestAnimationFrame(() => overlay.classList.add('modal-show'));

            // 焦点陷阱
            const confirmBtn = overlay.querySelector('#confirm-ok') as HTMLButtonElement;
            const cancelBtn = overlay.querySelector('#confirm-cancel') as HTMLButtonElement;
            confirmBtn.focus();

            const close = (result: boolean): void => {
                overlay.classList.remove('modal-show');
                setTimeout(() => {
                    overlay.remove();
                    resolve(result);
                }, 250);
            };

            cancelBtn.addEventListener('click', () => close(false));
            confirmBtn.addEventListener('click', () => close(true));
            overlay.addEventListener('click', (e: MouseEvent) => {
                if (e.target === overlay) close(false);
            });

            // 键盘支持
            overlay.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Escape') {
                    e.stopPropagation();
                    close(false);
                }
                // Tab 焦点循环
                if (e.key === 'Tab') {
                    const focusable = [cancelBtn, confirmBtn];
                    const first = focusable[0];
                    const last = focusable[focusable.length - 1];
                    if (e.shiftKey && document.activeElement === first) {
                        e.preventDefault();
                        last.focus();
                    } else if (!e.shiftKey && document.activeElement === last) {
                        e.preventDefault();
                        first.focus();
                    }
                }
            });
        });
    }

    /**
     * 危险操作确认（红色按钮）
     */
    static confirmDanger(options: Omit<ConfirmOptions, 'danger'>): Promise<boolean> {
        return ConfirmDialog.confirm({ ...options, danger: true });
    }
}
