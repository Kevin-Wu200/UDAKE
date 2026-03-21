/**
 * 宽松类型声明
 * 用于处理遗留代码和第三方库的类型问题
 */

// 完全禁用所有类型检查
declare module '*';

// 扩展所有模块以支持任意属性
declare module './js/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有类型以支持任意属性
declare module './types/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有组件以支持任意属性
declare module './js/components/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有工具以支持任意属性
declare module './js/utils/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有服务以支持任意属性
declare module './js/services/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有适配器以支持任意属性
declare module './js/adapters/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有管理器以支持任意属性
declare module './js/managers/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有采样组件以支持任意属性
declare module './js/sampling/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有配置以支持任意属性
declare module './js/config/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有模型以支持任意属性
declare module './js/models/*' {
    const content: any;
    export default content;
    export * from './';
}

// 扩展所有地图相关模块以支持任意属性
declare module './js/map/*' {
    const content: any;
    export default content;
    export * from './';
}

export {};