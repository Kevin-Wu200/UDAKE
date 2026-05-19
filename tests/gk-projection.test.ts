/**
 * GK 投影精度测试
 * 验证高斯-克吕格投影在局部区域的坐标转换精度
 */
import { describe, it, expect } from 'vitest';
import {
    GKProjectionService,
    calculateBandNumber,
    calculateCentralMeridian
} from '../apps/frontend/js/map/canvas/GKProjectionService';

describe('GKProjectionService', () => {
    // 使用北京地区（117E, 39N）的 3 度带初始化
    const service = new GKProjectionService({
        centralMeridian: 117,
        bandType: '3-degree'
    });

    describe('带号计算', () => {
        it('应该正确计算 3 度带带号（北京 117E → 39）', () => {
            const band = calculateBandNumber(117, '3-degree');
            expect(band).toBe(39); // (117 - 1.5) / 3 = 38.5 → 39
        });

        it('应该正确计算 6 度带带号（北京 117E → 20）', () => {
            const band = calculateBandNumber(117, '6-degree');
            expect(band).toBe(20); // (117 + 3) / 6 = 20
        });

        it('应该正确计算 3 度带带号（东经 120E → 40）', () => {
            const band = calculateBandNumber(120, '3-degree');
            expect(band).toBe(40); // (120 - 1.5) / 3 = 39.5 → 40
        });

        it('应该正确计算 6 度带带号（东经 120E → 21）', () => {
            const band = calculateBandNumber(120, '6-degree');
            expect(band).toBe(21); // (120 + 3) / 6 = 20.5 → 21
        });
    });

    describe('中央经线自动计算', () => {
        it('3度带：116.39 → 117', () => {
            const cm = calculateCentralMeridian(116.39, '3-degree');
            expect(cm).toBe(117);
        });

        it('3度带：120.5 → 120', () => {
            const cm = calculateCentralMeridian(120.5, '3-degree');
            expect(cm).toBe(120);
        });

        it('6度带：116.39 → 117', () => {
            const cm = calculateCentralMeridian(116.39, '6-degree');
            expect(cm).toBe(117);
        });

        it('6度带：120.5 → 123', () => {
            const cm = calculateCentralMeridian(120.5, '6-degree');
            expect(cm).toBe(123);
        });
    });

    describe('正向投影 (经纬度 → GK)', () => {
        it('北京天安门 (116.39, 39.9) 应投影到合理的 GK 坐标', () => {
            const gk = service.toGK(116.39, 39.9);
            // 中央经线 117E，天安门在 116.39E（西侧 0.61 度），所以东向应略小于 500000
            expect(gk.x).toBeLessThan(500000);
            expect(gk.x).toBeGreaterThan(440000);
            // 北半球，北向应为正
            expect(gk.y).toBeGreaterThan(0);
        });

        it('中央经线上的点 (117, 0) 东向应为 500000', () => {
            const gk = service.toGK(117, 0);
            expect(gk.x).toBeCloseTo(500000, -1); // 精度 10 米
            expect(gk.y).toBeCloseTo(0, -1);
        });

        it('赤道上的点 (117, 0) 北向应为 0', () => {
            const gk = service.toGK(117, 0);
            expect(Math.abs(gk.y)).toBeLessThan(10); // 10 米内
        });
    });

    describe('反向投影 (GK → 经纬度)', () => {
        it('应能从 GK 坐标恢复到原始经纬度', () => {
            const origLng = 116.39;
            const origLat = 39.9;
            const gk = service.toGK(origLng, origLat);
            const [lng, lat] = service.fromGK(gk.x, gk.y);

            // 往返精度应在厘米级（1e-7 度 ≈ 1cm）
            expect(Math.abs(lng - origLng)).toBeLessThan(1e-6);
            expect(Math.abs(lat - origLat)).toBeLessThan(1e-6);
        });

        it('多点往返精度测试', () => {
            const testPoints = [
                [116.39, 39.9],   // 北京
                [121.47, 31.23],  // 上海
                [104.06, 30.67],  // 成都
                [113.26, 23.13],  // 广州
                [120.15, 30.28],  // 杭州
            ];

            for (const [lng, lat] of testPoints) {
                const gk = service.toGK(lng, lat);
                const [backLng, backLat] = service.fromGK(gk.x, gk.y);

                expect(Math.abs(backLng - lng)).toBeLessThan(1e-6);
                expect(Math.abs(backLat - lat)).toBeLessThan(1e-6);
            }
        });
    });

    describe('自动配置 (autoConfig)', () => {
        it('应能根据中心经度自动切换中央经线', () => {
            const autoService = new GKProjectionService({ bandType: '3-degree' });
            autoService.autoConfig(120.5);

            expect(autoService.getCentralMeridian()).toBe(120);
            expect(autoService.getBandNumber()).toBe(40);
        });

        it('相同中央经线不应重复配置', () => {
            const autoService = new GKProjectionService({ bandType: '3-degree' });
            autoService.autoConfig(116.39);
            const cm1 = autoService.getCentralMeridian();

            autoService.autoConfig(116.5);
            const cm2 = autoService.getCentralMeridian();

            // 同属 117E 带，不应变化
            expect(cm1).toBe(117);
            expect(cm2).toBe(117);
        });
    });

    describe('像素坐标转换', () => {
        it('GK → 像素 → GK 往返应保持一致性', () => {
            const gkX = 500000;
            const gkY = 4500000;
            const offsetX = 490000;
            const offsetY = 4400000;
            const scale = 0.001; // 1mm/px
            const canvasHeight = 600;

            const [px, py] = service.gkToPixel(gkX, gkY, offsetX, offsetY, scale, canvasHeight);
            const result = service.pixelToGK(px, py, offsetX, offsetY, scale, canvasHeight);

            expect(Math.abs(result.x - gkX)).toBeLessThan(1e-3);
            expect(Math.abs(result.y - gkY)).toBeLessThan(1e-3);
        });

        it('经纬度 → 像素 → 经纬度 往返一致性', () => {
            const lng = 116.39;
            const lat = 39.9;
            const offsetX = 450000;
            const offsetY = 4400000;
            const scale = 0.001;
            const canvasHeight = 600;

            const [px, py] = service.lngLatToPixel(lng, lat, offsetX, offsetY, scale, canvasHeight);
            const [backLng, backLat] = service.pixelToLngLat(px, py, offsetX, offsetY, scale, canvasHeight);

            expect(Math.abs(backLng - lng)).toBeLessThan(1e-6);
            expect(Math.abs(backLat - lat)).toBeLessThan(1e-6);
        });
    });

    describe('距离计算', () => {
        it('两点间水平距离计算', () => {
            const p1 = service.toGK(116.39, 39.90);
            const p2 = service.toGK(116.40, 39.90);

            const dist = service.distanceBetween(p1, p2);
            // 约 854 米（1 度 ≈ 111km * cos(40°) ≈ 85km，0.01 度 ≈ 850m）
            expect(dist).toBeGreaterThan(800);
            expect(dist).toBeLessThan(900);
        });
    });

    describe('fitToGKBounds', () => {
        it('应返回合适的缩放和偏移以使边界适配画布', () => {
            const bounds = { minX: 450000, minY: 4400000, maxX: 460000, maxY: 4410000 };
            const result = service.fitToGKBounds(bounds, 800, 600);

            expect(result.scale).toBeGreaterThan(0);
            expect(result.offsetX).toBeLessThan(bounds.minX);
            expect(result.offsetY).toBeLessThan(bounds.minY);
        });
    });
});
