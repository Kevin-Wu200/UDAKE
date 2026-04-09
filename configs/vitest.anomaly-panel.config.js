import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: [resolve(__dirname, 'vitest.setup.js')],
        include: ['tests/components/AnomalyDetectionPanel.test.ts'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html', 'lcov'],
            all: true,
            include: ['apps/frontend/js/components/AnomalyDetectionPanel.ts'],
            exclude: ['tests/**', 'node_modules/**', 'coverage/**'],
            thresholds: {
                lines: 85,
                statements: 85,
                functions: 85,
                branches: 60
            }
        }
    }
});
