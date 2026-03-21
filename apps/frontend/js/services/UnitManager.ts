/**
 * 单位管理器
 * 处理坐标系统、长度单位和面积单位的转换和配置
 */

import { appStore } from '../store/Store';
import type {
    CoordinateSystem,
    LengthUnit,
    AreaUnit
} from '../../types/core';

// ========== 坐标系统转换 ==========

/**
 * 坐标转换工具类
 */
export class CoordinateConverter {
    /**
     * WGS84 转 GCJ02 (火星坐标)
     * @param lng 经度
     * @param lat 纬度
     */
    static wgs84ToGcj02(lng: number, lat: number): [number, number] {
        const a = 6378245.0;
        const ee = 0.00669342162296594323;

        if (this.outOfChina(lng, lat)) {
            return [lng, lat];
        }

        let dLat = this.transformLat(lng - 105.0, lat - 35.0);
        let dLng = this.transformLng(lng - 105.0, lat - 35.0);

        const radLat = (lat / 180.0) * Math.PI;
        let magic = Math.sin(radLat);
        magic = 1 - ee * magic * magic;
        const sqrtMagic = Math.sqrt(magic);

        dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
        dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);

        return [lng + dLng, lat + dLat];
    }

    /**
     * GCJ02 转 WGS84
     * @param lng 经度
     * @param lat 纬度
     */
    static gcj02ToWgs84(lng: number, lat: number): [number, number] {
        const a = 6378245.0;
        const ee = 0.00669342162296594323;

        if (this.outOfChina(lng, lat)) {
            return [lng, lat];
        }

        let dLat = this.transformLat(lng - 105.0, lat - 35.0);
        let dLng = this.transformLng(lng - 105.0, lat - 35.0);

        const radLat = (lat / 180.0) * Math.PI;
        let magic = Math.sin(radLat);
        magic = 1 - ee * magic * magic;
        const sqrtMagic = Math.sqrt(magic);

        dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
        dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);

        const mglat = lat + dLat;
        const mglng = lng + dLng;

        return [lng * 2 - mglng, lat * 2 - mglat];
    }

    /**
     * WGS84 转 BD09 (百度坐标)
     * @param lng 经度
     * @param lat 纬度
     */
    static wgs84ToBd09(lng: number, lat: number): [number, number] {
        const gcj = this.wgs84ToGcj02(lng, lat);
        return this.gcj02ToBd09(gcj[0], gcj[1]);
    }

    /**
     * BD09 转 WGS84
     * @param lng 经度
     * @param lat 纬度
     */
    static bd09ToWgs84(lng: number, lat: number): [number, number] {
        const gcj = this.bd09ToGcj02(lng, lat);
        return this.gcj02ToWgs84(gcj[0], gcj[1]);
    }

    /**
     * GCJ02 转 BD09
     * @param lng 经度
     * @param lat 纬度
     */
    static gcj02ToBd09(lng: number, lat: number): [number, number] {
        const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * 3000.0 * Math.PI / 180.0);
        const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * 3000.0 * Math.PI / 180.0);
        const bdLng = z * Math.cos(theta) + 0.0065;
        const bdLat = z * Math.sin(theta) + 0.006;
        return [bdLng, bdLat];
    }

    /**
     * BD09 转 GCJ02
     * @param lng 经度
     * @param lat 纬度
     */
    static bd09ToGcj02(lng: number, lat: number): [number, number] {
        const x = lng - 0.0065;
        const y = lat - 0.006;
        const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * 3000.0 * Math.PI / 180.0);
        const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * 3000.0 * Math.PI / 180.0);
        const gcjLng = z * Math.cos(theta);
        const gcjLat = z * Math.sin(theta);
        return [gcjLng, gcjLat];
    }

    private static transformLat(lng: number, lat: number): number {
        let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng));
        ret += (20.0 * Math.sin(6.0 * lng * Math.PI) + 20.0 * Math.sin(2.0 * lng * Math.PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(lat * Math.PI) + 40.0 * Math.sin(lat / 3.0 * Math.PI)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(lat / 12.0 * Math.PI) + 320.0 * Math.sin(lat * Math.PI / 30.0)) * 2.0 / 3.0;
        return ret;
    }

    private static transformLng(lng: number, lat: number): number {
        let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng));
        ret += (20.0 * Math.sin(6.0 * lng * Math.PI) + 20.0 * Math.sin(2.0 * lng * Math.PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(lng * Math.PI) + 40.0 * Math.sin(lng / 3.0 * Math.PI)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(lng / 12.0 * Math.PI) + 300.0 * Math.sin(lng / 30.0 * Math.PI)) * 2.0 / 3.0;
        return ret;
    }

    private static outOfChina(lng: number, lat: number): boolean {
        return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
    }
}

