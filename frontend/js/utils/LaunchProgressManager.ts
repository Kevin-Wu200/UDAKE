/**
 * 启动进度管理器
 * 跟踪和管理应用启动过程中的各个加载阶段
 */

export interface ProgressStage {
    id: string;
    name: string;
    description: string;
    weight: number; // 该阶段占总进度的权重
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number; // 该阶段的进度 0-100
    startTime?: number;
    endTime?: number;
    error?: Error;
}

export interface ProgressCallback {
    onStageStart?: (stage: ProgressStage) => void;
    onStageProgress?: (stage: ProgressStage) => void;
    onStageComplete?: (stage: ProgressStage) => void;
    onStageError?: (stage: ProgressStage) => void;
    onTotalProgress?: (total: number, stages: ProgressStage[]) => void;
    onComplete?: (stages: ProgressStage[]) => void;
    onError?: (error: Error) => void;
}

export class LaunchProgressManager {
    private static instance: LaunchProgressManager | null = null;
    private stages: Map<string, ProgressStage> = new Map();
    private callbacks: ProgressCallback = {};
    private totalProgress: number = 0;
    private currentStageId: string | null = null;
    private startTime: number = 0;

    private constructor() {
        this.startTime = Date.now();
    }

    /**
     * 获取单例实例
     */
    public static getInstance(): LaunchProgressManager {
        if (!LaunchProgressManager.instance) {
            LaunchProgressManager.instance = new LaunchProgressManager();
        }
        return LaunchProgressManager.instance;
    }

    /**
     * 注册加载阶段
     */
    public registerStage(stage: ProgressStage): void {
        this.stages.set(stage.id, stage);
        this.updateTotalProgress();
    }

    /**
     * 开始执行阶段
     */
    public async startStage(stageId: string): Promise<void> {
        const stage = this.stages.get(stageId);
        if (!stage) {
            throw new Error(`Stage ${stageId} not found`);
        }

        this.currentStageId = stageId;
        stage.status = 'running';
        stage.startTime = Date.now();
        stage.progress = 0;

        if (this.callbacks.onStageStart) {
            this.callbacks.onStageStart(stage);
        }

        this.updateTotalProgress();
    }

    /**
     * 更新阶段进度
     */
    public updateStageProgress(stageId: string, progress: number): void {
        const stage = this.stages.get(stageId);
        if (!stage) return;

        stage.progress = Math.min(100, Math.max(0, progress));

        if (this.callbacks.onStageProgress) {
            this.callbacks.onStageProgress(stage);
        }

        this.updateTotalProgress();
    }

    /**
     * 完成阶段
     */
    public async completeStage(stageId: string): Promise<void> {
        const stage = this.stages.get(stageId);
        if (!stage) {
            throw new Error(`Stage ${stageId} not found`);
        }

        stage.status = 'completed';
        stage.endTime = Date.now();
        stage.progress = 100;

        if (this.callbacks.onStageComplete) {
            this.callbacks.onStageComplete(stage);
        }

        this.updateTotalProgress();

        // 检查是否所有阶段都完成
        if (this.isAllStagesComplete()) {
            await this.onAllStagesComplete();
        }
    }

    /**
     * 阶段失败
     */
    public async failStage(stageId: string, error: Error): Promise<void> {
        const stage = this.stages.get(stageId);
        if (!stage) {
            throw new Error(`Stage ${stageId} not found`);
        }

        stage.status = 'failed';
        stage.endTime = Date.now();
        stage.error = error;

        if (this.callbacks.onStageError) {
            this.callbacks.onStageError(stage);
        }

        if (this.callbacks.onError) {
            this.callbacks.onError(error);
        }

        this.updateTotalProgress();
    }

    /**
     * 执行带进度跟踪的异步操作
     */
    public async executeStage<T>(
        stageId: string,
        asyncFn: (updateProgress: (progress: number) => void) => Promise<T>
    ): Promise<T> {
        await this.startStage(stageId);

        try {
            const result = await asyncFn((progress) => {
                this.updateStageProgress(stageId, progress);
            });

            await this.completeStage(stageId);
            return result;
        } catch (error) {
            await this.failStage(stageId, error as Error);
            throw error;
        }
    }

