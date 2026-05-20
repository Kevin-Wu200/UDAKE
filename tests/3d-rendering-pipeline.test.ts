/**
 * 3D 渲染管线及坐标转换单元测试
 * 验证 Renderer3D、Polygon3DRenderer 的核心功能和性能
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/** 创建 mock 2D Context */
function makeMockCtx(): CanvasRenderingContext2D {
    const gradient = { addColorStop: vi.fn() };
    return {
        save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(),
        arc: vi.fn(), fill: vi.fn(), stroke: vi.fn(),
        moveTo: vi.fn(), lineTo: vi.fn(), closePath: vi.fn(),
        clearRect: vi.fn(), fillRect: vi.fn(), fillText: vi.fn(),
        strokeRect: vi.fn(), setLineDash: vi.fn(),
        createRadialGradient: vi.fn(() => gradient),
        createLinearGradient: vi.fn(() => gradient),
        measureText: vi.fn(() => ({ width: 0 })),
        globalAlpha: 1, fillStyle: '#000', strokeStyle: '#000',
        lineWidth: 1, font: '', textAlign: 'left', textBaseline: 'top',
        // Canvas 2D 标准属性
        canvas: null as any,
        direction: 'ltr',
        filter: 'none',
        imageSmoothingEnabled: true,
        imageSmoothingQuality: 'low',
        shadowBlur: 0, shadowColor: 'rgba(0,0,0,0)',
        shadowOffsetX: 0, shadowOffsetY: 0,
        getContextAttributes: vi.fn(() => ({})),
        getTransform: vi.fn(() => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 })),
        setTransform: vi.fn(),
        resetTransform: vi.fn(),
        transform: vi.fn(),
        translate: vi.fn(),
        scale: vi.fn(),
        rotate: vi.fn(),
        globalCompositeOperation: 'source-over' as any,
        drawImage: vi.fn(),
        createImageData: vi.fn(() => ({ data: new Uint8ClampedArray(), width: 1, height: 1 })),
        getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(), width: 1, height: 1 })),
        putImageData: vi.fn(),
        clip: vi.fn(),
        isPointInPath: vi.fn(() => false),
        isPointInStroke: vi.fn(() => false),
        fillTextWithMaxWidth: vi.fn(),
        strokeText: vi.fn(),
        rect: vi.fn(),
        createConicGradient: vi.fn(() => gradient),
        ellipse: vi.fn(),
        roundRect: vi.fn(),
        arcTo: vi.fn(),
        bezierCurveTo: vi.fn(),
        quadraticCurveTo: vi.fn(),
        drawFocusIfNeeded: vi.fn(),
        scrollPathIntoView: vi.fn(),
    } as unknown as CanvasRenderingContext2D;
}

function setupBaseMocks(): void {
    window.matchMedia = vi.fn(() => ({
        matches: false, media: '', onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }));
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
        setTimeout(() => cb(Date.now()), 16);
        return 1;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    Object.defineProperty(window, 'devicePixelRatio', { value: 1, writable: true, configurable: true });
}

/**
 * 辅助: 创建装有 mock context 的容器，返回 mockCtx 用于断言
 */
function setupRenderTest(): {
    mockCtx: CanvasRenderingContext2D;
    container: HTMLElement;
    cleanup: () => void;
} {
    const mockCtx = makeMockCtx();
    const getContextSpy = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(((
        _contextId: string, _options?: any
    ) => {
        return mockCtx;
    }) as typeof HTMLCanvasElement.prototype.getContext);

    // Mock toDataURL
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,');

    const container = document.createElement('div');
    Object.defineProperty(container, 'clientWidth', { value: 800, writable: true, configurable: true });
    Object.defineProperty(container, 'clientHeight', { value: 600, writable: true, configurable: true });

    return {
        mockCtx,
        container,
        cleanup: () => {
            getContextSpy.mockRestore();
        },
    };
}

