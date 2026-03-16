/**
 * 路径规划服务
 */

import {
    RoutePlanningRequest,
    RoutePlanningResponse,
    RouteTemplate,
    AlgorithmInfo,
    VehicleTypeInfo,
    OptimizationGoalInfo,
    ValidationResult,
    PlannedRoute
} from '../models/RoutePlanningModels';

const API_BASE_URL = '/api/route-planning';

export class RoutePlanningService {
    /**
     * 执行路径规划
     */
    static async planRoute(request: RoutePlanningRequest): Promise<RoutePlanningResponse> {
        const response = await fetch(`${API_BASE_URL}/plan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            throw new Error(`路径规划失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 优化现有路径
     */
    static async optimizeRoute(
        route: any,
        optimizationGoal: string = 'shortest_distance'
    ): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/optimize?optimization_goal=${optimizationGoal}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(route)
        });

        if (!response.ok) {
            throw new Error(`路径优化失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 向路径中添加新采样点
     */
    static async addPointToRoute(
        route: any,
        newPoint: any,
        insertPosition?: number
    ): Promise<any> {
        const params = insertPosition !== undefined ? `?insert_position=${insertPosition}` : '';
        const response = await fetch(`${API_BASE_URL}/add-point${params}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                route: route,
                new_point_data: newPoint
            })
        });

        if (!response.ok) {
            throw new Error(`添加采样点失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 从路径中移除采样点
     */
    static async removePointFromRoute(route: any, pointId: string): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/remove-point?point_id=${pointId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(route)
        });

        if (!response.ok) {
            throw new Error(`移除采样点失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 重新排序路径中的采样点
     */
    static async reorderRoute(
        route: any,
        optimizationGoal: string = 'shortest_distance'
    ): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/reorder?optimization_goal=${optimizationGoal}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(route)
        });

        if (!response.ok) {
            throw new Error(`重新排序失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 创建路径模板
     */
    static async createTemplate(templateData: any): Promise<RouteTemplate> {
        const response = await fetch(`${API_BASE_URL}/templates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(templateData)
        });

        if (!response.ok) {
            throw new Error(`创建模板失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 获取所有路径模板
     */
    static async getTemplates(): Promise<RouteTemplate[]> {
        const response = await fetch(`${API_BASE_URL}/templates`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`获取模板失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 获取指定路径模板
     */
    static async getTemplate(templateId: string): Promise<RouteTemplate> {
        const response = await fetch(`${API_BASE_URL}/templates/${templateId}`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`获取模板失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 删除路径模板
     */
    static async deleteTemplate(templateId: string): Promise<any> {
        const response = await fetch(`${API_BASE_URL}/templates/${templateId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(`删除模板失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 获取可用的路径规划算法
     */
    static async getAvailableAlgorithms(): Promise<AlgorithmInfo[]> {
        const response = await fetch(`${API_BASE_URL}/algorithms`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`获取算法列表失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 获取支持的车辆类型
     */
    static async getVehicleTypes(): Promise<VehicleTypeInfo[]> {
        const response = await fetch(`${API_BASE_URL}/vehicle-types`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`获取车辆类型失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 获取支持的优化目标
     */
    static async getOptimizationGoals(): Promise<OptimizationGoalInfo[]> {
        const response = await fetch(`${API_BASE_URL}/optimization-goals`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error(`获取优化目标失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 验证路径是否满足约束条件
     */
    static async validateRoute(route: any, constraints: any): Promise<ValidationResult> {
        const response = await fetch(`${API_BASE_URL}/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                route: route,
                constraints: constraints
            })
        });

        if (!response.ok) {
            throw new Error(`验证路径失败: ${response.statusText}`);
        }

        return await response.json();
    }

    /**
     * 格式化距离显示
     */
    static formatDistance(meters: number): string {
        if (meters < 1000) {
            return `${meters.toFixed(0)} 米`;
        } else {
            return `${(meters / 1000).toFixed(2)} 公里`;
        }
    }

    /**
     * 格式化时间显示
     */
    static formatDuration(seconds: number): string {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours} 小时 ${minutes} 分钟`;
        } else {
            return `${minutes} 分钟`;
        }
    }

    /**
     * 格式化成本显示
     */
    static formatCost(cost: number): string {
        return `¥${cost.toFixed(2)}`;
    }
}