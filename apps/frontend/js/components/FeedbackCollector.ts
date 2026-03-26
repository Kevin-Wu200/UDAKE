import { I18nDialog } from './I18nDialog.js';
/**
 * 用户反馈收集组件
 * 反馈表单、分类、优先级、附件、提交和本地统计
 */

interface FeedbackEntry {
    id: string;
    type: 'bug' | 'feature' | 'improvement' | 'other';
    priority: 'low' | 'medium' | 'high' | 'critical';
    content: string;
    contact?: string;
    timestamp: number;
    status: 'pending' | 'submitted' | 'reviewed' | 'resolved';
    screenshot?: string;
    attachments?: string[];
    deviceInfo?: string;
    browserInfo?: string;
}

const STORAGE_KEY = 'udake_feedback';

const TYPES = [
    { value: 'bug', label: '问题反馈', icon: '🐛', color: '#ff3b30' },
    { value: 'feature', label: '功能建议', icon: '💡', color: '#007aff' },
    { value: 'improvement', label: '体验优化', icon: '✨', color: '#5856d6' },
    { value: 'other', label: '其他', icon: '💬', color: '#8e8e93' },
] as const;

const PRIORITIES = [
    { value: 'low', label: '低优先级', icon: '🟢' },
    { value: 'medium', label: '中优先级', icon: '🟡' },
    { value: 'high', label: '高优先级', icon: '🟠' },
    { value: 'critical', label: '紧急', icon: '🔴' },
] as const;

export class FeedbackCollector {
    private overlay: HTMLElement | null = null;
    private selectedType: string = 'bug';
    private selectedPriority: string = 'medium';
    private selectedFiles: File[] = [];

    show(): void {
        if (this.overlay) return;
        this.overlay = this._createOverlay();
        document.body.appendChild(this.overlay);
        requestAnimationFrame(() => this.overlay?.classList.add('modal-show'));
        // 聚焦第一个输入元素
        setTimeout(() => {
            const firstInput = this.overlay?.querySelector('textarea');
            if (firstInput) (firstInput as HTMLElement).focus();
        }, 100);
    }

    hide(): void {
        if (!this.overlay) return;
        this.overlay.classList.remove('modal-show');
        setTimeout(() => { this.overlay?.remove(); this.overlay = null; this.selectedFiles = []; }, 300);
    }