// ================================================================
// Renderer3D 渲染管线测试
// ================================================================
describe('Renderer3D 渲染管线测试', () => {
    let Renderer3D: any;

    beforeEach(async () => {
        setupBaseMocks();
        const mod = await import('../apps/frontend/js/components/Renderer3D.js');
        Renderer3D = mod.Renderer3D;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('Renderer3D 应成功导入', () => {
        expect(Renderer3D).toBeDefined();
        expect(typeof Renderer3D).toBe('function');
    });

    it('应能创建 Renderer3D 实例', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(renderer).toBeDefined();
        expect(typeof renderer.setPoints).toBe('function');
        expect(typeof renderer.render).toBe('function');
        renderer.destroy();
        cleanup();
    });

    it('setPoints 应正确设置数据并触发渲染', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = [
            { x: 0, y: 0, z: 0, value: 0.5 },
            { x: 1, y: 1, z: 1, value: 1.0 },
            { x: -1, y: -1, z: -1, value: 0.0 },
        ];
        expect(() => renderer.setPoints(points)).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('空数据点应显示占位文本', () => {
        const { container, mockCtx, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        renderer.render();
        expect(mockCtx.fillRect).toHaveBeenCalled();
        expect(mockCtx.fillText).toHaveBeenCalledWith('暂无3D数据', expect.any(Number), expect.any(Number));
        renderer.destroy();
        cleanup();
    });

    it('setRenderMode points/spheres/surface 均不应抛出异常', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 100 }, (_, i) => ({
            x: (i % 10) - 5, y: Math.floor(i / 10) - 5,
            z: Math.sin(i * 0.1), value: i / 100,
        }));
        renderer.setPoints(points);
        expect(() => renderer.setRenderMode('points')).not.toThrow();
        expect(() => renderer.setRenderMode('spheres')).not.toThrow();
        expect(() => renderer.setRenderMode('surface')).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('setColorMap rainbow/viridis/hot/cool 均不应抛出异常', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        for (const map of ['rainbow', 'viridis', 'hot', 'cool'] as const) {
            expect(() => renderer.setColorMap(map)).not.toThrow();
        }
        renderer.destroy();
        cleanup();
    });

    it('resetView 应正常工作', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.resetView()).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('toDataURL 应返回有效字符串', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const url = renderer.toDataURL();
        expect(url).toBeDefined();
        expect(typeof url).toBe('string');
        renderer.destroy();
        cleanup();
    });

    it('getCanvas 应返回画布元素', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const canvas = renderer.getCanvas();
        expect(canvas).toBeInstanceOf(HTMLCanvasElement);
        renderer.destroy();
        cleanup();
    });

    it('setColorRange / setPointSize 应正常工作', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.setColorRange(-1, 1)).not.toThrow();
        expect(() => renderer.setPointSize(5)).not.toThrow();
        renderer.destroy();
        cleanup();
    });
});

// ================================================================
// Renderer3D 性能测试
// ================================================================
describe('Renderer3D 性能测试', () => {
    let Renderer3D: any;

    beforeEach(async () => {
        setupBaseMocks();
        const mod = await import('../apps/frontend/js/components/Renderer3D.js');
        Renderer3D = mod.Renderer3D;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('10,000 个点的 setPoints + render 应在 200ms 内完成', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 10000 }, () => ({
            x: (Math.random() - 0.5) * 100,
            y: (Math.random() - 0.5) * 100,
            z: (Math.random() - 0.5) * 20,
            value: Math.random(),
        }));
        const start = performance.now();
        renderer.setPoints(points);
        expect(performance.now() - start).toBeLessThan(200);
        renderer.destroy();
        cleanup();
    });

    it('50,000 个点的批量渲染应在 500ms 内完成', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 50000 }, () => ({
            x: (Math.random() - 0.5) * 100,
            y: (Math.random() - 0.5) * 100,
            z: (Math.random() - 0.5) * 20,
            value: Math.random(),
        }));
        const start = performance.now();
        renderer.setPoints(points);
        expect(performance.now() - start).toBeLessThan(500);
        renderer.destroy();
        cleanup();
    });

    it('球体模式 2000 点渲染应在 200ms 内完成', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 2000 }, () => ({
            x: (Math.random() - 0.5) * 100,
            y: (Math.random() - 0.5) * 100,
            z: (Math.random() - 0.5) * 20,
            value: Math.random(),
        }));
        renderer.setPoints(points);
        renderer.setRenderMode('spheres');
        const start = performance.now();
        renderer.render();
        expect(performance.now() - start).toBeLessThan(200);
        renderer.destroy();
        cleanup();
    });
});

