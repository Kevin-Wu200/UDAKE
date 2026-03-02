/**
 * 坐标系统信息组件
 * 显示当前MapView的坐标系信息
 */
export class CoordinateSystemInfo {
    constructor(view) {
        this.view = view;
        this.container = null;
    }

    /**
     * 创建坐标系信息面板
     */
    createPanel() {
        const panel = document.createElement('div');
        panel.className = 'panel coordinate-system-panel';
        panel.innerHTML = `
            <h2 class="panel-title">坐标系统信息</h2>
            <div class="panel-content">
                <div class="coordinate-info">
                    <div class="info-item">
                        <span class="info-label">投影坐标系</span>
                        <span class="info-value" id="projection-name">加载中...</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">投影 EPSG</span>
                        <span class="info-value" id="projection-epsg">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">地理坐标系</span>
                        <span class="info-value" id="geographic-name">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">地理 EPSG</span>
                        <span class="info-value" id="geographic-epsg">-</span>
                    </div>
                    <div class="info-item wkt-item">
                        <span class="info-label">WKT</span>
                        <button class="btn-collapse" id="wkt-toggle">展开</button>
                    </div>
                    <div class="wkt-content" id="wkt-content" style="display: none;">
                        <pre id="wkt-text">-</pre>
                    </div>
                </div>
            </div>
        `;

        this.container = panel;
        this.bindEvents();
        this.updateInfo();

        return panel;
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        const toggleBtn = this.container.querySelector('#wkt-toggle');
        const wktContent = this.container.querySelector('#wkt-content');

        toggleBtn.addEventListener('click', () => {
            const isVisible = wktContent.style.display !== 'none';
            wktContent.style.display = isVisible ? 'none' : 'block';
            toggleBtn.textContent = isVisible ? '展开' : '收起';
        });
    }

    /**
     * 更新坐标系信息
     */
    async updateInfo() {
        const sr = this.view.spatialReference;

        if (!sr) {
            this.showUnknown();
            return;
        }

        // 获取 WKID
        const wkid = sr.wkid || sr.latestWkid;

        // 设置投影 EPSG
        const projectionEpsg = this.container.querySelector('#projection-epsg');
        projectionEpsg.textContent = wkid ? `EPSG:${wkid}` : '未识别';

        // 获取坐标系名称
        try {
            const projectionName = await this.getProjectionName(wkid);
            this.container.querySelector('#projection-name').textContent = projectionName;
        } catch (error) {
            this.container.querySelector('#projection-name').textContent = '未识别坐标系';
        }

        // 设置地理坐标系信息（如果是投影坐标系）
        if (sr.wkid && sr.wkid !== 4326 && sr.wkid !== 3857) {
            // 大多数投影坐标系基于 WGS84
            this.container.querySelector('#geographic-name').textContent = 'WGS 1984';
            this.container.querySelector('#geographic-epsg').textContent = 'EPSG:4326';
        } else if (sr.wkid === 4326) {
            this.container.querySelector('#geographic-name').textContent = 'WGS 1984';
            this.container.querySelector('#geographic-epsg').textContent = 'EPSG:4326';
        } else if (sr.wkid === 3857) {
            this.container.querySelector('#geographic-name').textContent = 'WGS 1984';
            this.container.querySelector('#geographic-epsg').textContent = 'EPSG:4326';
        }

        // 设置 WKT
        const wkt = sr.wkt || '无 WKT 信息';
        this.container.querySelector('#wkt-text').textContent = wkt;
    }

    /**
     * 获取投影坐标系名称
     */
    async getProjectionName(wkid) {
        const commonProjections = {
            4326: 'WGS 1984',
            3857: 'Web Mercator',
            2154: 'RGF93 / Lambert-93',
            32633: 'WGS 84 / UTM zone 33N',
            32634: 'WGS 84 / UTM zone 34N',
            32635: 'WGS 84 / UTM zone 35N',
            32636: 'WGS 84 / UTM zone 36N',
            3395: 'WGS 84 / World Mercator',
            4269: 'NAD83',
            4267: 'NAD27',
            2163: 'US National Atlas Equal Area',
            102100: 'Web Mercator Auxiliary Sphere'
        };

        return commonProjections[wkid] || `EPSG:${wkid}`;
    }

    /**
     * 显示未识别状态
     */
    showUnknown() {
        this.container.querySelector('#projection-name').textContent = '未识别坐标系';
        this.container.querySelector('#projection-epsg').textContent = '-';
        this.container.querySelector('#geographic-name').textContent = '-';
        this.container.querySelector('#geographic-epsg').textContent = '-';
        this.container.querySelector('#wkt-text').textContent = '-';
    }
}
