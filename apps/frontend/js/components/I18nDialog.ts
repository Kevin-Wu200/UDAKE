import { I18n } from '../utils/I18n.js';

type DialogParams = Record<string, string | number>;
type RegexTranslationRule = {
    pattern: RegExp;
    toEn: (match: RegExpMatchArray) => string;
};

const LITERAL_ZH_TO_EN: Record<string, string> = {
    '请在地图上点击以创建圆形围栏': 'Please click on the map to create a circular geofence',
    '请在浏览器的下载历史中找到下载的文件': 'Please find the downloaded file in your browser download history',
    '感谢您的反馈！我们已记录此错误。': 'Thank you for your feedback. We have recorded this error.',
    '参数已保存': 'Parameters saved',
    '更新间隔必须大于等于1000毫秒': 'Update interval must be greater than or equal to 1000 ms',
    '确定要清空所有缓存吗？': 'Are you sure you want to clear all cache?',
    '确定要重置所有性能统计吗？': 'Are you sure you want to reset all performance metrics?',
    '导出图表失败，请重试': 'Failed to export chart, please try again',
    '位置权限被拒绝': 'Location permission denied',
    '请先获取当前位置': 'Please get current location first',
    '开始记录轨迹失败': 'Failed to start track recording',
    '确定要删除这个地理围栏吗？': 'Are you sure you want to delete this geofence?',
    '没有已保存的布局': 'No saved layouts',
    '布局不存在': 'Layout does not exist',
    '确定要重置为默认布局吗？': 'Are you sure you want to reset to default layout?',
    '布局已重置为默认状态': 'Layout has been reset to default',
    '请先选择起点': 'Please select a start point first',
    '请至少添加2个采样点': 'Please add at least 2 sampling points',
    '确定要删除这条记录吗？': 'Are you sure you want to delete this record?',
    '确定要清空所有历史记录吗？': 'Are you sure you want to clear all history records?',
    '请填写反馈内容': 'Please fill in feedback content',
    '反馈已提交，感谢您的建议！': 'Feedback submitted, thank you for your suggestion!',
    '确定要清除所有反馈吗？此操作不可恢复。': 'Are you sure you want to clear all feedback? This action cannot be undone.',
    '请输入有效的半径': 'Please enter a valid radius',
    '获取推荐参数失败，请稍后重试': 'Failed to fetch recommended parameters, please try again later',
    '请输入参数组合名称:': 'Please enter parameter combination name:',
    '请输入订阅名称:': 'Please enter subscription name:',
    '请输入更新间隔（毫秒）:': 'Please enter update interval (ms):',
    '请输入围栏半径（米）：': 'Please enter geofence radius (m):',
    '请输入围栏名称：': 'Please enter geofence name:',
    '请输入新的围栏名称：': 'Please enter a new geofence name:',
    '请输入布局名称：': 'Please enter layout name:',
    '请输入配置名称：': 'Please enter config name:',
    '请输入配置描述（可选）：': 'Please enter config description (optional):',
    '请选择预设类型（environment/agriculture/geology/custom）：': 'Please select preset type (environment/agriculture/geology/custom):',
    '配置名称：': 'Config name:',
    '配置描述：': 'Config description:',
    '配置创建成功': 'Config created successfully',
    '配置更新成功': 'Config updated successfully',
    '配置复制成功': 'Config copied successfully',
    '配置删除成功': 'Config deleted successfully',
    '配置导出成功': 'Config exported successfully',
    '已重置为默认配置': 'Reset to default config',
    '确定要清除所有缓存吗？此操作不可撤销。': 'Are you sure you want to clear all cache? This action cannot be undone.',
    '确定要重置所有手势设置为默认值吗？': 'Are you sure you want to reset all gesture settings to default?',
    '确定要重置为默认配置吗？这将清除所有自定义配置。': 'Are you sure you want to reset to default configuration? This will clear all custom configurations.'
};

