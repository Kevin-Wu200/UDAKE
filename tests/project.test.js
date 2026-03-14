import { describe, it, expect } from 'vitest';
import { Project } from '../frontend/js/models/Project.js';

describe('Project', () => {
    it('应该使用默认配置创建项目', () => {
        const project = new Project();
        expect(project.sampling_mode).toBe('free');
        expect(project.coordinate_mode).toBe('manual');
        expect(project.points).toEqual([]);
        expect(project.crs).toBe('EPSG:4326');
    });

    it('应该正确添加采样点', () => {
        const project = new Project();
        const result = project.addPoint({ longitude: 116.39, latitude: 39.9, value: 10 });
        expect(result).toBe(true);
        expect(project.getPointCount()).toBe(1);
    });

    it('区域模式下超出边界的点应该被拒绝', () => {
        const project = new Project({
            sampling_mode: 'region',
            boundary_polygon: {
                type: 'Feature',
                geometry: {
                    type: 'Polygon',
                    coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]
                }
            }
        });

        // 在边界内
        expect(project.addPoint({ longitude: 5, latitude: 5, value: 1 })).toBe(true);
        // 在边界外
        expect(project.addPoint({ longitude: 50, latitude: 50, value: 2 })).toBe(false);
        expect(project.getPointCount()).toBe(1);
    });

    it('批量添加应该返回成功和失败计数', () => {
        const project = new Project();
        const result = project.addPoints([
            { longitude: 1, latitude: 1, value: 1 },
            { longitude: 2, latitude: 2, value: 2 },
            { longitude: 3, latitude: 3, value: 3 }
        ]);
        expect(result.success).toBe(3);
        expect(result.failed).toBe(0);
    });

    it('应该正确移除采样点', () => {
        const project = new Project();
        project.addPoint({ longitude: 1, latitude: 1, value: 1 });
        project.addPoint({ longitude: 2, latitude: 2, value: 2 });
        project.removePoint(0);
        expect(project.getPointCount()).toBe(1);
    });

    it('序列化和反序列化应该保持一致', () => {
        const project = new Project({ sampling_mode: 'region' });
        project.addPoint({ longitude: 5, latitude: 5, value: 10 });
        const json = project.toJSON();
        const restored = Project.fromJSON(json);
        expect(restored.sampling_mode).toBe('region');
        expect(restored.points.length).toBe(1);
    });

    it('validate 应该检测无效配置', () => {
        const project = new Project({ sampling_mode: 'invalid' });
        const result = project.validate();
        expect(result.valid).toBe(false);
        expect(result.errors.length).toBeGreaterThan(0);
    });

    it('validate 应该检测区域模式缺少边界', () => {
        const project = new Project({ sampling_mode: 'region' });
        const result = project.validate();
        expect(result.valid).toBe(false);
    });
});
