/**
 * 坐标解析器
 * 支持三种坐标格式：
 * 1. 十进制度数 (DD)
 * 2. 度数十进制 (DDM)
 * 3. 度分秒 (DMS)
 */

export class CoordinateParser {
    /**
     * 解析坐标字符串
     * @param {string} inputString - 输入的坐标字符串
     * @param {string} type - 坐标类型: 'longitude' | 'latitude'
     * @returns {Object} { valid, value, format, error }
     */
    static parseCoordinate(inputString, type = 'longitude') {
        if (!inputString || typeof inputString !== 'string') {
            return {
                valid: false,
                value: null,
                format: null,
                error: '请输入坐标值'
            };
        }

        // 预处理：去除前后空格，替换中文符号
        let cleaned = inputString.trim();
        cleaned = this.normalizeSymbols(cleaned);

        // 尝试按优先级解析
        let result = null;

        // 1. 尝试 DMS 格式
        result = this.parseDMS(cleaned);
        if (result.valid) {
            return this.validateRange(result.value, type, 'DMS');
        }

        // 2. 尝试 DDM 格式
        result = this.parseDDM(cleaned);
        if (result.valid) {
            return this.validateRange(result.value, type, 'DDM');
        }

        // 3. 尝试 DD 格式
        result = this.parseDD(cleaned);
        if (result.valid) {
            return this.validateRange(result.value, type, 'DD');
        }

        return {
            valid: false,
            value: null,
            format: null,
            error: '无法识别的坐标格式'
        };
    }

    /**
     * 标准化符号（中文符号转英文）
     * @param {string} str
     * @returns {string}
     */
    static normalizeSymbols(str) {
        return str
            .replace(/′/g, "'")  // 中文分符号
            .replace(/″/g, '"')  // 中文秒符号
            .replace(/。/g, '.')  // 中文句号
            .replace(/\s+/g, ' '); // 多个空格合并为一个
    }

    /**
     * 解析十进制度数 (DD)
     * 支持: 116.4074, -73.9857
     * @param {string} str
     * @returns {Object}
     */
    static parseDD(str) {
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
     * 支持: 116°24.444', 116 24.444, 116°24.444
     * @param {string} str
     * @returns {Object}
     */
    static parseDDM(str) {
        // 匹配模式：度数 + 可选的°符号 + 空格或无 + 分钟（小数） + 可选的'符号
        const patterns = [
            /^(-?\d+)°\s*(\d+(?:\.\d+)?)'?$/,  // 116°24.444' 或 116°24.444
            /^(-?\d+)\s+(\d+(?:\.\d+)?)$/      // 116 24.444
        ];

        for (const pattern of patterns) {
            const match = str.match(pattern);
            if (match) {
                const degrees = parseFloat(match[1]);
                const minutes = parseFloat(match[2]);

                // 验证分钟范围
                if (minutes < 0 || minutes >= 60) {
                    return { valid: false, value: null };
                }

                // 转换为十进制度数
                const decimal = degrees + (degrees >= 0 ? 1 : -1) * (minutes / 60);

                return { valid: true, value: decimal };
            }
        }

        return { valid: false, value: null };
    }

    /**
     * 解析度分秒 (DMS)
     * 支持: 116°24'26", 116 24 26, 116°24'26
     * @param {string} str
     * @returns {Object}
     */
    static parseDMS(str) {
        // 匹配模式：度数 + 分钟 + 秒数
        const patterns = [
            /^(-?\d+)°\s*(\d+)'\s*(\d+(?:\.\d+)?)"?$/,  // 116°24'26" 或 116°24'26
            /^(-?\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)$/       // 116 24 26
        ];

        for (const pattern of patterns) {
            const match = str.match(pattern);
            if (match) {
                const degrees = parseFloat(match[1]);
                const minutes = parseFloat(match[2]);
                const seconds = parseFloat(match[3]);

                // 验证分钟和秒数范围
                if (minutes < 0 || minutes >= 60) {
                    return { valid: false, value: null };
                }
                if (seconds < 0 || seconds >= 60) {
                    return { valid: false, value: null };
                }

                // 转换为十进制度数
                const decimal = degrees + (degrees >= 0 ? 1 : -1) * (minutes / 60 + seconds / 3600);

                return { valid: true, value: decimal };
            }
        }

        return { valid: false, value: null };
    }

    /**
     * 验证坐标范围
     * @param {number} value - 十进制度数
     * @param {string} type - 'longitude' | 'latitude'
     * @param {string} format - 坐标格式
     * @returns {Object}
     */
    static validateRange(value, type, format) {
        if (type === 'longitude') {
            if (value < -180 || value > 180) {
                return {
                    valid: false,
                    value: null,
                    format: null,
                    error: '经度超出合法范围 (-180 ~ 180)'
                };
            }
        } else if (type === 'latitude') {
            if (value < -90 || value > 90) {
                return {
                    valid: false,
                    value: null,
                    format: null,
                    error: '纬度超出合法范围 (-90 ~ 90)'
                };
            }
        }

        return {
            valid: true,
            value,
            format,
            error: null
        };
    }

    /**
     * 解析采样值
     * @param {string} inputString
     * @returns {Object}
     */
    static parseSampleValue(inputString) {
        if (!inputString || typeof inputString !== 'string') {
            return {
                valid: false,
                value: null,
                error: '请输入采样值'
            };
        }

        const cleaned = inputString.trim();

        if (cleaned === '') {
            return {
                valid: false,
                value: null,
                error: '采样值不能为空'
            };
        }

        const value = parseFloat(cleaned);

        if (isNaN(value)) {
            return {
                valid: false,
                value: null,
                error: '采样值必须为数值'
            };
        }

        return {
            valid: true,
            value,
            error: null
        };
    }
}
