/**
 * 路径规划模块测试
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';

// 由于我们使用的是Python后端，这里创建API测试
// 实际测试应该使用vitest或jest进行单元测试

describe('路径规划API测试', () => {
    const API_BASE_URL = 'http://localhost:8000/api/route-planning';

    it('应该成功获取可用算法列表', async () => {
        const response = await fetch(`${API_BASE_URL}/algorithms`);
        expect(response.ok).toBe(true);

        const algorithms = await response.json();
        expect(Array.isArray(algorithms)).toBe(true);
        expect(algorithms.length).toBeGreaterThan(0);

        console.log('可用算法:', algorithms);
    });

    it('应该成功获取车辆类型列表', async () => {
        const response = await fetch(`${API_BASE_URL}/vehicle-types`);
        expect(response.ok).toBe(true);

        const vehicleTypes = await response.json();
        expect(Array.isArray(vehicleTypes)).toBe(true);
        expect(vehicleTypes.length).toBeGreaterThan(0);

        console.log('车辆类型:', vehicleTypes);
    });

    it('应该成功获取优化目标列表', async () => {
        const response = await fetch(`${API_BASE_URL}/optimization-goals`);
        expect(response.ok).toBe(true);

        const goals = await response.json();
        expect(Array.isArray(goals)).toBe(true);
        expect(goals.length).toBeGreaterThan(0);

        console.log('优化目标:', goals);
    });

    it('应该成功执行路径规划', async () => {
        const request = {
            sampling_points: [
                {
                    id: 'point1',
                    name: '采样点1',
                    latitude: 39.9042,
                    longitude: 116.4074,
                    priority: 5,
                    service_time: 10,
                    is_reachable: true
                },
                {
                    id: 'point2',
                    name: '采样点2',
                    latitude: 39.9142,
                    longitude: 116.4174,
                    priority: 3,
                    service_time: 10,
                    is_reachable: true
                },
                {
                    id: 'point3',
                    name: '采样点3',
                    latitude: 39.9242,
                    longitude: 116.4274,
                    priority: 7,
                    service_time: 10,
                    is_reachable: true
                }
            ],
            start_point: {
                id: 'start',
                name: '起点',
                latitude: 39.8942,
                longitude: 116.3974,
                priority: 1,
                service_time: 0,
                is_reachable: true
            },
            constraints: {
                vehicle_type: 'car',
                time_windows: false,
                priority_constraint: false
            },
            optimization_goal: 'shortest_distance',
            algorithm: 'tsp',
            return_multiple_routes: true
        };

        const response = await fetch(`${API_BASE_URL}/plan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });

        expect(response.ok).toBe(true);

        const result = await response.json();
        expect(result.success).toBe(true);
        expect(Array.isArray(result.routes)).toBe(true);
        expect(result.routes.length).toBeGreaterThan(0);

        console.log('规划结果:', result);
    });

    it('应该能够创建和获取路径模板', async () => {
        const templateData = {
            template_id: 'test_template',
            name: '测试模板',
            description: '这是一个测试模板',
            sampling_points: [
                {
                    id: 'point1',
                    name: '采样点1',
                    latitude: 39.9042,
                    longitude: 116.4074,
                    priority: 5,
                    service_time: 10,
                    is_reachable: true
                }
            ],
            constraints: {
                vehicle_type: 'car',
                time_windows: false,
                priority_constraint: false
            },
            optimization_goal: 'shortest_distance'
        };

        // 创建模板
        const createResponse = await fetch(`${API_BASE_URL}/templates`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(templateData)
        });

        expect(createResponse.ok).toBe(true);

        // 获取模板
        const getResponse = await fetch(`${API_BASE_URL}/templates/${templateData.template_id}`);
        expect(getResponse.ok).toBe(true);

        const template = await getResponse.json();
        expect(template.template_id).toBe(templateData.template_id);

        console.log('模板详情:', template);

        // 删除模板
        const deleteResponse = await fetch(`${API_BASE_URL}/templates/${templateData.template_id}`, {
            method: 'DELETE'
        });

        expect(deleteResponse.ok).toBe(true);
    });
});

// 如果后端服务未运行，这些测试会失败
// 实际使用时应该先启动后端服务