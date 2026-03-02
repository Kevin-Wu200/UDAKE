/**
 * 字段匹配工具
 * 自动匹配 X、Y、Point_Data 字段
 */

export class FieldMatcher {
    /**
     * 匹配字段
     * @param {Array<String>} fields - 字段名数组
     * @returns {Object} 匹配结果
     */
    static matchFields(fields) {
        return {
            x: this.matchX(fields),
            y: this.matchY(fields),
            pointData: this.matchPointData(fields)
        };
    }

    /**
     * 匹配 X 字段
     * @param {Array<String>} fields - 字段名数组
     * @returns {String|null} 匹配的字段名
     */
    static matchX(fields) {
        const patterns = ['x', 'lon', 'longitude', 'lng', 'long'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 匹配 Y 字段
     * @param {Array<String>} fields - 字段名数组
     * @returns {String|null} 匹配的字段名
     */
    static matchY(fields) {
        const patterns = ['y', 'lat', 'latitude'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 匹配 Point_Data 字段
     * @param {Array<String>} fields - 字段名数组
     * @returns {String|null} 匹配的字段名
     */
    static matchPointData(fields) {
        const patterns = ['value', 'z', 'data', 'point_data', 'pointdata'];
        return this.findMatch(fields, patterns);
    }

    /**
     * 查找匹配的字段
     * @param {Array<String>} fields - 字段名数组
     * @param {Array<String>} patterns - 匹配模式数组
     * @returns {String|null} 匹配的字段名
     */
    static findMatch(fields, patterns) {
        for (const pattern of patterns) {
            const match = fields.find(field =>
                field.toLowerCase() === pattern.toLowerCase()
            );
            if (match) {
                return match;
            }
        }
        return null;
    }

    /**
     * 验证字段选择
     * @param {Object} selection - 字段选择对象
     * @returns {Object} 验证结果
     */
    static validateSelection(selection) {
        const errors = {};

        if (!selection.x) {
            errors.x = '请选择 X 字段';
        }

        if (!selection.y) {
            errors.y = '请选择 Y 字段';
        }

        if (!selection.pointData) {
            errors.pointData = '请选择 Point_Data 字段';
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    /**
     * 验证数值字段
     * @param {Object} geojson - GeoJSON 对象
     * @param {String} fieldName - 字段名
     * @returns {Boolean} 是否为数值字段
     */
    static isNumericField(geojson, fieldName) {
        const features = geojson.features;

        for (const feature of features) {
            const value = feature.properties[fieldName];
            if (value !== null && value !== undefined) {
                if (isNaN(parseFloat(value))) {
                    return false;
                }
            }
        }

        return true;
    }
}
