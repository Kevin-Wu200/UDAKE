/**
 * 地理工具类
 * 提供 GeoJSON 相关的计算功能
 */
import type { Bounds, GeoJSONGeometry, GeoJSONFeatureCollection } from '../../types/core';

type Position = [number, number];

export class GeoUtils {
    /**
     * 从 GeoJSON 计算边界
     */
    static calculateBoundsFromGeoJSON(geojson: GeoJSONFeatureCollection): Bounds {
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
     */
    static extractCoordinates(geometry: GeoJSONGeometry & { geometries?: GeoJSONGeometry[] }): Position[] {
        const coords: Position[] = [];

        switch (geometry.type) {
            case 'Point':
                coords.push(geometry.coordinates as unknown as Position);
                break;
            case 'MultiPoint':
            case 'LineString':
                coords.push(...(geometry.coordinates as unknown as Position[]));
                break;
            case 'MultiLineString':
            case 'Polygon':
                (geometry.coordinates as unknown as Position[][]).forEach(ring => {
                    coords.push(...ring);
                });
                break;
            case 'MultiPolygon':
                (geometry.coordinates as unknown as Position[][][]).forEach(polygon => {
                    polygon.forEach(ring => {
                        coords.push(...ring);
                    });
                });
                break;
            default:
                if ((geometry as any).type === 'GeometryCollection' && geometry.geometries) {
                    geometry.geometries.forEach(geom => {
                        coords.push(...this.extractCoordinates(geom));
                    });
                } else {
                    console.warn(`未知的几何类型: ${geometry.type}`);
                }
        }

        return coords;
    }

    /**
     * 计算两点之间的距离（米）
     */
    static calculateDistance(point1: Position, point2: Position): number {
        const [lng1, lat1] = point1;
        const [lng2, lat2] = point2;

        const R = 6371000;
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
     */
    static expandBounds(bounds: Bounds, padding: number = 0.1): Bounds {
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