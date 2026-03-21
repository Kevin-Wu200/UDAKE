/**
 * 批量操作管理器
 * 批量导入、导出、删除、更新采样点
 */

interface BatchResult {
    total: number;
    success: number;
    failed: number;
    errors: string[];
}

export class BatchOperations {
    /**
     * 批量导入多个 GeoJSON 文件
     */
    static async batchImport(
        files: FileList,
        onProgress?: (current: number, total: number) => void
    ): Promise<BatchResult> {
        const result: BatchResult = { total: files.length, success: 0, failed: 0, errors: [] };

        for (let i = 0; i < files.length; i++) {
            try {
                const file = files[i];
                if (!file.name.match(/\.(geojson|json)$/i)) {
                    result.failed++;
                    result.errors.push(`${file.name}: 不支持的文件格式`);
                    continue;
                }
                const text = await file.text();
                JSON.parse(text); // 验证 JSON 格式
                result.success++;
            } catch (e: any) {
                result.failed++;
                result.errors.push(`${files[i].name}: ${e.message}`);
            }
            onProgress?.(i + 1, files.length);
        }
        return result;
    }

    /**
     * 批量删除采样点
     */
    static batchDeletePoints(
        points: Array<{ x: number; y: number; value: number }>,
        indices: number[]
    ): Array<{ x: number; y: number; value: number }> {
        const toDelete = new Set(indices);
        return points.filter((_, i) => !toDelete.has(i));
    }

    /**
     * 批量更新采样点属性
     */
    static batchUpdatePoints<T extends Record<string, any>>(
        points: T[],
        indices: number[],
        updates: Partial<T>
    ): T[] {
        const toUpdate = new Set(indices);
        return points.map((p, i) => toUpdate.has(i) ? { ...p, ...updates } : p);
    }

    /**
     * 批量导出为多种格式
     */
    static async batchExport(
        data: Array<Record<string, any>>,
        formats: string[],
        baseFilename: string
    ): Promise<void> {
        for (const format of formats) {
            switch (format) {
                case 'csv': {
                    const { ExportEnhancer } = await import('../utils/ExportEnhancer.js');
                    ExportEnhancer.exportAsCSV(data, `${baseFilename}.csv`);
                    break;
                }
                case 'geojson': {
                    const geojson = {
                        type: 'FeatureCollection',
                        features: data.map(p => ({
                            type: 'Feature',
                            geometry: { type: 'Point', coordinates: [p.x || p.longitude, p.y || p.latitude] },
                            properties: { value: p.value, ...p }
                        }))
                    };
                    const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: 'application/geo+json' });
                    BatchOperations._download(blob, `${baseFilename}.geojson`);
                    break;
                }
            }
            await new Promise(r => setTimeout(r, 300));
        }
    }

    /**
     * 创建批量操作确认对话框
     */
    static async confirmBatch(action: string, count: number): Promise<boolean> {
        return new Promise(resolve => {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.innerHTML = `
                <div class="modal" style="max-width:400px;">
                    <div class="modal-header">
                        <h2 class="modal-title">批量操作确认</h2>
                    </div>
                    <div class="modal-body" style="padding:16px 24px;">
                        <p>确定要对 <strong>${count}</strong> 个项目执行「${action}」操作吗？</p>
                        <p style="color:var(--text-secondary);font-size:13px;margin-top:8px;">此操作可能无法撤销</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn" id="batch-cancel">取消</button>
                        <button class="btn btn-primary" id="batch-confirm">确认执行</button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);
            requestAnimationFrame(() => overlay.classList.add('modal-show'));

            const close = (result: boolean) => {
                overlay.classList.remove('modal-show');
                setTimeout(() => overlay.remove(), 300);
                resolve(result);
            };

            overlay.querySelector('#batch-cancel')!.addEventListener('click', () => close(false));
            overlay.querySelector('#batch-confirm')!.addEventListener('click', () => close(true));
            overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
        });
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
