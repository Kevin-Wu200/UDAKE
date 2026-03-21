/**
 * 实时插值告警管理器
 * Realtime Alert Manager Component

实现异常告警、性能告警、系统状态通知和消息中心
支持多种通知方式和告警级别
 */

import { RealtimeInterpolation, PerformanceMetrics, HotspotArea } from './RealtimeInterpolation';
import { NotificationManager } from './NotificationManager';
import type { NotificationType, NotificationPriority } from './NotificationManager';
import notificationManagerInstance from './NotificationManager';

export interface AlertRule {
    id: string;
    name: string;
    type: 'anomaly' | 'performance' | 'system' | 'hotspot';
    enabled: boolean;
    condition: (data: any) => boolean;
    severity: 'low' | 'medium' | 'high' | 'critical';
    message: string;
    actions?: AlertAction[];
    cooldown: number; // 冷却时间（毫秒）
}

export interface AlertAction {
    id: string;
    type: 'email' | 'sms' | 'webhook' | 'script';
    config: any;
}

export interface Alert {
    id: string;
    ruleId: string;
    ruleName: string;
    type: string;
    severity: string;
    message: string;
    timestamp: Date;
    acknowledged: boolean;
    resolved: boolean;
    data: any;
}

export interface AlertSettings {
    enabled: boolean;
    soundEnabled: boolean;
    vibrationEnabled: boolean;
    desktopNotifications: boolean;
    emailAlerts: boolean;
    smsAlerts: boolean;
    webhookUrl?: string;
    emailAddresses?: string[];
    phoneNumber?: string;
}

export class RealtimeAlertManager {
    private realtimeInterpolation: RealtimeInterpolation;
    private notificationManager: NotificationManager;
    private rules: Map<string, AlertRule> = new Map();
    private alerts: Alert[] = [];
    private maxAlerts = 1000;
    private alertHistory: Map<string, Date> = new Map(); // 告警触发历史
    private settings: AlertSettings;
    private messageCenter: Map<string, Alert> = new Map();
    private isInitialized = false;

    constructor(
        realtimeInterpolation: RealtimeInterpolation,
        settings: Partial<AlertSettings> = {}
    ) {
        this.realtimeInterpolation = realtimeInterpolation;
        this.notificationManager = notificationManagerInstance;
        this.settings = {
            enabled: true,
            soundEnabled: true,
            vibrationEnabled: true,
            desktopNotifications: true,
            emailAlerts: false,
            smsAlerts: false,
            ...settings
        };

        // 初始化默认告警规则
        this.initializeDefaultRules();
    }

    /**
     * 初始化告警管理器
     */
    async initialize(): Promise<void> {
        if (this.isInitialized) {
            return;
        }

        try {
            // 注册事件监听器
            this.registerEventListeners();

            // 启动告警检查定时器
            this.startAlertCheckTimer();

            this.isInitialized = true;
            console.log('实时插值告警管理器初始化成功');
        } catch (error) {
            console.error('实时插值告警管理器初始化失败:', error);
            throw error;
        }
    }

    /**
     * 初始化默认告警规则
     */
    private initializeDefaultRules(): void {
        // 性能告警规则
        this.addRule({
            id: 'high-latency',
            name: '高延迟告警',
            type: 'performance',
            enabled: true,
            condition: (data: PerformanceMetrics) => data.averageUpdateDuration > 3000,
            severity: 'high',
            message: '平均更新延迟超过3秒',
            cooldown: 60000 // 1分钟冷却
        });

        this.addRule({
            id: 'high-memory',
            name: '高内存使用告警',
            type: 'performance',
            enabled: true,
            condition: (data: PerformanceMetrics) => data.memoryUsage > 500,
            severity: 'medium',
            message: '内存使用超过500MB',
            cooldown: 300000 // 5分钟冷却
        });

        this.addRule({
            id: 'low-cache-hit',
            name: '低缓存命中率告警',
            type: 'performance',
            enabled: true,
            condition: (data: PerformanceMetrics) => data.cacheHitRate < 0.5 && data.totalUpdates > 10,
            severity: 'low',
            message: '缓存命中率低于50%',
            cooldown: 600000 // 10分钟冷却
        });

        // 异常检测告警规则
        this.addRule({
            id: 'anomaly-detected',
            name: '数据异常告警',
            type: 'anomaly',
            enabled: true,
            condition: (data: any) => data.hasAnomaly === true,
            severity: 'critical',
            message: '检测到数据异常',
            cooldown: 30000 // 30秒冷却
        });

        // 热点告警规则
        this.addRule({
            id: 'intense-hotspot',
            name: '高强度热点告警',
            type: 'hotspot',
            enabled: true,
            condition: (data: HotspotArea[]) => data.some(h => h.intensity > 0.9),
            severity: 'high',
            message: '检测到高强度热点区域',
            cooldown: 60000 // 1分钟冷却
        });

        // 系统状态告警规则
        this.addRule({
            id: 'connection-lost',
            name: '连接丢失告警',
            type: 'system',
            enabled: true,
            condition: (data: any) => data.connected === false,
            severity: 'critical',
            message: '与服务器的连接已丢失',
            cooldown: 30000 // 30秒冷却
        });
    }

