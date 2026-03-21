/**
 * 数据导出增强
 * PDF 报告生成、图表导出、批量导出
 */

interface ExportOptions {
    format: 'geojson' | 'csv' | 'pdf';
    includeMap?: boolean;
    includeStats?: boolean;
    includeVariogram?: boolean;
}

export class ExportEnhancer {
    private apiBaseURL: string;

    constructor(apiBaseURL: string) {
        this.apiBaseURL = apiBaseURL;
    }

    /** 导出为 CSV */
    static exportAsCSV(data: Array<Record<string, any>>, filename: string): void {
        if (!data.length) return;
        const headers = Object.keys(data[0]);
        const rows = [
            headers.join(','),
            ...data.map(row => headers.map(h => {
                const val = row[h];
                if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
                    return `"${val.replace(/"/g, '""')}"`;
                }
                return val ?? '';
            }).join(','))
        ];
        const csv = '\uFEFF' + rows.join('\n'); // BOM for Excel
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        ExportEnhancer._download(blob, filename);
    }

    /** 导出采样点为 CSV */
    static exportPointsCSV(points: Array<{ x: number; y: number; value: number; [k: string]: any }>, filename = 'sampling_points.csv'): void {
        this.exportAsCSV(points.map(p => ({
            longitude: p.x,
            latitude: p.y,
            value: p.value,
            ...(p.timestamp ? { timestamp: p.timestamp } : {}),
        })), filename);
    }

    /** 生成简易 HTML 报告并导出为可打印页面 */
    static generateHTMLReport(reportData: {
        taskId: string;
        method: string;
        pointCount: number;
        gridResolution: number;
        stats?: Record<string, number>;
        crossValidation?: Record<string, number>;
    }): void {
        const { taskId, method, pointCount, gridResolution, stats, crossValidation } = reportData;
        const methodNames: Record<string, string> = {
            ordinary: '普通克里金', universal: '泛克里金', block: '分块克里金'
        };

        const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>插值分析报告 - ${taskId}</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
        h1 { border-bottom: 2px solid #007aff; padding-bottom: 10px; }
        h2 { color: #007aff; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #e5e5e5; }
        th { background: #f5f5f7; font-weight: 600; }
        .meta { color: #666; font-size: 14px; }
        .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0; }
        .stat-card { background: #f5f5f7; border-radius: 12px; padding: 16px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: 700; color: #007aff; }
        .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
        @media print { body { margin: 0; } }
    </style>
</head>
<body>
    <h1>插值分析报告</h1>
    <p class="meta">任务ID: ${taskId} | 生成时间: ${new Date().toLocaleString('zh-CN')}</p>

    <h2>参数配置</h2>
    <table>
        <tr><th>参数</th><th>值</th></tr>
        <tr><td>克里金方法</td><td>${methodNames[method] || method}</td></tr>
        <tr><td>采样点数量</td><td>${pointCount}</td></tr>
        <tr><td>网格分辨率</td><td>${gridResolution}</td></tr>
    </table>

    ${stats ? `
    <h2>统计摘要</h2>
    <div class="stat-grid">
        ${Object.entries(stats).map(([k, v]) => `
            <div class="stat-card">
                <div class="stat-value">${typeof v === 'number' ? v.toFixed(4) : v}</div>
                <div class="stat-label">${k}</div>
            </div>
        `).join('')}
    </div>` : ''}

    ${crossValidation ? `
    <h2>交叉验证</h2>
    <table>
        <tr><th>指标</th><th>值</th></tr>
        ${Object.entries(crossValidation).map(([k, v]) => `
            <tr><td>${k}</td><td>${typeof v === 'number' ? v.toFixed(6) : v}</td></tr>
        `).join('')}
    </table>` : ''}

    <p class="meta" style="margin-top:40px;text-align:center;">
        UDAKE - 智能不确定性驱动空间决策平台
    </p>
</body>
</html>`;

        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        ExportEnhancer._download(blob, `report_${taskId}.html`);
    }

    /** 批量导出多个任务结果 */
    async batchExport(taskIds: string[], format: string): Promise<void> {
        for (const taskId of taskIds) {
            try {
                const filename = `${taskId}_prediction.${format}`;
                const url = `${this.apiBaseURL}/result/download/${taskId}/${filename}`;
                const response = await fetch(url, { mode: 'cors', credentials: 'omit' });
                if (!response.ok) continue;
                const blob = await response.blob();
                ExportEnhancer._download(blob, filename);
                // 间隔避免浏览器限制
                await new Promise(r => setTimeout(r, 500));
            } catch (e) {
                console.warn(`[Export] 批量导出失败: ${taskId}`, e);
            }
        }
    }

    /** 导出地图截图 */
    static async captureMap(mapContainer: HTMLElement): Promise<Blob | null> {
        try {
            // 使用 canvas 截图（需要地图引擎支持 toCanvas）
            const canvas = mapContainer.querySelector('canvas');
            if (!canvas) return null;
            return new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        } catch {
            return null;
        }
    }

    private static _download(blob: Blob, filename: string): void {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}
