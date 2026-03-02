#!/usr/bin/env node

/**
 * 地图引擎功能验证脚本
 * 验证新引擎架构的代码完整性和正确性
 */

const fs = require('fs');
const path = require('path');

const results = {
    timestamp: new Date().toISOString(),
    passed: [],
    failed: [],
    warnings: []
};

function log(message, type = 'info') {
    const prefix = {
        info: '✓',
        error: '✗',
        warning: '⚠'
    }[type];
    console.log(`${prefix} ${message}`);
}

function checkFileExists(filePath, description) {
    const fullPath = path.join(__dirname, '..', filePath);
    if (fs.existsSync(fullPath)) {
        log(`${description} 存在`, 'info');
        results.passed.push(`${description} 文件存在`);
        return true;
    } else {
        log(`${description} 不存在: ${filePath}`, 'error');
        results.failed.push(`${description} 文件不存在: ${filePath}`);
        return false;
    }
}

function checkFileContent(filePath, patterns, description) {
    const fullPath = path.join(__dirname, '..', filePath);
    if (!fs.existsSync(fullPath)) {
        log(`无法检查 ${description}: 文件不存在`, 'error');
        results.failed.push(`${description}: 文件不存在`);
        return false;
    }

    const content = fs.readFileSync(fullPath, 'utf-8');
    let allPassed = true;

    patterns.forEach(({ pattern, name }) => {
        if (content.includes(pattern)) {
            log(`${description} - ${name} ✓`, 'info');
            results.passed.push(`${description} - ${name}`);
        } else {
            log(`${description} - ${name} ✗`, 'error');
            results.failed.push(`${description} - ${name}`);
            allPassed = false;
        }
    });

    return allPassed;
}

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('  地图引擎功能验证');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

// 第一阶段：检查核心引擎文件
console.log('【第一阶段】检查核心引擎文件\n');

checkFileExists('build/frontend/js/map/core/BaseMapEngine.js', 'BaseMapEngine');
checkFileExists('build/frontend/js/map/core/TiandituEngine.js', 'TiandituEngine');
checkFileExists('build/frontend/js/map/core/ArcGISEngine.js', 'ArcGISEngine');

// 第二阶段：检查管理器和组件
console.log('\n【第二阶段】检查管理器和组件\n');

checkFileExists('build/frontend/js/managers/MapManager.js', 'MapManager');
checkFileExists('build/frontend/js/components/ZoomControl.js', 'ZoomControl');
checkFileExists('build/frontend/js/utils/GeoUtils.js', 'GeoUtils');

// 第三阶段：检查适配器更新
console.log('\n【第三阶段】检查适配器更新\n');

checkFileContent('build/frontend/js/adapters/TiandituAdapter.js', [
    { pattern: 'TiandituEngine', name: '引用 TiandituEngine' },
    { pattern: 'this.engine', name: '使用 engine 实例' },
    { pattern: 'getEngine()', name: '提供 getEngine 方法' }
], 'TiandituAdapter');

checkFileContent('build/frontend/js/adapters/ArcGISAdapter.js', [
    { pattern: 'ArcGISEngine', name: '引用 ArcGISEngine' },
    { pattern: 'this.engine', name: '使用 engine 实例' },
    { pattern: 'getEngine()', name: '提供 getEngine 方法' }
], 'ArcGISAdapter');

// 第四阶段：检查引擎实现
console.log('\n【第四阶段】检查引擎实现\n');

checkFileContent('build/frontend/js/map/core/TiandituEngine.js', [
    { pattern: 'supportsCustomReset = true', name: '支持自定义 reset' },
    { pattern: 'bindEvents()', name: '绑定事件' },
    { pattern: 'fitToBounds', name: '实现 fitToBounds' },
    { pattern: 'triggerZoomCallbacks', name: '触发缩放回调' },
    { pattern: 'e.button === 0', name: '左键拖动检测' }
], 'TiandituEngine');

checkFileContent('build/frontend/js/map/core/ArcGISEngine.js', [
    { pattern: 'supportsCustomReset = false', name: '不支持自定义 reset' },
    { pattern: 'Home', name: '使用 Home 控件' },
    { pattern: 'view.ui.add(homeWidget', name: '添加 Home 控件' },
    { pattern: 'fitToBounds', name: '实现 fitToBounds' },
    { pattern: 'view.goTo', name: '使用 view.goTo' }
], 'ArcGISEngine');

// 第五阶段：检查 MapManager 功能
console.log('\n【第五阶段】检查 MapManager 功能\n');

checkFileContent('build/frontend/js/managers/MapManager.js', [
    { pattern: 'createResetButton', name: '创建 reset 按钮' },
    { pattern: 'handleReset', name: '处理 reset 逻辑' },
    { pattern: 'enterAreaSamplingMode', name: '进入区域采样模式' },
    { pattern: 'enterNormalMode', name: '进入普通模式' },
    { pattern: 'supportsCustomReset', name: '检查 reset 支持' },
    { pattern: 'GeoUtils', name: '使用 GeoUtils' }
], 'MapManager');

// 第六阶段：检查 ZoomControl
console.log('\n【第六阶段】检查 ZoomControl\n');

checkFileContent('build/frontend/js/components/ZoomControl.js', [
    { pattern: 'updateThumbPosition', name: '更新滑块位置' },
    { pattern: 'showZoomBar', name: '显示缩放条' },
    { pattern: 'fadeOut', name: '淡出动画' },
    { pattern: 'setTimeout', name: '延时淡出' },
    { pattern: 'onZoom', name: '监听缩放' }
], 'ZoomControl');

// 第七阶段：检查 GeoUtils
console.log('\n【第七阶段】检查 GeoUtils\n');

checkFileContent('build/frontend/js/utils/GeoUtils.js', [
    { pattern: 'calculateBoundsFromGeoJSON', name: '计算 GeoJSON 边界' },
    { pattern: 'extractCoordinates', name: '提取坐标' },
    { pattern: 'expandBounds', name: '扩展边界' },
    { pattern: 'minLng', name: '返回边界对象' }
], 'GeoUtils');

// 第八阶段：检查向后兼容性
console.log('\n【第八阶段】检查向后兼容性\n');

checkFileContent('build/frontend/js/地图初始化.js', [
    { pattern: 'ArcGISAdapter', name: '保留 ArcGISAdapter' },
    { pattern: 'TiandituAdapter', name: '保留 TiandituAdapter' },
    { pattern: 'initializeMap', name: '保留 initializeMap 函数' }
], '地图初始化');

// 生成报告
console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('  验证结果统计');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log(`✓ 通过: ${results.passed.length}`);
console.log(`✗ 失败: ${results.failed.length}`);
console.log(`⚠ 警告: ${results.warnings.length}\n`);

const passed = results.failed.length === 0;

if (passed) {
    console.log('✅ 所有检查通过！代码结构完整。\n');
} else {
    console.log('❌ 存在问题，请检查失败项：\n');
    results.failed.forEach(item => console.log(`  - ${item}`));
    console.log('');
}

// 保存结果
const reportPath = path.join(__dirname, '..', '..', '.claude', '代码验证结果.json');
fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
console.log(`详细结果已保存至: ${reportPath}\n`);

process.exit(passed ? 0 : 1);
