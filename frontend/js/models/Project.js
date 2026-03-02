/**
 * 项目数据模型
 * 统一管理项目配置和采样点数据
 */
export class Project {
    /**
     * @param {Object} config - 项目配置
     * @param {string} config.sampling_mode - 采样模式: 'free' | 'region'
     * @param {string} config.coordinate_mode - 坐标获取方式: 'manual' | 'device'
     * @param {Object} [config.boundary_polygon] - 区域边界（可选）
     * @param {Array} [config.points] - 采样点数组
     */
    constructor(config = {}) {
        this.sampling_mode = config.sampling_mode || 'free';
        this.coordinate_mode = config.coordinate_mode || 'manual';
        this.boundary_polygon = config.boundary_polygon || null;
        this.points = config.points || [];
        this.crs = 'EPSG:4326'; // 固定坐标系
        this.created_at = new Date().toISOString();
        this.updated_at = new Date().toISOString();
    }

    /**
     * 添加采样点
     * @param {Object} point - 采样点数据
     * @param {number} point.longitude - 经度
     * @param {number} point.latitude - 纬度
     * @param {number} point.value - 采样值
     * @returns {boolean} 是否添加成功
     */
    addPoint(point) {
        // 区域采样模式下检查点是否在边界内
        if (this.sampling_mode === 'region' && this.boundary_polygon) {
            if (!this.isPointInPolygon(point)) {
                return false;
            }
        }

        this.points.push({
            ...point,
            timestamp: new Date().toISOString()
        });
        this.updated_at = new Date().toISOString();
        return true;
    }

    /**
     * 批量添加采样点
     * @param {Array} points - 采样点数组
     * @returns {Object} 添加结果 {success: number, failed: number}
     */
    addPoints(points) {
        let success = 0;
        let failed = 0;

        points.forEach(point => {
            if (this.addPoint(point)) {
                success++;
            } else {
                failed++;
            }
        });

        return { success, failed };
    }

    /**
     * 检查点是否在多边形内（Point in Polygon）
     * 使用射线法（Ray Casting Algorithm）
     * @param {Object} point - 点坐标
     * @returns {boolean}
     */
    isPointInPolygon(point) {
        if (!this.boundary_polygon) return true;

        const { longitude, latitude } = point;
        const coordinates = this.getPolygonCoordinates();

        let inside = false;
        for (let i = 0, j = coordinates.length - 1; i < coordinates.length; j = i++) {
            const xi = coordinates[i][0], yi = coordinates[i][1];
            const xj = coordinates[j][0], yj = coordinates[j][1];

            const intersect = ((yi > latitude) !== (yj > latitude))
                && (longitude < (xj - xi) * (latitude - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }

        return inside;
    }

    /**
     * 获取多边形坐标数组
     * 支持 Polygon 和 MultiPolygon
     * @returns {Array}
     */
    getPolygonCoordinates() {
        if (!this.boundary_polygon) return [];

        const geom = this.boundary_polygon.geometry || this.boundary_polygon;

        if (geom.type === 'Polygon') {
            return geom.coordinates[0]; // 外环
        } else if (geom.type === 'MultiPolygon') {
            // 对于 MultiPolygon，返回第一个多边形的外环
            return geom.coordinates[0][0];
        }

        return [];
    }

    /**
     * 设置边界多边形
     * @param {Object} polygon - GeoJSON 多边形
     */
    setBoundaryPolygon(polygon) {
        this.boundary_polygon = polygon;
        this.updated_at = new Date().toISOString();
    }

    /**
     * 移除采样点
     * @param {number} index - 点索引
     */
    removePoint(index) {
        if (index >= 0 && index < this.points.length) {
            this.points.splice(index, 1);
            this.updated_at = new Date().toISOString();
        }
    }

    /**
     * 清空所有采样点
     */
    clearPoints() {
        this.points = [];
        this.updated_at = new Date().toISOString();
    }

    /**
     * 获取采样点数量
     * @returns {number}
     */
    getPointCount() {
        return this.points.length;
    }

    /**
     * 序列化为 JSON
     * @returns {Object}
     */
    toJSON() {
        return {
            sampling_mode: this.sampling_mode,
            coordinate_mode: this.coordinate_mode,
            boundary_polygon: this.boundary_polygon,
            points: this.points,
            crs: this.crs,
            created_at: this.created_at,
            updated_at: this.updated_at
        };
    }

    /**
     * 从 JSON 恢复项目
     * @param {Object} json - JSON 数据
     * @returns {Project}
     */
    static fromJSON(json) {
        return new Project(json);
    }

    /**
     * 验证项目配置
     * @returns {Object} {valid: boolean, errors: Array}
     */
    validate() {
        const errors = [];

        if (!['free', 'region'].includes(this.sampling_mode)) {
            errors.push('无效的采样模式');
        }

        if (!['manual', 'device'].includes(this.coordinate_mode)) {
            errors.push('无效的坐标获取方式');
        }

        if (this.sampling_mode === 'region' && !this.boundary_polygon) {
            errors.push('区域采样模式需要设置边界多边形');
        }

        if (this.crs !== 'EPSG:4326') {
            errors.push('坐标系必须为 EPSG:4326');
        }

        return {
            valid: errors.length === 0,
            errors
        };
    }
}
