/* global AbortSignal */
/**
 * 高德地图配置文件
 * 职责：
 * - 设置安全密钥
 * - 动态加载 JS API
 * - 获取用户设备位置
 * - 使用官方结构初始化地图
 * - 支持从后端获取API密钥
 */
import { LocationPermissionManager } from '../utils/locationPermissionManager.js';

// 默认配置（当无法从后端获取时使用）
// 注意：API 密钥应该从环境变量或后端获取，不要硬编码
const DEFAULT_AMAP_CONFIG = {
    API_KEY: import.meta.env.AMAP_API_KEY || "",
    SECURITY_CODE: import.meta.env.AMAP_SECURITY_CODE || "",
    DEFAULT_CENTER: [119.72170376, 30.26262781], // 杭州
    DEFAULT_ZOOM: 18
};

// 当前配置（从后端获取或使用默认值）
let currentAmapConfig = { ...DEFAULT_AMAP_CONFIG };

export const AmapConfig = {
    /**
     * 从后端更新配置
     * @param {Object} config - 从后端获取的配置对象
     */
    updateConfig(config) {
        if (config && config.amap) {
            currentAmapConfig = {
                API_KEY: config.amap.apiKey || DEFAULT_AMAP_CONFIG.API_KEY,
                SECURITY_CODE: config.amap.securityCode || DEFAULT_AMAP_CONFIG.SECURITY_CODE,
                DEFAULT_CENTER: config.amap.defaultCenter || DEFAULT_AMAP_CONFIG.DEFAULT_CENTER,
                DEFAULT_ZOOM: config.amap.defaultZoom || DEFAULT_AMAP_CONFIG.DEFAULT_ZOOM
            };
            console.log('✅ 高德地图配置已从后端更新');
        }
    },

    /**
     * 获取API密钥
     */
    getApiKey() {
        return currentAmapConfig.API_KEY;
    },

    /**
     * 获取安全密钥
     */
    getSecurityCode() {
        return currentAmapConfig.SECURITY_CODE;
    },

    /**
     * 获取默认中心点
     */
    getDefaultCenter() {
        return currentAmapConfig.DEFAULT_CENTER;
    },

    /**
     * 获取默认缩放级别
     */
    getDefaultZoom() {
        return currentAmapConfig.DEFAULT_ZOOM;
    }
};

/**
 * 网络状态监听器
 */
let networkStatusListener = null;

/**
 * 设置网络状态监听器
 * @param {Function} listener - 网络状态变化回调函数
 */
export function setNetworkStatusListener(listener) {
    networkStatusListener = listener;

    // 监听网络状态变化
    window.addEventListener('online', () => {
        console.log('🌐 网络已连接');
        if (networkStatusListener) networkStatusListener(true);
    });

    window.addEventListener('offline', () => {
        console.log('❌ 网络已断开');
        if (networkStatusListener) networkStatusListener(false);
    });
}

/**
 * 测试网络连接
 * @returns {Promise<boolean>} 返回网络是否可用
 */
async function testNetworkConnection() {
    try {
        console.log('🌐 测试网络连接...');
        await fetch('https://webapi.amap.com/maps', {
            method: 'HEAD',
            mode: 'no-cors',
            cache: 'no-cache',
            signal: AbortSignal.timeout(5000) // 5秒超时
        });
        console.log('✅ 网络连接正常');
        return true;
    } catch (error) {
        console.error('❌ 网络连接测试失败:', error);
        return false;
    }
}

/**
 * 设置高德地图安全密钥
 * 必须在加载 JS API 之前调用
 */
export function setAMapSecurity() {
    window._AMapSecurityConfig = {
        securityJsCode: AmapConfig.getSecurityCode()
    };
}

/**
 * 动态加载高德地图 JS API
 * 使用 iframe 方式加载，绕过 Electron 的安全限制
 * @param {string} containerId - 地图容器 ID
 * @returns {Promise<Object>} 返回地图代理对象
 */