    /**
     * 注册事件监听器
     */
    private registerEventListeners(): void {
        // 监听更新事件
        this.realtimeInterpolation.onUpdate((update) => {
            this.checkRules('performance', update);
        });

        // 监听热点事件
        this.realtimeInterpolation.onHotspot((hotspots) => {
            this.checkRules('hotspot', hotspots);
        });

        // 监听错误事件
        this.realtimeInterpolation.onError((error) => {
            this.checkRules('system', { connected: false, error });
        });
    }

    /**
     * 启动告警检查定时器
     */
    private startAlertCheckTimer(): void {
        // 每30秒检查一次性能告警
        setInterval(() => {
            const metrics = this.realtimeInterpolation.getPerformanceMetrics();
            this.checkRules('performance', metrics);
        }, 30000);
    }

    /**
     * 检查告警规则
     */
    private checkRules(type: string, data: any): void {
        if (!this.settings.enabled) {
            return;
        }

        for (const [ruleId, rule] of this.rules) {
            if (!rule.enabled || rule.type !== type) {
                continue;
            }

            // 检查冷却时间
            const lastTriggered = this.alertHistory.get(ruleId);
            if (lastTriggered && Date.now() - lastTriggered.getTime() < rule.cooldown) {
                continue;
            }

            // 检查条件
            try {
                if (rule.condition(data)) {
                    this.triggerAlert(rule, data);
                }
            } catch (error) {
                console.error(`告警规则 ${ruleId} 检查失败:`, error);
            }
        }
    }

    /**
     * 触发告警
     */
    private triggerAlert(rule: AlertRule, data: any): void {
        const alert: Alert = {
            id: this.generateAlertId(),
            ruleId: rule.id,
            ruleName: rule.name,
            type: rule.type,
            severity: rule.severity,
            message: rule.message,
            timestamp: new Date(),
            acknowledged: false,
            resolved: false,
            data
        };

        // 添加到告警列表
        this.alerts.unshift(alert);
        if (this.alerts.length > this.maxAlerts) {
            this.alerts.pop();
        }

        // 添加到消息中心
        this.messageCenter.set(alert.id, alert);

        // 更新触发历史
        this.alertHistory.set(rule.id, alert.timestamp);

        // 发送通知
        this.sendNotification(alert);

        // 执行告警动作
        if (rule.actions) {
            this.executeActions(rule.actions, alert);
        }

        console.log('告警触发:', alert);
    }

    /**
     * 发送通知
     */
    private sendNotification(alert: Alert): void {
        const notificationType = this.mapSeverityToNotificationType(alert.severity);
        const priority = this.mapSeverityToPriority(alert.severity);

        // 桌面通知
        if (this.settings.desktopNotifications) {
            this.notificationManager.show({
                type: notificationType,
                title: `${alert.ruleName} (${alert.severity})`,
                body: alert.message,
                priority,
                timeout: this.getNotificationTimeout(alert.severity),
                data: { alertId: alert.id }
            });
        }

        // 邮件通知
        if (this.settings.emailAlerts && this.settings.emailAddresses) {
            this.sendEmailAlert(alert);
        }

        // 短信通知
        if (this.settings.smsAlerts && this.settings.phoneNumber) {
            this.sendSmsAlert(alert);
        }

        // Webhook通知
        if (this.settings.webhookUrl) {
            this.sendWebhookAlert(alert);
        }
    }

    /**
     * 执行告警动作
     */
    private executeActions(actions: AlertAction[], alert: Alert): void {
        actions.forEach(action => {
            try {
                switch (action.type) {
                    case 'email':
                        this.sendEmailAlert(alert, action.config);
                        break;
                    case 'sms':
                        this.sendSmsAlert(alert, action.config);
                        break;
                    case 'webhook':
                        this.sendWebhookAlert(alert, action.config);
                        break;
                    case 'script':
                        this.executeScript(alert, action.config);
                        break;
                }
            } catch (error) {
                console.error(`执行告警动作 ${action.id} 失败:`, error);
            }
        });
    }

    /**
     * 发送邮件告警
     */
    private sendEmailAlert(alert: Alert, config?: any): void {
        const recipients = config?.recipients || this.settings.emailAddresses || [];
        if (recipients.length === 0) {
            return;
        }

        // 这里需要实现邮件发送逻辑
        console.log('发送邮件告警:', alert, recipients);
    }

