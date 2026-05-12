import type { AuthService } from '../services/AuthService.js';

interface UserInfoDetailModalOptions {
    authService: AuthService;
    onLogout: () => void | Promise<void>;
}

export class UserInfoDetailModal {
    private readonly authService: AuthService;
    private readonly onLogout: () => void | Promise<void>;
    private readonly overlay: HTMLDivElement;

    constructor(options: UserInfoDetailModalOptions) {
        this.authService = options.authService;
        this.onLogout = options.onLogout;
        this.overlay = document.createElement('div');
        this.overlay.className = 'auth-modal-overlay';
        this.overlay.innerHTML = `
            <div class="auth-modal user-info-detail-modal" role="dialog" aria-modal="true" aria-label="用户详情">
                <h2>账户详情</h2>
                <div class="user-detail-content"></div>
                <div class="auth-modal-actions">
                    <button type="button" class="btn btn-secondary" id="user-info-close-btn">关闭</button>
                    <button type="button" class="btn btn-primary" id="user-info-logout-btn">退出登录</button>
                </div>
            </div>
        `;
        this.overlay.querySelector('#user-info-close-btn')?.addEventListener('click', () => this.hide());
        this.overlay.querySelector('#user-info-logout-btn')?.addEventListener('click', () => {
            void this.handleLogout();
        });
        this.overlay.addEventListener('click', (event) => {
            if (event.target === this.overlay) {
                this.hide();
            }
        });
    }

    public show(): void {
        this.render();
        if (!this.overlay.isConnected) {
            document.body.appendChild(this.overlay);
        }
    }

    public hide(): void {
        this.overlay.remove();
    }

    private render(): void {
        const user = this.authService.getStoredUserInfo();
        const key = this.authService.getStoredProductKeyInfo();
        const content = this.overlay.querySelector('.user-detail-content') as HTMLDivElement;
        content.innerHTML = `
            <div class="user-info-row"><span>用户ID</span><strong>${user?.id ?? '-'}</strong></div>
            <div class="user-info-row"><span>用户名</span><strong>${user?.username || '-'}</strong></div>
            <div class="user-info-row"><span>邮箱</span><strong>${user?.email || '-'}</strong></div>
            <div class="user-info-row"><span>角色</span><strong>${user?.role || '-'}</strong></div>
            <div class="user-info-row"><span>密钥</span><strong>${user?.product_key || key?.product_key || '-'}</strong></div>
            <div class="user-info-row"><span>类型</span><strong>${key?.key_type || '-'}</strong></div>
            <div class="user-info-row"><span>状态</span><strong>${user?.key_status || key?.status || '-'}</strong></div>
            <div class="user-info-row"><span>配额</span><strong>${key ? `${key.used_count} / ${key.total_quota}` : '-'}</strong></div>
            <div class="user-info-row"><span>到期时间</span><strong>${key?.expires_at || '-'}</strong></div>
        `;
    }

    private async handleLogout(): Promise<void> {
        await this.authService.logout();
        this.hide();
        await this.onLogout();
    }
}