    private _createOverlay(): HTMLElement {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', 'feedback-title');
        overlay.setAttribute('aria-describedby', 'feedback-description');

        overlay.innerHTML = `
            <div class="modal feedback-modal" role="document">
                <div class="modal-header">
                    <h2 class="modal-title" id="feedback-title">反馈与建议</h2>
                    <button class="modal-close" aria-label="关闭" tabindex="0">&times;</button>
                </div>
                <div class="modal-body feedback-body">
                    <p id="feedback-description" style="margin-bottom:16px;color:var(--text-secondary);font-size:14px;">
                        您的反馈对我们非常重要，请详细描述您遇到的问题或建议。
                    </p>

                    <!-- 反馈类型 -->
                    <fieldset style="border:none;padding:0;margin:0 0 16px 0;">
                        <legend style="font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;padding:0;">
                            反馈类型
                        </legend>
                        <div class="feedback-type-group" role="radiogroup" aria-label="反馈类型">
                            ${TYPES.map((t, i) => `
                                <button class="feedback-type-btn${i === 0 ? ' active' : ''}" 
                                        data-type="${t.value}" 
                                        role="radio" 
                                        aria-checked="${i === 0}"
                                        aria-label="${t.label}"
                                        tabindex="0">
                                    <span style="margin-right:4px;">${t.icon}</span>
                                    ${t.label}
                                </button>
                            `).join('')}
                        </div>
                    </fieldset>

                    <!-- 优先级 -->
                    <fieldset style="border:none;padding:0;margin:0 0 16px 0;">
                        <legend style="font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;padding:0;">
                            优先级
                        </legend>
                        <div class="feedback-priority-group" role="radiogroup" aria-label="优先级">
                            ${PRIORITIES.map((p, i) => `
                                <button class="feedback-priority-btn${i === 1 ? ' active' : ''}" 
                                        data-priority="${p.value}" 
                                        role="radio" 
                                        aria-checked="${i === 1}"
                                        aria-label="${p.label}"
                                        tabindex="0">
                                    <span style="margin-right:4px;">${p.icon}</span>
                                    ${p.label}
                                </button>
                            `).join('')}
                        </div>
                    </fieldset>

                    <!-- 反馈内容 -->
                    <div style="margin-bottom:16px;">
                        <label for="feedback-content" style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            反馈内容 <span style="color:var(--error-color);">*</span>
                        </label>
                        <textarea id="feedback-content" 
                                  placeholder="请详细描述您的问题或建议..." 
                                  aria-label="反馈内容"
                                  aria-required="true"
                                  rows="5"
                                  style="width:100%;min-height:120px;resize:vertical;"></textarea>
                        <div id="feedback-content-counter" style="text-align:right;font-size:12px;color:var(--text-tertiary);margin-top:4px;">
                            0 / 1000
                        </div>
                    </div>

                    <!-- 联系方式 -->
                    <div style="margin-bottom:16px;">
                        <label for="feedback-contact" style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            联系方式（可选）
                        </label>
                        <input type="text" 
                               id="feedback-contact" 
                               class="input" 
                               placeholder="邮箱或手机号" 
                               aria-label="联系方式">
                    </div>

                    <!-- 附件上传 -->
                    <div style="margin-bottom:16px;">
                        <label style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            附件（可选，最多3个，每个不超过5MB）
                        </label>
                        <div id="feedback-file-drop" 
                             class="feedback-file-drop"
                             role="button"
                             tabindex="0"
                             aria-label="点击或拖拽上传附件">
                            <input type="file" 
                                   id="feedback-file-input" 
                                   multiple 
                                   accept="image/*,.pdf,.doc,.docx,.txt"
                                   style="display:none;"
                                   aria-label="选择文件">
                            <div class="feedback-file-drop-content">
                                <span style="font-size:24px;margin-bottom:8px;display:block;">📎</span>
                                <span>点击或拖拽文件到此处</span>
                            </div>
                        </div>
                        <div id="feedback-file-list" style="margin-top:8px;"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <span id="feedback-stats" style="font-size:12px;color:var(--text-tertiary);flex:1;"></span>
                    <button class="btn" id="feedback-cancel" tabindex="0">取消</button>
                    <button class="btn btn-primary" id="feedback-submit" tabindex="0">提交反馈</button>
                </div>
            </div>
        `;

        this._bindEvents(overlay);
        this._updateStats(overlay);

        return overlay;
    }

