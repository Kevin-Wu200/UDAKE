import { ProductKeyService } from '../services/ProductKeyService.js';
import { ExitHandler } from '../utils/ExitHandler.js';

interface KeyActivationModalOptions {
    productKeyService: ProductKeyService;
    onActivated: () => void | Promise<void>;
}

export class KeyActivationModal {
    private readonly productKeyService: ProductKeyService;
    private readonly onActivated: () => void | Promise<void>;
    private readonly overlay: HTMLDivElement;
    private readonly keyInput: HTMLInputElement;
    private readonly activateBtn: HTMLButtonElement;
    private readonly attemptsText: HTMLDivElement;
    private readonly errorBox: HTMLDivElement;
    private lockTimer: number | null;

    constructor(options: KeyActivationModalOptions) {
        this.productKeyService = options.productKeyService;
        this.onActivated = options.onActivated;
        this.lockTimer = null;

        this.overlay = document.createElement('div');
        this.overlay.className = 'auth-modal-overlay';
        this.overlay.innerHTML = `
            <div class="auth-modal key-activation-modal" role="dialog" aria-modal="true" aria-label="密钥激活">
                <h2>密钥激活</h2>
                <p class="auth-modal-tip">请输入 15 位密钥（示例：ABC-1234-5678-9XYZ）</p>
                <div class="auth-modal-field">
                    <label for="product-key-input">产品密钥</label>
                    <input id="product-key-input" type="text" autocomplete="off" placeholder="请输入密钥">
                </div>
                <div class="auth-modal-attempts" aria-live="polite"></div>
                <div class="auth-modal-error" aria-live="polite"></div>
                <div class="auth-modal-links">
                    <a href="javascript:void(0)">没有密钥？请联系管理员</a>
                </div>
                <div class="auth-modal-actions">
                    <button type="button" class="btn btn-secondary" id="key-exit-btn">退出程序</button>
                    <button type="button" class="btn btn-primary" id="key-activate-btn">激活</button>
                </div>
            </div>
        `;

        this.keyInput = this.overlay.querySelector('#product-key-input') as HTMLInputElement;
        this.activateBtn = this.overlay.querySelector('#key-activate-btn') as HTMLButtonElement;
        this.attemptsText = this.overlay.querySelector('.auth-modal-attempts') as HTMLDivElement;
        this.errorBox = this.overlay.querySelector('.auth-modal-error') as HTMLDivElement;

        this.activateBtn.addEventListener('click', () => {
            void this.handleActivate();
        });
        this.keyInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                void this.handleActivate();
            }
        });
        this.overlay.querySelector('#key-exit-btn')?.addEventListener('click', () => {
            void ExitHandler.exitProgram();
        });
    }

    public async show(): Promise<void> {
        if (!this.overlay.isConnected) {
            document.body.appendChild(this.overlay);
        }
        await this.refreshStatus();
        this.keyInput.focus();
    }

    public hide(): void {
        if (this.lockTimer) {
            window.clearInterval(this.lockTimer);
            this.lockTimer = null;
        }
        this.overlay.remove();
    }

    private async refreshStatus(): Promise<void> {
        try {
            const status = await this.productKeyService.getKeyStatus();
            if (status.key_info && status.key_info.status === 'active') {
                this.hide();
                await this.onActivated();
                return;
            }
            if (status.lock_remaining_seconds > 0) {
                this.startLockCountdown(status.lock_remaining_seconds);
            } else {
                this.renderAttempts(status.remaining_attempts);
            }
        } catch {
            const local = this.productKeyService.checkActivationAttempts();
            if (local.isLocked) {
                this.startLockCountdown(local.lockRemainingSeconds);
            } else {
                this.renderAttempts(local.remainingAttempts);
            }
        }
    }

    private async handleActivate(): Promise<void> {
        const key = this.keyInput.value.trim().toUpperCase();
        if (!/^[A-Z0-9]{3}(?:-[A-Z0-9]{4}){3}$/.test(key)) {
            this.setError('密钥格式错误，请输入 15 位密钥（XXX-XXXX-XXXX-XXXX）');
            return;
        }
        const localState = this.productKeyService.checkActivationAttempts();
        if (localState.isLocked) {
            this.startLockCountdown(localState.lockRemainingSeconds);
            return;
        }

        this.setLoading(true);
        this.clearError();
        try {
            await this.productKeyService.activateKey(key);
            this.hide();
            await this.onActivated();
        } catch (error) {
            this.productKeyService.increaseLocalFailedAttempts();
            const updated = this.productKeyService.checkActivationAttempts();
            if (updated.isLocked) {
                this.startLockCountdown(updated.lockRemainingSeconds);
            } else {
                this.renderAttempts(updated.remainingAttempts);
            }
            const message = error instanceof Error ? error.message : '密钥激活失败';
            this.setError(message);
        } finally {
            this.setLoading(false);
        }
    }

    private startLockCountdown(seconds: number): void {
        if (this.lockTimer) {
            window.clearInterval(this.lockTimer);
            this.lockTimer = null;
        }
        let remain = Math.max(0, seconds);
        const render = () => {
            this.activateBtn.disabled = true;
            const mm = String(Math.floor(remain / 60)).padStart(2, '0');
            const ss = String(remain % 60).padStart(2, '0');
            this.attemptsText.textContent = `已锁定，请在 ${mm}:${ss} 后重试`;
            this.attemptsText.classList.add('is-locked');
        };
        render();
        this.lockTimer = window.setInterval(() => {
            remain -= 1;
            if (remain <= 0) {
                if (this.lockTimer) {
                    window.clearInterval(this.lockTimer);
                    this.lockTimer = null;
                }
                this.activateBtn.disabled = false;
                this.attemptsText.classList.remove('is-locked');
                this.renderAttempts(5);
                return;
            }
            render();
        }, 1000);
    }

    private renderAttempts(remaining: number): void {
        this.attemptsText.classList.remove('is-locked');
        this.attemptsText.textContent = `剩余 ${Math.max(0, remaining)} 次尝试`;
    }

    private setLoading(loading: boolean): void {
        this.activateBtn.disabled = loading;
        this.activateBtn.textContent = loading ? '激活中...' : '激活';
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
