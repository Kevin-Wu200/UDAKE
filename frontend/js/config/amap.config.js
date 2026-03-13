/**
 * 高德地图配置文件
 * 职责：
 * - 设置安全密钥
 * - 动态加载 JS API
 * - 获取用户设备位置
 * - 使用官方结构初始化地图
 */
import { LocationPermissionManager } from '../utils/locationPermissionManager.js';

/**
 * 设置高德地图安全密钥
 * 必须在加载 JS API 之前调用
 */
export function setAMapSecurity() {
    window._AMapSecurityConfig = {
        securityJsCode: "10b5ef21f6b36d09e24d7b076d35dccc"
    };
}

/**
 * 动态加载高德地图 JS API
 * @returns {Promise<AMap>} 返回 AMap 对象
 */
export function loadAMapScript() {
    return new Promise((resolve, reject) => {
        if (window.AMap) {
            resolve(window.AMap);
            return;
        }

        const script = document.createElement("script");
        script.src = "https://webapi.amap.com/maps?v=2.0&key=2f3f114aa5671425aa3c52f707d741c5";

        script.onload = () => resolve(window.AMap);
        script.onerror = reject;

        document.head.appendChild(script);
    });
}

/**
 * 获取用户设备位置（通过权限管理模块）
 * @returns {Promise<[number, number]>} 返回 [经度, 纬度]
 */
function getUserLocation() {
    return LocationPermissionManager.getCurrentPosition()
        .then(pos => [pos.longitude, pos.latitude]);
}

/**
 * 初始化高德地图
 * 严格按照官方示例结构
 * @param {string} containerId - 地图容器 ID
 * @returns {Promise<AMap.Map>} 返回地图实例
 */
export async function initAMap(containerId) {
    // 第一步：设置安全密钥
    setAMapSecurity();

    // 第二步：加载 JS API
    await loadAMapScript();

    // 第三步：获取用户位置
    let center;
    try {
        center = await getUserLocation();
    } catch (e) {
        // 定位失败，使用北京作为默认中心点
        center = [116.397428, 39.90923];
    }

    // 第四步：按照官方示例结构初始化地图
    var map = new AMap.Map(containerId, {
        center: center,
        layers: [
            new AMap.TileLayer()
        ],
        zoom: 13
    });

    return map;
}
