import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        include: ['tests/**/*.test.{js,ts}'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html'],
            include: ['frontend/js/**/*.{js,ts}'],
            exclude: [
                'frontend/js/config/**',
                'frontend/lib/**',
                'frontend/js/map/**',
                'frontend/js/adapters/**',
                'frontend/js/sampling/**',
                'frontend/js/managers/**',
                '**/主程序.js',
                '**/图层管理.js',
                '**/任务轮询.js',
                '**/单点采样输入.js',
                '**/地图初始化.js',
                '**/地图引擎集成.js',
                '**/坐标系统信息.js',
                '**/CoordinateParser.js',
                '**/coordinateTransformer.js',
                '**/GeoUtils.js',
                '**/fieldMatcher.js',
                '**/geojsonParser.js',
                '**/locationPermissionManager.js',
                '**/MapEngineTestHelper.js',
                '**/ZoomControl.js',
                '**/ErrorMonitor.ts'
            ],
            thresholds: {
                lines: 60,
                functions: 60,
                branches: 50,
                statements: 60
            }
        }
    }
});
