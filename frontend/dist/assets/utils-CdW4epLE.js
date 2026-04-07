import{n as y}from"./rolldown-runtime-DQCMaF4_.js";var p,b,E=y((()=>{b=class{static init(){const c=localStorage.getItem(this.STORAGE_KEY)||"auto";this._apply(c),this._mediaQuery.addEventListener("change",()=>{this._current==="auto"&&this._updateIcon()})}static toggle(){const c=["light","dark","auto"],e=c[(c.indexOf(this._current)+1)%c.length];this._apply(e),localStorage.setItem(this.STORAGE_KEY,e)}static set(c){this._apply(c),localStorage.setItem(this.STORAGE_KEY,c)}static get current(){return this._current}static get effectiveTheme(){return this._current==="auto"?this._mediaQuery.matches?"dark":"light":this._current}static _apply(c){this._current=c;const e=document.documentElement;e.classList.add("theme-transition"),c==="auto"?e.removeAttribute("data-theme"):e.setAttribute("data-theme",c),this._updateIcon(),setTimeout(()=>e.classList.remove("theme-transition"),350)}static _updateIcon(){const c=document.getElementById("theme-toggle-btn");if(!c)return;const e=c.querySelector(".theme-icon");if(!e)return;const t={light:"☀️",dark:"🌙",auto:"💻"},r={light:"当前：浅色模式（点击切换为深色）",dark:"当前：深色模式（点击切换为跟随系统）",auto:"当前：跟随系统（点击切换为浅色）"};e.textContent=t[this._current]||t.auto,c.title=r[this._current]||r.auto}},p=b,p.STORAGE_KEY="udake-theme-preference",p.THEMES={LIGHT:"light",DARK:"dark",AUTO:"auto"},p._current=null,p._mediaQuery=typeof window<"u"&&window.matchMedia?window.matchMedia("(prefers-color-scheme: dark)"):{matches:!1,addEventListener:()=>{}}})),v,w=y((()=>{v=class u{constructor(e){this.apiBaseURL=e}static exportAsCSV(e,t){if(!e.length)return;const r=Object.keys(e[0]),s="\uFEFF"+[r.join(","),...e.map(i=>r.map(o=>{const l=i[o];return typeof l=="string"&&(l.includes(",")||l.includes('"'))?`"${l.replace(/"/g,'""')}"`:l??""}).join(","))].join(`
`),n=new Blob([s],{type:"text/csv;charset=utf-8"});u._download(n,t)}static exportPointsCSV(e,t="sampling_points.csv"){this.exportAsCSV(e.map(r=>({longitude:r.x,latitude:r.y,value:r.value,...r.timestamp?{timestamp:r.timestamp}:{}})),t)}static generateHTMLReport(e){const{taskId:t,method:r,pointCount:s,gridResolution:n,stats:i,crossValidation:o}=e,l=`<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>插值分析报告 - ${t}</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
        h1 { border-bottom: 2px solid #007aff; padding-bottom: 10px; }
        h2 { color: #007aff; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #e5e5e5; }
        th { background: #f5f5f7; font-weight: 600; }
        .meta { color: #666; font-size: 14px; }
        .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 16px 0; }
        .stat-card { background: #f5f5f7; border-radius: 12px; padding: 16px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: 700; color: #007aff; }
        .stat-label { font-size: 12px; color: #666; margin-top: 4px; }
        @media print { body { margin: 0; } }
    </style>
</head>
<body>
    <h1>插值分析报告</h1>
    <p class="meta">任务ID: ${t} | 生成时间: ${new Date().toLocaleString("zh-CN")}</p>

    <h2>参数配置</h2>
    <table>
        <tr><th>参数</th><th>值</th></tr>
        <tr><td>克里金方法</td><td>${{ordinary:"普通克里金",universal:"泛克里金",block:"分块克里金"}[r]||r}</td></tr>
        <tr><td>采样点数量</td><td>${s}</td></tr>
        <tr><td>网格分辨率</td><td>${n}</td></tr>
    </table>

    ${i?`
    <h2>统计摘要</h2>
    <div class="stat-grid">
        ${Object.entries(i).map(([h,d])=>`
            <div class="stat-card">
                <div class="stat-value">${typeof d=="number"?d.toFixed(4):d}</div>
                <div class="stat-label">${h}</div>
            </div>
        `).join("")}
    </div>`:""}

    ${o?`
    <h2>交叉验证</h2>
    <table>
        <tr><th>指标</th><th>值</th></tr>
        ${Object.entries(o).map(([h,d])=>`
            <tr><td>${h}</td><td>${typeof d=="number"?d.toFixed(6):d}</td></tr>
        `).join("")}
    </table>`:""}

    <p class="meta" style="margin-top:40px;text-align:center;">
        UDAKE - 智能不确定性驱动空间决策平台
    </p>
</body>
</html>`,m=new Blob([l],{type:"text/html;charset=utf-8"});u._download(m,`report_${t}.html`)}async batchExport(e,t){for(const r of e)try{const s=`${r}_prediction.${t}`,n=`${this.apiBaseURL}/result/download/${r}/${s}`,i=await fetch(n,{mode:"cors",credentials:"omit"});if(!i.ok)continue;const o=await i.blob();u._download(o,s),await new Promise(l=>setTimeout(l,500))}catch(s){console.warn(`[Export] 批量导出失败: ${r}`,s)}}static async captureMap(e){try{const t=e.querySelector("canvas");return t?new Promise(r=>t.toBlob(r,"image/png")):null}catch{return null}}static _download(e,t){const r=URL.createObjectURL(e),s=document.createElement("a");s.href=r,s.download=t,document.body.appendChild(s),s.click(),document.body.removeChild(s),URL.revokeObjectURL(r)}}})),f,g,x,$=y((()=>{g=class a{constructor(){this.metrics=new Map,this.observers=[],this.maxMetricsPerName=1e3,this.initialized=!1,this.initialize()}initialize(){if(!this.initialized){if(typeof window>"u"||typeof performance>"u"){console.warn("[PerformanceMonitor] Performance API not available");return}try{this.initializeObservers(),this.initialized=!0,console.log("[PerformanceMonitor] Initialized successfully")}catch(e){console.error("[PerformanceMonitor] Initialization failed:",e)}}}initializeObservers(){try{const e=new PerformanceObserver(t=>{for(const r of t.getEntries())if(r.entryType==="resource"){const s=r;this.recordMetric("resource-load",s.duration,{name:s.name,type:s.initiatorType,size:s.transferSize,cached:s.transferSize===0})}});e.observe({entryTypes:["resource"]}),this.observers.push(e)}catch{console.warn("[PerformanceMonitor] Resource observer not supported")}try{const e=new PerformanceObserver(t=>{for(const r of t.getEntries())r.entryType==="longtask"&&this.recordMetric("long-task",r.duration,{name:r.name,startTime:r.startTime})});e.observe({entryTypes:["longtask"]}),this.observers.push(e)}catch{console.warn("[PerformanceMonitor] Long task observer not supported")}try{const e=new PerformanceObserver(t=>{for(const r of t.getEntries())r.entryType==="measure"&&this.recordMetric(r.name,r.duration)});e.observe({entryTypes:["measure"]}),this.observers.push(e)}catch{console.warn("[PerformanceMonitor] Measure observer not supported")}try{const e=new PerformanceObserver(t=>{for(const r of t.getEntries())if(r.entryType==="navigation"){const s=r;this.recordMetric("navigation",s.duration,{domContentLoaded:s.domContentLoadedEventEnd-s.domContentLoadedEventStart,loadComplete:s.loadEventEnd-s.loadEventStart,domInteractive:s.domInteractive-s.fetchStart,firstPaint:s.responseEnd-s.fetchStart})}});e.observe({entryTypes:["navigation"]}),this.observers.push(e)}catch{console.warn("[PerformanceMonitor] Navigation observer not supported")}}recordMetric(e,t,r){const s={name:e,duration:t,timestamp:Date.now(),metadata:r};this.metrics.has(e)||this.metrics.set(e,[]);const n=this.metrics.get(e);n.push(s),n.length>this.maxMetricsPerName&&n.splice(0,n.length-this.maxMetricsPerName)}startMeasure(e){const t=performance.now(),r=`${e}-start-${Date.now()}`;try{performance.mark(r)}catch{}return()=>{const s=performance.now(),n=`${e}-end-${Date.now()}`;try{performance.mark(n),performance.measure(e,r,n),performance.clearMarks(r),performance.clearMarks(n),performance.clearMeasures(e)}catch{}this.recordMetric(e,s-t)}}async measureAsync(e,t){const r=this.startMeasure(e);try{return await t()}finally{r()}}getStats(e){const t=this.metrics.get(e);if(!t||t.length===0)return null;const r=t.map(i=>i.duration).sort((i,o)=>i-o),s=r.reduce((i,o)=>i+o,0),n=i=>r[Math.floor((r.length-1)*i)];return{count:r.length,total:s,average:s/r.length,min:r[0],max:r[r.length-1],p50:n(.5),p95:n(.95),p99:n(.99)}}getAllStats(){const e=new Map;for(const t of this.metrics.keys()){const r=this.getStats(t);r&&e.set(t,r)}return e}getWebVitals(){const e={},t=performance.getEntriesByType("largest-contentful-paint");t.length>0&&(e.lcp=t[t.length-1].startTime);const r=performance.getEntriesByType("first-input");r.length>0&&(e.fid=r[0].processingStart-r[0].startTime);let s=0;const n=performance.getEntriesByType("layout-shift"),i=n.length>0?n:performance.getEntries();for(const m of i)m.entryType==="layout-shift"&&!m.hadRecentInput&&(s+=m.value);e.cls=s;const o=performance.getEntriesByType("paint").find(m=>m.name==="first-contentful-paint")||performance.getEntriesByName("first-contentful-paint","paint")[0];o&&(e.fcp=o.startTime);const l=performance.getEntriesByType("navigation")[0];return l&&(e.ttfb=l.responseStart-l.requestStart),e}getMemoryUsage(){if("memory"in performance){const e=performance.memory;return{usedJSHeapSize:e.usedJSHeapSize,totalJSHeapSize:e.totalJSHeapSize,jsHeapSizeLimit:e.jsHeapSizeLimit,usagePercent:e.usedJSHeapSize/e.jsHeapSizeLimit*100}}return null}getResourceStats(){const e=performance.getEntriesByType("resource"),t=new Map;let r=0,s=0;for(const n of e){const i=n.initiatorType||"other",o=Number(n.transferSize)||0;t.has(i)||t.set(i,{count:0,size:0});const l=t.get(i);l.count++,l.size+=o,r+=o,o===0&&s++}return{totalResources:e.length,totalSize:r,cachedResources:s,resourcesByType:t}}clear(){this.metrics.clear()}clearMetric(e){this.metrics.delete(e)}destroy(){this.observers.forEach(e=>e.disconnect()),this.observers=[],this.clear(),this.initialized=!1}generateReport(){const e=this.getAllStats(),t=this.getWebVitals(),r=this.getMemoryUsage(),s=this.getResourceStats();let n=`=== 性能监控报告 ===
`;n+=`生成时间: ${new Date().toLocaleString("zh-CN")}

`,n+=`## Core Web Vitals
`,n+=`- LCP (Largest Contentful Paint): ${t.lcp?t.lcp.toFixed(2)+"ms":"N/A"} (建议 < 2.5s)
`,n+=`- FID (First Input Delay): ${t.fid?t.fid.toFixed(2)+"ms":"N/A"} (建议 < 100ms)
`,n+=`- CLS (Cumulative Layout Shift): ${t.cls?t.cls.toFixed(4):"N/A"} (建议 < 0.1)
`,n+=`- FCP (First Contentful Paint): ${t.fcp?t.fcp.toFixed(2)+"ms":"N/A"} (建议 < 1.8s)
`,n+=`- TTFB (Time to First Byte): ${t.ttfb?t.ttfb.toFixed(2)+"ms":"N/A"} (建议 < 600ms)

`,r&&(n+=`## 内存使用
`,n+=`- 已使用: ${(r.usedJSHeapSize/1024/1024).toFixed(2)} MB
`,n+=`- 总计: ${(r.totalJSHeapSize/1024/1024).toFixed(2)} MB
`,n+=`- 限制: ${(r.jsHeapSizeLimit/1024/1024).toFixed(2)} MB
`,n+=`- 使用率: ${r.usagePercent.toFixed(2)}%

`),n+=`## 资源加载
`,n+=`- 总资源数: ${s.totalResources}
`,n+=`- 总大小: ${(s.totalSize/1024).toFixed(2)} KB
`,n+=`- 缓存资源: ${s.cachedResources} (${(s.cachedResources/s.totalResources*100).toFixed(1)}%)
`,n+=`
### 按类型统计
`;for(const[i,o]of s.resourcesByType.entries())n+=`- ${i}: ${o.count} 个, ${(o.size/1024).toFixed(2)} KB
`;n+=`
`,n+=`## 性能指标统计
`;for(const[i,o]of e.entries())n+=`
### ${i}
`,n+=`- 计数: ${o.count}
`,n+=`- 总时长: ${o.total.toFixed(2)}ms
`,n+=`- 平均: ${o.average.toFixed(2)}ms
`,n+=`- 最小: ${o.min.toFixed(2)}ms
`,n+=`- 最大: ${o.max.toFixed(2)}ms
`,n+=`- P50: ${o.p50.toFixed(2)}ms
`,n+=`- P95: ${o.p95.toFixed(2)}ms
`,n+=`- P99: ${o.p99.toFixed(2)}ms
`;return n}generateJSONReport(){return{timestamp:new Date().toISOString(),webVitals:this.getWebVitals(),memory:this.getMemoryUsage(),resources:this.getResourceStats(),metrics:Object.fromEntries(this.getAllStats())}}exportMetrics(){const e=[];for(const t of this.metrics.values())e.push(...t);return e.sort((t,r)=>t.timestamp-r.timestamp)}checkPerformanceThresholds(){const e=[],t=this.getWebVitals();t.lcp&&t.lcp>2500&&e.push(`LCP 过高: ${t.lcp.toFixed(2)}ms (建议 < 2.5s)`),t.fid&&t.fid>100&&e.push(`FID 过高: ${t.fid.toFixed(2)}ms (建议 < 100ms)`),t.cls&&t.cls>.1&&e.push(`CLS 过高: ${t.cls.toFixed(4)} (建议 < 0.1)`),t.fcp&&t.fcp>1800&&e.push(`FCP 过高: ${t.fcp.toFixed(2)}ms (建议 < 1.8s)`),t.ttfb&&t.ttfb>600&&e.push(`TTFB 过高: ${t.ttfb.toFixed(2)}ms (建议 < 600ms)`);const r=this.getMemoryUsage();return r&&r.usagePercent>80&&e.push(`内存使用率过高: ${r.usagePercent.toFixed(2)}% (建议 < 80%)`),{passed:e.length===0,issues:e}}static init(){a.instance||(a.instance=new a);const e=()=>{try{a._collectNavigationMetrics()}catch{}};typeof document<"u"&&document.readyState==="loading"&&typeof window<"u"&&typeof window.addEventListener=="function"?window.addEventListener("load",e):e()}static mark(e){const t=typeof performance<"u"&&typeof performance.now=="function"?performance.now():Date.now();a._marks[e]=t,typeof performance<"u"&&typeof performance.mark=="function"&&performance.mark(e)}static measure(e,t,r){const s=a._marks[t];if(typeof s!="number")return null;const n=(typeof r=="string"&&typeof a._marks[r]=="number"?a._marks[r]:typeof performance<"u"&&typeof performance.now=="function"?performance.now():Date.now())-s;if(a._metrics[e]=n,typeof performance<"u"&&typeof performance.measure=="function")try{r?performance.measure(e,t,r):performance.measure(e,t)}catch{}return n}static getMetrics(){return{...a._metrics}}static report(){console.group("Performance Report"),Object.entries(a._metrics).forEach(([e,t])=>{typeof t=="number"&&Number.isFinite(t)?console.log(`${e}: ${t.toFixed(2)}ms`):console.log(`${e}:`,t)}),console.groupEnd()}static _collectNavigationMetrics(){if(typeof performance>"u"||typeof performance.getEntriesByType!="function")return;const e=performance.getEntriesByType("navigation")[0];e&&(a._metrics.domContentLoaded=e.domContentLoadedEventEnd-e.startTime,a._metrics.loadComplete=e.loadEventEnd-e.startTime,a._metrics.ttfb=e.responseStart-e.requestStart,a._metrics.domInteractive=e.domInteractive-e.startTime);const t=performance.getEntriesByType("resource");a._metrics.resourceCount=t.length,a._metrics.totalTransferSize=t.reduce((r,s)=>{const n=Number(s.transferSize);return r+(Number.isFinite(n)?n:0)},0)}},f=g,f.instance=null,f._metrics={},f._marks={},x=new g}));export{b as a,w as i,$ as n,E as o,v as r,g as t};