const REGEX_TRANSLATION_RULES: RegexTranslationRule[] = [
    {
        pattern: /^导出成功:\s*(.+)$/,
        toEn: (match) => `Export successful: ${match[1]}`
    },
    {
        pattern: /^导出失败:\s*(.+)$/,
        toEn: (match) => `Export failed: ${match[1]}`
    },
    {
        pattern: /^已应用参数组合:\s*(.+)$/,
        toEn: (match) => `Applied parameter combination: ${match[1]}`
    },
    {
        pattern: /^已保存参数组合:\s*(.+)$/,
        toEn: (match) => `Saved parameter combination: ${match[1]}`
    },
    {
        pattern: /^导入成功:\s*(\d+) 条，失败:\s*(\d+) 条$/,
        toEn: (match) => `Import completed: ${match[1]} succeeded, ${match[2]} failed`
    },
    {
        pattern: /^最多只能上传\s*(\d+)\s*个文件$/,
        toEn: (match) => `You can upload at most ${match[1]} files`
    },
    {
        pattern: /^文件\s+(.+)\s+超过 5MB 限制$/,
        toEn: (match) => `File ${match[1]} exceeds the 5MB limit`
    },
    {
        pattern: /^布局 "(.+)" 已保存$/,
        toEn: (match) => `Layout "${match[1]}" saved`
    },
    {
        pattern: /^布局 "(.+)" 已加载$/,
        toEn: (match) => `Layout "${match[1]}" loaded`
    },
    {
        pattern: /^确定要删除布局 "(.+)" 吗？$/,
        toEn: (match) => `Are you sure you want to delete layout "${match[1]}"?`
    },
    {
        pattern: /^路径规划失败:\s*(.+)$/,
        toEn: (match) => `Route planning failed: ${match[1]}`
    },
    {
        pattern: /^已应用\s+(.+)\s+预设$/,
        toEn: (match) => `Applied preset ${match[1]}`
    },
    {
        pattern: /^已应用配置:\s*(.+)$/,
        toEn: (match) => `Applied config: ${match[1]}`
    },
    {
        pattern: /^创建配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to create config: ${match[1]}`
    },
    {
        pattern: /^更新配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to update config: ${match[1]}`
    },
    {
        pattern: /^复制配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to copy config: ${match[1]}`
    },
    {
        pattern: /^删除配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to delete config: ${match[1]}`
    },
    {
        pattern: /^导出配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to export config: ${match[1]}`
    },
    {
        pattern: /^导入配置失败:\s*(.+)$/,
        toEn: (match) => `Failed to import config: ${match[1]}`
    },
    {
        pattern: /^重置失败:\s*(.+)$/,
        toEn: (match) => `Reset failed: ${match[1]}`
    },
    {
        pattern: /^地理围栏 "(.+)" 创建成功$/,
        toEn: (match) => `Geofence "${match[1]}" created successfully`
    },
    {
        pattern: /^创建地理围栏失败：\s*(.+)$/,
        toEn: (match) => `Failed to create geofence: ${match[1]}`
    },
    {
        pattern: /^获取位置失败：\s*(.+)$/,
        toEn: (match) => `Failed to get location: ${match[1]}`
    },
    {
        pattern: /^开始记录轨迹失败：\s*(.+)$/,
        toEn: (match) => `Failed to start track recording: ${match[1]}`
    },
    {
        pattern: /^停止记录轨迹失败：\s*(.+)$/,
        toEn: (match) => `Failed to stop track recording: ${match[1]}`
    }
];

function hasChinese(text: string): boolean {
    return /[\u4e00-\u9fff]/.test(text);
}

export class I18nDialog {
    private static interpolate(text: string, params?: DialogParams): string {
        if (!params) {
            return text;
        }

        return Object.entries(params).reduce((result, [key, value]) => {
            const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            return result.replace(new RegExp(`\\{${escapedKey}\\}`, 'g'), String(value));
        }, text);
    }

    private static translateLiteralText(message: string): string {
        if (I18n.locale !== 'en-US') {
            return message;
        }

        if (!hasChinese(message)) {
            return message;
        }

        if (LITERAL_ZH_TO_EN[message]) {
            return LITERAL_ZH_TO_EN[message];
        }

        for (const rule of REGEX_TRANSLATION_RULES) {
            const match = message.match(rule.pattern);
            if (match) {
                return rule.toEn(match);
            }
        }

        return message;
    }

    static resolve(messageKeyOrText: string, params?: DialogParams): string {
        const translated = I18n.t(messageKeyOrText, params);

        if (translated !== messageKeyOrText) {
            return translated;
        }

        const interpolated = this.interpolate(messageKeyOrText, params);
        return this.translateLiteralText(interpolated);
    }

    static alert(messageKey: string, params?: DialogParams): void {
        window.alert(this.resolve(messageKey, params));
    }

    static confirm(messageKey: string, params?: DialogParams): boolean {
        return window.confirm(this.resolve(messageKey, params));
    }

    static prompt(messageKey: string, defaultValueKey?: string, params?: DialogParams): string | null {
        const message = this.resolve(messageKey, params);
        const defaultValue = typeof defaultValueKey === 'string' ? this.resolve(defaultValueKey) : undefined;
        return window.prompt(message, defaultValue);
    }
}
