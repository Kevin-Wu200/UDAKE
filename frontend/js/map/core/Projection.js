/**
 * 投影转换模块
 * 负责经纬度与瓦片坐标之间的转换
 */
export class Projection {
    /**
     * 将经纬度转换为瓦片坐标
     * @param {number} lng - 经度
     * @param {number} lat - 纬度
     * @param {number} zoom - 缩放级别
     * @returns {{x: number, y: number}} 瓦片坐标
     */
    static lngLatToTile(lng, lat, zoom) {
        const n = Math.pow(2, zoom);
        const x = Math.floor((lng + 180) / 360 * n);
        const latRad = lat * Math.PI / 180;
        const y = Math.floor((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n);
        return { x, y };
    }

    /**
     * 将瓦片坐标转换为经纬度
     * @param {number} x - 瓦片 X 坐标
     * @param {number} y - 瓦片 Y 坐标
     * @param {number} zoom - 缩放级别
     * @returns {{lng: number, lat: number}} 经纬度
     */
    static tileToLngLat(x, y, zoom) {
        const n = Math.pow(2, zoom);
        const lng = x / n * 360 - 180;
        const latRad = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n)));
        const lat = latRad * 180 / Math.PI;
        return { lng, lat };
    }

    /**
     * 将经纬度转换为像素坐标
     * @param {number} lng - 经度
     * @param {number} lat - 纬度
     * @param {number} zoom - 缩放级别
     * @returns {{x: number, y: number}} 像素坐标
     */
    static lngLatToPixel(lng, lat, zoom) {
        const tile = this.lngLatToTile(lng, lat, zoom);
        const n = Math.pow(2, zoom);
        const x = (lng + 180) / 360 * n * 256;
        const latRad = lat * Math.PI / 180;
        const y = (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n * 256;
        return { x, y };
    }

    /**
     * 将像素坐标转换为经纬度
     * @param {number} x - 像素 X 坐标
     * @param {number} y - 像素 Y 坐标
     * @param {number} zoom - 缩放级别
     * @returns {{lng: number, lat: number}} 经纬度
     */
    static pixelToLngLat(x, y, zoom) {
        const n = Math.pow(2, zoom);
        const lng = x / (n * 256) * 360 - 180;
        const latRad = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / (n * 256))));
        const lat = latRad * 180 / Math.PI;
        return { lng, lat };
    }
}
