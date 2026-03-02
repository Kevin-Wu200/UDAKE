/**
 * 导航服务
 * 封装高德地图导航功能，为未来导航功能预留接口
 */
export class NavigationService {
    constructor(map) {
        this.map = map;
        this.driving = null;
        this.walking = null;
        this.transfer = null;
    }

    /**
     * 规划路线
     * @param {string} type - 路线类型: 'driving', 'walking', 'transfer'
     * @param {Array} start - 起点 [lng, lat]
     * @param {Array} end - 终点 [lng, lat]
     * @returns {Promise}
     */
    async planRoute(type, start, end) {
        return new Promise((resolve, reject) => {
            switch (type) {
                case 'driving':
                    this.planDriving(start, end, resolve, reject);
                    break;
                case 'walking':
                    this.planWalking(start, end, resolve, reject);
                    break;
                case 'transfer':
                    this.planTransfer(start, end, resolve, reject);
                    break;
                default:
                    reject(new Error(`不支持的路线类型: ${type}`));
            }
        });
    }

    /**
     * 驾车导航
     */
    planDriving(start, end, resolve, reject) {
        this.map.plugin(['AMap.Driving'], () => {
            this.driving = new AMap.Driving({
                map: this.map,
                panel: null // 可选：指定结果面板
            });

            this.driving.search(start, end, (status, result) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('驾车路线规划失败'));
                }
            });
        });
    }

    /**
     * 步行导航
     */
    planWalking(start, end, resolve, reject) {
        this.map.plugin(['AMap.Walking'], () => {
            this.walking = new AMap.Walking({
                map: this.map
            });

            this.walking.search(start, end, (status, result) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('步行路线规划失败'));
                }
            });
        });
    }

    /**
     * 公交换乘
     */
    planTransfer(start, end, resolve, reject) {
        this.map.plugin(['AMap.Transfer'], () => {
            this.transfer = new AMap.Transfer({
                map: this.map,
                city: '北京' // 需要指定城市
            });

            this.transfer.search(start, end, (status, result) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('公交路线规划失败'));
                }
            });
        });
    }

    /**
     * 清除路线
     */
    clearRoute() {
        if (this.driving) {
            this.driving.clear();
        }
        if (this.walking) {
            this.walking.clear();
        }
        if (this.transfer) {
            this.transfer.clear();
        }
    }

    /**
     * 销毁服务
     */
    destroy() {
        this.clearRoute();
        this.driving = null;
        this.walking = null;
        this.transfer = null;
    }
}
