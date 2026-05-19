/**
 * 高斯-克吕格投影坐标转换服务
 * 基于 proj4 实现经纬度与 GK 平面坐标的双向转换
 */
import proj4 from 'proj4';
import type { GKProjectionConfig, GKCoordinate, GKBandType } from '../../../types/map-engine';

/** WGS84 坐标系 EPSG 代码 */
const WGS84_EPSG = 'EPSG:4326';

/**
 * 计算 GK 投影带号（3度带或6度带）
 */
export function calculateBandNumber(centralMeridian: number, bandType: GKBandType): number {
    if (bandType === '3-degree') {
        // 3度带：带号 = (中央经线 - 1.5) / 3
        return Math.round((centralMeridian - 1.5) / 3);
    } else {
        // 6度带：带号 = (中央经线 + 3) / 6
        return Math.round((centralMeridian + 3) / 6);
    }
}

/**
 * 根据经度自动计算 GK 3度带中央经线
 */
export function calculateCentralMeridian(lng: number, bandType: GKBandType = '3-degree'): number {
    if (bandType === '3-degree') {
        return Math.round(lng / 3) * 3;
    } else {
        return Math.round((lng - 3) / 6) * 6 + 3;
    }
}

/**
 * 构建 GK 投影的 proj4 定义字符串
 */
function buildGKProjString(config: GKProjectionConfig): string {
    const {
        centralMeridian = 117,
        semiMajorAxis = 6378137,
        inverseFlattening = 298.257223563,
        falseEasting = 500000,
        falseNorthing = 0
    } = config;

    // 计算扁率
    const flattening = 1 / inverseFlattening;

    // 构建 proj4 字符串（tmerc = Transverse Mercator，即高斯-克吕格投影）
    // +approx 使用球面近似避免椭球计算的限制
    return `+proj=tmerc +lat_0=0 +lon_0=${centralMeridian} +k=1 ` +
        `+x_0=${falseEasting} +y_0=${falseNorthing} ` +
        `+a=${semiMajorAxis} +f=${flattening} +units=m +no_defs +approx`;
}

/**
 * 高斯-克吕格投影坐标转换服务
 */
export class GKProjectionService {
    private config: GKProjectionConfig;
    private gkProjString: string;
    private _forward: proj4.Converter;
    private _inverse: proj4.Converter;

    constructor(config: GKProjectionConfig = {}) {
        this.config = {
            centralMeridian: config.centralMeridian ?? 117,
            bandType: config.bandType ?? '3-degree',
            semiMajorAxis: config.semiMajorAxis ?? 6378137,
            inverseFlattening: config.inverseFlattening ?? 298.257223563,
            falseEasting: config.falseEasting ?? 500000,
            falseNorthing: config.falseNorthing ?? 0
        };

        this.gkProjString = buildGKProjString(this.config);
        this._forward = proj4(WGS84_EPSG, this.gkProjString);
        this._inverse = proj4(this.gkProjString, WGS84_EPSG);
    }

    /**
     * 自动根据中心经度更新投影配置
     */
    autoConfig(centerLng: number): void {
        const centralMeridian = calculateCentralMeridian(centerLng, this.config.bandType);
        if (centralMeridian !== this.config.centralMeridian) {
            this.config.centralMeridian = centralMeridian;
            this.gkProjString = buildGKProjString(this.config);
            this._forward = proj4(WGS84_EPSG, this.gkProjString);
            this._inverse = proj4(this.gkProjString, this.gkProjString);
        }
    }

    /**
     * 获取当前配置
     */
    getConfig(): Readonly<GKProjectionConfig> {
        return this.config;
    }

    /**
     * 获取当前中央经线
     */
    getCentralMeridian(): number {
        return this.config.centralMeridian!;
    }

    /**
     * 获取带号
     */
    getBandNumber(): number {
        return calculateBandNumber(this.config.centralMeridian!, this.config.bandType!);
    }

    /**
     * [经纬度] -> [GK 平面坐标 (米)]
     * @param lng 经度（度）
     * @param lat 纬度（度）
     * @returns GK 平面坐标 { x: 东向, y: 北向 }
     */
    toGK(lng: number, lat: number): GKCoordinate {
        const [x, y] = this._forward.forward([lng, lat]);
        return { x, y };
    }

    /**
     * [GK 平面坐标 (米)] -> [经纬度]
     * @param x 东向坐标（米）
     * @param y 北向坐标（米）
     * @returns [lng, lat]
     */
    fromGK(x: number, y: number): [number, number] {
        const [lng, lat] = this._inverse.forward([x, y]);
        return [lng, lat];
    }