    /**
     * 发送短信告警
     */
    private sendSmsAlert(alert: Alert, config?: any): void {
        const phoneNumber = config?.phoneNumber || this.settings.phoneNumber;
        if (!phoneNumber) {
            return;
        }

        // 这里需要实现短信发送逻辑
        console.log('发送短信告警:', alert, phoneNumber);
    }

    /**
     * 发送Webhook告警
     */
    private async sendWebhookAlert(alert: Alert, config?: any): Promise<void> {
        const url = config?.url || this.settings.webhookUrl;
        if (!url) {
            return;
        }

        try {
            await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    alert: {
                        id: alert.id,
                        ruleName: alert.ruleName,
                        type: alert.type,
                        severity: alert.severity,
                        message: alert.message,
                        timestamp: alert.timestamp
                    },
                    data: alert.data
                })
            });
        } catch (error) {
            console.error('发送Webhook告警失败:', error);
        }
    }

    /**
     * 执行脚本
     */
    private executeScript(alert: Alert, config: any): void {
        // 这里需要实现脚本执行逻辑
        console.log('执行告警脚本:', alert, config);
    }

    /**
     * 映射严重性到通知类型
     */
    private mapSeverityToNotificationType(severity: string): NotificationType {
        switch (severity) {
            case 'critical':
                return 'interpolationError';
            case 'high':
                return 'networkError';
            case 'medium':
                return 'dataUpdate';
            case 'low':
                return 'newFeature';
            default:
                return 'systemMaintenance';
        }
    }

    /**
     * 映射严重性到优先级
     */
    private mapSeverityToPriority(severity: string): NotificationPriority {
        switch (severity) {
            case 'critical':
                return 'urgent';
            case 'high':
                return 'high';
            case 'medium':
                return 'normal';
            case 'low':
                return 'low';
            default:
                return 'low';
        }
    }

    /**
     * 获取通知超时时间
     */
    private getNotificationTimeout(severity: string): number {
        switch (severity) {
            case 'critical':
                return 0; // 不自动关闭
            case 'high':
                return 10000; // 10秒
            case 'medium':
                return 5000; // 5秒
            case 'low':
                return 3000; // 3秒
            default:
                return 3000;
        }
    }

    /**
     * 添加告警规则
     */
    addRule(rule: AlertRule): void {
        this.rules.set(rule.id, rule);
    }

    /**
     * 移除告警规则
     */
    removeRule(ruleId: string): void {
        this.rules.delete(ruleId);
    }

    /**
     * 启用告警规则
     */
    enableRule(ruleId: string): void {
        const rule = this.rules.get(ruleId);
        if (rule) {
            rule.enabled = true;
        }
    }

    /**
     * 禁用告警规则
     */
    disableRule(ruleId: string): void {
        const rule = this.rules.get(ruleId);
        if (rule) {
            rule.enabled = false;
        }
    }

    /**
     * 获取所有规则
     */
    getRules(): AlertRule[] {
        return Array.from(this.rules.values());
    }

    /**
     * 获取所有告警
     */
    getAlerts(): Alert[] {
        return [...this.alerts];
    }

    /**
     * 获取未确认告警
     */
    getUnacknowledgedAlerts(): Alert[] {
        return this.alerts.filter(alert => !alert.acknowledged);
    }

    /**
     * 确认告警
     */
    acknowledgeAlert(alertId: string): void {
        const alert = this.alerts.find(a => a.id === alertId);
        if (alert) {
            alert.acknowledged = true;
        }
    }

    /**
     * 解决告警
     */
    resolveAlert(alertId: string): void {
        const alert = this.alerts.find(a => a.id === alertId);
        if (alert) {
            alert.resolved = true;
            alert.acknowledged = true;
        }
    }

    /**
     * 获取消息中心告警
     */
    getMessageCenterAlerts(): Alert[] {
        return Array.from(this.messageCenter.values());
    }

    /**
     * 清空消息中心
     */
    clearMessageCenter(): void {
        this.messageCenter.clear();
    }

    /**
     * 更新设置
     */
    updateSettings(settings: Partial<AlertSettings>): void {
        this.settings = { ...this.settings, ...settings };
    }

    /**
     * 获取设置
     */
    getSettings(): AlertSettings {
        return { ...this.settings };
    }

    /**
     * 生成告警ID
     */
    private generateAlertId(): string {
        return `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * 销毁告警管理器
     */
    destroy(): void {
        this.rules.clear();
        this.alerts = [];
        this.alertHistory.clear();
        this.messageCenter.clear();
        this.isInitialized = false;

        console.log('实时插值告警管理器已销毁');
    }
}

export default RealtimeAlertManager;