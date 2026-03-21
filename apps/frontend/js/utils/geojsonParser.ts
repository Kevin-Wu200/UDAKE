/**
 * GeoJSON 解析工具
 * 解析 GeoJSON 文件并提取坐标系统和字段信息
 */
import type { GeoJSONFeatureCollection } from '../../types/core';
import type { CRSInfo, GeoJSONParseResult } from '../../types/geojson';

export class GeoJSONParser {
    /**
     * 解析 GeoJSON 文件
     */
    static async parseFile(file: File): Promise<GeoJSONParseResult> {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = (e: ProgressEvent<FileReader>) => {
                try {
                    const geojson = JSON.parse(e.target!.result as string);
                    const result = this.parseGeoJSON(geojson);
                    resolve(result);
                } catch {
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
     */
    static parseGeoJSON(geojson: GeoJSONFeatureCollection): GeoJSONParseResult {
        if (geojson.type !== 'FeatureCollection') {
            throw new Error('仅支持 FeatureCollection 类型');
        }

        if (!geojson.features || geojson.features.length === 0) {
            throw new Error('GeoJSON 中没有要素');
        }

        const hasNonPoint = geojson.features.some(
            feature => feature.geometry.type !== 'Point'
        );

        if (hasNonPoint) {
            throw new Error('当前仅支持 Point 类型数据');
        }

        const crsInfo = this.extractCRS(geojson);
        const fields = this.extractFields(geojson);

        return { geojson, crsInfo, fields, pointCount: geojson.features.length };
    }

    /**
     * 提取坐标系统信息
     */
    static extractCRS(geojson: GeoJSONFeatureCollection & { crs?: any }): CRSInfo {
        if (geojson.crs && geojson.crs.properties && geojson.crs.properties.name) {
            const crsName: string = geojson.crs.properties.name;
            const epsg = this.extractEPSG(crsName);

            return {
                detected: true,
                projectedName: crsName,
                projectedEPSG: epsg,
                geographicName: 'WGS84',
                geographicEPSG: 4326
            };
        }

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
     */
    static extractEPSG(crsName: string): number | null {
        const match = crsName.match(/EPSG[:\s]*(\d+)/i);
        return match ? parseInt(match[1]) : null;
    }

    /**
     * 提取字段信息
     */
    static extractFields(geojson: GeoJSONFeatureCollection): string[] {
        if (!geojson.features[0].properties) {
            return [];
        }
        return Object.keys(geojson.features[0].properties);
    }

    /**
     * 验证文件类型
     */
    static validateFileType(file: File): boolean {
        const validExtensions = ['.geojson', '.json'];
        const fileName = file.name.toLowerCase();
        return validExtensions.some(ext => fileName.endsWith(ext));
    }
}