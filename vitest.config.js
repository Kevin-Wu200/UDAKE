import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: ['./vitest.setup.js'],
        include: ['tests/**/*.test.{js,ts}'],
        exclude: ['tests/e2e/**'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html', 'lcov'],
            all: true,
            include: [
                'apps/frontend/js/**/*.{js,ts}',
                'apps/frontend/js/services/**/*.{js,ts}',
                'apps/frontend/js/components/**/*.{js,ts}',
                'apps/frontend/js/utils/**/*.{js,ts}',
                'apps/frontend/js/models/**/*.{js,ts}',
                'apps/frontend/js/config/**/*.{js,ts}',
                'apps/frontend/js/store/**/*.{js,ts}'
            ],
            exclude: [
                // 第三方库
                'apps/frontend/lib/**',
                'node_modules/**',

                // 第三方类型定义
                'apps/frontend/types/**',

                // 测试辅助工具
                '**/MapEngineTestHelper.js',

                // 构建产物
                'apps/frontend/dist/**',

                // 测试文件
                'tests/**',

                // 配置文件
                '**/*.config.*',

                // Mock 数据
                '**/mockData',

                // 覆盖率报告目录
                'coverage/**',

                // 临时文件
                '**/*.tmp',
                '**/*.bak'
            ],
            thresholds: {
                lines: 80,
                functions: 80,
                branches: 80,
                statements: 80
            }
        }
    }
});