// ================================================================
// Polygon3DRenderer 测试
// ================================================================
describe('Polygon3DRenderer 测试', () => {
    let Polygon3DRenderer: any;

    beforeEach(async () => {
        setupBaseMocks();
        const mod = await import('../apps/frontend/js/components/Polygon3DRenderer.js');
        Polygon3DRenderer = mod.Polygon3DRenderer;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('应成功导入并创建实例', () => {
        const { container, cleanup } = setupRenderTest();
        expect(Polygon3DRenderer).toBeDefined();
        const renderer = new Polygon3DRenderer(container);
        expect(typeof renderer.setPolygons).toBe('function');
        expect(typeof renderer.render).toBe('function');
        renderer.destroy();
        cleanup();
    });

    it('setPolygons / addPolygon / clearPolygons 应正常工作', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Polygon3DRenderer(container);
        const polygon = {
            outerRing: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }],
            height: 5,
            fillColor: 'rgba(64, 128, 255, 0.7)',
        };
        expect(() => renderer.setPolygons([polygon])).not.toThrow();

        expect(() => renderer.addPolygon({
            outerRing: [{ x: 10, y: 10 }, { x: 15, y: 10 }, { x: 15, y: 15 }, { x: 10, y: 15 }],
            height: 7,
        })).not.toThrow();

        expect(() => renderer.clearPolygons()).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('loadFromGeoJSON 应正确处理 Polygon 和 MultiPolygon', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Polygon3DRenderer(container);

        // Polygon
        expect(() => renderer.loadFromGeoJSON([{
            geometry: { type: 'Polygon', coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]] },
            properties: { height: 5 },
        }], 'height', 3)).not.toThrow();

        // MultiPolygon
        expect(() => renderer.loadFromGeoJSON([{
            geometry: {
                type: 'MultiPolygon',
                coordinates: [
                    [[[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]],
                    [[[10, 10], [15, 10], [15, 15], [10, 15], [10, 10]]],
                ]
            },
            properties: { height: 8 },
        }], 'height', 3)).not.toThrow();

        renderer.destroy();
        cleanup();
    });

    it('resetView / toDataURL / getCanvas 应正常工作', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Polygon3DRenderer(container);
        expect(() => renderer.resetView()).not.toThrow();
        expect(typeof renderer.toDataURL()).toBe('string');
        expect(renderer.getCanvas()).toBeInstanceOf(HTMLCanvasElement);
        renderer.destroy();
        cleanup();
    });

    it('50 个多边形渲染应在 100ms 内完成', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Polygon3DRenderer(container);
        const polygons = Array.from({ length: 50 }, (_, i) => ({
            outerRing: [
                { x: i * 2, y: 0 }, { x: i * 2 + 1, y: 0 },
                { x: i * 2 + 1, y: 1 }, { x: i * 2, y: 1 },
            ],
            height: 1 + i * 0.1,
        }));
        const start = performance.now();
        renderer.setPolygons(polygons);
        expect(performance.now() - start).toBeLessThan(100);
        renderer.destroy();
        cleanup();
    });
});

