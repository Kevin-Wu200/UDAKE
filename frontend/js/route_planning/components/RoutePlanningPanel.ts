/**
 * 路径规划面板组件
 */

import {
    SamplingPoint,
    RouteConstraint,
    VehicleType,
    OptimizationGoal,
    RoutePlanningRequest,
    RoutePlanningResponse,
    PlannedRoute,
    AlgorithmInfo,
    VehicleTypeInfo,
    OptimizationGoalInfo
} from '../models/RoutePlanningModels';
import { RoutePlanningService } from '../services/RoutePlanningService';

export class RoutePlanningPanel {
    private container: HTMLElement;
    private samplingPoints: SamplingPoint[] = [];
    private startPoint: SamplingPoint | null = null;
    private endPoint: SamplingPoint | null = null;
    private currentRoute: PlannedRoute | null = null;
    private algorithms: AlgorithmInfo[] = [];
    private vehicleTypes: VehicleTypeInfo[] = [];
    private optimizationGoals: OptimizationGoalInfo[] = [];

    constructor(containerId: string) {
        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }
        this.container = container;
        this.init();
    }

    private async init() {
        // 加载配置数据
        await this.loadConfiguration();

        // 渲染UI
        this.render();

        // 绑定事件
        this.bindEvents();
    }

    private async loadConfiguration() {
        try {
            [this.algorithms, this.vehicleTypes, this.optimizationGoals] = await Promise.all([
                RoutePlanningService.getAvailableAlgorithms(),
                RoutePlanningService.getVehicleTypes(),
                RoutePlanningService.getOptimizationGoals()
            ]);
        } catch (error) {
            console.error('加载配置失败:', error);
        }
    }

    private render() {
        this.container.innerHTML = `
            <div class="route-planning-panel">
                <div class="panel-header">
                    <h2>路径规划</h2>
                    <button class="btn btn-primary" id="plan-route-btn">开始规划</button>
                </div>

                <div class="panel-content">
                    <!-- 采样点列表 -->
                    <div class="section">
                        <h3>采样点列表</h3>
                        <div class="sampling-points-list" id="sampling-points-list">
                            <div class="empty-state">暂无采样点，请在地图上添加</div>
                        </div>
                        <div class="point-controls">
                            <div class="control-group">
                                <label>起点:</label>
                                <select id="start-point-select">
                                    <option value="">请选择起点</option>
                                </select>
                            </div>
                            <div class="control-group">
                                <label>终点:</label>
                                <select id="end-point-select">
                                    <option value="">请选择终点（可选）</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- 规划参数 -->
                    <div class="section">
                        <h3>规划参数</h3>
                        <div class="planning-parameters">
                            <div class="control-group">
                                <label>算法:</label>
                                <select id="algorithm-select">
                                    ${this.algorithms.map(alg => `
                                        <option value="${alg.id}">${alg.name}</option>
                                    `).join('')}
                                </select>
                            </div>
                            <div class="control-group">
                                <label>优化目标:</label>
                                <select id="optimization-goal-select">
                                    ${this.optimizationGoals.map(goal => `
                                        <option value="${goal.id}">${goal.name}</option>
                                    `).join('')}
                                </select>
                            </div>
                            <div class="control-group">
                                <label>车辆类型:</label>
                                <select id="vehicle-type-select">
                                    ${this.vehicleTypes.map(type => `
                                        <option value="${type.id}">${type.name}</option>
                                    `).join('')}
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- 约束条件 -->
                    <div class="section">
                        <h3>约束条件</h3>
                        <div class="constraints">
                            <div class="control-group">
                                <label>
                                    <input type="checkbox" id="time-windows-check">
                                    考虑时间窗
                                </label>
                            </div>
                            <div class="control-group">
                                <label>
                                    <input type="checkbox" id="priority-constraint-check">
                                    考虑优先级
                                </label>
                            </div>
                            <div class="control-group">
                                <label>最大距离 (米):</label>
                                <input type="number" id="max-distance-input" placeholder="不限制">
                            </div>
                            <div class="control-group">
                                <label>最大时间 (秒):</label>
                                <input type="number" id="max-duration-input" placeholder="不限制">
                            </div>
                            <div class="control-group">
                                <label>最大成本:</label>
                                <input type="number" id="max-cost-input" placeholder="不限制">
                            </div>
                        </div>
                    </div>

                    <!-- 规划结果 -->
                    <div class="section" id="results-section" style="display: none;">
                        <h3>规划结果</h3>
                        <div class="route-results" id="route-results">
                            <!-- 结果将在这里显示 -->
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    private bindEvents() {
        // 规划按钮
        const planBtn = document.getElementById('plan-route-btn');
        if (planBtn) {
            planBtn.addEventListener('click', () => this.planRoute());
        }

        // 起点选择
        const startSelect = document.getElementById('start-point-select') as HTMLSelectElement;
        if (startSelect) {
            startSelect.addEventListener('change', (e) => {
                const target = e.target as HTMLSelectElement;
                const pointId = target.value;
                this.startPoint = this.samplingPoints.find(p => p.id === pointId) || null;
            });
        }

        // 终点选择
        const endSelect = document.getElementById('end-point-select') as HTMLSelectElement;
        if (endSelect) {
            endSelect.addEventListener('change', (e) => {
                const target = e.target as HTMLSelectElement;
                const pointId = target.value;
                this.endPoint = this.samplingPoints.find(p => p.id === pointId) || null;
            });
        }
    }

    /**
     * 添加采样点
     */
    addSamplingPoint(point: SamplingPoint) {
        this.samplingPoints.push(point);
        this.updateSamplingPointsList();
    }

    /**
     * 移除采样点
     */
    removeSamplingPoint(pointId: string) {
        this.samplingPoints = this.samplingPoints.filter(p => p.id !== pointId);
        if (this.startPoint?.id === pointId) {
            this.startPoint = null;
        }
        if (this.endPoint?.id === pointId) {
            this.endPoint = null;
        }
        this.updateSamplingPointsList();
    }

    /**
     * 更新采样点列表UI
     */
    private updateSamplingPointsList() {
        const listContainer = document.getElementById('sampling-points-list');
        if (!listContainer) return;

        if (this.samplingPoints.length === 0) {
            listContainer.innerHTML = '<div class="empty-state">暂无采样点，请在地图上添加</div>';
            return;
        }

        listContainer.innerHTML = this.samplingPoints.map(point => `
            <div class="sampling-point-item" data-point-id="${point.id}">
                <div class="point-info">
                    <strong>${point.name || point.id}</strong>
                    <span class="point-coordinates">
                        (${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)})
                    </span>
                </div>
                <div class="point-priority">优先级: ${point.priority}</div>
                <button class="btn btn-sm btn-danger remove-point-btn" data-point-id="${point.id}">
                    删除
                </button>
            </div>
        `).join('');

        // 绑定删除按钮事件
        listContainer.querySelectorAll('.remove-point-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.target as HTMLElement;
                const pointId = target.dataset.pointId;
                if (pointId) {
                    this.removeSamplingPoint(pointId);
                }
            });
        });

        // 更新起点和终点选择器
        this.updatePointSelectors();
    }

    /**
     * 更新起点和终点选择器
     */
    private updatePointSelectors() {
        const startSelect = document.getElementById('start-point-select') as HTMLSelectElement;
        const endSelect = document.getElementById('end-point-select') as HTMLSelectElement;

        if (!startSelect || !endSelect) return;

        const options = this.samplingPoints.map(point =>
            `<option value="${point.id}">${point.name || point.id}</option>`
        ).join('');

        startSelect.innerHTML = `<option value="">请选择起点</option>${options}`;
        endSelect.innerHTML = `<option value="">请选择终点（可选）</option>${options}`;
    }

    /**
     * 执行路径规划
     */
    private async planRoute() {
        if (!this.startPoint) {
            alert('请先选择起点');
            return;
        }

        if (this.samplingPoints.length < 2) {
            alert('请至少添加2个采样点');
            return;
        }

        // 获取约束条件
        const constraints: RouteConstraint = {
            vehicleType: (document.getElementById('vehicle-type-select') as HTMLSelectElement).value as VehicleType,
            timeWindows: (document.getElementById('time-windows-check') as HTMLInputElement).checked,
            priorityConstraint: (document.getElementById('priority-constraint-check') as HTMLInputElement).checked
        };

        const maxDistanceInput = document.getElementById('max-distance-input') as HTMLInputElement;
        if (maxDistanceInput.value) {
            constraints.maxDistance = parseFloat(maxDistanceInput.value);
        }

        const maxDurationInput = document.getElementById('max-duration-input') as HTMLInputElement;
        if (maxDurationInput.value) {
            constraints.maxDuration = parseFloat(maxDurationInput.value);
        }

        const maxCostInput = document.getElementById('max-cost-input') as HTMLInputElement;
        if (maxCostInput.value) {
            constraints.maxCost = parseFloat(maxCostInput.value);
        }

        // 构建请求
        const request: RoutePlanningRequest = {
            samplingPoints: this.samplingPoints.filter(p => p.id !== this.startPoint?.id && p.id !== this.endPoint?.id),
            startPoint: this.startPoint,
            endPoint: this.endPoint || undefined,
            constraints: constraints,
            optimizationGoal: (document.getElementById('optimization-goal-select') as HTMLSelectElement).value as OptimizationGoal,
            algorithm: (document.getElementById('algorithm-select') as HTMLSelectElement).value,
            returnMultipleRoutes: true
        };

        try {
            // 显示加载状态
            const planBtn = document.getElementById('plan-route-btn');
            if (planBtn) {
                planBtn.disabled = true;
                planBtn.textContent = '规划中...';
            }

            // 调用API
            const response = await RoutePlanningService.planRoute(request);

            // 显示结果
            this.displayResults(response);

        } catch (error) {
            console.error('路径规划失败:', error);
            alert(`路径规划失败: ${error}`);
        } finally {
            // 恢复按钮状态
            const planBtn = document.getElementById('plan-route-btn');
            if (planBtn) {
                planBtn.disabled = false;
                planBtn.textContent = '开始规划';
            }
        }
    }

    /**
     * 显示规划结果
     */
    private displayResults(response: RoutePlanningResponse) {
        const resultsSection = document.getElementById('results-section');
        const resultsContainer = document.getElementById('route-results');

        if (!resultsSection || !resultsContainer) return;

        resultsSection.style.display = 'block';

        if (!response.success || response.routes.length === 0) {
            resultsContainer.innerHTML = '<div class="error-message">规划失败，未找到有效路径</div>';
            return;
        }

        const bestRoute = response.bestRoute || response.routes[0];
        this.currentRoute = bestRoute;

        resultsContainer.innerHTML = `
            <div class="route-summary">
                <h4>最优路径</h4>
                <div class="summary-stats">
                    <div class="stat-item">
                        <span class="stat-label">总距离:</span>
                        <span class="stat-value">${RoutePlanningService.formatDistance(bestRoute.totalDistance)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">总时间:</span>
                        <span class="stat-value">${RoutePlanningService.formatDuration(bestRoute.totalDuration)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">总成本:</span>
                        <span class="stat-value">${RoutePlanningService.formatCost(bestRoute.totalCost)}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">计算时间:</span>
                        <span class="stat-value">${response.computationTime.toFixed(2)} 秒</span>
                    </div>
                </div>
            </div>

            <div class="route-segments">
                <h4>路径详情</h4>
                <div class="segments-list">
                    ${bestRoute.segments.map((segment, index) => `
                        <div class="segment-item">
                            <div class="segment-index">${index + 1}</div>
                            <div class="segment-info">
                                <div class="segment-route">
                                    ${segment.fromPointId} → ${segment.toPointId}
                                </div>
                                <div class="segment-stats">
                                    <span>${RoutePlanningService.formatDistance(segment.distance)}</span>
                                    <span>${RoutePlanningService.formatDuration(segment.duration)}</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>

            ${response.warnings.length > 0 ? `
                <div class="warnings">
                    <h4>警告</h4>
                    <ul>
                        ${response.warnings.map(warning => `<li>${warning}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
        `;

        // 触发自定义事件，通知地图组件显示路径
        this.container.dispatchEvent(new CustomEvent('route-planned', {
            detail: {
                route: bestRoute,
                samplingPoints: this.samplingPoints
            }
        }));
    }

    /**
     * 获取当前路径
     */
    getCurrentRoute(): PlannedRoute | null {
        return this.currentRoute;
    }

    /**
     * 清空数据
     */
    clear() {
        this.samplingPoints = [];
        this.startPoint = null;
        this.endPoint = null;
        this.currentRoute = null;
        this.updateSamplingPointsList();

        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }
    }
}