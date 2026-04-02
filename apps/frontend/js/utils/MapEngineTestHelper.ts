/**
 * 地图引擎测试工具
 * 用于验证地图引擎切换功能的完整性
 */

/** 测试结果项 */
interface TestResult {
    test: string;
    status: 'passed' | 'failed';
    message: string;
}

/** 测试报告 */
interface TestReport {
    engine: string | null;
    timestamp: string;
    results: TestResult[];
    summary: {
        total: number;
        passed: number;
        failed: number;
    };
}

/** 采样点 */
interface SamplingPoint {
    x: number;
    y: number;
    value: number;
}

/** 地图适配器接口 */
interface MapAdapter {
    getView(): any;
    addMarker(point: SamplingPoint): Promise<void>;
    addPointsLayer(geojson: any, layerId: string): Promise<void>;
    toggleLayer(layerId: string, visible: boolean): void;
    setLayerOpacity(layerId: string, opacity: number): void;
    getSamplingPoints(): SamplingPoint[];
}

/** 地图配置模块 */
interface MapConfigModule {
    getProvider(): string;
}

/** ArcGIS 配置模块 */
interface ArcGISConfigModule {
    getConfig(): any;
}

/** 高德地图配置模块 */
interface AMapConfigModule {
    getConfig(): any;
}

/** 坐标转换器模块 */
interface CoordinateTransformerModule {
    isGeographic(x: number, y: number): boolean;
    wgs84ToWebMercator(lon: number, lat: number): { x: number; y: number };
}

export class MapEngineTestHelper {
    private testResults: TestResult[] = [];
    private currentEngine: string | null = null;

    constructor() {
        this.testResults = [];
        this.currentEngine = null;
    }

    /**
     * 初始化测试环境
     */
    async init(): Promise<this> {
        console.log('🧪 地图引擎测试工具已启动');

        // 检测当前地图引擎
        const { MapConfig } = await import('../config/map.config.js') as { MapConfig: MapConfigModule };
        this.currentEngine = MapConfig.getProvider();

        console.log(`📍 当前地图引擎: ${this.currentEngine}`);

        return this;
    }

