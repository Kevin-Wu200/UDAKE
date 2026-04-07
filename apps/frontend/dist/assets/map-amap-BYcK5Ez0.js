import{n as C}from"./rolldown-runtime-CW5kiRZL.js";import{h as L,m as d}from"./charts-Dw6YLjy2.js";import{m as F,p as K}from"./core-components-BWaeVeTI.js";async function x(){if(!navigator.geolocation)return s=i.DENIED,i.DENIED;if(navigator.permissions&&navigator.permissions.query)try{const e=await navigator.permissions.query({name:"geolocation"});return e.state==="granted"?s=i.GRANTED:e.state==="denied"?s=i.DENIED:s=i.UNKNOWN,e.addEventListener("change",()=>{e.state==="granted"?s=i.GRANTED:e.state==="denied"?s=i.DENIED:s=i.UNKNOWN}),s}catch(e){return i.UNKNOWN}return i.UNKNOWN}async function Y(){const e=await x();return e===i.GRANTED?i.GRANTED:e===i.DENIED?i.DENIED:(K.showWarning("UDAKE 需要使用设备定位以支持当前位置采样功能。"),new Promise(o=>{navigator.geolocation.getCurrentPosition(()=>{s=i.GRANTED,o(i.GRANTED)},t=>{t.code===t.PERMISSION_DENIED?(s=i.DENIED,o(i.DENIED)):(s=i.UNKNOWN,o(i.UNKNOWN))},{enableHighAccuracy:!1,timeout:1e4,maximumAge:0})}))}function B(){return new Promise((e,o)=>{if(!navigator.geolocation){o({type:"unsupported",message:"当前设备不支持定位功能"});return}if(s===i.DENIED){o({type:"denied",message:"定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。"});return}navigator.geolocation.getCurrentPosition(t=>{s=i.GRANTED,e({longitude:t.coords.longitude,latitude:t.coords.latitude,accuracy:t.coords.accuracy,timestamp:new Date(t.timestamp).toISOString()})},t=>{t.code===t.PERMISSION_DENIED?(s=i.DENIED,o({type:"denied",message:"定位权限未授权，无法使用当前位置采样功能，请在系统设置中开启定位权限。"})):t.code===t.TIMEOUT?o({type:"timeout",message:"定位获取超时"}):t.code===t.POSITION_UNAVAILABLE?o({type:"unavailable",message:"设备定位不可用"}):o({type:"unknown",message:"未知的定位错误"})},{enableHighAccuracy:!1,timeout:1e4,maximumAge:0})})}function V(){return s}var i,s,P,Z=C((()=>{F(),i={GRANTED:"granted",DENIED:"denied",UNKNOWN:"unknown"},s=i.UNKNOWN,P={PermissionStatus:i,checkPermission:x,requestPermission:Y,getCurrentPosition:B,getPermissionStatus:V}}));function H(){I+=1,p&&!p.signal.aborted&&p.abort(),p=null}async function J(){try{return console.log("🌐 测试网络连接..."),await fetch("https://webapi.amap.com/maps",{method:"HEAD",mode:"no-cors",cache:"no-cache",signal:AbortSignal.timeout(5e3)}),console.log("✅ 网络连接正常"),!0}catch(e){return console.error("❌ 网络连接测试失败:",e),!1}}function $(){window._AMapSecurityConfig={securityJsCode:v.getSecurityCode()}}function q(e){return new Promise((o,t)=>{console.log("🔄 开始加载高德地图 API（iframe 方式）..."),console.log("📦 地图容器 ID:",e),H();const r=new AbortController;p=r;const k=++I;if(window.AMap&&window.AMap.Map){console.log("✅ 高德地图 API 已加载，直接返回"),o(window.AMap);return}if(!navigator.onLine){console.error("❌ 网络连接不可用"),t(new Error("网络连接不可用，无法加载高德地图 API"));return}const a=document.createElement("iframe");a.style.display="none",a.style.width="0",a.style.height="0",a.id="amap-loader-iframe";let c=!1;const T=new Set,D=()=>!c&&!r.signal.aborted&&k===I,l=(m,f)=>{if(!D()||!a.contentWindow)return console.warn(`⚠️ iframe 不可用，跳过 ${f} 调用`),!1;try{return a.contentWindow.postMessage(m,"*"),!0}catch(u){return console.error(`❌ ${f} postMessage 失败:`,u),!1}};document.body.appendChild(a),console.log("📤 创建 iframe 用于加载高德地图 API");const W=`
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
                        securityJsCode: "${v.getSecurityCode()}"
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
                        } else if (e.data.type === 'MAP_DESTROY') {
                            if (mapInstance) {
                                mapInstance.destroy();
                                mapInstance = null;
                            }
                            window.parent.postMessage({
                                type: 'MAP_DESTROYED'
                            }, '*');
                        }
                    });
                    
                    // 加载高德地图 API
                    var script = document.createElement('script');
                    script.src = 'https://webapi.amap.com/maps?v=2.0&key=${v.getApiKey()}';
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
        `,N=m=>{if(D()&&!(m.origin!==window.location.origin&&m.origin!=="null")&&m.source===a.contentWindow)if(m.data&&m.data.type==="AMAP_LOADED"){console.log("✅ 收到 iframe 消息：高德地图已加载");const f=document.getElementById(e);if(!f){console.error("❌ 找不到地图容器:",e),M(),t(new Error(`找不到地图容器: ${e}`));return}const u=f.getBoundingClientRect();console.log("📤 发送地图容器信息到 iframe"),console.log("   容器尺寸:",u.width,"x",u.height);const O={center:[119.72170376,30.26262781],zoom:18};if(!l({type:"INIT_MAP",containerInfo:{width:u.width,height:u.height,top:u.top,left:u.left},mapOptions:O},"INIT_MAP")){console.warn("⚠️ iframe 已失效，无法发送 INIT_MAP 消息"),M(),t(new Error("iframe 已失效"));return}const A=S=>{if(!(!D()||S.source!==a.contentWindow)&&S.data&&S.data.type==="MAP_READY"){console.log("✅ 地图在 iframe 中创建成功"),window.removeEventListener("message",A),h&&(clearTimeout(h),h=null),a.style.display="block",a.style.position="absolute",a.style.top="0",a.style.left="0",a.style.width="100%",a.style.height="100%",a.style.zIndex="1",f.style.visibility="hidden";let y=O.center||[119.7167014612051,30.265068364569423],_=O.zoom||13;const G={iframe:a,getCenter:()=>y,getZoom:()=>_,setCenter:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setCenter 调用");return}y=n,l({type:"MAP_SET_CENTER",center:n},"MAP_SET_CENTER")},setZoom:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setZoom 调用");return}_=n,l({type:"MAP_SET_ZOOM",zoom:n},"MAP_SET_ZOOM")},setStatus:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setStatus 调用");return}l({type:"MAP_SET_STATUS",status:n},"MAP_SET_STATUS")},setZooms:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setZooms 调用");return}l({type:"MAP_SET_ZOOMS",zooms:n},"MAP_SET_ZOOMS")},on:(n,z)=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 on 调用");return}const b=w=>{w.source===a.contentWindow&&w.data.type===`MAP_EVENT_${n.toUpperCase()}`&&(n==="moveend"?y=w.data.data:n==="zoomend"&&(_=w.data.data),z(w.data.data))};window.addEventListener("message",b),T.add(b),l({type:"MAP_ON",event:n},"MAP_ON")},add:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 add 调用");return}l({type:"MAP_ADD_LAYER",layer:n},"MAP_ADD_LAYER")},remove:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 remove 调用");return}l({type:"MAP_REMOVE_LAYER",layer:n},"MAP_REMOVE_LAYER")},setFitView:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setFitView 调用");return}l({type:"MAP_SET_FIT_VIEW",layers:n},"MAP_SET_FIT_VIEW")},setBounds:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 setBounds 调用");return}l({type:"MAP_SET_BOUNDS",bounds:n},"MAP_SET_BOUNDS")},addMarker:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 addMarker 调用");return}l({type:"MAP_ADD_MARKER",marker:n},"MAP_ADD_MARKER")},removeMarker:n=>{if(c||!a.contentWindow){console.warn("⚠️ iframe 已失效，跳过 removeMarker 调用");return}l({type:"MAP_REMOVE_MARKER",marker:n},"MAP_REMOVE_MARKER")},destroy:()=>{l({type:"MAP_DESTROY"},"MAP_DESTROY"),c=!0,r.abort(),window.removeEventListener("message",N),window.removeEventListener("message",A),T.forEach(n=>{window.removeEventListener("message",n)}),T.clear(),document.body.contains(a)&&a.remove(),f.style.visibility="visible",p===r&&(p=null)}},R=n=>{n.source===a.contentWindow&&(n.data.type==="MAP_GET_CENTER_RESPONSE"?(y=n.data.center,window.removeEventListener("message",R)):n.data.type==="MAP_GET_ZOOM_RESPONSE"&&(_=n.data.zoom,window.removeEventListener("message",R)))};window.addEventListener("message",R),l({type:"MAP_GET_CENTER"},"MAP_GET_CENTER"),l({type:"MAP_GET_ZOOM"},"MAP_GET_ZOOM"),o(G)}};window.addEventListener("message",A),h=setTimeout(()=>{console.error("❌ 等待 iframe 创建地图超时"),window.removeEventListener("message",A),M(),t(new Error("等待 iframe 创建地图超时"))},15e3)}else m.data&&m.data.type==="AMAP_ERROR"&&(console.error("❌ 收到 iframe 消息：高德地图加载失败"),M(),t(new Error(m.data.error||"高德地图 API 加载失败")))};window.addEventListener("message",N);let h=null;r.signal.addEventListener("abort",()=>{c||(M(),t(new Error("高德地图加载已取消")))},{once:!0});function M(){c=!0,r.signal.aborted||r.abort(),window.removeEventListener("message",N),h&&(clearTimeout(h),h=null),document.body.contains(a)&&document.body.removeChild(a),p===r&&(p=null)}a.srcdoc=W})}function Q(){return P.getCurrentPosition().then(e=>[e.longitude,e.latitude])}async function X(e){console.log("🗺️ 开始初始化高德地图..."),await J()||console.warn("⚠️ 网络连接异常，继续尝试加载高德地图..."),console.log("🔒 设置高德地图安全密钥..."),$(),console.log("📡 加载高德地图 JS API...");const o=await q(e);try{console.log("📍 获取用户位置...");const t=await Q();console.log("✅ 用户位置:",t)}catch(t){console.warn("⚠️ 定位失败，使用杭州作为默认中心点")}return console.log("✅ 高德地图初始化完成"),o}var E,g,v,p,I,j=C((()=>{Z(),E={API_KEY:"2f3f114aa5671425aa3c52f707d741c5",SECURITY_CODE:"10b5ef21f6b36d09e24d7b076d35dccc",DEFAULT_CENTER:[119.72170376,30.26262781],DEFAULT_ZOOM:18},g={...E},v={updateConfig(e){e&&e.amap&&(g={API_KEY:e.amap.apiKey||E.API_KEY,SECURITY_CODE:e.amap.securityCode||E.SECURITY_CODE,DEFAULT_CENTER:e.amap.defaultCenter||E.DEFAULT_CENTER,DEFAULT_ZOOM:e.amap.defaultZoom||E.DEFAULT_ZOOM},console.log("✅ 高德地图配置已从后端更新"))},getApiKey(){return g.API_KEY},getSecurityCode(){return g.SECURITY_CODE},getDefaultCenter(){return g.DEFAULT_CENTER},getDefaultZoom(){return g.DEFAULT_ZOOM}},p=null,I=0})),U,ee=C((()=>{L(),U=class{constructor(){d(this,"supportsCustomReset",void 0),d(this,"zoomCallbacks",void 0),d(this,"moveCallbacks",void 0),this.supportsCustomReset=!1,this.zoomCallbacks=[],this.moveCallbacks=[]}onZoom(e){this.zoomCallbacks.push(e)}onMove(e){this.moveCallbacks.push(e)}triggerZoomCallbacks(e){this.zoomCallbacks.forEach(o=>o(e))}triggerMoveCallbacks(e){this.moveCallbacks.forEach(o=>o(e))}destroy(){this.zoomCallbacks=[],this.moveCallbacks=[]}}})),te,ie=C((()=>{ee(),j(),Z(),L(),te=class extends U{constructor(e={}){super(),d(this,"map",void 0),d(this,"initialCenter",void 0),d(this,"initialZoom",void 0),d(this,"polygons",void 0),d(this,"markers",void 0),d(this,"locationMarker",void 0),d(this,"watchId",void 0),d(this,"locationPermissionGranted",void 0),this.supportsCustomReset=!0,this.initialCenter=null,this.initialZoom=null,this.map=null,this.polygons=[],this.markers=[],this.locationMarker=null,this.watchId=null,this.locationPermissionGranted=!1}async init(e,o={}){let t;if(typeof e=="string"?t=e:t=e.id,!t)throw new Error("地图容器 ID 不存在");this.map=await X(t),this.initialCenter=this.map.getCenter(),this.initialZoom=this.map.getZoom(),o.zoom&&this.map.setZoom(o.zoom),o.center&&this.map.setCenter(o.center),this.map.setStatus({resizeEnable:!0,animateEnable:!0,zoomEnable:!0}),this.map.setZooms([3,18]),this.map.on("zoomend",()=>{this.triggerZoomCallbacks(this.map.getZoom())}),this.map.on("moveend",()=>{const r=this.map.getCenter();this.triggerMoveCallbacks([r.lng,r.lat])}),console.log("✅ 高德地图引擎初始化完成")}setCenter(e){this.map.setCenter(e)}getCenter(){const e=this.map.getCenter();return[e.lng,e.lat]}setZoom(e){this.map.setZoom(e)}getZoom(){return this.map.getZoom()}getLocationPosition(){return this.locationMarker&&this.locationMarker.position?this.locationMarker.position:null}panToLocation(){const e=this.getLocationPosition();return e?this.map&&this.map.setCenter?(this.map.setCenter(e),console.log("✅ 地图已移动到定位蓝点位置:",e),!0):!1:(console.warn("⚠️ 定位蓝点不存在，无法回到中心"),!1)}fitToBounds(e){const{minLng:o,minLat:t,maxLng:r,maxLat:k}=e,a=new window.AMap.Bounds([o,t],[r,k]);this.map.setBounds(a)}addPolygon(e){this.clearPolygons();const o=this.parseGeoJSONCoordinates(e);if(o.length===0){console.warn("GeoJSON 无有效坐标");return}o.forEach(t=>{const r=new window.AMap.Polygon({path:t,strokeColor:"#3366FF",strokeWeight:2,strokeOpacity:.8,fillColor:"#3366FF",fillOpacity:.2});this.map.add(r),this.polygons.push(r)}),this.polygons.length>0&&this.map.setFitView(this.polygons)}parseGeoJSONCoordinates(e){const o=[];if(e.type==="FeatureCollection")e.features.forEach(t=>{const r=this.extractCoordinates(t.geometry);r&&o.push(...r)});else if(e.type==="Feature"){const t=this.extractCoordinates(e.geometry);t&&o.push(...t)}else{const t=this.extractCoordinates(e);t&&o.push(...t)}return o}extractCoordinates(e){if(!e)return null;switch(e.type){case"Polygon":return e.coordinates.map(o=>o.map(t=>[t[0],t[1]]));case"MultiPolygon":return e.coordinates.flatMap(o=>o.map(t=>t.map(r=>[r[0],r[1]])));default:return null}}clearPolygons(){this.polygons.forEach(e=>{this.map.remove(e)}),this.polygons=[]}addMarker(e,o={}){const t=new window.AMap.Marker({position:e,icon:o.icon,title:o.title,extData:o.data});return this.map.add(t),this.markers.push(t),t}addMarkers(e){e.forEach(o=>{this.addMarker(o.position,o.options)})}clearMarkers(){this.markers.forEach(e=>{this.map.remove(e)}),this.markers=[]}async enableLocation(e=!1){return this.locationPermissionGranted?(this.addLocationMarker(),this.watchPosition(),!0):e?await P.requestPermission()===P.PermissionStatus.GRANTED?(this.locationPermissionGranted=!0,this.addLocationMarker(),this.watchPosition(),console.log("✅ 定位功能已启用"),!0):(console.warn("⚠️ 定位权限未授权，无法显示定位蓝点"),!1):!1}addLocationMarker(){if(!this.locationMarker){if(this.locationMarker={position:this.map.getCenter(),id:"location-marker-"+Date.now()},this.map.addMarker)this.map.addMarker({position:this.locationMarker.position,content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',zIndex:9999,title:"当前位置"});else{console.warn("⚠️ map.addMarker 方法不可用，使用备用方案");try{const e=new window.AMap.Marker({position:this.locationMarker.position,content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3); transform: translate(-50%, -50%);"></div>',zIndex:9999,title:"当前位置"});this.map.add(e),this.locationMarker.marker=e}catch(e){console.error("❌ 创建定位蓝点失败:",e),this.locationMarker=null;return}}console.log("✅ 定位蓝点已添加")}}removeLocationMarker(){this.locationMarker&&(this.locationMarker.marker&&this.map.remove?this.map.remove(this.locationMarker.marker):this.map.removeMarker&&this.map.removeMarker(this.locationMarker),this.locationMarker=null,console.log("✅ 定位蓝点已移除"))}updateLocationMarker(e,o){this.locationMarker&&(this.locationMarker.position=[e,o],this.locationMarker.marker?this.locationMarker.marker.setPosition([e,o]):this.map.addMarker&&this.map.addMarker({position:[e,o],content:'<div style="background-color: #4A90E2; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',offset:new window.AMap.Pixel(-8,-8),zIndex:9999,title:"当前位置"}))}watchPosition(){if(this.watchId===null){if(!navigator.geolocation){console.warn("⚠️ 当前设备不支持定位功能");return}this.watchId=navigator.geolocation.watchPosition(e=>{const{longitude:o,latitude:t}=e.coords;this.updateLocationMarker(o,t)},e=>{console.error("❌ 定位失败:",e),e.code===e.PERMISSION_DENIED&&(this.locationPermissionGranted=!1,this.removeLocationMarker(),this.stopWatching())},{enableHighAccuracy:!0,timeout:1e4,maximumAge:5e3}),console.log("✅ 开始监听位置变化")}}stopWatching(){this.watchId!==null&&(navigator.geolocation.clearWatch(this.watchId),this.watchId=null,console.log("✅ 停止监听位置"))}destroy(){super.destroy(),this.clearPolygons(),this.clearMarkers(),this.stopWatching(),this.removeLocationMarker(),this.map&&(this.map.destroy(),this.map=null)}}}));export{H as a,Z as c,ee as i,ie as n,j as o,U as r,P as s,te as t};
