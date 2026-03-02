/**
 * 图层管理器
 * 管理GeoJSON采样点、预测栅格、方差栅格、不确定性指数图层
 * 支持图层开关、动态色带、点击查询
 * 使用适配器模式，支持多种地图引擎
 */

export class LayerManager {
    constructor(adapter) {
        this.adapter = adapter;
        this.view = adapter.getView();
        this.setupClickHandler();
    }

    /**
     * 添加GeoJSON采样点图层
     */
    async addPointsLayer(geojson) {
        await this.adapter.addPointsLayer(geojson, 'points');
    }

    /**
     * 添加栅格图层（预测或方差）
     */
    async addRasterLayer(type, url) {
        await this.adapter.addRasterLayer(type, url);
    }

    /**
     * 切换图层可见性
     */
    toggleLayer(layerName, visible) {
        this.adapter.toggleLayer(layerName, visible);
    }

    /**
     * 设置图层透明度
     */
    setLayerOpacity(layerName, opacity) {
        this.adapter.setLayerOpacity(layerName, opacity);
    }

    /**
     * 设置点击查询处理器
     */
    setupClickHandler() {
        this.adapter.setClickHandler((graphic, mapPoint) => {
            this.showInfoPanel(graphic, mapPoint);
        });
    }

    /**
     * 显示信息浮窗
     */
    showInfoPanel(graphic, mapPoint) {
        const infoPanel = document.getElementById('info-panel');
        const infoContent = document.getElementById('info-content');

        if (!infoPanel || !infoContent) return;

        let content = `<p><strong>坐标:</strong> ${mapPoint.longitude.toFixed(6)}, ${mapPoint.latitude.toFixed(6)}</p>`;

        if (graphic && graphic.attributes) {
            for (const [key, value] of Object.entries(graphic.attributes)) {
                if (key !== 'OBJECTID' && key !== 'FID') {
                    content += `<p><strong>${key}:</strong> ${value}</p>`;
                }
            }
        }

        infoContent.innerHTML = content;
        infoPanel.style.display = 'block';
    }

    /**
     * 隐藏信息浮窗
     */
    hideInfoPanel() {
        const infoPanel = document.getElementById('info-panel');
        if (infoPanel) {
            infoPanel.style.display = 'none';
        }
    }

    /**
     * 添加单个采样点
     */
    async addSamplingPoint(pointData) {
        await this.adapter.addMarker(pointData);
    }

    /**
     * 获取所有采样点数据
     */
    getSamplingPoints() {
        return this.adapter.getSamplingPoints();
    }

    /**
     * 移除所有图层
     */
    clearAllLayers() {
        this.adapter.clearAllLayers();
    }
}
