/**
 * GeoJSON 解析工具
 * 解析 GeoJSON 文件并提取坐标系统和字段信息
 */

export class GeoJSONParser {
    /**
     * 解析 GeoJSON 文件
     * @param {File} file - GeoJSON 文件
     * @returns {Promise<Object>} 解析结果
     */
    static async parseFile(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = (e) => {
                try {
                    const geojson = JSON.parse(e.target.result);
                    const result = this.parseGeoJSON(geojson);
                    resolve(result);
                } catch (error) {
                    reject(new Error('GeoJSON 文件解析失败'));
                }
            };

            reader.onerror = () => {
                reject(new Error('文件读取失败'));
            };

            reader.readAsText(file);
        });
    }

    /**
     * 解析 GeoJSON 对象
     * @param {Object} geojson - GeoJSON 对象
     * @returns {Object} 解析结果
     */
    static parseGeoJSON(geojson) {
        // 验证 FeatureCollection
        if (geojson.type !== 'FeatureCollection') {
            throw new Error('仅支持 FeatureCollection 类型');
        }

        if (!geojson.features || geojson.features.length === 0) {
            throw new Error('GeoJSON 中没有要素');
        }

        // 验证 Point 类型
        const hasNonPoint = geojson.features.some(
            feature => feature.geometry.type !== 'Point'
        );

        if (hasNonPoint) {
            throw new Error('当前仅支持 Point 类型数据');
        }

        // 提取坐标系统信息
        const crsInfo = this.extractCRS(geojson);

        // 提取字段信息
        const fields = this.extractFields(geojson);

        return {
            geojson,
            crsInfo,
            fields,
            pointCount: geojson.features.length
        };
    }

    /**
     * 提取坐标系统信息
     * @param {Object} geojson - GeoJSON 对象
     * @returns {Object} 坐标系统信息
     */
    static extractCRS(geojson) {
        if (geojson.crs && geojson.crs.properties && geojson.crs.properties.name) {
            const crsName = geojson.crs.properties.name;
            const epsg = this.extractEPSG(crsName);

            return {
                detected: true,
                projectedName: crsName,
                projectedEPSG: epsg,
                geographicName: 'WGS84',
                geographicEPSG: 4326
            };
        }

        // 默认 WGS84
        return {
            detected: false,
            projectedName: '未检测到坐标系信息',
            projectedEPSG: null,
            geographicName: 'WGS84',
            geographicEPSG: 4326
        };
    }

    /**
     * 从 CRS 名称中提取 EPSG 代码
     * @param {String} crsName - CRS 名称
     * @returns {Number|null} EPSG 代码
     */
    static extractEPSG(crsName) {
        const match = crsName.match(/EPSG[:\s]*(\d+)/i);
        return match ? parseInt(match[1]) : null;
    }

    /**
     * 提取字段信息
     * @param {Object} geojson - GeoJSON 对象
     * @returns {Array<String>} 字段名数组
     */
    static extractFields(geojson) {
        if (!geojson.features[0].properties) {
            return [];
        }

        return Object.keys(geojson.features[0].properties);
    }

    /**
     * 验证文件类型
     * @param {File} file - 文件对象
     * @returns {Boolean} 是否为有效的 GeoJSON 文件
     */
    static validateFileType(file) {
        const validExtensions = ['.geojson', '.json'];
        const fileName = file.name.toLowerCase();
        return validExtensions.some(ext => fileName.endsWith(ext));
    }
}
