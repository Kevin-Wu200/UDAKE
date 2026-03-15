import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: ['./vitest.setup.js'],
        include: ['tests/**/*.test.{js,ts}'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html', 'lcov'],
            all: true,
            include: [
                'frontend/js/**/*.{js,ts}',
                'frontend/js/services/**/*.{js,ts}',
                'frontend/js/components/**/*.{js,ts}',
                'frontend/js/utils/**/*.{js,ts}',
                'frontend/js/models/**/*.{js,ts}',
                'frontend/js/config/**/*.{js,ts}',
                'frontend/js/store/**/*.{js,ts}'
            ],
            exclude: [
                // 第三方库
                'frontend/lib/**',
                'node_modules/**',

                // 第三方类型定义
                'frontend/types/**',

                // 测试辅助工具
                '**/MapEngineTestHelper.js',

                // 构建产物
                'frontend/dist/**',

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