    /**
     * [GK 平面坐标] -> [画布像素坐标]
     * @param gkX GK 东向坐标（米）
     * @param gkY GK 北向坐标（米）
     * @param offsetX 视口偏移 X（像素，对应左上角 GK X 坐标）
     * @param offsetY 视口偏移 Y（像素，对应左上角 GK Y 坐标 的负值）
     * @param scale 当前缩放比例（像素/米）
     * @param canvasHeight 画布高度（像素，用于 Y 轴翻转）
     * @returns [pixelX, pixelY]
     */
    gkToPixel(
        gkX: number,
        gkY: number,
        offsetX: number,
        offsetY: number,
        scale: number,
        canvasHeight: number
    ): [number, number] {
        const pixelX = (gkX - offsetX) * scale;
        // Y 轴翻转：GK 坐标 Y 增大 = 向北 = 画布像素 Y 减小
        const pixelY = canvasHeight - (gkY - offsetY) * scale;
        return [pixelX, pixelY];
    }

    /**
     * [画布像素坐标] -> [GK 平面坐标]
     * @param pixelX 画布像素 X
     * @param pixelY 画布像素 Y
     * @param offsetX 视口偏移 X（GK X 坐标）
     * @param offsetY 视口偏移 Y（GK Y 坐标）
     * @param scale 当前缩放比例（像素/米）
     * @param canvasHeight 画布高度（像素）
     * @returns GKCoordinate
     */
    pixelToGK(
        pixelX: number,
        pixelY: number,
        offsetX: number,
        offsetY: number,
        scale: number,
        canvasHeight: number
    ): GKCoordinate {
        const gkX = pixelX / scale + offsetX;
        const gkY = (canvasHeight - pixelY) / scale + offsetY;
        return { x: gkX, y: gkY };
    }

    /**
     * [经纬度] -> [画布像素坐标]（便捷方法）
     */
    lngLatToPixel(
        lng: number,
        lat: number,
        offsetX: number,
        offsetY: number,
        scale: number,
        canvasHeight: number
    ): [number, number] {
        const gk = this.toGK(lng, lat);
        return this.gkToPixel(gk.x, gk.y, offsetX, offsetY, scale, canvasHeight);
    }

    /**
     * [画布像素坐标] -> [经纬度]（便捷方法）
     */
    pixelToLngLat(
        pixelX: number,
        pixelY: number,
        offsetX: number,
        offsetY: number,
        scale: number,
        canvasHeight: number
    ): [number, number] {
        const gk = this.pixelToGK(pixelX, pixelY, offsetX, offsetY, scale, canvasHeight);
        return this.fromGK(gk.x, gk.y);
    }

    /**
     * 计算两点之间的水平距离（米）
     */
    distanceBetween(gk1: GKCoordinate, gk2: GKCoordinate): number {
        const dx = gk1.x - gk2.x;
        const dy = gk1.y - gk2.y;
        return Math.sqrt(dx * dx + dy * dy);
    }

    /**
     * 获取适合初始显示的缩放比例（根据视口需要覆盖的GK范围）
     * @param gkBounds 需要显示的 GK 坐标范围
     * @param canvasWidth 画布宽度（像素）
     * @param canvasHeight 画布高度（像素）
     * @param padding 边距比例（0-1），默认 0.1
     * @returns 缩放比例（像素/米）
     */
    fitToGKBounds(
        gkBounds: { minX: number; minY: number; maxX: number; maxY: number },
        canvasWidth: number,
        canvasHeight: number,
        padding: number = 0.1
    ): { offsetX: number; offsetY: number; scale: number } {
        const gkWidth = gkBounds.maxX - gkBounds.minX;
        const gkHeight = gkBounds.maxY - gkBounds.minY;

        const paddedWidth = gkWidth * (1 + padding * 2);
        const paddedHeight = gkHeight * (1 + padding * 2);

        const scaleX = canvasWidth / paddedWidth;
        const scaleY = canvasHeight / paddedHeight;
        const scale = Math.min(scaleX, scaleY);

        const centerGKX = (gkBounds.minX + gkBounds.maxX) / 2;
        const centerGKY = (gkBounds.minY + gkBounds.maxY) / 2;

        const offsetX = centerGKX - canvasWidth / (2 * scale);
        const offsetY = centerGKY - canvasHeight / (2 * scale);

        return { offsetX, offsetY, scale };
    }
}
