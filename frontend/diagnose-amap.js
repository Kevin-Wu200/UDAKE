/**
 * 高德地图加载诊断工具
 * 用于诊断高德地图加载问题
 */

console.log('=== 高德地图加载诊断工具 ===');
console.log('');

// 1. 检查环境
console.log('1. 环境检查');
console.log('- User Agent:', navigator.userAgent);
console.log('- 在线状态:', navigator.onLine);
console.log('- 语言:', navigator.language);
console.log('');

// 2. 检查网络
console.log('2. 网络测试');
async function testNetwork() {
    try {
        const start = Date.now();
        const response = await fetch('https://webapi.amap.com/maps', {
            method: 'HEAD',
            mode: 'no-cors',
            cache: 'no-cache'
        });
        const time = Date.now() - start;
        console.log('- 网络连接: ✅ 正常');
        console.log('- 响应时间:', time, 'ms');
    } catch (error) {
        console.log('- 网络连接: ❌ 失败');
        console.log('- 错误:', error.message);
    }
}
testNetwork().then(() => {
    console.log('');
});

// 3. 检查脚本标签
console.log('3. 检查已加载的脚本');
const scripts = document.querySelectorAll('script[src*="amap.com"]');
console.log('- 已加载的高德地图脚本数量:', scripts.length);
scripts.forEach((script, index) => {
    console.log(`  脚本 ${index + 1}:`, script.src);
});
console.log('');

// 4. 检查 AMap 对象
console.log('4. AMap 对象状态');
console.log('- window.AMap 存在:', !!window.AMap);
if (window.AMap) {
    console.log('- AMap.Map 存在:', !!window.AMap.Map);
    console.log('- AMap 主要属性:', Object.keys(window.AMap).slice(0, 20));
    console.log('- AMap.Plugins:', window.AMap.Plugins ? '存在' : '不存在');
} else {
    console.log('- AMap 对象未加载');
}
console.log('');

// 5. 检查回调函数
console.log('5. 回调函数检查');
console.log('- window.amapLoadCallback 存在:', !!window.amapLoadCallback);
console.log('- window.testAMapCallback 存在:', !!window.testAMapCallback);
console.log('');

// 6. 测试加载
console.log('6. 测试加载高德地图');
async function testLoadAMap() {
    console.log('- 设置安全密钥...');
    window._AMapSecurityConfig = {
        securityJsCode: "10b5ef21f6b36d09e24d7b076d35dccc"
    };
    console.log('✅ 安全密钥已设置');

    console.log('- 开始加载脚本...');
    const script = document.createElement('script');
    script.src = 'https://webapi.amap.com/maps?v=2.0&key=2f3f114aa5671425aa3c52f707d741c5';
    script.async = true;

    script.onload = () => {
        console.log('✅ 脚本 onload 事件触发');
        console.log('- 开始轮询检查 AMap 对象...');

        let checkCount = 0;
        const checkInterval = setInterval(() => {
            checkCount++;
            const hasAMap = !!window.AMap;
            const hasMap = hasAMap ? !!window.AMap.Map : false;

            if (checkCount % 20 === 0) {
                console.log(`  检查 ${checkCount}: AMap=${hasAMap}, Map=${hasMap}`);
            }

            if (hasMap) {
                clearInterval(checkInterval);
                console.log('✅ AMap 对象加载成功！');
                console.log('- AMap 主要属性:', Object.keys(window.AMap).slice(0, 15));
                console.log('- 可以使用 new AMap.Map() 创建地图');
            } else if (checkCount >= 300) {
                clearInterval(checkInterval);
                console.log('❌ AMap 对象加载超时（15秒）');
                console.log('- 最终状态:');
                console.log('  window.AMap 存在:', !!window.AMap);
                if (window.AMap) {
                    console.log('  AMap 属性:', Object.keys(window.AMap));
                }
            }
        }, 50);
    };

    script.onerror = (error) => {
        console.log('❌ 脚本 onerror 事件触发');
        console.log('- 错误:', error);
    };

    document.head.appendChild(script);
}

// 等待网络测试完成后执行加载测试
setTimeout(() => {
    testLoadAMap();
}, 1000);

console.log('=== 诊断完成，请等待 16 秒后查看结果 ===');