import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { DataComparison } from '../frontend/js/utils/DataComparison.js';

describe('DataComparison', () => {
    let comparison;
    let datasetA;
    let datasetB;

    beforeEach(() => {
        comparison = new DataComparison();

        // Mock document
        global.document = {
            createElement: vi.fn((tag) => ({
                className: '',
                innerHTML: '',
                querySelector: vi.fn(() => ({
                    addEventListener: vi.fn(),
                    value: '',
                    disabled: true
                })),
                appendChild: vi.fn()
            }))
        };

        // 创建测试数据集
        datasetA = {
            name: 'Dataset A',
            points: [
                { x: 1, y: 1, value: 10 },
                { x: 2, y: 2, value: 20 },
                { x: 3, y: 3, value: 30 }
            ]
        };

        datasetB = {
            name: 'Dataset B',
            points: [
                { x: 1, y: 1, value: 12 },
                { x: 2, y: 2, value: 22 },
                { x: 4, y: 4, value: 40 }
            ]
        };
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('数据集设置', () => {
        it('应该成功设置两个数据集', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result).not.toBeNull();
            expect(result?.fieldStats).toHaveProperty('value');
        });

        it('应该处理空数据集', () => {
            comparison.setDatasets({ name: 'A', points: [] }, { name: 'B', points: [] });

            const result = comparison.compare();

            expect(result).not.toBeNull();
            expect(result?.matchedPoints).toBe(0);
            expect(result?.unmatchedA).toBe(0);
            expect(result?.unmatchedB).toBe(0);
        });

        it('应该处理只有一个数据集的情况', () => {
            comparison.setDatasets(datasetA, null);

            const result = comparison.compare();

            expect(result).toBeNull();
        });

        it('应该处理两个数据集都为null的情况', () => {
            comparison.setDatasets(null, null);

            const result = comparison.compare();

            expect(result).toBeNull();
        });
    });

    describe('统计计算', () => {
        it('应该正确计算最小值', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.min).toBe(10);
            expect(result?.fieldStats.value.datasetB.min).toBe(12);
        });

        it('应该正确计算最大值', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.max).toBe(30);
            expect(result?.fieldStats.value.datasetB.max).toBe(40);
        });

        it('应该正确计算均值', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.mean).toBeCloseTo(20);
            expect(result?.fieldStats.value.datasetB.mean).toBeCloseTo(24.6667, 3);
        });

        it('应该正确计算标准差', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.std).toBeGreaterThan(0);
            expect(result?.fieldStats.value.datasetB.std).toBeGreaterThan(0);
        });

        it('应该处理包含NaN值的数据', () => {
            const datasetWithNaN = {
                name: 'NaN Dataset',
                points: [
                    { x: 1, y: 1, value: NaN },
                    { x: 2, y: 2, value: 20 },
                    { x: 3, y: 3, value: 30 }
                ]
            };

            comparison.setDatasets(datasetWithNaN, datasetA);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该处理非数值数据', () => {
            const datasetWithStrings = {
                name: 'String Dataset',
                points: [
                    { x: 1, y: 1, value: '10' },
                    { x: 2, y: 2, value: '20' }
                ]
            };

            comparison.setDatasets(datasetWithStrings, datasetA);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该正确计算差异', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.diff.meanDiff).toBeCloseTo(4.6667, 3);
        });

        it('应该正确计算百分比变化', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.fieldStats.value.diff.percentChange).toBeCloseTo(23.3333, 3);
        });

        it('应该处理均值为零的情况', () => {
            const zeroMeanDataset = {
                name: 'Zero Mean',
                points: [
                    { x: 1, y: 1, value: 0 },
                    { x: 2, y: 2, value: 0 }
                ]
            };

            comparison.setDatasets(zeroMeanDataset, datasetA);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });
    });

    describe('匹配点识别', () => {
        it('应该正确识别完全匹配的点', () => {
            const matchedDataset = {
                name: 'Matched Dataset',
                points: [
                    { x: 1, y: 1, value: 10 },
                    { x: 2, y: 2, value: 20 }
                ]
            };

            comparison.setDatasets(matchedDataset, {
                name: 'Matched B',
                points: [
                    { x: 1, y: 1, value: 12 },
                    { x: 2, y: 2, value: 22 }
                ]
            });

            const result = comparison.compare();

            expect(result?.matchedPoints).toBe(2);
        });

        it('应该识别部分匹配的点', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.matchedPoints).toBe(2);
        });

        it('应该识别不匹配的点', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result?.unmatchedA).toBe(1); // { x: 3, y: 3 }
            expect(result?.unmatchedB).toBe(1); // { x: 4, y: 4 }
        });

        it('应该使用距离阈值进行匹配', () => {
            const closeDataset = {
                name: 'Close Dataset',
                points: [
                    { x: 1.00005, y: 1.00005, value: 10 }
                ]
            };

            comparison.setDatasets(closeDataset, {
                name: 'Close B',
                points: [
                    { x: 1, y: 1, value: 12 }
                ]
            });

            const result = comparison.compare();

            expect(result?.matchedPoints).toBe(1);
        });

        it('应该拒绝超出阈值的点', () => {
            const farDataset = {
                name: 'Far Dataset',
                points: [
                    { x: 1.0002, y: 1.0002, value: 10 }
                ]
            };

            comparison.setDatasets(farDataset, {
                name: 'Far B',
                points: [
                    { x: 1, y: 1, value: 12 }
                ]
            });

            const result = comparison.compare();

            expect(result?.matchedPoints).toBe(0);
        });

        it('应该处理空数据集的匹配', () => {
            comparison.setDatasets(
                { name: 'Empty A', points: [] },
                { name: 'Empty B', points: [] }
            );

            const result = comparison.compare();

            expect(result?.matchedPoints).toBe(0);
        });
    });

    describe('报告生成', () => {
        it('应该生成有效的HTML报告', () => {
            comparison.setDatasets(datasetA, datasetB);

            const report = comparison.generateReport();

            expect(report).toContain('<table');
            expect(report).toContain('Dataset A');
            expect(report).toContain('Dataset B');
        });

        it('应该在未设置数据集时返回错误消息', () => {
            const report = comparison.generateReport();

            expect(report).toContain('无法生成对比报告');
        });

        it('应该包含所有统计指标', () => {
            comparison.setDatasets(datasetA, datasetB);

            const report = comparison.generateReport();

            expect(report).toContain('最小值');
            expect(report).toContain('最大值');
            expect(report).toContain('均值');
            expect(report).toContain('标准差');
        });

        it('应该显示正确的CSS类名表示差异方向', () => {
            comparison.setDatasets(datasetA, datasetB);

            const report = comparison.generateReport();

            expect(report).toContain('diff-positive'); // datasetB 的均值更大
        });

        it('应该处理负差异', () => {
            comparison.setDatasets(datasetB, datasetA);

            const report = comparison.generateReport();

            expect(report).toContain('diff-negative');
        });

        it('应该处理零差异', () => {
            const sameDataset = {
                name: 'Same Dataset',
                points: [
                    { x: 1, y: 1, value: 10 },
                    { x: 2, y: 2, value: 20 }
                ]
            };

            comparison.setDatasets(sameDataset, sameDataset);

            const report = comparison.generateReport();

            expect(report).toContain('diff-neutral');
        });

        it('应该显示匹配点信息', () => {
            comparison.setDatasets(datasetA, datasetB);

            const report = comparison.generateReport();

            expect(report).toContain('匹配点');
            expect(report).toContain('2 个重合点');
        });

        it('应该支持自定义字段', () => {
            const customFieldDataset = {
                name: 'Custom Field',
                points: [
                    { x: 1, y: 1, customValue: 100 },
                    { x: 2, y: 2, customValue: 200 }
                ]
            };

            comparison.setDatasets(customFieldDataset, customFieldDataset);

            const report = comparison.generateReport('customValue');

            expect(report).toContain('100.0000');
            expect(report).toContain('200.0000');
        });
    });

    describe('面板创建', () => {
        it('应该创建有效的面板元素', () => {
            const panel = comparison.createPanel();

            expect(panel).toHaveProperty('className');
            expect(panel).toHaveProperty('innerHTML');
        });

        it('应该包含必要的UI元素', () => {
            const panel = comparison.createPanel();

            expect(panel.innerHTML).toContain('数据对比');
            expect(panel.innerHTML).toContain('compare-dataset-a');
            expect(panel.innerHTML).toContain('compare-dataset-b');
            expect(panel.innerHTML).toContain('compare-btn');
        });

        it('应该正确设置面板类名', () => {
            const panel = comparison.createPanel();

            expect(panel.className).toBe('panel');
        });

        it('应该包含结果显示区域', () => {
            const panel = comparison.createPanel();

            expect(panel.innerHTML).toContain('compare-result');
        });
    });

    describe('边界情况', () => {
        it('应该处理大量数据点', () => {
            const largeDatasetA = {
                name: 'Large A',
                points: Array.from({ length: 10000 }, (_, i) => ({
                    x: i,
                    y: i,
                    value: i * 10
                }))
            };

            const largeDatasetB = {
                name: 'Large B',
                points: Array.from({ length: 10000 }, (_, i) => ({
                    x: i,
                    y: i,
                    value: i * 10 + 5
                }))
            };

            comparison.setDatasets(largeDatasetA, largeDatasetB);

            const result = comparison.compare();

            expect(result).not.toBeNull();
            expect(result?.matchedPoints).toBe(10000);
        });

        it('应该处理极端数值', () => {
            const extremeDataset = {
                name: 'Extreme',
                points: [
                    { x: 1, y: 1, value: Number.MAX_VALUE },
                    { x: 2, y: 2, value: -Number.MAX_VALUE },
                    { x: 3, y: 3, value: 0 }
                ]
            };

            comparison.setDatasets(extremeDataset, extremeDataset);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该处理重复坐标', () => {
            const duplicateDataset = {
                name: 'Duplicate',
                points: [
                    { x: 1, y: 1, value: 10 },
                    { x: 1, y: 1, value: 20 },
                    { x: 2, y: 2, value: 30 }
                ]
            };

            comparison.setDatasets(duplicateDataset, duplicateDataset);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该处理负坐标', () => {
            const negativeDataset = {
                name: 'Negative',
                points: [
                    { x: -1, y: -1, value: 10 },
                    { x: -2, y: -2, value: 20 }
                ]
            };

            comparison.setDatasets(negativeDataset, negativeDataset);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该处理小数坐标', () => {
            const decimalDataset = {
                name: 'Decimal',
                points: [
                    { x: 1.123456, y: 2.234567, value: 10 },
                    { x: 3.345678, y: 4.456789, value: 20 }
                ]
            };

            comparison.setDatasets(decimalDataset, decimalDataset);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });

        it('应该处理包含额外字段的数据', () => {
            const extraFieldsDataset = {
                name: 'Extra Fields',
                points: [
                    { x: 1, y: 1, value: 10, timestamp: '2024-01-01', label: 'Point 1' },
                    { x: 2, y: 2, value: 20, timestamp: '2024-01-02', label: 'Point 2' }
                ]
            };

            comparison.setDatasets(extraFieldsDataset, extraFieldsDataset);

            const result = comparison.compare();

            expect(result).not.toBeNull();
        });
    });

    describe('私有方法测试', () => {
        it('应该正确计算统计值', () => {
            const points = [
                { value: 10 },
                { value: 20 },
                { value: 30 }
            ];

            comparison.setDatasets(
                { name: 'Test', points },
                { name: 'Test B', points: [] }
            );

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.min).toBe(10);
            expect(result?.fieldStats.value.datasetA.max).toBe(30);
            expect(result?.fieldStats.value.datasetA.mean).toBe(20);
        });

        it('应该处理空点数组', () => {
            comparison.setDatasets(
                { name: 'Empty', points: [] },
                { name: 'Empty B', points: [] }
            );

            const result = comparison.compare();

            expect(result?.fieldStats.value.datasetA.min).toBe(0);
            expect(result?.fieldStats.value.datasetA.max).toBe(0);
            expect(result?.fieldStats.value.datasetA.mean).toBe(0);
            expect(result?.fieldStats.value.datasetA.std).toBe(0);
        });
    });

    describe('数据类型接口', () => {
        it('应该接受符合DataSet接口的数据', () => {
            const validDataSet = {
                name: 'Valid Dataset',
                points: [
                    { x: 1, y: 1, value: 10 }
                ],
                timestamp: Date.now()
            };

            expect(() => comparison.setDatasets(validDataSet, validDataSet)).not.toThrow();
        });

        it('应该返回符合ComparisonResult接口的数据', () => {
            comparison.setDatasets(datasetA, datasetB);

            const result = comparison.compare();

            expect(result).toHaveProperty('fieldStats');
            expect(result).toHaveProperty('matchedPoints');
            expect(result).toHaveProperty('unmatchedA');
            expect(result).toHaveProperty('unmatchedB');
        });
    });
});