    /**
     * 测试 1: 地图加载测试
     */
    async testMapLoading(adapter: MapAdapter): Promise<boolean> {
        const testName = '地图加载测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            const view = adapter.getView();

            // 检查地图视图是否存在
            if (!view) {
                throw new Error('地图视图未初始化');
            }

            // 检查地图容器
            const container = document.getElementById('viewDiv');
            if (!container) {
                throw new Error('地图容器不存在');
            }

            // 检查容器是否有内容
            if (container.children.length === 0) {
                throw new Error('地图容器为空');
            }

            this.logSuccess(testName, '地图加载成功');
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 2: 适配器接口完整性测试
     */
    async testAdapterInterface(adapter: MapAdapter): Promise<boolean> {
        const testName = '适配器接口完整性测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        const requiredMethods = [
            'initMap',
            'getView',
            'addPointsLayer',
            'addRasterLayer',
            'addMarker',
            'addPolygon',
            'toggleLayer',
            'setLayerOpacity',
            'removeLayer',
            'clearAllLayers',
            'zoomToLayer',
            'setClickHandler',
            'getSamplingPoints'
        ];

        try {
            const missingMethods: string[] = [];

            for (const method of requiredMethods) {
                if (typeof (adapter as any)[method] !== 'function') {
                    missingMethods.push(method);
                }
            }

            if (missingMethods.length > 0) {
                throw new Error(`缺少方法: ${missingMethods.join(', ')}`);
            }

            this.logSuccess(testName, `所有 ${requiredMethods.length} 个接口方法都已实现`);
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 3: 采样点添加测试
     */
    async testAddMarker(adapter: MapAdapter): Promise<boolean> {
        const testName = '采样点添加测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            const testPoint: SamplingPoint = {
                x: 139.767125,
                y: 35.681236,
                value: 100
            };

            await adapter.addMarker(testPoint);

            const points = adapter.getSamplingPoints();
            if (points.length === 0) {
                throw new Error('采样点未添加到数组');
            }

            const lastPoint = points[points.length - 1];
            if (lastPoint.x !== testPoint.x || lastPoint.y !== testPoint.y) {
                throw new Error('采样点坐标不匹配');
            }

            this.logSuccess(testName, '采样点添加成功');
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 4: GeoJSON 图层测试
     */
    async testGeoJSONLayer(adapter: MapAdapter): Promise<boolean> {
        const testName = 'GeoJSON 图层测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            const testGeoJSON = {
                type: 'FeatureCollection',
                features: [
                    {
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [139.767125, 35.681236]
                        },
                        properties: {
                            value: 100
                        }
                    }
                ]
            };

            await adapter.addPointsLayer(testGeoJSON, 'test-layer');

            this.logSuccess(testName, 'GeoJSON 图层加载成功');
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 5: 图层控制测试
     */
    async testLayerControl(adapter: MapAdapter): Promise<boolean> {
        const testName = '图层控制测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            // 先添加一个测试图层
            const testGeoJSON = {
                type: 'FeatureCollection',
                features: []
            };
            await adapter.addPointsLayer(testGeoJSON, 'control-test-layer');

            // 测试隐藏
            adapter.toggleLayer('control-test-layer', false);

            // 测试显示
            adapter.toggleLayer('control-test-layer', true);

            // 测试透明度
            adapter.setLayerOpacity('control-test-layer', 0.5);

            this.logSuccess(testName, '图层控制功能正常');
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 6: 坐标系统测试
     */
    async testCoordinateSystem(): Promise<boolean> {
        const testName = '坐标系统测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            const { CoordinateTransformer } = await import('../utils/coordinateTransformer.js') as { CoordinateTransformer: CoordinateTransformerModule };

            // 测试地理坐标检测
            const isGeo1 = CoordinateTransformer.isGeographic(139.767125, 35.681236);
            if (!isGeo1) {
                throw new Error('地理坐标检测失败');
            }

            const isGeo2 = CoordinateTransformer.isGeographic(15000000, 4000000);
            if (isGeo2) {
                throw new Error('投影坐标误判为地理坐标');
            }

            // 测试坐标转换
            const result = CoordinateTransformer.wgs84ToWebMercator(139.767125, 35.681236);
            if (!result.x || !result.y) {
                throw new Error('坐标转换失败');
            }

            this.logSuccess(testName, '坐标系统功能正常');
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 测试 7: 配置文件测试
     */
    async testConfiguration(): Promise<boolean> {
        const testName = '配置文件测试';
        console.log(`\n🔍 开始测试: ${testName}`);

        try {
            const { MapConfig } = await import('../config/map.config.js') as { MapConfig: MapConfigModule };

            const provider = MapConfig.getProvider();
            if (!provider || (provider !== 'arcgis' && provider !== 'amap')) {
                throw new Error('地图引擎配置无效');
            }

            if (provider === 'arcgis') {
                const { ArcGISConfig } = await import('../config/geoscene.config.js') as { ArcGISConfig: ArcGISConfigModule };
                const config = ArcGISConfig.getConfig();
                if (!config) {
                    throw new Error('ArcGIS 配置加载失败');
                }
            } else if (provider === 'amap') {
                // 高德地图配置直接导出函数，不需要 getConfig
                const amapConfig = await import('../config/amap.config.js');
                if (!amapConfig) {
                    throw new Error('高德地图配置加载失败');
                }
            }

            this.logSuccess(testName, `配置文件正常 (${provider} 模式)`);
            return true;
        } catch (error: any) {
            this.logError(testName, error.message);
            return false;
        }
    }

    /**
     * 运行所有测试
     */
    async runAllTests(adapter: MapAdapter): Promise<{ passed: number; failed: number; total: number; results: TestResult[] }> {
        console.log('\n' + '='.repeat(60));
        console.log('🚀 开始运行地图引擎测试套件');
        console.log('='.repeat(60));

        const tests = [
            () => this.testConfiguration(),
            () => this.testMapLoading(adapter),
            () => this.testAdapterInterface(adapter),
            () => this.testCoordinateSystem(),
            () => this.testAddMarker(adapter),
            () => this.testGeoJSONLayer(adapter),
            () => this.testLayerControl(adapter)
        ];

        let passed = 0;
        let failed = 0;

        for (const test of tests) {
            try {
                const result = await test();
                if (result) {
                    passed++;
                } else {
                    failed++;
                }
            } catch (error: any) {
                console.error('❌ 测试执行失败:', error);
                failed++;
            }
        }

        console.log('\n' + '='.repeat(60));
        console.log('📊 测试结果汇总');
        console.log('='.repeat(60));
        console.log(`✅ 通过: ${passed}`);
        console.log(`❌ 失败: ${failed}`);
        console.log(`📈 通过率: ${((passed / (passed + failed)) * 100).toFixed(1)}%`);
        console.log('='.repeat(60));

        return {
            passed,
            failed,
            total: passed + failed,
            results: this.testResults
        };
    }

    /**
     * 记录成功
     */
    private logSuccess(testName: string, message: string): void {
        console.log(`✅ ${testName}: ${message}`);
        this.testResults.push({
            test: testName,
            status: 'passed',
            message: message
        });
    }

    /**
     * 记录错误
     */
    private logError(testName: string, message: string): void {
        console.error(`❌ ${testName}: ${message}`);
        this.testResults.push({
            test: testName,
            status: 'failed',
            message: message
        });
    }

    /**
     * 生成测试报告
     */
    generateReport(): TestReport {
        const report: TestReport = {
            engine: this.currentEngine,
            timestamp: new Date().toISOString(),
            results: this.testResults,
            summary: {
                total: this.testResults.length,
                passed: this.testResults.filter(r => r.status === 'passed').length,
                failed: this.testResults.filter(r => r.status === 'failed').length
            }
        };

        console.log('\n📄 测试报告:');
        console.log(JSON.stringify(report, null, 2));

        return report;
    }
}

// 导出便捷函数
export async function runMapEngineTests(adapter: MapAdapter): Promise<{ passed: number; failed: number; total: number; results: TestResult[] }> {
    const tester = new MapEngineTestHelper();
    await tester.init();
    const results = await tester.runAllTests(adapter);
    tester.generateReport();
    return results;
}
