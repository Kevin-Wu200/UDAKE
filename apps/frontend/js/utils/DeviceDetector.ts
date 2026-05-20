/**
 * 设备类型检测模块
 * 基于 UserAgent 与 TouchEvent 自动识别桌面端 / 移动端
 * 用于无人机视角操控方案的自动适配
 */
export type DeviceType = 'desktop' | 'mobile';

export interface DeviceInfo {
    /** 设备类型 */
    type: DeviceType;
    /** 是否支持触屏 */
    hasTouch: boolean;
    /** 是否支持多点触控 */
    hasMultiTouch: boolean;
    /** 操作系统 */
    os: 'windows' | 'macos' | 'linux' | 'ios' | 'android' | 'unknown';
    /** 是否为平板设备 */
    isTablet: boolean;
    /** 屏幕宽度 (px) */
    screenWidth: number;
    /** 屏幕高度 (px) */
    screenHeight: number;
}

let cachedDeviceInfo: DeviceInfo | null = null;

/**
 * 检测设备类型及能力
 * 结果会被缓存，后续调用直接返回缓存结果
 */
export function detectDevice(): DeviceInfo {
    if (cachedDeviceInfo) {
        return cachedDeviceInfo;
    }

    const ua = navigator.userAgent.toLowerCase();
    const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const hasMultiTouch = navigator.maxTouchPoints > 1;

    // 操作系统检测
    let os: DeviceInfo['os'] = 'unknown';
    if (/windows/.test(ua)) os = 'windows';
    else if (/macintosh|mac os x/.test(ua)) os = 'macos';
    else if (/linux/.test(ua) && !/android/.test(ua)) os = 'linux';
    else if (/iphone|ipod/.test(ua)) os = 'ios';
    else if (/ipad/.test(ua) || (hasTouch && /macintosh/.test(ua) && navigator.maxTouchPoints > 1)) os = 'ios';
    else if (/android/.test(ua)) os = 'android';

    // 平板检测
    const isTablet = /ipad/.test(ua) ||
        (os === 'ios' && hasTouch && !/iphone|ipod/.test(ua)) ||
        (os === 'android' && !/mobile/.test(ua)) ||
        (hasMultiTouch && window.screen.width >= 768);

    // 设备类型判定
    const type: DeviceType = (hasMultiTouch && (os === 'ios' || os === 'android')) || isTablet
        ? 'mobile'
        : 'desktop';

    cachedDeviceInfo = {
        type,
        hasTouch,
        hasMultiTouch,
        os,
        isTablet,
        screenWidth: window.screen.width,
        screenHeight: window.screen.height,
    };

    console.log(
        `📱 设备检测: ${type} | OS: ${os} | ` +
        `触屏: ${hasTouch} | 多点触控: ${hasMultiTouch} | ` +
        `平板: ${isTablet} | 分辨率: ${window.screen.width}x${window.screen.height}`
    );

    return cachedDeviceInfo;
}

/**
 * 重置设备检测缓存（用于设备方向变化等场景）
 */
export function resetDeviceDetection(): void {
    cachedDeviceInfo = null;
}

/**
 * 监听设备类型变化（如平板旋转、外接键盘等）
 */
export function onDeviceChange(callback: (info: DeviceInfo) => void): () => void {
    const handler = () => {
        resetDeviceDetection();
        callback(detectDevice());
    };

    window.addEventListener('resize', handler);
    window.addEventListener('orientationchange', handler);

    return () => {
        window.removeEventListener('resize', handler);
        window.removeEventListener('orientationchange', handler);
    };
}
