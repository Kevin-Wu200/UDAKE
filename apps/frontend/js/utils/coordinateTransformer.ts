/**
 * 坐标转换工具
 * 处理不同坐标系统之间的转换
 * 支持 ArcGIS 和独立的坐标转换
 */
import type {
    MercatorCoordinate,
    WGS84Coordinate,
    SpatialReference,
    PointWithValue
} from '../../types/coordinate';

export class CoordinateTransformer {
    /**
     * WGS-84 转 Web Mercator（独立实现）
     */
    static wgs84ToWebMercator(lon: number, lat: number): MercatorCoordinate {
        const x = lon * 20037508.34 / 180;
        let y = Math.log(Math.tan((90 + lat) * Math.PI / 360)) / (Math.PI / 180);
        y = y * 20037508.34 / 180;
        return { x, y };
    }

    /**
     * Web Mercator 转 WGS-84（独立实现）
     */
    static webMercatorToWgs84(x: number, y: number): WGS84Coordinate {
        const lon = x / 20037508.34 * 180;
        let lat = y / 20037508.34 * 180;
        lat = 180 / Math.PI * (2 * Math.atan(Math.exp(lat * Math.PI / 180)) - Math.PI / 2);
        return { lon, lat };
    }

    /**
     * 转换点坐标到目标投影（使用 ArcGIS）
     */
    static async transformPoint(
        x: number,
        y: number,
        sourceSR: SpatialReference,
        targetSR: SpatialReference
    ): Promise<MercatorCoordinate> {
        const projection = await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js' as any);
        const Point = (await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js' as any)).default;

        await projection.load();

        const sourcePoint = new Point({ x, y, spatialReference: sourceSR });
        const targetPoint = projection.project(sourcePoint, targetSR);

        if (!targetPoint) {
            throw new Error('坐标转换失败');
        }

        return { x: targetPoint.x, y: targetPoint.y };
    }

    /**
     * 批量转换点坐标（使用 ArcGIS）
     */
    static async transformPoints(
        points: PointWithValue[],
        sourceSR: SpatialReference,
        targetSR: SpatialReference
    ): Promise<PointWithValue[]> {
        const projection = await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js' as any);
        const Point = (await import('https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js' as any)).default;

        await projection.load();

        const transformedPoints: PointWithValue[] = [];

        for (const point of points) {
            const sourcePoint = new Point({ x: point.x, y: point.y, spatialReference: sourceSR });
            const targetPoint = projection.project(sourcePoint, targetSR);

            if (!targetPoint) {
                throw new Error('坐标转换失败');
            }

            transformedPoints.push({ x: targetPoint.x, y: targetPoint.y, value: point.value });
        }

        return transformedPoints;
    }

    /**
     * 检测坐标是否为地理坐标（经纬度）
     */
    static isGeographic(x: number, y: number): boolean {
        return Math.abs(x) <= 180 && Math.abs(y) <= 90;
    }

    /**
     * 从 EPSG 代码创建空间参考
     */
    static createSpatialReference(epsg: number): SpatialReference {
        return { wkid: epsg };
    }

    /** WGS84 空间参考 */
    static get WGS84(): SpatialReference {
        return { wkid: 4326 };
    }

    /** Web Mercator 空间参考 */
    static get WebMercator(): SpatialReference {
        return { wkid: 3857 };
    }
}