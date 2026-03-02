/**
 * 新建项目弹窗组件
 * 引导用户选择采样模式和坐标获取方式
 */
import { Project } from '../models/Project.js';
import { FreeSampling } from '../sampling/FreeSampling.js';
import { RegionSampling } from '../sampling/RegionSampling.js';
import { ErrorHandler } from '../utils/ErrorHandler.js';

export class NewProjectModal {
    /**
     * @param {Function} onProjectCreated - 项目创建回调
     * @param {Object} view - ArcGIS MapView
     */
    constructor(onProjectCreated, view) {
        this.onProjectCreated = onProjectCreated;
        this.view = view;
        this.overlay = null;
        this.currentStep = 1;
        this.config = {
            sampling_mode: null,
            coordinate_mode: null
        };
    }

    /**
     * 显示弹窗
     */
    show() {
        this.createOverlay();
        this.renderStep1();

        // 添加到 DOM
        document.body.appendChild(this.overlay);

        // 触发动画
        requestAnimationFrame(() => {
            this.overlay.classList.add('modal-show');
        });
    }

    /**
     * 创建弹窗容器
     */
    createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'modal-overlay';
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });
    }

    /**
     * 渲染第一步：选择采样模式
     */
    renderStep1() {
        const content = document.createElement('div');
        content.className = 'modal-content';

        content.innerHTML = `
            <h2 class="modal-title">新建项目 - 选择采样模式</h2>

            <div class="modal-section">
                <div class="sampling-mode-options">
                    <div class="option-card" data-mode="free">
                        <div class="option-icon">🌍</div>
                        <h3 class="option-title">自由采样</h3>
                        <p class="option-description">可在任意位置添加采样点，不受区域限制</p>
                    </div>

                    <div class="option-card" data-mode="region">
                        <div class="option-icon">📍</div>
                        <h3 class="option-title">区域采样</h3>
                        <p class="option-description">仅允许在指定区域内添加采样点</p>
                    </div>
                </div>
            </div>

            <div class="modal-actions">
                <button class="btn btn-secondary" id="cancel-btn">取消</button>
            </div>
        `;

        // 清空并添加内容
        this.overlay.innerHTML = '';
        this.overlay.appendChild(content);

        // 绑定事件
        this.bindStep1Events(content);
    }

    /**
     * 绑定第一步事件
     */
    bindStep1Events(content) {
        const options = content.querySelectorAll('.option-card');
        const cancelBtn = content.querySelector('#cancel-btn');

        options.forEach(option => {
            option.addEventListener('click', () => {
                const mode = option.dataset.mode;
                this.config.sampling_mode = mode;
                this.renderStep2();
            });

            option.addEventListener('mouseenter', () => {
                option.style.transform = 'translateY(-4px)';
                option.style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.12)';
            });

            option.addEventListener('mouseleave', () => {
                option.style.transform = 'translateY(0)';
                option.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
            });
        });

        cancelBtn.addEventListener('click', () => this.close());
    }

    /**
     * 渲染第二步：选择坐标获取方式
     */
    renderStep2() {
        const content = document.createElement('div');
        content.className = 'modal-content';

        content.innerHTML = `
            <h2 class="modal-title">新建项目 - 选择坐标获取方式</h2>

            <div class="modal-section">
                <div class="sampling-mode-options">
                    <div class="option-card" data-mode="manual">
                        <div class="option-icon">⌨️</div>
                        <h3 class="option-title">手动输入</h3>
                        <p class="option-description">手动输入经纬度坐标</p>
                    </div>

                    <div class="option-card" data-mode="device">
                        <div class="option-icon">📱</div>
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

        // 清空并添加内容
        this.overlay.innerHTML = '';
        this.overlay.appendChild(content);

        // 绑定事件
        this.bindStep2Events(content);
    }

    /**
     * 绑定第二步事件
     */
    bindStep2Events(content) {
        const options = content.querySelectorAll('.option-card');
        const backBtn = content.querySelector('#back-btn');
        const cancelBtn = content.querySelector('#cancel-btn');

        options.forEach(option => {
            option.addEventListener('click', () => {
                const mode = option.dataset.mode;
                this.config.coordinate_mode = mode;
                this.createProject();
            });

            option.addEventListener('mouseenter', () => {
                option.style.transform = 'translateY(-4px)';
                option.style.boxShadow = '0 12px 24px rgba(0, 0, 0, 0.12)';
            });

            option.addEventListener('mouseleave', () => {
                option.style.transform = 'translateY(0)';
                option.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.08)';
            });
        });

        backBtn.addEventListener('click', () => this.renderStep1());
        cancelBtn.addEventListener('click', () => this.close());
    }

    /**
     * 创建项目
     */
    createProject() {
        // 创建项目实例
        const project = new Project(this.config);

        // 验证项目配置
        const validation = project.validate();
        if (!validation.valid) {
            ErrorHandler.showError(
                ErrorHandler.ErrorTypes.VALIDATION_ERROR,
                validation.errors.join(', ')
            );
            return;
        }

        // 触发回调
        if (this.onProjectCreated) {
            this.onProjectCreated(project, this.config);
        }

        // 关闭弹窗
        this.close();

        ErrorHandler.showSuccess('项目创建成功！');
    }

    /**
     * 关闭弹窗
     */
    close() {
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
