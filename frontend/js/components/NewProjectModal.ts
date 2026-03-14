/**
 * 新建项目弹窗组件
 * 引导用户选择采样模式和坐标获取方式
 */
import { Project } from '../models/Project.js';
import { FreeSampling } from '../sampling/FreeSampling.js';
import { RegionSampling } from '../sampling/RegionSampling.js';
import { ErrorHandler } from '../utils/ErrorHandler.js';
import { KeyboardManager } from '../utils/KeyboardManager.js';
import type { SamplingMode, CoordinateMode } from '../../types/core';

interface ProjectConfig {
    sampling_mode: 'free' | 'region' | null;
    coordinate_mode: 'manual' | 'device' | null;
}

export class NewProjectModal {
    private onProjectCreated: ((project: any, config: ProjectConfig) => void) | null;
    private view: any;
    private overlay: HTMLDivElement | null;
    private currentStep: number;
    private _releaseFocusTrap: (() => void) | null;
    private config: ProjectConfig;

    constructor(onProjectCreated: ((project: any, config: ProjectConfig) => void) | null, view: any) {
        this.onProjectCreated = onProjectCreated;
        this.view = view;
        this.overlay = null;
        this.currentStep = 1;
        this._releaseFocusTrap = null;
        this.config = {
            sampling_mode: null,
            coordinate_mode: null
        };
    }

    show(): void {
        this.createOverlay();
        this.renderStep1();
        document.body.appendChild(this.overlay!);
        requestAnimationFrame(() => {
            this.overlay!.classList.add('modal-show');
        });
    }