    private _bindEvents(overlay: HTMLElement): void {
        // 类型选择
        overlay.querySelectorAll('.feedback-type-btn').forEach(btn => {
            btn.addEventListener('click', () => this._selectType(overlay, btn as HTMLElement));
            btn.addEventListener('keydown', (e: Event) => {
                if ((e as KeyboardEvent).key === 'Enter' || (e as KeyboardEvent).key === ' ') {
                    e.preventDefault();
                    this._selectType(overlay, btn as HTMLElement);
                }
            });
        });

        // 优先级选择
        overlay.querySelectorAll('.feedback-priority-btn').forEach(btn => {
            btn.addEventListener('click', () => this._selectPriority(overlay, btn as HTMLElement));
            btn.addEventListener('keydown', (e: Event) => {
                if ((e as KeyboardEvent).key === 'Enter' || (e as KeyboardEvent).key === ' ') {
                    e.preventDefault();
                    this._selectPriority(overlay, btn as HTMLElement);
                }
            });
        });

        // 内容字数统计
        const contentArea = overlay.querySelector('#feedback-content') as HTMLTextAreaElement;
        const counter = overlay.querySelector('#feedback-content-counter')!;
        contentArea.addEventListener('input', () => {
            const count = contentArea.value.length;
            counter.textContent = `${count} / 1000`;
            if (count > 1000) {
                counter.style.color = 'var(--error-color)';
                contentArea.value = contentArea.value.substring(0, 1000);
                counter.textContent = `1000 / 1000`;
            } else {
                counter.style.color = 'var(--text-tertiary)';
            }
        });

        // 文件上传
        const fileDrop = overlay.querySelector('#feedback-file-drop')!;
        const fileInput = overlay.querySelector('#feedback-file-input') as HTMLInputElement;
        const fileList = overlay.querySelector('#feedback-file-list')! as HTMLElement;

        fileDrop.addEventListener('click', () => fileInput.click());
        fileDrop.addEventListener('keydown', (e: Event) => {
            if ((e as KeyboardEvent).key === 'Enter' || (e as KeyboardEvent).key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        fileDrop.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileDrop.classList.add('drag-over');
        });

        fileDrop.addEventListener('dragleave', () => {
            fileDrop.classList.remove('drag-over');
        });

        fileDrop.addEventListener('drop', (e: Event) => {
            e.preventDefault();
            fileDrop.classList.remove('drag-over');
            const files = (e as DragEvent).dataTransfer?.files;
            if (files) {
                this._handleFiles(files, fileList);
            }
        });

        fileInput.addEventListener('change', () => {
            const files = fileInput.files;
            if (files) {
                this._handleFiles(files, fileList);
            }
        });

        // 关闭按钮
        overlay.querySelector('.modal-close')!.addEventListener('click', () => this.hide());
        overlay.querySelector('#feedback-cancel')!.addEventListener('click', () => this.hide());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.hide();
        });