    /**
     * 更新总进度
     */
    private updateTotalProgress(): void {
        let totalWeight = 0;
        let completedWeight = 0;

        for (const stage of this.stages.values()) {
            totalWeight += stage.weight;

            if (stage.status === 'completed') {
                completedWeight += stage.weight;
            } else if (stage.status === 'running') {
                completedWeight += stage.weight * (stage.progress / 100);
            }
        }

        this.totalProgress = totalWeight > 0 ? (completedWeight / totalWeight) * 100 : 0;

        if (this.callbacks.onTotalProgress) {
            this.callbacks.onTotalProgress(this.totalProgress, Array.from(this.stages.values()));
        }
    }

    /**
     * 检查是否所有阶段都完成
     */
    private isAllStagesComplete(): boolean {
        for (const stage of this.stages.values()) {
            if (stage.status !== 'completed' && stage.status !== 'failed') {
                return false;
            }
        }
        return true;
    }

    /**
     * 所有阶段完成时的处理
     */
    private async onAllStagesComplete(): Promise<void> {
        const totalTime = Date.now() - this.startTime;

        // 记录性能数据
        console.log(`[LaunchProgress] 所有加载阶段完成，总耗时: ${totalTime}ms`);
        for (const stage of this.stages.values()) {
            const duration = (stage.endTime || 0) - (stage.startTime || 0);
            console.log(`[LaunchProgress] ${stage.name}: ${duration}ms`);
        }

        if (this.callbacks.onComplete) {
            this.callbacks.onComplete(Array.from(this.stages.values()));
        }
    }

    /**
     * 设置回调函数
     */
    public setCallbacks(callbacks: ProgressCallback): void {
        this.callbacks = { ...this.callbacks, ...callbacks };
    }

    /**
     * 获取当前总进度
     */
    public getTotalProgress(): number {
        return this.totalProgress;
    }

    /**
     * 获取当前阶段
     */
    public getCurrentStage(): ProgressStage | null {
        if (!this.currentStageId) return null;
        return this.stages.get(this.currentStageId) || null;
    }

    /**
     * 获取所有阶段
     */
    public getAllStages(): ProgressStage[] {
        return Array.from(this.stages.values());
    }

    /**
     * 获取特定阶段
     */
    public getStage(stageId: string): ProgressStage | undefined {
        return this.stages.get(stageId);
    }

    /**
     * 重置进度
     */
    public reset(): void {
        this.stages.clear();
        this.totalProgress = 0;
        this.currentStageId = null;
        this.startTime = Date.now();
    }

    /**
     * 获取总耗时
     */
    public getTotalTime(): number {
        return Date.now() - this.startTime;
    }

    /**
     * 创建预设的启动阶段
     */
    public static createDefaultStages(): ProgressStage[] {
        return [
            {
                id: 'initialize',
                name: '初始化应用',
                description: '正在初始化应用环境...',
                weight: 5,
                status: 'pending',
                progress: 0
            },
            {
                id: 'backend-connection',
                name: '连接后端',
                description: '正在连接后端服务...',
                weight: 10,
                status: 'pending',
                progress: 0
            },
            {
                id: 'api-init',
                name: '初始化 API',
                description: '正在初始化 API 服务...',
                weight: 15,
                status: 'pending',
                progress: 0
            },
            {
                id: 'map-load',
                name: '加载地图',
                description: '正在加载地图引擎...',
                weight: 25,
                status: 'pending',
                progress: 0
            },
            {
                id: 'components-init',
                name: '初始化组件',
                description: '正在初始化界面组件...',
                weight: 25,
                status: 'pending',
                progress: 0
            },
            {
                id: 'events-bind',
                name: '绑定事件',
                description: '正在绑定事件处理...',
                weight: 10,
                status: 'pending',
                progress: 0
            },
            {
                id: 'permission-check',
                name: '检查权限',
                description: '正在检查系统权限...',
                weight: 5,
                status: 'pending',
                progress: 0
            },
            {
                id: 'ready',
                name: '准备就绪',
                description: '应用已准备就绪',
                weight: 5,
                status: 'pending',
                progress: 0
            }
        ];
    }
}