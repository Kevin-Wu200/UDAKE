/**
 * 任务轮询器
 * 每2秒轮询任务状态，防止重复请求，支持进度条动画
 */

export class TaskPoller {
    constructor(apiService, taskId, onUpdate) {
        this.apiService = apiService;
        this.taskId = taskId;
        this.onUpdate = onUpdate;
        this.intervalId = null;
        this.interval = 2000; // 2秒轮询间隔
        this.isPolling = false; // 防止重复轮询
        this.retryCount = 0;
        this.maxRetries = 3;
    }

    /**
     * 开始轮询
     */
    start() {
        if (this.isPolling) {
            console.warn('轮询已在进行中');
            return;
        }

        this.isPolling = true;
        this.retryCount = 0;
        this.poll(); // 立即执行一次
        this.intervalId = setInterval(() => this.poll(), this.interval);
        console.log(`✅ 开始轮询任务: ${this.taskId}`);
    }

    /**
     * 停止轮询
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.isPolling = false;
        console.log(`⏹️ 停止轮询任务: ${this.taskId}`);
    }

    /**
     * 执行轮询
     */
    async poll() {
        if (!this.isPolling) {
            return;
        }

        try {
            const status = await this.apiService.getTaskStatus(this.taskId);
            this.retryCount = 0; // 重置重试计数

            // 调用更新回调
            if (this.onUpdate) {
                this.onUpdate(status);
            }

            // 任务完成或失败时停止轮询
            if (status.status === 'completed' || status.status === 'failed') {
                this.stop();
            }
        } catch (error) {
            console.error('轮询失败:', error);
            this.retryCount++;

            // 超过最大重试次数则停止
            if (this.retryCount >= this.maxRetries) {
                console.error(`轮询失败次数过多，停止轮询`);
                this.stop();
                if (this.onUpdate) {
                    this.onUpdate({
                        status: 'failed',
                        error: '无法连接到服务器',
                        progress: 0
                    });
                }
            }
        }
    }

    /**
     * 重置轮询器
     */
    reset() {
        this.stop();
        this.retryCount = 0;
    }
}
