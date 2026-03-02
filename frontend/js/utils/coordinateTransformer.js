/**
 * 坐标转换工具
 * 处理不同坐标系统之间的转换
 * 支持 ArcGIS 和独立的坐标转换
 */

export class CoordinateTransformer {
    /**
     * WGS-84 转 Web Mercator（独立实现）
     * @param {Number} lon - 经度
     * @param {Number} lat - 纬度
     * @returns {Object} {x, y} Web Mercator 坐标
     */
    static wgs84ToWebMercator(lon, lat) {
        const x = lon * 20037508.34 / 180;
        let y = Math.log(Math.tan((90 + lat) * Math.PI / 360)) / (Math.PI / 180);
        y = y * 20037508.34 / 180;
        return { x, y };
    }

    /**
     * Web Mercator 转 WGS-84（独立实现）
     * @param {Number} x - X 坐标
     * @param {Number} y - Y 坐标
     * @returns {Object} {lon, lat} WGS-84 坐标
     */
    static webMercatorToWgs84(x, y) {
        const lon = x / 20037508.34 * 180;
        let lat = y / 20037508.34 * 180;
        lat = 180 / Math.PI * (2 * Math.atan(Math.exp(lat * Math.PI / 180)) - Math.PI / 2);
        return { lon, lat };
    }

    /**
     * 转换点坐标到目标投影（使用 ArcGIS）
     * @param {Number} x - X 坐标
     * @param {Number} y - Y 坐标
     * @param {Object} sourceSR - 源空间参考
     * @param {Object} targetSR - 目标空间参考
     * @returns {Promise<Object>} 转换后的坐标
     */
    static async transformPoint(x, y, sourceSR, targetSR) {
        const projection = await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js');
        const Point = (await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js')).default;

        await projection.load();

        const sourcePoint = new Point({
            x: x,
            y: y,
            spatialReference: sourceSR
        });

        const targetPoint = projection.project(sourcePoint, targetSR);

        if (!targetPoint) {
            throw new Error('坐标转换失败');
        }

        return {
            x: targetPoint.x,
            y: targetPoint.y
        };
    }

    /**
     * 批量转换点坐标（使用 ArcGIS）
     * @param {Array<Object>} points - 点数组 [{x, y, value}]
     * @param {Object} sourceSR - 源空间参考
     * @param {Object} targetSR - 目标空间参考
     * @returns {Promise<Array<Object>>} 转换后的点数组
     */
    static async transformPoints(points, sourceSR, targetSR) {
        const projection = await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js');
        const Point = (await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js')).default;

        await projection.load();

        const transformedPoints = [];

        for (const point of points) {
            const sourcePoint = new Point({
                x: point.x,
                y: point.y,
                spatialReference: sourceSR
            });

            const targetPoint = projection.project(sourcePoint, targetSR);

            if (!targetPoint) {
                throw new Error('坐标转换失败');
            }

            transformedPoints.push({
                x: targetPoint.x,
                y: targetPoint.y,
                value: point.value
            });
        }

        return transformedPoints;
    }

    /**
     * 检测坐标是否为地理坐标（经纬度）
     * @param {Number} x - X 坐标
     * @param {Number} y - Y 坐标
     * @returns {Boolean} 是否为地理坐标
     */
    static isGeographic(x, y) {
        return Math.abs(x) <= 180 && Math.abs(y) <= 90;
    }

    /**
     * 从 EPSG 代码创建空间参考
     * @param {Number} epsg - EPSG 代码
     * @returns {Object} 空间参考对象
     */
    static createSpatialReference(epsg) {
        return { wkid: epsg };
    }

    /**
     * WGS84 空间参考
     */
    static get WGS84() {
        return { wkid: 4326 };
    }

    /**
     * Web Mercator 空间参考
     */
    static get WebMercator() {
        return { wkid: 3857 };
    }
}
