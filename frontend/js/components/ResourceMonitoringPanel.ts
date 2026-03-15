/**
 * 资源监控面板组件
 * 显示系统资源使用情况、警告和优化建议
 */

interface ResourceUsage {
    resource_type: string;
    usage_percent: number;
    used_value: number;
    total_value: number;
    unit: string;
    timestamp: string;
}

interface SystemResources {
    cpu: ResourceUsage;
    memory: ResourceUsage;
    disk: ResourceUsage;
    network?: Record<string, number>;
    timestamp: string;
}

interface ResourceWarning {
    warning_id: string;
    resource_type: string;
    warning_level: string;
    message: string;
    threshold: number;
    current_value: number;
    task_id?: string;
    timestamp: string;
}

interface ResourceSuggestion {
    suggestion_id: string;
    resource_type: string;
    suggestion_type: string;
    title: string;
    description: string;
    priority: string;
    expected_improvement?: string;
    action_steps: string[];
    timestamp: string;
}

export class ResourceMonitoringPanel {
    private container: HTMLElement;
    private overlay!: HTMLElement;
    private panel!: HTMLElement;
    private pollingInterval: number | null = null;

    constructor(container: HTMLElement | string) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        this.init();
    }

    private init(): void {
        this.createPanel();
        this.bindEvents();
        this.startMonitoring();
    }

    private createPanel(): void {
        // 创建面板
        this.panel = document.createElement('div');
        this.panel.className = 'resource-monitoring-panel';
        this.panel.innerHTML = `
            <div class="resource-monitoring-content">
                <div class="resource-monitoring-header">
                    <h2 class="resource-monitoring-title">资源监控</h2>
                    <div class="resource-monitoring-controls">
                        <button class="btn btn-icon" id="refresh-resources-btn" title="刷新">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M23 4v6h-6"></path>
                                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="resource-monitoring-body">
                    <!-- 系统资源概览 -->
                    <div class="resource-section">
                        <h3 class="resource-section-title">系统资源</h3>
                        <div class="resources-grid">
                            <!-- CPU -->
                            <div class="resource-card">
                                <div class="resource-card-header">
                                    <span class="resource-card-title">CPU</span>
                                    <span class="resource-card-percentage" id="cpu-percentage">0%</span>
                                </div>
                                <div class="resource-card-bar">
                                    <div class="resource-card-fill" id="cpu-fill" style="width: 0%"></div>
                                </div>
                                <div class="resource-card-info">
                                    <span class="resource-card-info-text" id="cpu-info">--</span>
                                </div>
                            </div>

                            <!-- 内存 -->
                            <div class="resource-card">
                                <div class="resource-card-header">
                                    <span class="resource-card-title">内存</span>
                                    <span class="resource-card-percentage" id="memory-percentage">0%</span>
                                </div>
                                <div class="resource-card-bar">
                                    <div class="resource-card-fill" id="memory-fill" style="width: 0%"></div>
                                </div>
                                <div class="resource-card-info">
                                    <span class="resource-card-info-text" id="memory-info">--</span>
                                </div>
                            </div>

                            <!-- 磁盘 -->
                            <div class="resource-card">
                                <div class="resource-card-header">
                                    <span class="resource-card-title">磁盘</span>
                                    <span class="resource-card-percentage" id="disk-percentage">0%</span>
                                </div>
                                <div class="resource-card-bar">
                                    <div class="resource-card-fill" id="disk-fill" style="width: 0%"></div>
                                </div>
                                <div class="resource-card-info">
                                    <span class="resource-card-info-text" id="disk-info">--</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 资源警告 -->
                    <div class="resource-section" id="warnings-section">
                        <div class="resource-section-header">
                            <h3 class="resource-section-title">资源警告</h3>
                            <button class="btn btn-sm btn-secondary" id="clear-warnings-btn">清除警告</button>
                        </div>
                        <div class="warnings-container" id="warnings-container">
                            <div class="no-warnings">暂无警告</div>
                        </div>
                    </div>

                    <!-- 优化建议 -->
                    <div class="resource-section" id="suggestions-section">
                        <div class="resource-section-header">
                            <h3 class="resource-section-title">优化建议</h3>
                            <button class="btn btn-sm btn-secondary" id="clear-suggestions-btn">清除建议</button>
                        </div>
                        <div class="suggestions-container" id="suggestions-container">
                            <div class="no-suggestions">暂无建议</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.container.appendChild(this.panel);
    }

    private bindEvents(): void {
        const refreshBtn = document.getElementById('refresh-resources-btn') as HTMLElement;
        refreshBtn.addEventListener('click', () => this.updateResources());

        const clearWarningsBtn = document.getElementById('clear-warnings-btn') as HTMLElement;
        clearWarningsBtn.addEventListener('click', () => this.clearWarnings());

        const clearSuggestionsBtn = document.getElementById('clear-suggestions-btn') as HTMLElement;
        clearSuggestionsBtn.addEventListener('click', () => this.clearSuggestions());
    }

    private startMonitoring(): void {
        this.updateResources(); // 立即更新一次

        this.pollingInterval = window.setInterval(() => {
            this.updateResources();
        }, 5000); // 每5秒更新一次

        // 定期更新警告和建议
        this.updateWarningsAndSuggestions();
        setInterval(() => {
            this.updateWarningsAndSuggestions();
        }, 30000); // 每30秒更新一次警告和建议
    }

    private stopMonitoring(): void {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    private async updateResources(): Promise<void> {
        try {
            const response = await fetch('/api/system/resources');
            if (!response.ok) {
                throw new Error('获取资源信息失败');
            }

            const data: SystemResources = await response.json();
            this.updateResourcesUI(data);
        } catch (error) {
            console.error('更新资源信息失败:', error);
        }
    }

    private updateResourcesUI(data: SystemResources): void {
        // 更新CPU
        this.updateResourceCard('cpu', data.cpu);

        // 更新内存
        this.updateResourceCard('memory', data.memory);

        // 更新磁盘
        this.updateResourceCard('disk', data.disk);
    }

    private updateResourceCard(type: string, resource: ResourceUsage): void {
        const percentage = document.getElementById(`${type}-percentage`) as HTMLElement;
        const fill = document.getElementById(`${type}-fill`) as HTMLElement;
        const info = document.getElementById(`${type}-info`) as HTMLElement;

        percentage.textContent = `${Math.round(resource.usage_percent)}%`;
        fill.style.width = `${resource.usage_percent}%`;
        info.textContent = `${resource.used_value.toFixed(1)}${resource.unit} / ${resource.total_value.toFixed(1)}${resource.unit}`;

        // 根据使用率设置颜色
        if (resource.usage_percent >= 90) {
            fill.style.background = 'linear-gradient(90deg, #D32F2F 0%, #F44336 100%)';
        } else if (resource.usage_percent >= 80) {
            fill.style.background = 'linear-gradient(90deg, #FF9800 0%, #FFC107 100%)';
        } else {
            fill.style.background = 'linear-gradient(90deg, #4CAF50 0%, #66BB6A 100%)';
        }
    }

    private async updateWarningsAndSuggestions(): Promise<void> {
        try {
            // 获取警告
            const warningsResponse = await fetch('/api/system/resources/warnings?limit=5');
            if (warningsResponse.ok) {
                const warnings: ResourceWarning[] = await warningsResponse.json();
                this.updateWarningsUI(warnings);
            }

            // 获取建议
            const suggestionsResponse = await fetch('/api/system/resources/suggestions?limit=5');
            if (suggestionsResponse.ok) {
                const suggestions: ResourceSuggestion[] = await suggestionsResponse.json();
                this.updateSuggestionsUI(suggestions);
            }
        } catch (error) {
            console.error('更新警告和建议失败:', error);
        }
    }

    private updateWarningsUI(warnings: ResourceWarning[]): void {
        const container = document.getElementById('warnings-container') as HTMLElement;

        if (warnings.length === 0) {
            container.innerHTML = '<div class="no-warnings">暂无警告</div>';
            return;
        }

        container.innerHTML = '';
        warnings.forEach(warning => {
            const warningElement = document.createElement('div');
            warningElement.className = `warning-item warning-${warning.warning_level}`;
            warningElement.innerHTML = `
                <div class="warning-header">
                    <span class="warning-level">${this.getWarningLevelText(warning.warning_level)}</span>
                    <span class="warning-resource">${warning.resource_type.toUpperCase()}</span>
                </div>
                <div class="warning-message">${warning.message}</div>
                <div class="warning-footer">
                    <span class="warning-time">${this.formatTime(warning.timestamp)}</span>
                </div>
            `;
            container.appendChild(warningElement);
        });
    }

    private updateSuggestionsUI(suggestions: ResourceSuggestion[]): void {
        const container = document.getElementById('suggestions-container') as HTMLElement;

        if (suggestions.length === 0) {
            container.innerHTML = '<div class="no-suggestions">暂无建议</div>';
            return;
        }

        container.innerHTML = '';
        suggestions.forEach(suggestion => {
            const suggestionElement = document.createElement('div');
            suggestionElement.className = `suggestion-item suggestion-${suggestion.priority}`;
            suggestionElement.innerHTML = `
                <div class="suggestion-header">
                    <span class="suggestion-title">${suggestion.title}</span>
                    <span class="suggestion-priority">${this.getPriorityText(suggestion.priority)}</span>
                </div>
                <div class="suggestion-description">${suggestion.description}</div>
                ${suggestion.expected_improvement ? `<div class="suggestion-improvement">预期改善: ${suggestion.expected_improvement}</div>` : ''}
                <div class="suggestion-steps">
                    <strong>建议步骤:</strong>
                    <ul>
                        ${suggestion.action_steps.map(step => `<li>${step}</li>`).join('')}
                    </ul>
                </div>
            `;
            container.appendChild(suggestionElement);
        });
    }

    private async clearWarnings(): Promise<void> {
        try {
            const response = await fetch('/api/system/resources/warnings', {
                method: 'DELETE'
            });
            if (response.ok) {
                this.updateWarningsUI([]);
            }
        } catch (error) {
            console.error('清除警告失败:', error);
        }
    }

    private async clearSuggestions(): Promise<void> {
        try {
            const response = await fetch('/api/system/resources/suggestions', {
                method: 'DELETE'
            });
            if (response.ok) {
                this.updateSuggestionsUI([]);
            }
        } catch (error) {
            console.error('清除建议失败:', error);
        }
    }

    private formatTime(timestamp: string): string {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (diff < 60) {
            return `${diff}秒前`;
        } else if (diff < 3600) {
            return `${Math.floor(diff / 60)}分钟前`;
        } else if (diff < 86400) {
            return `${Math.floor(diff / 3600)}小时前`;
        } else {
            return date.toLocaleDateString();
        }
    }

    private getWarningLevelText(level: string): string {
        const levelMap: Record<string, string> = {
            'warning': '警告',
            'critical': '严重'
        };
        return levelMap[level] || level;
    }

    private getPriorityText(priority: string): string {
        const priorityMap: Record<string, string> = {
            'high': '高',
            'medium': '中',
            'low': '低'
        };
        return priorityMap[priority] || priority;
    }

    public destroy(): void {
        this.stopMonitoring();
        if (this.container.contains(this.panel)) {
            this.container.removeChild(this.panel);
        }
    }
}