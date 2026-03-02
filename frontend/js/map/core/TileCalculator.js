/**
 * 瓦片计算模块
 * 负责计算需要加载的瓦片列表
 */
export class TileCalculator {
    /**
     * 计算视口内需要加载的瓦片
     * @param {number} centerLng - 中心点经度
     * @param {number} centerLat - 中心点纬度
     * @param {number} zoom - 缩放级别
     * @param {number} width - 容器宽度
     * @param {number} height - 容器高度
     * @returns {Array} 瓦片列表 [{x, y, z}]
     */
    static calculateVisibleTiles(centerLng, centerLat, zoom, width, height) {
        const n = Math.pow(2, zoom);

        // 计算中心点的瓦片坐标
        const centerTileX = (centerLng + 180) / 360 * n;
        const latRad = centerLat * Math.PI / 180;
        const centerTileY = (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n;

        // 计算需要显示的瓦片范围
        const tilesX = Math.ceil(width / 256) + 1;
        const tilesY = Math.ceil(height / 256) + 1;

        const startX = Math.floor(centerTileX - tilesX / 2);
        const startY = Math.floor(centerTileY - tilesY / 2);

        const tiles = [];
        for (let y = startY; y < startY + tilesY; y++) {
            for (let x = startX; x < startX + tilesX; x++) {
                // 确保瓦片坐标在有效范围内
                if (x >= 0 && x < n && y >= 0 && y < n) {
                    tiles.push({ x, y, z: zoom });
                }
            }
        }

        return tiles;
    }

    /**
     * 计算瓦片在容器中的位置
     * @param {number} tileX - 瓦片 X 坐标
     * @param {number} tileY - 瓦片 Y 坐标
     * @param {number} centerLng - 中心点经度
     * @param {number} centerLat - 中心点纬度
     * @param {number} zoom - 缩放级别
     * @param {number} width - 容器宽度
     * @param {number} height - 容器高度
     * @returns {{left: number, top: number}} 瓦片位置
     */
    static calculateTilePosition(tileX, tileY, centerLng, centerLat, zoom, width, height) {
        const n = Math.pow(2, zoom);

        // 计算中心点的像素坐标
        const centerPixelX = (centerLng + 180) / 360 * n * 256;
        const latRad = centerLat * Math.PI / 180;
        const centerPixelY = (1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2 * n * 256;

        // 计算瓦片的像素坐标
        const tilePixelX = tileX * 256;
        const tilePixelY = tileY * 256;

        // 计算相对于容器中心的偏移
        const left = tilePixelX - centerPixelX + width / 2;
        const top = tilePixelY - centerPixelY + height / 2;

        return { left, top };
    }
}