        // 键盘事件
        overlay.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Escape') this.hide();
        });

        // 提交
        overlay.querySelector('#feedback-submit')!.addEventListener('click', () => this._submit(overlay));
    }

    private _selectType(overlay: HTMLElement, selectedBtn: HTMLElement): void {
        overlay.querySelectorAll('.feedback-type-btn').forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-checked', 'false');
        });
        selectedBtn.classList.add('active');
        selectedBtn.setAttribute('aria-checked', 'true');
        this.selectedType = selectedBtn.dataset.type!;
    }

    private _selectPriority(overlay: HTMLElement, selectedBtn: HTMLElement): void {
        overlay.querySelectorAll('.feedback-priority-btn').forEach(b => {
            b.classList.remove('active');
            b.setAttribute('aria-checked', 'false');
        });
        selectedBtn.classList.add('active');
        selectedBtn.setAttribute('aria-checked', 'true');
        this.selectedPriority = selectedBtn.dataset.priority!;
    }

    private _handleFiles(files: FileList, fileListEl: HTMLElement): void {
        const maxFiles = 3;
        const maxSize = 5 * 1024 * 1024; // 5MB

        for (let i = 0; i < files.length; i++) {
            const file = files[i];

            if (this.selectedFiles.length >= maxFiles) {
                I18nDialog.alert(`最多只能上传 ${maxFiles} 个文件`);
                break;
            }

            if (file.size > maxSize) {
                I18nDialog.alert(`文件 ${file.name} 超过 5MB 限制`);
                continue;
            }

            this.selectedFiles.push(file);
        }

        this._renderFileList(fileListEl);
    }

    private _renderFileList(fileListEl: HTMLElement): void {
        fileListEl.innerHTML = this.selectedFiles.map((file, index) => `
            <div class="feedback-file-item" style="display:flex;align-items:center;justify-content:space-between;padding:8px;background:var(--bg-secondary);border-radius:8px;margin-bottom:4px;">
                <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;">${file.name}</span>
                <button class="feedback-file-remove" data-index="${index}" aria-label="删除文件" style="background:none;border:none;color:var(--error-color);cursor:pointer;padding:4px;">✕</button>
            </div>
        `).join('');

        fileListEl.querySelectorAll('.feedback-file-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt((btn as HTMLElement).dataset.index!);
                this.selectedFiles.splice(index, 1);
                this._renderFileList(fileListEl);
            });
        });
    }

    private _updateStats(overlay: HTMLElement): void {
        const stats = FeedbackCollector.getStats();
        const statsEl = overlay.querySelector('#feedback-stats')!;
        statsEl.textContent = `已提交 ${stats.total} 条反馈`;
    }

    private _submit(overlay: HTMLElement): void {
        const content = (overlay.querySelector('#feedback-content') as HTMLTextAreaElement).value.trim();
        if (!content) {
            (overlay.querySelector('#feedback-content') as HTMLTextAreaElement).focus();
            I18nDialog.alert('请填写反馈内容');
            return;
        }

        const contact = (overlay.querySelector('#feedback-contact') as HTMLInputElement).value.trim();

        // 处理附件
        const attachments: string[] = [];
        this.selectedFiles.forEach(file => {
            // 在实际应用中，这里应该上传文件到服务器
            // 这里我们只保存文件名作为示例
            attachments.push(file.name);
        });

        FeedbackCollector.save({
            type: this.selectedType as any,
            priority: this.selectedPriority as any,
            content,
            contact: contact || undefined,
            attachments: attachments.length > 0 ? attachments : undefined,
            deviceInfo: this._getDeviceInfo(),
            browserInfo: this._getBrowserInfo(),
        });

        I18nDialog.alert('反馈已提交，感谢您的建议！');
        this.hide();
    }

    private _getDeviceInfo(): string {
        return `${navigator.platform} - ${screen.width}x${screen.height}`;
    }

    private _getBrowserInfo(): string {
        return navigator.userAgent;
    }

    /** 保存反馈到本地 */
    static save(data: Partial<FeedbackEntry>): void {
        const entries = this.getAll();
        entries.push({
            id: `fb_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            type: 'bug',
            priority: 'medium',
            ...data,
            timestamp: Date.now(),
            status: 'pending',
        } as FeedbackEntry);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
        console.log('[Feedback] 反馈已保存');
    }

    /** 获取所有反馈 */
    static getAll(): FeedbackEntry[] {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch { return []; }
    }

    /** 获取统计信息 */
    static getStats(): { total: number; byType: Record<string, number>; byPriority: Record<string, number> } {
        const entries = this.getAll();
        const byType: Record<string, number> = {};
        const byPriority: Record<string, number> = {};
        entries.forEach(e => {
            byType[e.type] = (byType[e.type] || 0) + 1;
            byPriority[e.priority] = (byPriority[e.priority] || 0) + 1;
        });
        return { total: entries.length, byType, byPriority };
    }

    /** 导出反馈为 JSON */
    static exportJSON(): void {
        const entries = this.getAll();
        const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `feedback_export_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /** 导出反馈为 CSV */
    static exportCSV(): void {
        const entries = this.getAll();
        const headers = ['ID', 'Type', 'Priority', 'Content', 'Contact', 'Timestamp', 'Status'];
        const rows = entries.map(e => [
            e.id,
            e.type,
            e.priority,
            `"${e.content.replace(/"/g, '""')}"`,
            e.contact || '',
            new Date(e.timestamp).toISOString(),
            e.status,
        ]);
        const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `feedback_export_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /** 清除所有反馈 */
    static clearAll(): void {
        if (I18nDialog.confirm('确定要清除所有反馈吗？此操作不可恢复。')) {
            localStorage.removeItem(STORAGE_KEY);
        }
    }

    /** 更新反馈状态 */
    static updateStatus(id: string, status: FeedbackEntry['status']): void {
        const entries = this.getAll();
        const index = entries.findIndex(e => e.id === id);
        if (index !== -1) {
            entries[index].status = status;
            localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
        }
    }
}