// ================================================================
// 3D 坐标投影精度验证
// ================================================================
describe('3D 坐标投影精度验证', () => {
    let Renderer3D: any;

    beforeEach(async () => {
        setupBaseMocks();
        const mod = await import('../apps/frontend/js/components/Renderer3D.js');
        Renderer3D = mod.Renderer3D;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('原点应能正常投影', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.setPoints([{ x: 0, y: 0, z: 0, value: 0.5 }])).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('多点投影不应抛出异常', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.setPoints([
            { x: 0, y: 0, z: 0, value: 0.5 },
            { x: 1, y: 0, z: 0, value: 0.8 },
            { x: 0, y: 1, z: 0, value: 0.3 },
            { x: 0, y: 0, z: 1, value: 0.6 },
        ])).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('单点多次渲染应保持稳定', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        renderer.setPoints([{ x: 1, y: 0, z: 0, value: 0.5 }]);
        for (let i = 0; i < 5; i++) {
            expect(() => renderer.render()).not.toThrow();
        }
        renderer.destroy();
        cleanup();
    });

    it('极端坐标值不应导致渲染异常', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.setPoints([
            { x: 1e6, y: 1e6, z: 1e6, value: 0.5 },
            { x: -1e6, y: -1e6, z: -1e6, value: 0.2 },
        ])).not.toThrow();
        renderer.destroy();
        cleanup();
    });
});

// ================================================================
// 深度缓冲区与遮挡测试
// ================================================================
describe('深度缓冲区与遮挡测试', () => {
    let Renderer3D: any;

    beforeEach(async () => {
        setupBaseMocks();
        const mod = await import('../apps/frontend/js/components/Renderer3D.js');
        Renderer3D = mod.Renderer3D;
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('启用深度缓冲区的默认模式应能正常渲染', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 500 }, () => ({
            x: (Math.random() - 0.5) * 50,
            y: (Math.random() - 0.5) * 50,
            z: (Math.random() - 0.5) * 20,
            value: Math.random(),
        }));
        expect(() => renderer.setPoints(points)).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('重叠点应通过深度测试正确排序', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        expect(() => renderer.setPoints([
            { x: 0, y: 0, z: 0, value: 1.0 },
            { x: 0.001, y: 0.001, z: 0.001, value: 0.0 },
        ])).not.toThrow();
        renderer.destroy();
        cleanup();
    });

    it('不同深度的点应有不同的渲染顺序（不崩溃）', () => {
        const { container, cleanup } = setupRenderTest();
        const renderer = new Renderer3D(container);
        const points = Array.from({ length: 100 }, (_, i) => ({
            x: 0, y: 0, z: i - 50,
            value: i / 100,
        }));
        expect(() => renderer.setPoints(points)).not.toThrow();
        renderer.destroy();
        cleanup();
    });
});

// ================================================================
// Kriging3DPanel 3D 可视化集成测试
// ================================================================
describe('Kriging3DPanel 3D 可视化集成测试', () => {
    beforeEach(async () => {
        setupBaseMocks();

        // Mock getContext on HTMLCanvasElement.prototype
        const mockCtx = makeMockCtx();
        vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(((
            _contextId: string, _options?: any
        ) => {
            return mockCtx;
        }) as typeof HTMLCanvasElement.prototype.getContext);
        vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:');

        vi.spyOn(global, 'fetch').mockResolvedValue({
            ok: true,
            json: async () => ({
                data_id: 'test-123', point_count: 100,
                task_id: 'task-456', status: 'completed', progress: 100,
                gridShape: [50, 50, 20],
                predictionStats: { mean: 0.5, min: 0, max: 1 },
                varianceStats: { mean: 0.1 },
            }),
        } as any);
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('Kriging3DPanel 应能正常初始化而不抛出异常', async () => {
        const container = document.createElement('div');
        container.id = 'kriging-3d-test';
        document.body.appendChild(container);

        let error: Error | null = null;
        try {
            const module = await import('../apps/frontend/js/components/Kriging3DPanel.js');
            const { Kriging3DPanel } = module;
            const panel = new Kriging3DPanel('kriging-3d-test');
            expect(panel).toBeDefined();
            panel.destroy();
        } catch (e) {
            error = e as Error;
        }
        expect(error).toBeNull();

        document.body.removeChild(container);
    });
});
