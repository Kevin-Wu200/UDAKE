/**
 * 地理工具类
 * 提供 GeoJSON 相关的计算功能
 */
export class GeoUtils {
    /**
     * 从 GeoJSON 计算边界
     * @param {Object} geojson - GeoJSON 对象
     * @returns {Object} {minLng, minLat, maxLng, maxLat}
     */
    static calculateBoundsFromGeoJSON(geojson) {
        if (!geojson || !geojson.features || geojson.features.length === 0) {
            throw new Error('无效的 GeoJSON 数据');
        }

        let minLng = Infinity;
        let minLat = Infinity;
        let maxLng = -Infinity;
        let maxLat = -Infinity;

        geojson.features.forEach(feature => {
            if (!feature.geometry) return;

            const coords = this.extractCoordinates(feature.geometry);

            coords.forEach(([lng, lat]) => {
                if (lng < minLng) minLng = lng;
                if (lng > maxLng) maxLng = lng;
                if (lat < minLat) minLat = lat;
                if (lat > maxLat) maxLat = lat;
            });
        });

        if (!isFinite(minLng) || !isFinite(minLat) || !isFinite(maxLng) || !isFinite(maxLat)) {
            throw new Error('无法计算 GeoJSON 边界');
        }

        return { minLng, minLat, maxLng, maxLat };
    }

    /**
     * 从几何对象中提取所有坐标
     * @param {Object} geometry - GeoJSON 几何对象
     * @returns {Array<Array<number>>} 坐标数组
     */
    static extractCoordinates(geometry) {
        const coords = [];

        switch (geometry.type) {
            case 'Point':
                coords.push(geometry.coordinates);
                break;

            case 'MultiPoint':
            case 'LineString':
                coords.push(...geometry.coordinates);
                break;

            case 'MultiLineString':
            case 'Polygon':
                geometry.coordinates.forEach(ring => {
                    coords.push(...ring);
                });
                break;

            case 'MultiPolygon':
                geometry.coordinates.forEach(polygon => {
                    polygon.forEach(ring => {
                        coords.push(...ring);
                    });
                });
                break;

            case 'GeometryCollection':
                geometry.geometries.forEach(geom => {
                    coords.push(...this.extractCoordinates(geom));
                });
                break;

            default:
                console.warn(`未知的几何类型: ${geometry.type}`);
        }

        return coords;
    }

    /**
     * 计算两点之间的距离（米）
     * @param {Array<number>} point1 - [lng, lat]
     * @param {Array<number>} point2 - [lng, lat]
     * @returns {number} 距离（米）
     */
    static calculateDistance(point1, point2) {
        const [lng1, lat1] = point1;
        const [lng2, lat2] = point2;

        const R = 6371000; // 地球半径（米）
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        const Δφ = (lat2 - lat1) * Math.PI / 180;
        const Δλ = (lng2 - lng1) * Math.PI / 180;

        const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
                  Math.cos(φ1) * Math.cos(φ2) *
                  Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }

    /**
     * 扩展边界（添加边距）
     * @param {Object} bounds - {minLng, minLat, maxLng, maxLat}
     * @param {number} padding - 边距比例（0-1）
     * @returns {Object} 扩展后的边界
     */
    static expandBounds(bounds, padding = 0.1) {
        const { minLng, minLat, maxLng, maxLat } = bounds;

        const lngPadding = (maxLng - minLng) * padding;
        const latPadding = (maxLat - minLat) * padding;

        return {
            minLng: minLng - lngPadding,
            minLat: minLat - latPadding,
            maxLng: maxLng + lngPadding,
            maxLat: maxLat + latPadding
        };
    }
}
