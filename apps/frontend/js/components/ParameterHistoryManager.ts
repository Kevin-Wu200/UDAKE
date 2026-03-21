/**
 * 历史参数记录管理器
 * 使用 localStorage 存储和管理历史参数
 */

export interface HistoryRecord {
    id: string;
    name: string;
    parameters: Record<string, number>;
    score?: {
        rmse?: number;
        mae?: number;
        r2?: number;
    };
    timestamp: string;
    favorite: boolean;
}

export class ParameterHistoryManager {
    private static instance: ParameterHistoryManager;
    private records: HistoryRecord[] = [];

    private constructor() {
        this.loadRecords();
    }

    public static getInstance(): ParameterHistoryManager {
        if (!ParameterHistoryManager.instance) {
            ParameterHistoryManager.instance = new ParameterHistoryManager();
        }
        return ParameterHistoryManager.instance;
    }

    /**
     * 加载历史记录
     */
    private loadRecords(): void {
        try {
            const saved = localStorage.getItem('parameterHistory');
            if (saved) {
                this.records = JSON.parse(saved);
            }
        } catch (error) {
            console.error('Failed to load parameter history:', error);
            this.records = [];
        }
    }

    /**
     * 保存历史记录
     */
    private saveRecords(): void {
        try {
            localStorage.setItem('parameterHistory', JSON.stringify(this.records));
        } catch (error) {
            console.error('Failed to save parameter history:', error);
        }
    }

    /**
     * 添加历史记录
     */
    public addRecord(
        name: string,
        parameters: Record<string, number>,
        score?: HistoryRecord['score']
    ): HistoryRecord {
        const record: HistoryRecord = {
            id: Date.now().toString(),
            name: name || `参数组合 ${this.records.length + 1}`,
            parameters,
            score,
            timestamp: new Date().toISOString(),
            favorite: false
        };

        this.records.unshift(record);
        this.saveRecords();
        return record;
    }

    /**
     * 获取所有历史记录
     */
    public getAllRecords(): HistoryRecord[] {
        return [...this.records];
    }

    /**
     * 根据ID获取记录
     */
    public getRecord(id: string): HistoryRecord | undefined {
        return this.records.find(r => r.id === id);
    }

    /**
     * 更新记录
     */
    public updateRecord(id: string, updates: Partial<HistoryRecord>): void {
        const index = this.records.findIndex(r => r.id === id);
        if (index !== -1) {
            this.records[index] = { ...this.records[index], ...updates };
            this.saveRecords();
        }
    }

    /**
     * 删除记录
     */
    public deleteRecord(id: string): void {
        this.records = this.records.filter(r => r.id !== id);
        this.saveRecords();
    }

    /**
     * 切换收藏状态
     */
    public toggleFavorite(id: string): void {
        const record = this.getRecord(id);
        if (record) {
            record.favorite = !record.favorite;
            this.saveRecords();
        }
    }

    /**
     * 获取收藏的记录
     */
    public getFavorites(): HistoryRecord[] {
        return this.records.filter(r => r.favorite);
    }

    /**
     * 搜索记录
     */
    public searchRecords(query: string): HistoryRecord[] {
        const lowerQuery = query.toLowerCase();
        return this.records.filter(r =>
            r.name.toLowerCase().includes(lowerQuery) ||
            Object.entries(r.parameters).some(([key, value]) =>
                `${key}:${value}`.toLowerCase().includes(lowerQuery)
            )
        );
    }

    /**
     * 筛选记录
     */
    public filterRecords(options: {
        favorite?: boolean;
        minScore?: number;
        maxScore?: number;
        startDate?: Date;
        endDate?: Date;
    }): HistoryRecord[] {
        return this.records.filter(record => {
            if (options.favorite !== undefined && record.favorite !== options.favorite) {
                return false;
            }

            if (options.minScore !== undefined && record.score?.rmse && record.score.rmse < options.minScore) {
                return false;
            }

            if (options.maxScore !== undefined && record.score?.rmse && record.score.rmse > options.maxScore) {
                return false;
            }

            if (options.startDate && new Date(record.timestamp) < options.startDate) {
                return false;
            }

            if (options.endDate && new Date(record.timestamp) > options.endDate) {
                return false;
            }

            return true;
        });
    }

    /**
     * 导出记录为 JSON
     */
    public exportRecords(records?: HistoryRecord[]): string {
        const data = records || this.records;
        return JSON.stringify(data, null, 2);
    }

    /**
     * 导入记录
     */
    public importRecords(jsonString: string): { success: number; failed: number } {
        try {
            const imported = JSON.parse(jsonString) as HistoryRecord[];
            let success = 0;
            let failed = 0;

            imported.forEach(record => {
                if (this.validateRecord(record)) {
                    this.records.push(record);
                    success++;
                } else {
                    failed++;
                }
            });

            this.saveRecords();
            return { success, failed };
        } catch (error) {
            console.error('Failed to import records:', error);
            return { success: 0, failed: 0 };
        }
    }

    /**
     * 验证记录格式
     */
    private validateRecord(record: any): record is HistoryRecord {
        return (
            record &&
            typeof record.id === 'string' &&
            typeof record.name === 'string' &&
            typeof record.parameters === 'object' &&
            typeof record.timestamp === 'string' &&
            typeof record.favorite === 'boolean'
        );
    }

    /**
     * 清空所有记录
     */
    public clearAll(): void {
        this.records = [];
        this.saveRecords();
    }

    /**
     * 获取统计信息
     */
    public getStatistics(): {
        total: number;
        favorites: number;
        avgRMSE?: number;
        bestRMSE?: HistoryRecord;
    } {
        const favorites = this.records.filter(r => r.favorite).length;
        const scoredRecords = this.records.filter(r => r.score?.rmse);

        let avgRMSE: number | undefined;
        let bestRMSE: HistoryRecord | undefined;

        if (scoredRecords.length > 0) {
            const sumRMSE = scoredRecords.reduce((sum, r) => sum + (r.score?.rmse || 0), 0);
            avgRMSE = sumRMSE / scoredRecords.length;

            bestRMSE = scoredRecords.reduce((best, current) => {
                if (!best || (current.score?.rmse || 0) < (best.score?.rmse || 0)) {
                    return current;
                }
                return best;
            });
        }

        return {
            total: this.records.length,
            favorites,
            avgRMSE,
            bestRMSE
        };
    }
}