// ========== 长度单位转换 ==========

/**
 * 长度单位转换工具类
 */
export class LengthConverter {
    private static readonly CONVERSIONS: Record<LengthUnit, number> = {
        'm': 1,           // 米
        'km': 0.001,      // 千米
        'ft': 3.28084,    // 英尺
        'mi': 0.000621371 // 英里
    };

    /**
     * 转换长度单位
     * @param value 数值
     * @param from 源单位
     * @param to 目标单位
     */
    static convert(value: number, from: LengthUnit, to: LengthUnit): number {
        // 先转换为米
        const inMeters = value / this.CONVERSIONS[from];
        // 再转换为目标单位
        return inMeters * this.CONVERSIONS[to];
    }

    /**
     * 格式化长度值
     * @param value 数值
     * @param unit 单位
     * @param decimals 小数位数
     */
    static format(value: number, unit: LengthUnit, decimals: number = 2): string {
        const units: Record<LengthUnit, string> = {
            'm': 'm',
            'km': 'km',
            'ft': 'ft',
            'mi': 'mi'
        };
        return `${value.toFixed(decimals)} ${units[unit]}`;
    }

    /**
     * 获取单位全称
     * @param unit 单位
     */
    static getUnitName(unit: LengthUnit): string {
        const names: Record<LengthUnit, string> = {
            'm': '米',
            'km': '千米',
            'ft': '英尺',
            'mi': '英里'
        };
        return names[unit];
    }
}

// ========== 面积单位转换 ==========

/**
 * 面积单位转换工具类
 */
export class AreaConverter {
    private static readonly CONVERSIONS: Record<AreaUnit, number> = {
        'm2': 1,              // 平方米
        'km2': 0.000001,      // 平方千米
        'ha': 0.0001,         // 公顷
        'ac': 0.000247105     // 英亩
    };

    /**
     * 转换面积单位
     * @param value 数值
     * @param from 源单位
     * @param to 目标单位
     */
    static convert(value: number, from: AreaUnit, to: AreaUnit): number {
        // 先转换为平方米
        const inSquareMeters = value / this.CONVERSIONS[from];
        // 再转换为目标单位
        return inSquareMeters * this.CONVERSIONS[to];
    }

    /**
     * 格式化面积值
     * @param value 数值
     * @param unit 单位
     * @param decimals 小数位数
     */
    static format(value: number, unit: AreaUnit, decimals: number = 2): string {
        const units: Record<AreaUnit, string> = {
            'm2': 'm²',
            'km2': 'km²',
            'ha': 'ha',
            'ac': 'ac'
        };
        return `${value.toFixed(decimals)} ${units[unit]}`;
    }

    /**
     * 获取单位全称
     * @param unit 单位
     */
    static getUnitName(unit: AreaUnit): string {
        const names: Record<AreaUnit, string> = {
            'm2': '平方米',
            'km2': '平方千米',
            'ha': '公顷',
            'ac': '英亩'
        };
        return names[unit];
    }
}

// ========== 单位管理器 ==========

/**
 * 单位管理器
 * 提供统一的单位配置和转换接口
 */
export class UnitManager {
    private static instance: UnitManager;

    private constructor() {
        this.subscribeToUnitConfig();
    }

    public static getInstance(): UnitManager {
        if (!UnitManager.instance) {
            UnitManager.instance = new UnitManager();
        }
        return UnitManager.instance;
    }

    /**
     * 获取当前坐标系统
     */
    getCoordinateSystem(): CoordinateSystem {
        return appStore.get('units.coordinateSystem');
    }

    /**
     * 设置坐标系统
     */
    setCoordinateSystem(system: CoordinateSystem): void {
        appStore.set('units.coordinateSystem', system);
    }

