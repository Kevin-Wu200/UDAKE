import { AuthService } from '../services/AuthService.js';
import { ExitHandler } from '../utils/ExitHandler.js';

interface LoginModalOptions {
    authService: AuthService;
    onLoginSuccess: () => void | Promise<void>;
}

export class LoginModal {
    private readonly authService: AuthService;
    private readonly onLoginSuccess: () => void | Promise<void>;
    private readonly overlay: HTMLDivElement;
    private readonly usernameInput: HTMLInputElement;
    private readonly passwordInput: HTMLInputElement;
    private readonly submitBtn: HTMLButtonElement;
    private readonly errorBox: HTMLDivElement;

    constructor(options: LoginModalOptions) {
        this.authService = options.authService;
        this.onLoginSuccess = options.onLoginSuccess;
        this.overlay = document.createElement('div');
        this.overlay.className = 'auth-modal-overlay';
        this.overlay.innerHTML = `
            <div class="auth-modal login-modal" role="dialog" aria-modal="true" aria-label="登录">
                <h2>账号登录</h2>
                <div class="auth-modal-field">
                    <label for="auth-username">用户名 / 邮箱</label>
                    <input id="auth-username" type="text" autocomplete="username" placeholder="请输入用户名或邮箱">
                </div>
                <div class="auth-modal-field">
                    <label for="auth-password">密码</label>
                    <input id="auth-password" type="password" autocomplete="current-password" placeholder="请输入密码">
                </div>
                <div class="auth-modal-error" aria-live="polite"></div>
                <div class="auth-modal-links">
                    <a href="javascript:void(0)">忘记密码</a>
                    <a href="javascript:void(0)">注册</a>
                </div>
                <div class="auth-modal-actions">
                    <button type="button" class="btn btn-secondary" id="auth-exit-btn">退出</button>
                    <button type="button" class="btn btn-primary" id="auth-login-btn">登录</button>
                </div>
            </div>
        `;

        this.usernameInput = this.overlay.querySelector('#auth-username') as HTMLInputElement;
        this.passwordInput = this.overlay.querySelector('#auth-password') as HTMLInputElement;
        this.submitBtn = this.overlay.querySelector('#auth-login-btn') as HTMLButtonElement;
        this.errorBox = this.overlay.querySelector('.auth-modal-error') as HTMLDivElement;
        const exitBtn = this.overlay.querySelector('#auth-exit-btn') as HTMLButtonElement;

        this.submitBtn.addEventListener('click', () => {
            void this.handleSubmit();
        });
        [this.usernameInput, this.passwordInput].forEach((input) => {
            input.addEventListener('keydown', (event) => {
                if (event.key === 'Enter') {
                    void this.handleSubmit();
                }
            });
        });
        exitBtn.addEventListener('click', () => {
            void ExitHandler.exitProgram();
        });
    }

    public show(): void {
        if (!this.overlay.isConnected) {
            document.body.appendChild(this.overlay);
        }
        this.clearError();
        this.usernameInput.focus();
    }

    public hide(): void {
        this.overlay.remove();
    }

    private async handleSubmit(): Promise<void> {
        const username = this.usernameInput.value.trim();
        const password = this.passwordInput.value;
        if (!username || !password) {
            this.setError('用户名和密码不能为空');
            return;
        }

        this.setLoading(true);
        this.clearError();
        try {
            await this.authService.login(username, password);
            this.hide();
            await this.onLoginSuccess();
        } catch (error) {
            const message = error instanceof Error ? error.message : '登录失败，请稍后重试';
            this.setError(message);
        } finally {
            this.setLoading(false);
        }
    }

    private setLoading(loading: boolean): void {
        this.submitBtn.disabled = loading;
        this.submitBtn.textContent = loading ? '登录中...' : '登录';
        this.overlay.classList.toggle('is-loading', loading);
    }

    private setError(message: string): void {
        this.errorBox.textContent = message;
        this.errorBox.style.display = 'block';
    }

    private clearError(): void {
        this.errorBox.textContent = '';
        this.errorBox.style.display = 'none';
    }
}
