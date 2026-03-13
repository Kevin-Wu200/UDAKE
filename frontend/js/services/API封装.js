/**
 * API服务封装
 * 处理所有后端API调用，包含错误处理、跨域处理、请求防重复
 */

export class APIService {
    constructor(baseURL) {
        this.baseURL = baseURL;
        this.pendingRequests = new Map(); // 防止重复请求
    }

    /**
     * 通用请求方法
     * 包含错误处理和跨域配置
     */
    async request(url, options = {}) {
        const requestKey = `${options.method || 'GET'}_${url}`;

        // 防止重复请求
        if (this.pendingRequests.has(requestKey)) {
            console.warn(`请求已在进行中: ${requestKey}`);
            return this.pendingRequests.get(requestKey);
        }

        const requestPromise = (async () => {
            try {
                const response = await fetch(url, {
                    ...options,
                    mode: 'cors', // 跨域配置
                    credentials: 'omit'
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
                }

                return await response.json();
            } catch (error) {
                if (error.name === 'TypeError' && error.message.includes('fetch')) {
                    throw new Error('网络连接失败，请检查后端服务是否启动');
                }
                throw error;
            } finally {
                this.pendingRequests.delete(requestKey);
            }
        })();

        this.pendingRequests.set(requestKey, requestPromise);
        return requestPromise;
    }

    /**
     * 上传数据
     */
    async uploadData(file) {
        const formData = new FormData();
        formData.append('file', file);

        return this.request(`${this.baseURL}/upload-data`, {
            method: 'POST',
            body: formData
        });
    }

    /**
     * 启动克里金插值
     */
    async startKriging(params) {
        return this.request(`${this.baseURL}/start-kriging`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        });
    }

    /**
     * 获取任务状态
     */
    async getTaskStatus(taskId) {
        return this.request(`${this.baseURL}/task-status/${taskId}`);
    }

    /**
     * 获取预测结果
     */
    async getPredictionResult(taskId) {
        return this.request(`${this.baseURL}/result/prediction/${taskId}`);
    }

    /**
     * 获取方差结果
     */
    async getVarianceResult(taskId) {
        return this.request(`${this.baseURL}/result/variance/${taskId}`);
    }

    /**
     * 获取报告
     */
    async getReport(taskId) {
        return this.request(`${this.baseURL}/result/report/${taskId}`);
    }

    /**
     * 下载导出文件
     */
    async downloadExportFile(taskId, filename) {
        const url = `${this.baseURL}/result/download/${taskId}/${filename}`;
        const response = await fetch(url, { mode: 'cors', credentials: 'omit' });
        if (!response.ok) {
            throw new Error(`下载失败: HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    }

    /**
     * 取消所有待处理请求
     */
    cancelAllRequests() {
        this.pendingRequests.clear();
    }
}