export function loadAMapScript(containerId) {
    return new Promise((resolve, reject) => {
        console.log('🔄 开始加载高德地图 API（iframe 方式）...');
        console.log('📦 地图容器 ID:', containerId);

        // 检查 AMap 是否已加载
        if (window.AMap && window.AMap.Map) {
            console.log('✅ 高德地图 API 已加载，直接返回');
            resolve(window.AMap);
            return;
        }

        // 检查网络连接
        if (!navigator.onLine) {
            console.error('❌ 网络连接不可用');
            reject(new Error('网络连接不可用，无法加载高德地图 API'));
            return;
        }

        // 创建 iframe 来加载高德地图 API
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.style.width = '0';
        iframe.style.height = '0';
        iframe.id = 'amap-loader-iframe';
        
        document.body.appendChild(iframe);
        console.log('📤 创建 iframe 用于加载高德地图 API');

        // 设置 iframe 的内容
        const iframeContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { margin: 0; overflow: hidden; }
                    #amap-container { width: 100%; height: 100%; }
                </style>
            </head>
            <body>
                <div id="amap-container"></div>
                <script>
                    // 设置安全密钥
                    window._AMapSecurityConfig = {
                        securityJsCode: "${AmapConfig.getSecurityCode()}"
                    };
                    
                    var mapInstance = null;
                    
                    // 监听主窗口的消息
                    window.addEventListener('message', function(e) {
                        console.log('📨 iframe 收到消息:', e.data.type);
                        
                        if (e.data.type === 'INIT_MAP') {
                            console.log('📦 收到 INIT_MAP 消息');
                            // 创建地图
                            var containerInfo = e.data.containerInfo;
                            var mapOptions = e.data.mapOptions;
                            
                            console.log('   容器尺寸:', containerInfo.width, 'x', containerInfo.height);
                            
                            // 设置容器尺寸
                            var container = document.getElementById('amap-container');
                            container.style.width = containerInfo.width + 'px';
                            container.style.height = containerInfo.height + 'px';
                            
                            console.log('🎨 准备创建地图实例...');
                            // 创建地图实例
                            mapInstance = new AMap.Map('amap-container', {
                                center: mapOptions.center,
                                layers: [new AMap.TileLayer.Satellite()],
                                zoom: mapOptions.zoom
                            });
                            
                            console.log('✅ 地图实例在 iframe 中创建成功');
                            
                            // 通知主窗口地图已准备就绪
                            console.log('📤 发送 MAP_READY 消息到主窗口');
                            window.parent.postMessage({
                                type: 'MAP_READY',
                                success: true
                            }, '*');
                            
                        } else if (e.data.type === 'MAP_SET_CENTER') {
                            if (mapInstance) {
                                mapInstance.setCenter(e.data.center);
                            }
                        } else if (e.data.type === 'MAP_SET_ZOOM') {
                            if (mapInstance) {
                                mapInstance.setZoom(e.data.zoom);
                            }
                        } else if (e.data.type === 'MAP_GET_CENTER') {
                            if (mapInstance) {
                                var center = mapInstance.getCenter();
                                window.parent.postMessage({
                                    type: 'MAP_GET_CENTER_RESPONSE',
                                    center: [center.lng, center.lat]
                                }, '*');
                            }
                        } else if (e.data.type === 'MAP_GET_ZOOM') {
                            if (mapInstance) {
                                var zoom = mapInstance.getZoom();
                                window.parent.postMessage({
                                    type: 'MAP_GET_ZOOM_RESPONSE',
                                    zoom: zoom
                                }, '*');
                            }
                        } else if (e.data.type === 'MAP_SET_STATUS') {
                            if (mapInstance) {
                                mapInstance.setStatus(e.data.status);
                            }
                        } else if (e.data.type === 'MAP_SET_ZOOMS') {
                            if (mapInstance) {
                                mapInstance.setZooms(e.data.zooms);
                            }
                        } else if (e.data.type === 'MAP_ON') {
                            if (mapInstance) {
                                mapInstance.on(e.data.event, function(data) {
                                    var eventData = data;
                                    if (e.data.event === 'moveend') {
                                        var center = mapInstance.getCenter();
                                        eventData = [center.lng, center.lat];
                                    } else if (e.data.event === 'zoomend') {
                                        eventData = mapInstance.getZoom();
                                    }
                                    window.parent.postMessage({
                                        type: 'MAP_EVENT_' + e.data.event.toUpperCase(),
                                        data: eventData
                                    }, '*');
                                });
                            }
                        }
                    });
                    
                    // 加载高德地图 API
                    var script = document.createElement('script');
                    script.src = 'https://webapi.amap.com/maps?v=2.0&key=${AmapConfig.getApiKey()}';
                    script.onload = function() {
                        console.log('✅ 高德地图 API 在 iframe 中加载完成');
                        
                        // 等待 AMap 对象完全初始化
                        var checkCount = 0;
                        var maxChecks = 200;
                        var checkInterval = setInterval(function() {
                            checkCount++;
                            if (window.AMap && window.AMap.Map) {
                                clearInterval(checkInterval);
                                console.log('✅ AMap 对象在 iframe 中完全初始化');
                                
                                // 通知主窗口 AMap 已加载
                                window.parent.postMessage({
                                    type: 'AMAP_LOADED',
                                    success: true
                                }, '*');
                            } else if (checkCount >= maxChecks) {
                                clearInterval(checkInterval);
                                console.error('❌ iframe 中 AMap 初始化超时');
                                window.parent.postMessage({
                                    type: 'AMAP_ERROR',
                                    error: 'AMap initialization timeout in iframe'
                                }, '*');
                            }
                        }, 50);
                    };
                    script.onerror = function() {
                        console.error('❌ 高德地图脚本加载失败');
                        window.parent.postMessage({
                            type: 'AMAP_ERROR',
                            error: 'Script loading failed'
                        }, '*');
                    };
                    document.head.appendChild(script);
                </script>
            </body>
            </html>
        `;

        // 监听来自 iframe 的消息
        const messageHandler = (event) => {
            if (event.origin !== window.location.origin && event.origin !== 'null') {
                return; // 安全检查
            }

            if (event.data && event.data.type === 'AMAP_LOADED') {
                console.log('✅ 收到 iframe 消息：高德地图已加载');
                
                // 让 iframe 创建地图实例，而不是复制对象
                // 发送地图容器信息到 iframe
                const mapContainer = document.getElementById(containerId);
                if (!mapContainer) {
                    console.error('❌ 找不到地图容器:', containerId);
                    cleanup();
                    reject(new Error(`找不到地图容器: ${containerId}`));
                    return;
                }

                // 获取容器的尺寸和位置信息
                const rect = mapContainer.getBoundingClientRect();
                
                console.log('📤 发送地图容器信息到 iframe');
                console.log('   容器尺寸:', rect.width, 'x', rect.height);
                
                // 定义默认地图配置
                const defaultMapOptions = {
                    center: [119.72170376, 30.26262781], // 默认杭州
                    zoom: 18
                };
                
                // 发送消息到 iframe
                iframe.contentWindow.postMessage({
                    type: 'INIT_MAP',
                    containerInfo: {
                        width: rect.width,
                        height: rect.height,
                        top: rect.top,
                        left: rect.left
                    },
                    mapOptions: defaultMapOptions
                }, '*');
                
                // 监听地图创建成功的消息
                const mapReadyHandler = (e) => {
                    if (e.data && e.data.type === 'MAP_READY') {
                        console.log('✅ 地图在 iframe 中创建成功');
                        
                        // 清除超时定时器
                        if (timeoutId) {
                            clearTimeout(timeoutId);
                            timeoutId = null;
                        }
                        
                        // 注意：不要调用 cleanup()，因为我们还需要使用 iframe
                        // cleanup(); // 移除这行
                        
                        // 调整 iframe 的大小和位置
                        iframe.style.display = 'block';
                        iframe.style.position = 'absolute';
                        iframe.style.top = '0';
                        iframe.style.left = '0';
                        iframe.style.width = '100%';
                        iframe.style.height = '100%';
                        iframe.style.zIndex = '1';
                        
                        // 隐藏原来的地图容器
                        mapContainer.style.visibility = 'hidden';
                        
                        // 创建一个代理对象，包含所有必要的地图方法
                        // 使用默认值初始化
                        let cachedCenter = defaultMapOptions.center || [119.7167014612051, 30.265068364569423];
                        let cachedZoom = defaultMapOptions.zoom || 13;
                        
                        const mapProxy = {
                            iframe: iframe,
                            
                            // 同步方法（使用缓存值）
                            getCenter: () => {
                                return cachedCenter;
                            },
                            
                            getZoom: () => {
                                return cachedZoom;
                            },
                            
                            // 异步更新方法
                            setCenter: (center) => {
                                cachedCenter = center;
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_CENTER',
                                    center: center
                                }, '*');
                            },
                            
                            setZoom: (zoom) => {
                                cachedZoom = zoom;
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_ZOOM',
                                    zoom: zoom
                                }, '*');
                            },
                            
                            setStatus: (status) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_STATUS',
                                    status: status
                                }, '*');
                            },
                            
                            setZooms: (zooms) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_ZOOMS',
                                    zooms: zooms
                                }, '*');
                            },
                            
                            on: (event, callback) => {
                                // 监听事件
                                const eventHandler = (e) => {
                                    if (e.data.type === `MAP_EVENT_${event.toUpperCase()}`) {
                                        // 更新缓存
                                        if (event === 'moveend') {
                                            cachedCenter = e.data.data;
                                        } else if (event === 'zoomend') {
                                            cachedZoom = e.data.data;
                                        }
                                        callback(e.data.data);
                                    }
                                };
                                window.addEventListener('message', eventHandler);
                                
                                // 通知 iframe 监听事件
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_ON',
                                    event: event
                                }, '*');
                            },
                            
                            add: (layer) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_ADD_LAYER',
                                    layer: layer
                                }, '*');
                            },
                            
                            remove: (layer) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_REMOVE_LAYER',
                                    layer: layer
                                }, '*');
                            },
                            
                            setFitView: (layers) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_FIT_VIEW',
                                    layers: layers
                                }, '*');
                            },
                            
                            setBounds: (bounds) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_SET_BOUNDS',
                                    bounds: bounds
                                }, '*');
                            },
                            
                            addMarker: (marker) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_ADD_MARKER',
                                    marker: marker
                                }, '*');
                            },
                            
                            removeMarker: (marker) => {
                                iframe.contentWindow.postMessage({
                                    type: 'MAP_REMOVE_MARKER',
                                    marker: marker
                                }, '*');
                            },
                            
                            destroy: () => {
                                // 清理事件监听器
                                window.removeEventListener('message', messageHandler);
                                window.removeEventListener('message', mapReadyHandler);
                                
                                // 移除 iframe
                                if (document.body.contains(iframe)) {
                                    iframe.remove();
                                }
                                
                                // 恢复容器可见性
                                mapContainer.style.visibility = 'visible';
                            }
                        };
                        
                        // 获取初始值
                        const initHandler = (e) => {
                            if (e.data.type === 'MAP_GET_CENTER_RESPONSE') {
                                cachedCenter = e.data.center;
                                window.removeEventListener('message', initHandler);
                            } else if (e.data.type === 'MAP_GET_ZOOM_RESPONSE') {
                                cachedZoom = e.data.zoom;
                                window.removeEventListener('message', initHandler);
                            }
                        };
                        window.addEventListener('message', initHandler);
                        
                        // 请求初始值（检查 iframe 是否存在）
                        if (iframe.contentWindow) {
                            iframe.contentWindow.postMessage({ type: 'MAP_GET_CENTER' }, '*');
                            iframe.contentWindow.postMessage({ type: 'MAP_GET_ZOOM' }, '*');
                        }
                        
                        resolve(mapProxy);
                    }
                };
                
                window.addEventListener('message', mapReadyHandler);
                
                // 添加超时保护
                timeoutId = setTimeout(() => {
                    console.error('❌ 等待 iframe 创建地图超时');
                    window.removeEventListener('message', mapReadyHandler);
                    cleanup();
                    reject(new Error('等待 iframe 创建地图超时'));
                }, 15000); // 15秒超时
                
            } else if (event.data && event.data.type === 'AMAP_ERROR') {
                console.error('❌ 收到 iframe 消息：高德地图加载失败');
                cleanup();
                reject(new Error(event.data.error || '高德地图 API 加载失败'));
            }
        };

        window.addEventListener('message', messageHandler);

        let timeoutId = null; // 超时定时器 ID

        function cleanup() {
            window.removeEventListener('message', messageHandler);
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            if (document.body.contains(iframe)) {
                document.body.removeChild(iframe);
            }
        }

        // 设置 iframe 的内容
        iframe.srcdoc = iframeContent;
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
    console.log('🗺️ 开始初始化高德地图...');

    // 第一步：测试网络连接
    const networkOk = await testNetworkConnection();
    if (!networkOk) {
        console.warn('⚠️ 网络连接异常，继续尝试加载高德地图...');
    }

    // 第二步：设置安全密钥
    console.log('🔒 设置高德地图安全密钥...');
    setAMapSecurity();

    // 第三步：加载 JS API
    console.log('📡 加载高德地图 JS API...');
    const mapProxy = await loadAMapScript(containerId);
    
    // 第四步：获取用户位置
    try {
        console.log('📍 获取用户位置...');
        const center = await getUserLocation();
        console.log('✅ 用户位置:', center);
    } catch {
        console.warn('⚠️ 定位失败，使用杭州作为默认中心点');
    }

    console.log('✅ 高德地图初始化完成');
    return mapProxy;
}
