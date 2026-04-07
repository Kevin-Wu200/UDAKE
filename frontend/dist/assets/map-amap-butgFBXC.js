import{n as A}from"./rolldown-runtime-DQCMaF4_.js";import{d as R,f as L}from"./core-components-BzHiWJh9.js";async function k(){if(!navigator.geolocation)return c=i.DENIED,i.DENIED;if(navigator.permissions&&navigator.permissions.query)try{const e=await navigator.permissions.query({name:"geolocation"});return e.state==="granted"?c=i.GRANTED:e.state==="denied"?c=i.DENIED:c=i.UNKNOWN,e.addEventListener("change",()=>{e.state==="granted"?c=i.GRANTED:e.state==="denied"?c=i.DENIED:c=i.UNKNOWN}),c}catch{return i.UNKNOWN}return i.UNKNOWN}async function x(){const e=await k();return e===i.GRANTED?i.GRANTED:e===i.DENIED?i.DENIED:(R.showWarning("UDAKE 需要使用设备定位以支持当前位置采样功能。"),new Promise(t=>{navigator.geolocation.getCurrentPosition(()=>{c=i.GRANTED,t(i.GRANTED)},o=>{o.code===o.PERMISSION_DENIED?(c=i.DENIED,t(i.DENIED)):(c=i.UNKNOWN,t(i.UNKNOWN))},{enableHighAccuracy:!1,timeout:1e4,maximumAge:0})}))}function W(){return new Promise((e,t)=>{if(!navigator.geolocation){t({type:"unsupported",message:"当前设备不支持定位功能"});return}if(c===i.DENIED){t({type:"denied",message:"定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。"});return}navigator.geolocation.getCurrentPosition(o=>{c=i.GRANTED,e({longitude:o.coords.longitude,latitude:o.coords.latitude,accuracy:o.coords.accuracy,timestamp:new Date(o.timestamp).toISOString()})},o=>{o.code===o.PERMISSION_DENIED?(c=i.DENIED,t({type:"denied",message:"定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。"})):o.code===o.TIMEOUT?t({type:"timeout",message:"定位获取超时"}):o.code===o.POSITION_UNAVAILABLE?t({type:"unavailable",message:"设备定位不可用"}):t({type:"unknown",message:"未知的定位错误"})},{enableHighAccuracy:!1,timeout:1e4,maximumAge:0})})}function Z(){return c}var i,c,M,N=A((()=>{L(),i={GRANTED:"granted",DENIED:"denied",UNKNOWN:"unknown"},c=i.UNKNOWN,M={PermissionStatus:i,checkPermission:k,requestPermission:x,getCurrentPosition:W,getPermissionStatus:Z}})),D,U=A((()=>{D=class{constructor(){this.supportsCustomReset=!1,this.zoomCallbacks=[],this.moveCallbacks=[]}onZoom(e){this.zoomCallbacks.push(e)}onMove(e){this.moveCallbacks.push(e)}triggerZoomCallbacks(e){this.zoomCallbacks.forEach(t=>t(e))}triggerMoveCallbacks(e){this.moveCallbacks.forEach(t=>t(e))}destroy(){this.zoomCallbacks=[],this.moveCallbacks=[]}}}));async function z(){try{return console.log("🌐 测试网络连接..."),await fetch("https://webapi.amap.com/maps",{method:"HEAD",mode:"no-cors",cache:"no-cache",signal:AbortSignal.timeout(5e3)}),console.log("✅ 网络连接正常"),!0}catch(e){return console.error("❌ 网络连接测试失败:",e),!1}}function G(){window._AMapSecurityConfig={securityJsCode:y.getSecurityCode()}}function F(e){return new Promise((t,o)=>{console.log("🔄 开始加载高德地图 API（iframe 方式）..."),console.log("📦 地图容器 ID:",e);const r=new AbortController;if(window.AMap&&window.AMap.Map){console.log("✅ 高德地图 API 已加载，直接返回"),t(window.AMap);return}if(!navigator.onLine){console.error("❌ 网络连接不可用"),o(new Error("网络连接不可用，无法加载高德地图 API"));return}const a=document.createElement("iframe");a.style.display="none",a.style.width="0",a.style.height="0",a.id="amap-loader-iframe",document.body.appendChild(a),console.log("📤 创建 iframe 用于加载高德地图 API");let s=!1;const T=`
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { margin: 0; overflow: hidden; }
                    #amap-container { width: 100%; height: 100%; }
                </style>
            </head>
            <body>
                <div id="amap-container"></div>
                <script>
                    // 设置安全密钥
                    window._AMapSecurityConfig = {
                        securityJsCode: "${y.getSecurityCode()}"
                    };
                    
                    var mapInstance = null;
                    
                    // 监听主窗口的消息
                    window.addEventListener('message', function(e) {
                        console.log('📨 iframe 收到消息:', e.data.type);
                        
                        if (e.data.type === 'INIT_MAP') {
                            console.log('📦 收到 INIT_MAP 消息');
                            // 创建地图
                            var containerInfo = e.data.containerInfo;
                            var mapOptions = e.data.mapOptions;
                            
                            console.log('   容器尺寸:', containerInfo.width, 'x', containerInfo.height);
                            
                            // 设置容器尺寸
                            var container = document.getElementById('amap-container');
                            container.style.width = containerInfo.width + 'px';
                            container.style.height = containerInfo.height + 'px';
                            
                            console.log('🎨 准备创建地图实例...');
                            // 创建地图实例
                            mapInstance = new AMap.Map('amap-container', {
                                center: mapOptions.center,
                                layers: [new AMap.TileLayer.Satellite()],
                                zoom: mapOptions.zoom
                            });
                            
                            console.log('✅ 地图实例在 iframe 中创建成功');
                            
                            // 通知主窗口地图已准备就绪
                            console.log('📤 发送 MAP_READY 消息到主窗口');
                            window.parent.postMessage({
                                type: 'MAP_READY',
                                success: true
                            }, '*');
                            
                        } else if (e.data.type === 'MAP_SET_CENTER') {
                            if (mapInstance) {
                                mapInstance.setCenter(e.data.center);
                            }
                        } else if (e.data.type === 'MAP_SET_ZOOM') {
                            if (mapInstance) {
                                mapInstance.setZoom(e.data.zoom);
                            }
                        } else if (e.data.type === 'MAP_GET_CENTER') {
                            if (mapInstance) {
                                var center = mapInstance.getCenter();
                                window.parent.postMessage({
                                    type: 'MAP_GET_CENTER_RESPONSE',
                                    center: [center.lng, center.lat]
                                }, '*');
                            }
                        } else if (e.data.type === 'MAP_GET_ZOOM') {
                            if (mapInstance) {
                                var zoom = mapInstance.getZoom();
                                window.parent.postMessage({
                                    type: 'MAP_GET_ZOOM_RESPONSE',
                                    zoom: zoom
                                }, '*');
                            }
                        } else if (e.data.type === 'MAP_SET_STATUS') {
                            if (mapInstance) {
                                mapInstance.setStatus(e.data.status);
                            }
                        } else if (e.data.type === 'MAP_SET_ZOOMS') {
                            if (mapInstance) {
                                mapInstance.setZooms(e.data.zooms);
                            }
                        } else if (e.data.type === 'MAP_ON') {
                            if (mapInstance) {
                                mapInstance.on(e.data.event, function(data) {
                                    var eventData = data;
                                    if (e.data.event === 'moveend') {
                                        var center = mapInstance.getCenter();
                                        eventData = [center.lng, center.lat];
                                    } else if (e.data.event === 'zoomend') {
                                        eventData = mapInstance.getZoom();
                                    }
                                    window.parent.postMessage({
                                        type: 'MAP_EVENT_' + e.data.event.toUpperCase(),
                                        data: eventData
                                    }, '*');
                                });
                            }
                        }
                    });
                    
                    // 加载高德地图 API
                    var script = document.createElement('script');
                    script.src = 'https://webapi.amap.com/maps?v=2.0&key=${y.getApiKey()}';
                    script.onload = function() {
                        console.log('✅ 高德地图 API 在 iframe 中加载完成');
                        
                        // 等待 AMap 对象完全初始化
                        var checkCount = 0;
                        var maxChecks = 200;
                        var checkInterval = setInterval(function() {
                            checkCount++;
                            if (window.AMap && window.AMap.Map) {
                                clearInterval(checkInterval);
                                console.log('✅ AMap 对象在 iframe 中完全初始化');
                                
                                // 通知主窗口 AMap 已加载
                                window.parent.postMessage({
                                    type: 'AMAP_LOADED',
                                    success: true
                                }, '*');
                            } else if (checkCount >= maxChecks) {
                                clearInterval(checkInterval);
                                console.error('❌ iframe 中 AMap 初始化超时');
                                window.parent.postMessage({
                                    type: 'AMAP_ERROR',
                                    error: 'AMap initialization timeout in iframe'
                                }, '*');
                            }
                        }, 50);
                    };
                    script.onerror = function() {
                        console.error('❌ 高德地图脚本加载失败');
                        window.parent.postMessage({
                            type: 'AMAP_ERROR',
                            error: 'Script loading failed'
                        }, '*');
                    };
                    document.head.appendChild(script);
                <\/script>
            </body>
            </html>
        `,_=d=>{if(!(d.origin!==window.location.origin&&d.origin!=="null"))if(d.data&&d.data.type==="AMAP_LOADED"){console.log("✅ 收到 iframe 消息：高德地图已加载");const g=document.getElementById(e);if(!g){console.error("❌ 找不到地图容器:",e),h(),o(new Error(`找不到地图容器: ${e}`));return}const m=g.getBoundingClientRect();console.log("📤 发送地图容器信息到 iframe"),console.log("   容器尺寸:",m.width,"x",m.height);const P={center:[119.72170376,30.26262781],zoom:18};if(a.contentWindow&&!s)a.contentWindow.postMessage({type:"INIT_MAP",containerInfo:{width:m.width,height:m.height,top:m.top,left:m.left},mapOptions:P},"*");else{console.warn("⚠️ iframe 已失效，无法发送 INIT_MAP 消息"),h(),o(new Error("iframe 已失效"));return}const I=v=>{if(v.data&&v.data.type==="MAP_READY"){console.log("✅ 地图在 iframe 中创建成功"),l&&(clearTimeout(l),l=null),a.style.display="block",a.style.position="absolute",a.style.top="0",a.style.left="0",a.style.width="100%",a.style.height="100%",a.style.zIndex="1",g.style.visibility="hidden";let f=P.center||[119.7167014612051,30.265068364569423],w=P.zoom||13;const O={iframe:a,getCenter:()=>f,getZoom:()=>w,setCenter:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setCenter 调用");return}f=n,a.contentWindow.postMessage({type:"MAP_SET_CENTER",center:n},"*")},setZoom:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setZoom 调用");return}w=n,a.contentWindow.postMessage({type:"MAP_SET_ZOOM",zoom:n},"*")},setStatus:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setStatus 调用");return}a.contentWindow.postMessage({type:"MAP_SET_STATUS",status:n},"*")},setZooms:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setZooms 调用");return}a.contentWindow.postMessage({type:"MAP_SET_ZOOMS",zooms:n},"*")},on:(n,S)=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 on 调用");return}const b=E=>{E.data.type===`MAP_EVENT_${n.toUpperCase()}`&&(n==="moveend"?f=E.data.data:n==="zoomend"&&(w=E.data.data),S(E.data.data))};window.addEventListener("message",b),!s&&a.contentWindow&&a.contentWindow.postMessage({type:"MAP_ON",event:n},"*")},add:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 add 调用");return}a.contentWindow.postMessage({type:"MAP_ADD_LAYER",layer:n},"*")},remove:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 remove 调用");return}a.contentWindow.postMessage({type:"MAP_REMOVE_LAYER",layer:n},"*")},setFitView:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setFitView 调用");return}a.contentWindow.postMessage({type:"MAP_SET_FIT_VIEW",layers:n},"*")},setBounds:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setBounds 调用");return}a.contentWindow.postMessage({type:"MAP_SET_BOUNDS",bounds:n},"*")},addMarker:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 addMarker 调用");return}a.contentWindow.postMessage({type:"MAP_ADD_MARKER",marker:n},"*")},removeMarker:n=>{if(s||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 removeMarker 调用");return}a.contentWindow.postMessage({type:"MAP_REMOVE_MARKER",marker:n},"*")},destroy:()=>{s=!0,r.abort(),window.removeEventListener("message",_),window.removeEventListener("message",I),document.body.contains(a)&&a.remove(),g.style.visibility="visible"}},C=n=>{n.data.type==="MAP_GET_CENTER_RESPONSE"?(f=n.data.center,window.removeEventListener("message",C)):n.data.type==="MAP_GET_ZOOM_RESPONSE"&&(w=n.data.zoom,window.removeEventListener("message",C))};window.addEventListener("message",C),!s&&a.contentWindow&&(a.contentWindow.postMessage({type:"MAP_GET_CENTER"},"*"),a.contentWindow.postMessage({type:"MAP_GET_ZOOM"},"*")),t(O)}};window.addEventListener("message",I),l=setTimeout(()=>{console.error("❌ 等待 iframe 创建地图超时"),window.removeEventListener("message",I),h(),o(new Error("等待 iframe 创建地图超时"))},15e3)}else d.data&&d.data.type==="AMAP_ERROR"&&(console.error("❌ 收到 iframe 消息：高德地图加载失败"),h(),o(new Error(d.data.error||"高德地图 API 加载失败")))};window.addEventListener("message",_);let l=null;function h(){s=!0,r.abort(),window.removeEventListener("message",_),l&&(clearTimeout(l),l=null),document.body.contains(a)&&document.body.removeChild(a)}a.srcdoc=T})}function K(){return M.getCurrentPosition().then(e=>[e.longitude,e.latitude])}async function Y(e){console.log("🗺️ 开始初始化高德地图..."),await z()||console.warn("⚠️ 网络连接异常，继续尝试加载高德地图..."),console.log("🔒 设置高德地图安全密钥..."),G(),console.log("📡 加载高德地图 JS API...");const t=await F(e);try{console.log("📍 获取用户位置...");const o=await K();console.log("✅ 用户位置:",o)}catch{console.warn("⚠️ 定位失败，使用杭州作为默认中心点")}return console.log("✅ 高德地图初始化完成"),t}var p,u,y,B=A((()=>{N(),p={API_KEY:"",SECURITY_CODE:"",DEFAULT_CENTER:[119.72170376,30.26262781],DEFAULT_ZOOM:18},u={...p},y={updateConfig(e){e&&e.amap&&(u={API_KEY:e.amap.apiKey||p.API_KEY,SECURITY_CODE:e.amap.securityCode||p.SECURITY_CODE,DEFAULT_CENTER:e.amap.defaultCenter||p.DEFAULT_CENTER,DEFAULT_ZOOM:e.amap.defaultZoom||p.DEFAULT_ZOOM},console.log("✅ 高德地图配置已从后端更新"))},getApiKey(){return u.API_KEY},getSecurityCode(){return u.SECURITY_CODE},getDefaultCenter(){return u.DEFAULT_CENTER},getDefaultZoom(){return u.DEFAULT_ZOOM}}})),H,q=A((()=>{U(),B(),N(),H=class extends D{constructor(e={}){super(),this.supportsCustomReset=!0,this.initialCenter=null,this.initialZoom=null,this.map=null,this.polygons=[],this.markers=[],this.locationMarker=null,this.watchId=null,this.locationPermissionGranted=!1}async init(e,t={}){let o;if(typeof e=="string"?o=e:o=e.id,!o)throw new Error("地图容器 ID 不存在");this.map=await Y(o),this.initialCenter=this.map.getCenter(),this.initialZoom=this.map.getZoom(),t.zoom&&this.map.setZoom(t.zoom),t.center&&this.map.setCenter(t.center),this.map.setStatus({resizeEnable:!0,animateEnable:!0,zoomEnable:!0}),this.map.setZooms([3,18]),this.map.on("zoomend",()=>{this.triggerZoomCallbacks(this.map.getZoom())}),this.map.on("moveend",()=>{const r=this.map.getCenter();this.triggerMoveCallbacks([r.lng,r.lat])}),console.log("✅ 高德地图引擎初始化完成")}setCenter(e){this.map.setCenter(e)}getCenter(){const e=this.map.getCenter();return[e.lng,e.lat]}setZoom(e){this.map.setZoom(e)}getZoom(){return this.map.getZoom()}getLocationPosition(){return this.locationMarker&&this.locationMarker.position?this.locationMarker.position:null}panToLocation(){const e=this.getLocationPosition();return e?this.map&&this.map.setCenter?(this.map.setCenter(e),console.log("✅ 地图已移动到定位蓝点位置:",e),!0):!1:(console.warn("⚠️ 定位蓝点不存在，无法回到中心"),!1)}fitToBounds(e){const{minLng:t,minLat:o,maxLng:r,maxLat:a}=e,s=new window.AMap.Bounds([t,o],[r,a]);this.map.setBounds(s)}addPolygon(e){this.clearPolygons();const t=this.parseGeoJSONCoordinates(e);if(t.length===0){console.warn("GeoJSON 无有效坐标");return}t.forEach(o=>{const r=new window.AMap.Polygon({path:o,strokeColor:"#3366FF",strokeWeight:2,strokeOpacity:.8,fillColor:"#3366FF",fillOpacity:.2});this.map.add(r),this.polygons.push(r)}),this.polygons.length>0&&this.map.setFitView(this.polygons)}parseGeoJSONCoordinates(e){const t=[];if(e.type==="FeatureCollection")e.features.forEach(o=>{const r=this.extractCoordinates(o.geometry);r&&t.push(...r)});else if(e.type==="Feature"){const o=this.extractCoordinates(e.geometry);o&&t.push(...o)}else{const o=this.extractCoordinates(e);o&&t.push(...o)}return t}extractCoordinates(e){if(!e)return null;switch(e.type){case"Polygon":return e.coordinates.map(t=>t.map(o=>[o[0],o[1]]));case"MultiPolygon":return e.coordinates.flatMap(t=>t.map(o=>o.map(r=>[r[0],r[1]])));default:return null}}clearPolygons(){this.polygons.forEach(e=>{this.map.remove(e)}),this.polygons=[]}addMarker(e,t={}){const o=new window.AMap.Marker({position:e,icon:t.icon,title:t.title,extData:t.data});return this.map.add(o),this.markers.push(o),o}addMarkers(e){e.forEach(t=>{this.addMarker(t.position,t.options)})}clearMarkers(){this.markers.forEach(e=>{this.map.remove(e)}),this.markers=[]}async enableLocation(e=!1){return this.locationPermissionGranted?(this.addLocationMarker(),this.watchPosition(),!0):e?await M.requestPermission()===M.PermissionStatus.GRANTED?(this.locationPermissionGranted=!0,this.addLocationMarker(),this.watchPosition(),console.log("✅ 定位功能已启用"),!0):(console.warn("⚠️ 定位权限未授权，无法显示定位蓝点"),!1):!1}addLocationMarker(){if(!this.locationMarker){if(this.locationMarker={position:this.map.getCenter(),id:"location-marker-"+Date.now()},this.map.addMarker)this.map.addMarker({position:this.locationMarker.position,content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',zIndex:9999,title:"当前位置"});else{console.warn("⚠️ map.addMarker 方法不可用，使用备用方案");try{const e=new window.AMap.Marker({position:this.locationMarker.position,content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',zIndex:9999,title:"当前位置"});this.map.add(e),this.locationMarker.marker=e}catch(e){console.error("❌ 创建定位蓝点失败:",e),this.locationMarker=null;return}}console.log("✅ 定位蓝点已添加")}}removeLocationMarker(){this.locationMarker&&(this.locationMarker.marker&&this.map.remove?this.map.remove(this.locationMarker.marker):this.map.removeMarker&&this.map.removeMarker(this.locationMarker),this.locationMarker=null,console.log("✅ 定位蓝点已移除"))}updateLocationMarker(e,t){this.locationMarker&&(this.locationMarker.position=[e,t],this.locationMarker.marker?this.locationMarker.marker.setPosition([e,t]):this.map.addMarker&&this.map.addMarker({position:[e,t],content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',offset:new window.AMap.Pixel(-8,-8),zIndex:9999,title:"当前位置"}))}watchPosition(){if(this.watchId===null){if(!navigator.geolocation){console.warn("⚠️ 当前设备不支持定位功能");return}this.watchId=navigator.geolocation.watchPosition(e=>{const{longitude:t,latitude:o}=e.coords;this.updateLocationMarker(t,o)},e=>{console.error("❌ 定位失败:",e),e.code===e.PERMISSION_DENIED&&(this.locationPermissionGranted=!1,this.removeLocationMarker(),this.stopWatching())},{enableHighAccuracy:!0,timeout:1e4,maximumAge:5e3}),console.log("✅ 开始监听位置变化")}}stopWatching(){this.watchId!==null&&(navigator.geolocation.clearWatch(this.watchId),this.watchId=null,console.log("✅ 停止监听位置"))}destroy(){super.destroy(),this.clearPolygons(),this.clearMarkers(),this.stopWatching(),this.removeLocationMarker(),this.map&&(this.map.destroy(),this.map=null)}}}));export{M as a,U as i,q as n,N as o,D as r,H as t};
