import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: [resolve(__dirname, 'vitest.setup.js')],
        include: ['tests/components/SpatiotemporalExplainPanel.test.ts'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html', 'lcov'],
            all: true,
            include: ['apps/frontend/js/components/SpatiotemporalExplainPanel.ts'],
            exclude: ['tests/**', 'node_modules/**', 'coverage/**'],
            thresholds: {
                lines: 70,
                functions: 70,
                branches: 50,
                statements: 70
            }
        }
    }
});
