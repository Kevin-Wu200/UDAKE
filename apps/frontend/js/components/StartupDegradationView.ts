/**
 * 启动降级界面组件
 * - fatal: 全屏错误页（重试 / 退出）
 * - functional: 顶部横幅（限制功能）
 * - experience: 轻量提示（静默处理）
 */

export type StartupDegradationLevel = 'fatal' | 'functional' | 'experience';

export interface DegradationDisplayOptions {
    title?: string;
    message: string;
    onRetry?: () => void;
    onExit?: () => void;
}

export class StartupDegradationView {
    private fatalElement: HTMLDivElement | null = null;
    private functionalBanner: HTMLDivElement | null = null;
    private experienceToast: HTMLDivElement | null = null;

    public show(level: StartupDegradationLevel, options: DegradationDisplayOptions): void {
        if (level === 'fatal') {
            this.showFatal(options);
            return;
        }

        if (level === 'functional') {
            this.showFunctional(options.message);
            return;
        }

        this.showExperience(options.message);
    }

    public clear(): void {
        this.fatalElement?.remove();
        this.fatalElement = null;

        this.functionalBanner?.remove();
        this.functionalBanner = null;

        this.experienceToast?.remove();
        this.experienceToast = null;
    }

    private showFatal(options: DegradationDisplayOptions): void {
        this.clear();
        const container = document.createElement('div');
        container.className = 'startup-degrade-fatal';
        container.innerHTML = `
            <div class="startup-degrade-fatal-card">
                <h1>${options.title ?? '启动失败'}</h1>
                <p>${options.message}</p>
                <div class="startup-degrade-actions">
                    <button class="startup-degrade-retry">重试</button>
                    <button class="startup-degrade-exit">退出</button>
                </div>
            </div>
        `;

        const retryButton = container.querySelector('.startup-degrade-retry') as HTMLButtonElement | null;
        const exitButton = container.querySelector('.startup-degrade-exit') as HTMLButtonElement | null;

        retryButton?.addEventListener('click', () => {
            if (options.onRetry) {
                options.onRetry();
            } else {
                window.location.reload();
            }
        });

        exitButton?.addEventListener('click', () => {
            if (options.onExit) {
                options.onExit();
                return;
            }
            this.tryExitApp();
        });

        document.body.appendChild(container);
        this.fatalElement = container;
    }

    private showFunctional(message: string): void {
        this.functionalBanner?.remove();
        const banner = document.createElement('div');
        banner.className = 'startup-degrade-banner';
        banner.textContent = `部分功能暂不可用：${message}`;
        document.body.appendChild(banner);
        this.functionalBanner = banner;
    }

    private showExperience(message: string): void {
        this.experienceToast?.remove();
        const toast = document.createElement('div');
        toast.className = 'startup-degrade-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        this.experienceToast = toast;
        window.setTimeout(() => {
            toast.remove();
            if (this.experienceToast === toast) {
                this.experienceToast = null;
            }
        }, 2600);
    }

    private tryExitApp(): void {
        window.close();
    }
}
