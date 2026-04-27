/**
 * 坐标解析器
 * 支持三种坐标格式：
 * 1. 十进制度数 (DD)
 * 2. 度数十进制 (DDM)
 * 3. 度分秒 (DMS)
 */
import type {
    CoordinateType,
    CoordinateFormat,
    CoordinateParseResult,
    SampleValueParseResult,
    InternalParseResult
} from '../../types/coordinate';
import { I18n } from './I18n';

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

export class CoordinateParser {
    /**
     * 解析坐标字符串
     */
    static parseCoordinate(inputString: string, type: CoordinateType = 'longitude'): CoordinateParseResult {
        if (!inputString || typeof inputString !== 'string') {
            return { valid: false, value: null, format: null, error: t('coordinate.error.valueRequired') };
        }

        let cleaned = inputString.trim();
        cleaned = this.normalizeSymbols(cleaned);

        // 1. 尝试 DMS 格式
        let result = this.parseDMS(cleaned);
        if (result.valid) {
            return this.validateRange(result.value!, type, 'DMS');
        }

        // 2. 尝试 DDM 格式
        result = this.parseDDM(cleaned);
        if (result.valid) {
            return this.validateRange(result.value!, type, 'DDM');
        }

        // 3. 尝试 DD 格式
        result = this.parseDD(cleaned);
        if (result.valid) {
            return this.validateRange(result.value!, type, 'DD');
        }

        return { valid: false, value: null, format: null, error: t('coordinate.error.invalidFormat') };
    }

    /**
     * 标准化符号（中文符号转英文）
     */
    static normalizeSymbols(str: string): string {
        return str
            .replace(/′/g, "'")
            .replace(/″/g, '"')
            .replace(/。/g, '.')
            .replace(/\s+/g, ' ');
    }

    /**
     * 解析十进制度数 (DD)
     */
    static parseDD(str: string): InternalParseResult {
        const regex = /^-?\d+(\.\d+)?$/;
        if (!regex.test(str)) {
            return { valid: false, value: null };
        }
        const value = parseFloat(str);
        if (isNaN(value)) {
            return { valid: false, value: null };
        }
        return { valid: true, value };
    }

    /**
     * 解析度数十进制 (DDM)
     */
    static parseDDM(str: string): InternalParseResult {
        const patterns = [
            /^(-?\d+)°\s*(\d+(?:\.\d+)?)'?$/,
            /^(-?\d+)\s+(\d+(?:\.\d+)?)$/
        ];

        for (const pattern of patterns) {
            const match = str.match(pattern);
            if (match) {
                const degrees = parseFloat(match[1]);
                const minutes = parseFloat(match[2]);
                if (minutes < 0 || minutes >= 60) {
                    return { valid: false, value: null };
                }
                const decimal = degrees + (degrees >= 0 ? 1 : -1) * (minutes / 60);
                return { valid: true, value: decimal };
            }
        }

        return { valid: false, value: null };
    }

    /**
     * 解析度分秒 (DMS)
     */
    static parseDMS(str: string): InternalParseResult {
        const patterns = [
            /^(-?\d+)°\s*(\d+)'\s*(\d+(?:\.\d+)?)"?$/,
            /^(-?\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)$/
        ];

        for (const pattern of patterns) {
            const match = str.match(pattern);
            if (match) {
                const degrees = parseFloat(match[1]);
                const minutes = parseFloat(match[2]);
                const seconds = parseFloat(match[3]);
                if (minutes < 0 || minutes >= 60) {
                    return { valid: false, value: null };
                }
                if (seconds < 0 || seconds >= 60) {
                    return { valid: false, value: null };
                }
                const decimal = degrees + (degrees >= 0 ? 1 : -1) * (minutes / 60 + seconds / 3600);
                return { valid: true, value: decimal };
            }
        }

        return { valid: false, value: null };
    }

    /**
     * 验证坐标范围
     */
    static validateRange(value: number, type: CoordinateType, format: CoordinateFormat): CoordinateParseResult {
        if (type === 'longitude') {
            if (value < -180 || value > 180) {
                return { valid: false, value: null, format: null, error: t('coordinate.error.invalidRange.longitude') };
            }
        } else if (type === 'latitude') {
            if (value < -90 || value > 90) {
                return { valid: false, value: null, format: null, error: t('coordinate.error.invalidRange.latitude') };
            }
        }
        return { valid: true, value, format, error: null };
    }

    /**
     * 解析采样值
     */
    static parseSampleValue(inputString: string): SampleValueParseResult {
        if (!inputString || typeof inputString !== 'string') {
            return { valid: false, value: null, error: t('coordinate.error.sampling.valueRequired') };
        }
        const cleaned = inputString.trim();
        if (cleaned === '') {
            return { valid: false, value: null, error: t('coordinate.error.sampling.valueEmpty') };
        }
        const value = parseFloat(cleaned);
        if (isNaN(value)) {
            return { valid: false, value: null, error: t('coordinate.error.sampling.mustNum') };
        }
        return { valid: true, value, error: null };
    }
}