/**
 * 数据对比功能
 * 支持两组数据集的差异计算、可视化和对比报告
 */

interface DataSet {
    name: string;
    points: Array<{ x: number; y: number; value: number; [k: string]: any }>;
    timestamp?: number;
}

interface ComparisonResult {
    fieldStats: Record<string, {
        datasetA: { min: number; max: number; mean: number; std: number };
        datasetB: { min: number; max: number; mean: number; std: number };
        diff: { meanDiff: number; percentChange: number };
    }>;
    matchedPoints: number;
    unmatchedA: number;
    unmatchedB: number;
}

export class DataComparison {
    private datasetA: DataSet | null = null;
    private datasetB: DataSet | null = null;

    setDatasets(a: DataSet, b: DataSet): void {
        this.datasetA = a;
        this.datasetB = b;
    }

    /** 计算两组数据的统计差异 */
    compare(field = 'value'): ComparisonResult | null {
        if (!this.datasetA || !this.datasetB) return null;

        const statsA = DataComparison._calcStats(this.datasetA.points, field);
        const statsB = DataComparison._calcStats(this.datasetB.points, field);

        const meanDiff = statsB.mean - statsA.mean;
        const percentChange = statsA.mean !== 0 ? (meanDiff / statsA.mean) * 100 : 0;

        // 匹配点（基于坐标距离阈值）
        const threshold = 0.0001; // ~11m
        let matched = 0;
        for (const pa of this.datasetA.points) {
            for (const pb of this.datasetB.points) {
                if (Math.abs(pa.x - pb.x) < threshold && Math.abs(pa.y - pb.y) < threshold) {
                    matched++;
                    break;
                }
            }
        }

        return {
            fieldStats: {
                [field]: {
                    datasetA: statsA,
                    datasetB: statsB,
                    diff: { meanDiff, percentChange },
                }
            },
            matchedPoints: matched,
            unmatchedA: this.datasetA.points.length - matched,
            unmatchedB: this.datasetB.points.length - matched,
        };
    }

    /** 生成对比报告 HTML */
    generateReport(field = 'value'): string {
        const result = this.compare(field);
        if (!result || !this.datasetA || !this.datasetB) return '<p>无法生成对比报告</p>';

        const stats = result.fieldStats[field];
        const diffClass = stats.diff.meanDiff > 0 ? 'diff-positive' : stats.diff.meanDiff < 0 ? 'diff-negative' : 'diff-neutral';

        return `
            <div class="comparison-report">
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>指标</th>
                            <th>${this.datasetA.name}</th>
                            <th>${this.datasetB.name}</th>
                            <th>差异</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>点数</td>
                            <td>${this.datasetA.points.length}</td>
                            <td>${this.datasetB.points.length}</td>
                            <td>${this.datasetB.points.length - this.datasetA.points.length}</td>
                        </tr>
                        <tr>
                            <td>最小值</td>
                            <td>${stats.datasetA.min.toFixed(4)}</td>
                            <td>${stats.datasetB.min.toFixed(4)}</td>
                            <td class="${diffClass}">${(stats.datasetB.min - stats.datasetA.min).toFixed(4)}</td>
                        </tr>
                        <tr>
                            <td>最大值</td>
                            <td>${stats.datasetA.max.toFixed(4)}</td>
                            <td>${stats.datasetB.max.toFixed(4)}</td>
                            <td class="${diffClass}">${(stats.datasetB.max - stats.datasetA.max).toFixed(4)}</td>
                        </tr>
                        <tr>
                            <td>均值</td>
                            <td>${stats.datasetA.mean.toFixed(4)}</td>
                            <td>${stats.datasetB.mean.toFixed(4)}</td>
                            <td class="${diffClass}">${stats.diff.meanDiff.toFixed(4)} (${stats.diff.percentChange.toFixed(1)}%)</td>
                        </tr>
                        <tr>
                            <td>标准差</td>
                            <td>${stats.datasetA.std.toFixed(4)}</td>
                            <td>${stats.datasetB.std.toFixed(4)}</td>
                            <td>${(stats.datasetB.std - stats.datasetA.std).toFixed(4)}</td>
                        </tr>
                        <tr>
                            <td>匹配点</td>
                            <td colspan="3">${result.matchedPoints} 个重合点</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    /** 创建对比面板 */
    createPanel(): HTMLElement {
        const panel = document.createElement('div');
        panel.className = 'panel';
        panel.innerHTML = `
            <h2 class="panel-title">数据对比</h2>
            <div class="panel-content">
                <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
                    选择两组数据集进行对比分析
                </p>
                <div style="display:flex;gap:8px;margin-bottom:12px;">
                    <div style="flex:1;">
                        <label style="font-size:12px;color:var(--text-secondary);">数据集 A</label>
                        <select class="select" id="compare-dataset-a" style="width:100%;margin-top:4px;">
                            <option value="">选择数据集</option>
                        </select>
                    </div>
                    <div style="flex:1;">
                        <label style="font-size:12px;color:var(--text-secondary);">数据集 B</label>
                        <select class="select" id="compare-dataset-b" style="width:100%;margin-top:4px;">
                            <option value="">选择数据集</option>
                        </select>
                    </div>
                </div>
                <button class="btn btn-primary" id="compare-btn" style="width:100%;height:36px;font-size:13px;" disabled>开始对比</button>
                <div id="compare-result" style="margin-top:12px;max-height:300px;overflow-y:auto;"></div>
            </div>
        `;

        const selectA = panel.querySelector('#compare-dataset-a') as HTMLSelectElement;
        const selectB = panel.querySelector('#compare-dataset-b') as HTMLSelectElement;
        const compareBtn = panel.querySelector('#compare-btn') as HTMLButtonElement;
        const resultDiv = panel.querySelector('#compare-result')!;

        const checkReady = () => {
            compareBtn.disabled = !selectA.value || !selectB.value;
        };
        selectA.addEventListener('change', checkReady);
        selectB.addEventListener('change', checkReady);

        compareBtn.addEventListener('click', () => {
            if (this.datasetA && this.datasetB) {
                resultDiv.innerHTML = this.generateReport();
            }
        });

        return panel;
    }

    private static _calcStats(points: Array<{ [k: string]: any }>, field: string) {
        const values = points.map(p => Number(p[field])).filter(v => !isNaN(v));
        if (values.length === 0) return { min: 0, max: 0, mean: 0, std: 0 };
        const min = Math.min(...values);
        const max = Math.max(...values);
        const mean = values.reduce((a, b) => a + b, 0) / values.length;
        const std = Math.sqrt(values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length);
        return { min, max, mean, std };
    }
}
