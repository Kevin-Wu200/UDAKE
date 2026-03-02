import { MapAdapter } from './MapAdapter.js';
import { TiandituConfig } from '../config/tianditu.config.js';

/**
 * 天地图适配器
 * 使用 Leaflet 加载天地图底图
 */
export class TiandituAdapter extends MapAdapter {
    constructor() {
        super();
        this.map = null;
        this.layers = {};
        this.markersLayer = null;
        this.samplingPoints = [];
    }

    /**
     * 初始化天地图
     */
    async initMap(containerId) {
        // 检查 Leaflet 是否已加载
        if (typeof L === 'undefined') {
            throw new Error('Leaflet 库未加载');
        }

        const config = TiandituConfig.getConfig();

        // 创建地图实例
        this.map = L.map(containerId, {
            center: config.center,
            zoom: config.zoom,
            minZoom: config.minZoom,
            maxZoom: config.maxZoom,
            zoomControl: true,
            attributionControl: true
        });

        // 添加天地图矢量底图
        const vecLayer = L.tileLayer(config.vecUrl, {
            subdomains: config.subdomains,
            attribution: '&copy; 天地图'
        });
        vecLayer.addTo(this.map);

        // 添加天地图注记图层
        const cvaLayer = L.tileLayer(config.cvaUrl, {
            subdomains: config.subdomains
        });
        cvaLayer.addTo(this.map);

        // 创建标记图层组
        this.markersLayer = L.layerGroup().addTo(this.map);

        console.log('✅ 天地图初始化完成', config.isMock ? '(Mock模式)' : '');

        return this.map;
    }

    getView() {
        return this.map;
    }

    /**
     * 添加 GeoJSON 点图层
     */
    async addPointsLayer(geojson, layerName = 'points') {
        try {
            // 移除旧图层
            if (this.layers[layerName]) {
                this.map.removeLayer(this.layers[layerName]);
            }

            // 创建 GeoJSON 图层
            const layer = L.geoJSON(geojson, {
                pointToLayer: (feature, latlng) => {
                    return L.circleMarker(latlng, {
                        radius: 6,
                        fillColor: '#007AFF',
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.8
                    });
                },
                onEachFeature: (feature, layer) => {
                    if (feature.properties) {
                        let popupContent = '<div>';
                        for (const [key, value] of Object.entries(feature.properties)) {
                            popupContent += `<p><strong>${key}:</strong> ${value}</p>`;
                        }
                        popupContent += '</div>';
                        layer.bindPopup(popupContent);
                    }
                }
            });

            layer.addTo(this.map);
            this.layers[layerName] = layer;

            // 缩放到图层范围
            const bounds = layer.getBounds();
            if (bounds.isValid()) {
                this.map.fitBounds(bounds);
            }

            console.log('✅ 采样点图层加载完成');
        } catch (error) {
            console.error('❌ 加载采样点失败:', error);
            throw error;
        }
    }

    /**
     * 添加栅格图层
     * 注意：Leaflet 需要使用 georaster-layer-for-leaflet 插件来加载 GeoTIFF
     * 这里提供基础实现，实际使用时需要引入相应插件
     */
    async addRasterLayer(type, url) {
        try {
            console.warn('⚠️ 天地图模式下栅格图层加载需要额外插件支持');
            console.log(`栅格图层 URL: ${url}`);

            // 移除旧图层
            if (this.layers[type]) {
                this.map.removeLayer(this.layers[type]);
            }

            // 这里需要使用 georaster-layer-for-leaflet 或类似插件
            // 暂时使用 ImageOverlay 作为占位
            // 实际项目中需要根据后端返回的栅格格式选择合适的加载方式

            console.log(`✅ ${type}栅格图层已准备（需要插件支持）`);
        } catch (error) {
            console.error(`❌ 加载${type}栅格失败:`, error);
            throw error;
        }
    }

    /**
     * 添加单个采样点
     */
    async addMarker(pointData) {
        // Leaflet 使用 [纬度, 经度] 格式
        const marker = L.circleMarker([pointData.y, pointData.x], {
            radius: 6,
            fillColor: '#007AFF',
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8
        });

        marker.bindPopup(`
            <div>
                <p><strong>值:</strong> ${pointData.value}</p>
                <p><strong>坐标:</strong> ${pointData.x.toFixed(6)}, ${pointData.y.toFixed(6)}</p>
            </div>
        `);

        marker.addTo(this.markersLayer);
        this.samplingPoints.push(pointData);

        console.log('✅ 采样点已添加:', pointData);
    }

    /**
     * 添加多边形
     */
    async addPolygon(coordinates, options = {}) {
        // 转换坐标格式：从 [x, y] 到 [y, x]
        const latlngs = coordinates.map(ring =>
            ring.map(coord => [coord[1], coord[0]])
        );

        const polygon = L.polygon(latlngs, {
            color: options.strokeColor || '#007AFF',
            weight: options.strokeWidth || 2,
            fillColor: options.fillColor || '#007AFF',
            fillOpacity: options.fillOpacity || 0.2
        });

        polygon.addTo(this.markersLayer);
    }

    toggleLayer(layerName, visible) {
        if (this.layers[layerName]) {
            if (visible) {
                this.map.addLayer(this.layers[layerName]);
            } else {
                this.map.removeLayer(this.layers[layerName]);
            }
            console.log(`${layerName}图层: ${visible ? '显示' : '隐藏'}`);
        }
    }

    setLayerOpacity(layerName, opacity) {
        if (this.layers[layerName]) {
            this.layers[layerName].setOpacity(opacity);
        }
    }

    removeLayer(layerName) {
        if (this.layers[layerName]) {
            this.map.removeLayer(this.layers[layerName]);
            delete this.layers[layerName];
        }
    }

    clearAllLayers() {
        for (const [name, layer] of Object.entries(this.layers)) {
            this.map.removeLayer(layer);
        }
        this.layers = {};
        if (this.markersLayer) {
            this.markersLayer.clearLayers();
        }
        this.samplingPoints = [];
        console.log('✅ 所有图层已清除');
    }

    zoomToLayer(layerName) {
        if (this.layers[layerName]) {
            const bounds = this.layers[layerName].getBounds();
            if (bounds.isValid()) {
                this.map.fitBounds(bounds);
            }
        }
    }

    setClickHandler(handler) {
        this.map.on('click', (event) => {
            try {
                const latlng = event.latlng;
                // 转换为统一格式：{longitude, latitude}
                const mapPoint = {
                    longitude: latlng.lng,
                    latitude: latlng.lat
                };
                handler(null, mapPoint);
            } catch (error) {
                console.error('点击查询失败:', error);
            }
        });
    }

    getSamplingPoints() {
        return this.samplingPoints;
    }
}
