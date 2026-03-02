/**
 * 天地图配置文件
 *
 * 重要说明：
 * 1. 需要申请天地图 Token：https://console.tianditu.gov.cn/
 * 2. 使用 WGS-84 坐标系（EPSG:4326）
 * 3. 支持矢量底图和注记图层
 */

export const TiandituConfig = {
    // 天地图 Token（需要替换为真实 Token）
    TOKEN: 'YOUR_TIANDITU_TOKEN_PLACEHOLDER',

    // 天地图服务地址
    VEC_URL: 'http://t{s}.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=',
    CVA_URL: 'http://t{s}.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=',

    // 子域名
    SUBDOMAINS: ['0', '1', '2', '3', '4', '5', '6', '7'],

    // 默认地图配置
    DEFAULT_CENTER: [35.681236, 139.767125], // [纬度, 经度] - 东京
    DEFAULT_ZOOM: 10,

    // 地图视图配置
    MIN_ZOOM: 3,
    MAX_ZOOM: 18,

    // 坐标系
    CRS: 'EPSG:4326',

    // Mock 模式检测
    isMockMode() {
        return !this.TOKEN || this.TOKEN === 'YOUR_TIANDITU_TOKEN_PLACEHOLDER';
    },

    // 获取矢量底图 URL
    getVecUrl() {
        return this.VEC_URL + this.TOKEN;
    },

    // 获取注记图层 URL
    getCvaUrl() {
        return this.CVA_URL + this.TOKEN;
    },

    // 获取配置信息
    getConfig() {
        if (this.isMockMode()) {
            console.warn('⚠️ 天地图 Token 未配置，当前为 Mock 模式');
        }
        return {
            token: this.TOKEN,
            vecUrl: this.getVecUrl(),
            cvaUrl: this.getCvaUrl(),
            subdomains: this.SUBDOMAINS,
            center: this.DEFAULT_CENTER,
            zoom: this.DEFAULT_ZOOM,
            minZoom: this.MIN_ZOOM,
            maxZoom: this.MAX_ZOOM,
            crs: this.CRS,
            isMock: this.isMockMode()
        };
    }
};