    /**
     * 转换坐标
     * @param lng 经度
     * @param lat 纬度
     * @param from 源坐标系统
     * @param to 目标坐标系统
     */
    convertCoordinate(lng: number, lat: number, from: CoordinateSystem, to: CoordinateSystem): [number, number] {
        // 先转换为 WGS84
        let [wgsLng, wgsLat] = this.toWgs84(lng, lat, from);
        // 再转换为目标系统
        return this.fromWgs84(wgsLng, wgsLat, to);
    }

    /**
     * 转换为 WGS84
     */
    private toWgs84(lng: number, lat: number, from: CoordinateSystem): [number, number] {
        switch (from) {
            case 'wgs84':
                return [lng, lat];
            case 'gcj02':
                return CoordinateConverter.gcj02ToWgs84(lng, lat);
            case 'bd09':
                return CoordinateConverter.bd09ToWgs84(lng, lat);
        }
    }

    /**
     * 从 WGS84 转换
     */
    private fromWgs84(lng: number, lat: number, to: CoordinateSystem): [number, number] {
        switch (to) {
            case 'wgs84':
                return [lng, lat];
            case 'gcj02':
                return CoordinateConverter.wgs84ToGcj02(lng, lat);
            case 'bd09':
                return CoordinateConverter.wgs84ToBd09(lng, lat);
        }
    }

    /**
     * 获取当前长度单位
     */
    getLengthUnit(): LengthUnit {
        return appStore.get('units.lengthUnit');
    }

    /**
     * 设置长度单位
     */
    setLengthUnit(unit: LengthUnit): void {
        appStore.set('units.lengthUnit', unit);
    }

    /**
     * 转换长度值
     */
    convertLength(value: number, from?: LengthUnit, to?: LengthUnit): number {
        const fromUnit = from || this.getLengthUnit();
        const toUnit = to || this.getLengthUnit();
        return LengthConverter.convert(value, fromUnit, toUnit);
    }

    /**
     * 格式化长度值
     */
    formatLength(value: number, unit?: LengthUnit, decimals: number = 2): string {
        const targetUnit = unit || this.getLengthUnit();
        const convertedValue = this.convertLength(value, 'm', targetUnit);
        return LengthConverter.format(convertedValue, targetUnit, decimals);
    }

    /**
     * 获取当前面积单位
     */
    getAreaUnit(): AreaUnit {
        return appStore.get('units.areaUnit');
    }

    /**
     * 设置面积单位
     */
    setAreaUnit(unit: AreaUnit): void {
        appStore.set('units.areaUnit', unit);
    }

    /**
     * 转换面积值
     */
    convertArea(value: number, from?: AreaUnit, to?: AreaUnit): number {
        const fromUnit = from || this.getAreaUnit();
        const toUnit = to || this.getAreaUnit();
        return AreaConverter.convert(value, fromUnit, toUnit);
    }

    /**
     * 格式化面积值
     */
    formatArea(value: number, unit?: AreaUnit, decimals: number = 2): string {
        const targetUnit = unit || this.getAreaUnit();
        const convertedValue = this.convertArea(value, 'm2', targetUnit);
        return AreaConverter.format(convertedValue, targetUnit, decimals);
    }

    /**
     * 订阅单位配置变化
     */
    private subscribeToUnitConfig(): void {
        appStore.subscribe('units', (units) => {
            console.log('单位配置已更新:', units);
        });
    }

    /**
     * 重置为默认单位配置
     */
    resetToDefaults(): void {
        appStore.set('units', {
            coordinateSystem: 'wgs84',
            lengthUnit: 'm',
            areaUnit: 'm2'
        });
    }

    /**
     * 导出单位配置
     */
    exportConfig(): string {
        const config = appStore.get('units');
        return JSON.stringify(config, null, 2);
    }

    /**
     * 导入单位配置
     */
    importConfig(configJson: string): boolean {
        try {
            const config = JSON.parse(configJson);
            if (config.coordinateSystem && config.lengthUnit && config.areaUnit) {
                appStore.set('units', config);
                return true;
            }
            return false;
        } catch (e) {
            console.error('导入单位配置失败:', e);
            return false;
        }
    }
}

// 导出单例实例
export const unitManager = UnitManager.getInstance();