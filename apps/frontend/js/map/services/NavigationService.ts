/**
 * 导航服务
 * 封装高德地图导航功能，为未来导航功能预留接口
 */

import type { RouteType } from '../../../types/map-engine';

/**
 * 导航服务
 * 封装高德地图导航功能
 */
export class NavigationService {
    /** 地图实例 */
    map: any;

    /** 驾车导航实例 */
    driving: any;

    /** 步行导航实例 */
    walking: any;

    /** 公交换乘实例 */
    transfer: any;

    constructor(map: any) {
        this.map = map;
        this.driving = null;
        this.walking = null;
        this.transfer = null;
    }

    /**
     * 规划路线
     * @param type - 路线类型: 'driving', 'walking', 'transfer'
     * @param start - 起点 [lng, lat]
     * @param end - 终点 [lng, lat]
     * @returns Promise
     */
    async planRoute(type: RouteType, start: [number, number], end: [number, number]): Promise<any> {
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
    protected planDriving(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void
    ): void {
        this.map.plugin(['AMap.Driving'], () => {
            const AMap = (window as any).AMap;
            this.driving = new AMap.Driving({
                map: this.map,
                panel: null // 可选：指定结果面板
            });

            this.driving.search(start, end, (status: string, result: any) => {
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
    protected planWalking(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void
    ): void {
        this.map.plugin(['AMap.Walking'], () => {
            const AMap = (window as any).AMap;
            this.walking = new AMap.Walking({
                map: this.map
            });

            this.walking.search(start, end, (status: string, result: any) => {
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
    protected planTransfer(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void
    ): void {
        this.map.plugin(['AMap.Transfer'], () => {
            const AMap = (window as any).AMap;
            this.transfer = new AMap.Transfer({
                map: this.map,
                city: '北京' // 需要指定城市
            });

            this.transfer.search(start, end, (status: string, result: any) => {
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
    clearRoute(): void {
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
    destroy(): void {
        this.clearRoute();
        this.driving = null;
        this.walking = null;
        this.transfer = null;
    }
}