    private createOverlay(): void {
        this.overlay = document.createElement('div') as HTMLDivElement;
        this.overlay.className = 'modal-overlay';
        this.overlay.setAttribute('role', 'dialog');
        this.overlay.setAttribute('aria-modal', 'true');
        this.overlay.setAttribute('aria-label', '新建项目');
        this.overlay.addEventListener('click', (e: MouseEvent) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
        this.overlay.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                this.close();
            }
        });
    }

    private renderStep1(): void {
        const content = document.createElement('div') as HTMLDivElement;
        content.className = 'modal-content';

        content.innerHTML = `
            <h2 class="modal-title">新建项目 - 选择采样模式</h2>
            <div class="modal-section">
                <div class="sampling-mode-options" role="group" aria-label="采样模式选项">
                    <div class="option-card" data-mode="free" tabindex="0" role="button" aria-label="自由采样：可在任意位置添加采样点，不受区域限制">
                        <div class="option-icon" aria-hidden="true">🌍</div>
                        <h3 class="option-title">自由采样</h3>
                        <p class="option-description">可在任意位置添加采样点，不受区域限制</p>
                    </div>
                    <div class="option-card" data-mode="region" tabindex="0" role="button" aria-label="区域采样：仅允许在指定区域内添加采样点">
                        <div class="option-icon" aria-hidden="true">📍</div>
                        <h3 class="option-title">区域采样</h3>
                        <p class="option-description">仅允许在指定区域内添加采样点</p>
                    </div>
                </div>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="cancel-btn">取消</button>
            </div>
        `;

        this.overlay!.innerHTML = '';
        this.overlay!.appendChild(content);
        this.bindStep1Events(content);
        if (this._releaseFocusTrap) this._releaseFocusTrap();
        this._releaseFocusTrap = KeyboardManager.trapFocus(this.overlay!);
    }

    private bindStep1Events(content: HTMLDivElement): void {
        const options = content.querySelectorAll('.option-card');
        const cancelBtn = content.querySelector('#cancel-btn') as HTMLButtonElement;

        options.forEach((option: Element) => {
            const selectOption = () => {
                const mode = (option as HTMLElement).dataset.mode!;
                this.config.sampling_mode = mode as 'free' | 'region';
                this.renderStep2();
            };

            option.addEventListener('click', selectOption);
            option.addEventListener('keydown', (e: Event) => {
                const key = (e as KeyboardEvent).key;
                if (key === 'Enter' || key === ' ') {
                    e.preventDefault();
                    selectOption();
                }
            });

            option.addEventListener('mouseenter', () => {
                (option as HTMLElement).style.transform = 'translateY(-4px)';
                (option as HTMLElement).style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.12)';
            });

            option.addEventListener('mouseleave', () => {
                (option as HTMLElement).style.transform = 'translateY(0)';
                (option as HTMLElement).style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
            });
        });

        cancelBtn.addEventListener('click', () => this.close());
    }

    private renderStep2(): void {
        const content = document.createElement('div') as HTMLDivElement;
        content.className = 'modal-content';

        content.innerHTML = `
            <h2 class="modal-title">新建项目 - 选择坐标获取方式</h2>
            <div class="modal-section">
                <div class="sampling-mode-options" role="group" aria-label="坐标获取方式选项">
                    <div class="option-card" data-mode="manual" tabindex="0" role="button" aria-label="手动输入：手动输入经纬度坐标">
                        <div class="option-icon" aria-hidden="true">⌨️</div>
                        <h3 class="option-title">手动输入</h3>
                        <p class="option-description">手动输入经纬度坐标</p>
                    </div>
                    <div class="option-card" data-mode="device" tabindex="0" role="button" aria-label="自动获取：使用设备自动获取当前位置">
                        <div class="option-icon" aria-hidden="true">📱</div>
                        <h3 class="option-title">自动获取</h3>
                        <p class="option-description">使用设备自动获取当前位置（WGS-84）</p>
                    </div>
                </div>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="back-btn">返回</button>
                <button class="btn btn-secondary" id="cancel-btn">取消</button>
            </div>
        `;

        this.overlay!.innerHTML = '';
        this.overlay!.appendChild(content);
        this.bindStep2Events(content);
        if (this._releaseFocusTrap) this._releaseFocusTrap();
        this._releaseFocusTrap = KeyboardManager.trapFocus(this.overlay!);
    }

    private bindStep2Events(content: HTMLDivElement): void {
        const options = content.querySelectorAll('.option-card');
        const backBtn = content.querySelector('#back-btn') as HTMLButtonElement;
        const cancelBtn = content.querySelector('#cancel-btn') as HTMLButtonElement;

        options.forEach((option: Element) => {
            const selectOption = () => {
                const mode = (option as HTMLElement).dataset.mode!;
                this.config.coordinate_mode = mode as 'manual' | 'device';
                this.createProject();
            };

            option.addEventListener('click', selectOption);
            option.addEventListener('keydown', (e: Event) => {
                const key = (e as KeyboardEvent).key;
                if (key === 'Enter' || key === ' ') {
                    e.preventDefault();
                    selectOption();
                }
            });

            option.addEventListener('mouseenter', () => {
                (option as HTMLElement).style.transform = 'translateY(-4px)';
                (option as HTMLElement).style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.12)';
            });

            option.addEventListener('mouseleave', () => {
                (option as HTMLElement).style.transform = 'translateY(0)';
                (option as HTMLElement).style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
            });
        });

        backBtn.addEventListener('click', () => this.renderStep1());
        cancelBtn.addEventListener('click', () => this.close());
    }

    private createProject(): void {
        const project = new Project(this.config as any);

        const validation: any = project.validate();
        if (!validation.valid) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                validation.errors.join(', ')
            );
            return;
        }

        if (this.onProjectCreated) {
            this.onProjectCreated(project, this.config);
        }

        this.close();
        ErrorHandler.showSuccess('项目创建成功！');
    }

    close(): void {
        if (this._releaseFocusTrap) {
            this._releaseFocusTrap();
            this._releaseFocusTrap = null;
        }
        if (this.overlay) {
            this.overlay.classList.remove('modal-show');
            setTimeout(() => {
                if (this.overlay && this.overlay.parentNode) {
                    document.body.removeChild(this.overlay);
                }
            }, 300);
        }
    }
}
