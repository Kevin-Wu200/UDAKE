import type { AuthService } from '../services/AuthService.js';
import type { AuthUserInfo, ProductKeyInfo } from '../services/AuthService.js';

interface UserInfoDisplayOptions {
    authService: AuthService;
    onShowDetail: () => void;
}

export class UserInfoDisplay {
    private readonly authService: AuthService;
    private readonly onShowDetail: () => void;
    private readonly panel: HTMLDivElement;
    private refreshTimer: number | null;

    constructor(options: UserInfoDisplayOptions) {
        this.authService = options.authService;
        this.onShowDetail = options.onShowDetail;
        this.refreshTimer = null;
        this.panel = document.createElement('div');
        this.panel.className = 'user-info-display';
        this.panel.innerHTML = `
            <div class="user-info-summary"></div>
            <button type="button" class="btn btn-secondary user-info-detail-btn">查看详情</button>
        `;
        this.panel.querySelector('.user-info-detail-btn')?.addEventListener('click', () => this.onShowDetail());
    }

    public mount(container: HTMLElement): void {
        if (!this.panel.isConnected) {
            container.appendChild(this.panel);
        }
        this.render();
        this.startRefresh();
    }

    public unmount(): void {
        this.stopRefresh();
        this.panel.remove();
    }

    public toggle(container: HTMLElement): void {
        if (this.panel.isConnected) {
            this.unmount();
            return;
        }
        this.mount(container);
    }

    public render(): void {
        const user = this.authService.getStoredUserInfo();
        const key = this.authService.getStoredProductKeyInfo();
        const summary = this.panel.querySelector('.user-info-summary') as HTMLDivElement;
        summary.innerHTML = this.renderSummary(user, key);
    }

    private renderSummary(user: AuthUserInfo | null, key: ProductKeyInfo | null): string {
        if (!user) {
            return '<div class="user-info-empty">未登录</div>';
        }

        // 优先从 AuthUserInfo 读取密钥状态，回退到 ProductKeyInfo
        const keyStatus = user.key_status || key?.status || 'unused';
        const keyType = key?.key_type || '未激活';
        const quotaText = key ? `${key.used_count} / ${key.total_quota}` : '- / -';
        const expires = key?.expires_at || '未设置';
        return `
            <div class="user-info-row"><span>用户</span><strong>${user.username || user.email}</strong></div>
            <div class="user-info-row"><span>密钥类型</span><strong>${keyType}</strong></div>
            <div class="user-info-row"><span>密钥状态</span><strong class="key-status ${keyStatus === 'active' ? 'active' : 'expired'}">${keyStatus}</strong></div>
            <div class="user-info-row"><span>配额</span><strong>${quotaText}</strong></div>
            <div class="user-info-row"><span>到期时间</span><strong>${expires}</strong></div>
            <div class="user-info-progress">
                <div class="bar" style="width:${this.progressPercent(key)}%"></div>
            </div>
        `;
    }

    private progressPercent(key: ProductKeyInfo | null): number {
        if (!key || key.total_quota <= 0) {
            return 0;
        }
        return Math.min(100, Math.max(0, Math.round((key.used_count / key.total_quota) * 100)));
    }

    private startRefresh(): void {
        this.stopRefresh();
        this.refreshTimer = window.setInterval(() => {
            this.render();
        }, 30_000);
    }

    private stopRefresh(): void {
        if (this.refreshTimer) {
            window.clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
}
