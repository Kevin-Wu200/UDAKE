/**
 * 数据导出增强
 * PDF 报告生成、图表导出、批量导出
 */
import { I18n } from "./I18n";

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

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

    /** 导出采样点为 GeoJSON（纯前端生成） */
    static exportPointsGeoJSON(points: Array<{ x: number; y: number; value: number; [k: string]: any }>, filename = 'sampling_points.geojson'): void {
        const features = points.map(p => ({
            type: 'Feature' as const,
            geometry: {
                type: 'Point' as const,
                coordinates: [p.x, p.y]
            },
            properties: {
                value: p.value,
                ...(p.timestamp ? { timestamp: p.timestamp } : {}),
            }
        }));

        const geojson = {
            type: 'FeatureCollection',
            features
        };

        const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/geo+json;charset=utf-8' });
        this._download(blob, filename);
    }

    /** 导出采样点为 Excel（XLSX 格式） */
    static exportPointsExcel(points: Array<{ x: number; y: number; value: number; [k: string]: any }>, filename = 'sampling_points.xlsx'): void {
        // 使用简单 CSV 格式作为 Excel 导出（.xlsx 扩展名，Excel 可打开 CSV）
        // 如果需要真正的 XLSX，需要引入 SheetJS 库
        const headers = ['longitude', 'latitude', 'value'];
        const hasTimestamp = points.some(p => p.timestamp);
        if (hasTimestamp) headers.push('timestamp');
        
        const rows = [
            headers.join(','),
            ...points.map(p => {
                const row = [p.x, p.y, p.value];
                if (hasTimestamp) row.push(p.timestamp || '');
                return row.map(v => {
                    const str = String(v ?? '');
                    return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
                }).join(',');
            })
        ];
        const csv = '\uFEFF' + rows.join('\n'); // BOM for Excel UTF-8
        const blob = new Blob([csv], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;charset=utf-8' });
        this._download(blob, filename);
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
            ordinary: t('kriging.ordinary'), universal: t('kriging.universal'), block: t('kriging.block')
        };

        const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>${t('export.report.interpolation')} - ${taskId}</title>
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
    <h1>${t('export.report.interpolation')}</h1>
    <p class="meta">${t('export.report.interpolation.detail', { taskId: taskId, generatedTime: new Date().toLocaleString('zh-CN') })}</p>

    <h2>${t('export.report.parameter.config')}</h2>
    <table>
        <tr><th>${t('export.report.parameter.config.parameter')}</th><th>${t('export.report.parameter.config.value')}</th></tr>
        <tr><td>${t('export.report.parameter.config.kriging')}</td><td>${methodNames[method] || method}</td></tr>
        <tr><td>${t('export.report.parameter.config.samplingPoints')}</td><td>${pointCount}</td></tr>
        <tr><td>${t('export.report.parameter.config.gridResolution')}</td><td>${gridResolution}</td></tr>
    </table>

    ${stats ? `
    <h2>${t('export.report.stats')}</h2>
    <div class="stat-grid">
        ${Object.entries(stats).map(([k, v]) => `
            <div class="stat-card">
                <div class="stat-value">${typeof v === 'number' ? v.toFixed(4) : v}</div>
                <div class="stat-label">${k}</div>
            </div>
        `).join('')}
    </div>` : ''}

    ${crossValidation ? `
    <h2>${t('export.report.crossValidation')}</h2>
    <table>
        <tr><th>${t('export.report.crossValidation.target')}</th><th>${t('export.report.crossValidation.value')}</th></tr>
        ${Object.entries(crossValidation).map(([k, v]) => `
            <tr><td>${k}</td><td>${typeof v === 'number' ? v.toFixed(6) : v}</td></tr>
        `).join('')}
    </table>` : ''}

    <p class="meta" style="margin-top:40px;text-align:center;">
        UDAKE - ${t('app.title')}
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
