const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["./ArcGISAdapter-BbiulVWF.js","./components-nadRvCAJ.js","./rolldown-runtime-DQCMaF4_.js","./map-core-BTJDFJLu.js","./map-amap-butgFBXC.js","./core-components-BzHiWJh9.js","./map-arcgis-6uCe7i-M.js","./AMapAdapter-C4gFWR1W.js"])))=>i.map(i=>d[i]);
import{n as f}from"./rolldown-runtime-DQCMaF4_.js";import{C as Le,D as ls,F as ct,M as h,N as Se,P as R,S as cs,T as yt,_ as ds,b as hs,v as us,w as ps,x as ms,y as gs}from"./components-nadRvCAJ.js";import{i as ke,n as fs,r as ys,t as vs}from"./core-components-BzHiWJh9.js";var Ce,Si=f((()=>{Ce={MAP_PROVIDER:"arcgis",getProvider(){return this.MAP_PROVIDER},isArcGIS(){return this.MAP_PROVIDER==="arcgis"},isAMap(){return this.MAP_PROVIDER==="amap"}}}));async function Ci(){return{ArcGISAdapter:await R(()=>import("./ArcGISAdapter-BbiulVWF.js"),__vite__mapDeps([0,1,2,3,4,5,6]),import.meta.url),AMapAdapter:await R(()=>import("./AMapAdapter-C4gFWR1W.js"),__vite__mapDeps([7,3,2,1,4,5,6]),import.meta.url)}}async function Sn(e){const{ArcGISAdapter:t,AMapAdapter:i}=await Ci(),s=Ce.getProvider();console.log(`🗺️ 使用地图引擎: ${s}`);let n;switch(s){case"arcgis":n=new t.ArcGISAdapter;break;case"amap":n=new i.AMapAdapter;break;default:throw new Error(`不支持的地图引擎: ${s}`)}return await n.initMap(e),n}async function bs(){const e=Ce.getProvider();if(e!=="arcgis"&&e!=="amap")throw new Error(`无效的地图引擎: ${e}`);return e}async function Cn(e,t){console.log(`🔄 重新初始化地图，使用引擎: ${t}`);const{ArcGISAdapter:i,AMapAdapter:s}=await Ci();let n;switch(t){case"arcgis":n=new i.ArcGISAdapter;break;case"amap":n=new s.AMapAdapter;break;default:throw new Error(`不支持的地图引擎: ${t}`)}return await n.initMap(e),n}var ws=f((()=>{Si(),ct()})),re,vt,bt,x,I,dt=f((()=>{vt="udake_offline",bt=1,x={projects:"projects",points:"points",results:"results",pendingActions:"pendingActions"},I=class{static async init(){await this._openDB(),this._bindNetworkEvents(),this.onStatusChange(e=>{e&&this.sync()})}static get isOnline(){return this._online}static onStatusChange(e){return this._listeners.add(e),()=>{this._listeners.delete(e)}}static _bindNetworkEvents(){window.addEventListener("online",()=>this._setOnline(!0)),window.addEventListener("offline",()=>this._setOnline(!1))}static _setOnline(e){this._online!==e&&(this._online=e,console.log(`[Offline] 网络状态: ${e?"在线":"离线"}`),this._listeners.forEach(t=>{try{t(e)}catch(i){console.error(i)}}))}static _openDB(){return new Promise((e,t)=>{if(this.db){e(this.db);return}const i=indexedDB.open(vt,bt);i.onupgradeneeded=()=>{const s=i.result;s.objectStoreNames.contains(x.projects)||s.createObjectStore(x.projects,{keyPath:"id"}),s.objectStoreNames.contains(x.points)||s.createObjectStore(x.points,{keyPath:"id",autoIncrement:!0}).createIndex("projectId","projectId",{unique:!1}),s.objectStoreNames.contains(x.results)||s.createObjectStore(x.results,{keyPath:"taskId"}),s.objectStoreNames.contains(x.pendingActions)||s.createObjectStore(x.pendingActions,{keyPath:"id"})},i.onsuccess=()=>{this.db=i.result,e(this.db)},i.onerror=()=>t(i.error)})}static _tx(e,t="readonly"){if(!this.db)throw new Error("IndexedDB 未初始化");return this.db.transaction(e,t).objectStore(e)}static _req(e){return new Promise((t,i)=>{e.onsuccess=()=>t(e.result),e.onerror=()=>i(e.error)})}static async saveProject(e){const t=this._tx(x.projects,"readwrite");await this._req(t.put({...e,_savedAt:Date.now()}))}static async getProject(e){const t=this._tx(x.projects,"readonly");return this._req(t.get(e))}static async getAllProjects(){const e=this._tx(x.projects,"readonly");return this._req(e.getAll())}static async savePoints(e,t){const i=this._tx(x.points,"readwrite");for(const s of t)await this._req(i.put({...s,projectId:e,_savedAt:Date.now()}))}static async getPoints(e){const t=this._tx(x.points,"readonly").index("projectId");return this._req(t.getAll(e))}static async cacheResult(e,t){const i=this._tx(x.results,"readwrite");await this._req(i.put({taskId:e,...t,_cachedAt:Date.now()}))}static async getCachedResult(e){const t=this._tx(x.results,"readonly");return this._req(t.get(e))}static async enqueue(e){const t=this._tx(x.pendingActions,"readwrite"),i={...e,id:`${Date.now()}_${Math.random().toString(36).slice(2,8)}`,timestamp:Date.now(),retries:0};await this._req(t.put(i)),console.log(`[Offline] 操作已入队: ${e.type}`)}static async getPendingActions(){const e=this._tx(x.pendingActions,"readonly");return this._req(e.getAll())}static async _removeAction(e){const t=this._tx(x.pendingActions,"readwrite");await this._req(t.delete(e))}static async sync(e="latest-wins"){if(this._syncInProgress||!this._online)return{success:0,failed:0,conflicts:0};this._syncInProgress=!0;const t={success:0,failed:0,conflicts:0};try{const i=await this.getPendingActions();if(i.length===0)return t;console.log(`[Offline] 开始同步 ${i.length} 个操作...`);for(const s of i)try{await this._executeAction(s,e),await this._removeAction(s.id),t.success++}catch(n){n?.message?.includes("conflict")?(t.conflicts++,await this._resolveConflict(s,e)):(s.retries++,s.retries>=3&&(await this._removeAction(s.id),console.warn(`[Offline] 操作重试超限，已丢弃: ${s.id}`)),t.failed++)}console.log("[Offline] 同步完成:",t)}finally{this._syncInProgress=!1}return t}static async _executeAction(e,t){const i=this._actionHandlers;i?.has(e.type)?await i.get(e.type)(e.payload):console.warn(`[Offline] 未注册的操作类型: ${e.type}`)}static async _resolveConflict(e,t){switch(t){case"client-wins":await this._executeAction(e,t),await this._removeAction(e.id);break;case"server-wins":await this._removeAction(e.id);break;default:await this._removeAction(e.id);break}}static registerHandler(e,t){this._actionHandlers||(this._actionHandlers=new Map),this._actionHandlers.set(e,t)}static async getPendingCount(){return(await this.getPendingActions()).length}static async clearAll(){for(const e of Object.values(x)){const t=this._tx(e,"readwrite");await this._req(t.clear())}console.log("[Offline] 已清除所有离线数据")}},re=I,re.db=null,re._online=navigator.onLine,re._listeners=new Set,re._syncInProgress=!1})),Pe,Te,Re,wt,Ei,xs=f((()=>{Pe=class{constructor(e=100){this.accessQueue=new Map,this.maxSize=e}shouldEvict(e){return!1}onAccess(e,t){this.accessQueue.set(t,Date.now())}onInsert(e,t){this.accessQueue.set(t,Date.now())}getEvictionKey(){let e=null,t=1/0;return this.accessQueue.forEach((i,s)=>{i<t&&(t=i,e=s)}),e}updateMaxSize(e){this.maxSize=e}clear(){this.accessQueue.clear()}},Te=class{constructor(e=100){this.frequencyMap=new Map,this.maxSize=e}shouldEvict(e){return!1}onAccess(e,t){const i=this.frequencyMap.get(t)||0;this.frequencyMap.set(t,i+1)}onInsert(e,t){this.frequencyMap.set(t,1)}getEvictionKey(){let e=null,t=1/0;return this.frequencyMap.forEach((i,s)=>{i<t&&(t=i,e=s)}),e}getFrequency(e){return this.frequencyMap.get(e)||0}clear(){this.frequencyMap.clear()}},Re=class{constructor(e=.95,t=.1){this.decayRate=e,this.scoreMap=new Map,this.lastAccessMap=new Map,this.minScore=t}shouldEvict(e){const t=this._getKey(e),i=this._calculateScore(e);return this.scoreMap.set(t,i),i<this.minScore}onAccess(e,t){e.accessCount++,e.lastAccessTime=Date.now(),this.lastAccessMap.set(t,Date.now())}onInsert(e,t){e.accessCount=1,e.lastAccessTime=Date.now(),this.scoreMap.set(t,1),this.lastAccessMap.set(t,Date.now())}getEvictionKey(){let e=null,t=1/0;return this.scoreMap.forEach((i,s)=>{i<t&&(t=i,e=s)}),e}_calculateScore(e){const t=(Date.now()-e.timestamp)/6e4;return e.accessCount*Math.pow(this.decayRate,t)}_getKey(e){return String(e.timestamp)}clear(){this.scoreMap.clear(),this.lastAccessMap.clear()}updateDecayRate(e){this.decayRate=e}},wt=class{constructor(e=100){this.lru=new Pe(e),this.lfu=new Te(e),this.timeDecay=new Re,this.maxSize=e,this.accessMap=new Map}shouldEvict(e){return this.timeDecay.shouldEvict(e)}onAccess(e,t){this.lru.onAccess(e,t),this.lfu.onAccess(e,t),this.timeDecay.onAccess(e,t);const i=this.accessMap.get(t)||{lruTime:0,lfuFreq:0,decayScore:0};i.lruTime=Date.now(),i.lfuFreq=this.lfu.getFrequency(t),this.accessMap.set(t,i)}onInsert(e,t){this.lru.onInsert(e,t),this.lfu.onInsert(e,t),this.timeDecay.onInsert(e,t),this.accessMap.set(t,{lruTime:Date.now(),lfuFreq:1,decayScore:1})}getEvictionKey(){let e=null,t=1/0;return this.accessMap.forEach((i,s)=>{const n=this._normalizeTime(i.lruTime),a=this._normalizeFrequency(i.lfuFreq),r=i.decayScore,o=n*.4+a*.3+r*.3;o<t&&(t=o,e=s)}),e}_normalizeTime(e){const t=Date.now()-e;return Math.max(0,1-t/36e5)}_normalizeFrequency(e){return Math.min(1,e/100)}clear(){this.lru.clear(),this.lfu.clear(),this.timeDecay.clear(),this.accessMap.clear()}getScore(e){const t=this.accessMap.get(e);if(!t)return 0;const i=this._normalizeTime(t.lruTime),s=this._normalizeFrequency(t.lfuFreq),n=t.decayScore;return i*.4+s*.3+n*.3}},Ei=class{static create(e,t=100){switch(e){case"lru":return new Pe(t);case"lfu":return new Te(t);case"time-decay":return new Re;default:return new wt(t)}}}})),nt,Ss=f((()=>{xs(),nt=class{constructor(e={}){this.cleanupTimer=null,this.responseTimeHistory=[],this.isDestroyed=!1,this.cache=new Map,this.config={maxSize:e.maxSize||100,ttl:e.ttl||300*1e3,strategy:e.strategy||"hybrid",persistence:e.persistence||!1,storageKey:e.storageKey||"smart-cache",enableStats:e.enableStats!==!1,enableAutoCleanup:e.enableAutoCleanup!==!1,cleanupInterval:e.cleanupInterval||60*1e3},this.strategy=Ei.create(this.config.strategy,this.config.maxSize),this.stats={hits:0,misses:0,size:0,hitRate:0,evictionCount:0,totalRequests:0,avgResponseTime:0},this.eventListeners=new Map,["hit","miss","set","delete","evict","clear","expire"].forEach(t=>{this.eventListeners.set(t,new Set)}),this.config.persistence&&this.loadFromPersistence(),this.config.enableAutoCleanup&&this.startCleanup()}get(e){if(this.isDestroyed){console.warn("[SmartCache] 缓存已销毁，无法获取值");return}const t=Date.now(),i=this.cache.get(e);if(!i){this._onEvent("miss",String(e)),this.config.enableStats&&(this.stats.misses++,this.stats.totalRequests++,this._updateHitRate(),this._updateResponseTime(t));return}if(Date.now()>i.expiresAt){this.delete(e),this._onEvent("expire",String(e),i),this.config.enableStats&&(this.stats.misses++,this.stats.totalRequests++,this._updateHitRate(),this._updateResponseTime(t));return}return this.strategy.onAccess(i,String(e)),i.lastAccessTime=Date.now(),this._onEvent("hit",String(e),i),this.config.enableStats&&(this.stats.hits++,this.stats.totalRequests++,this._updateHitRate(),this._updateResponseTime(t)),i.value}set(e,t,i){if(this.isDestroyed){console.warn("[SmartCache] 缓存已销毁，无法设置值");return}const s=i||this.config.ttl,n=Date.now()+s,a=this._calculateSize(t),r={value:t,timestamp:Date.now(),accessCount:0,lastAccessTime:Date.now(),expiresAt:n,size:a};this.cache.size>=this.config.maxSize&&!this.cache.has(e)&&this.evict({checkExpired:!1}),this.cache.set(e,r),this.strategy.onInsert(r,String(e)),this.config.enableStats&&(this.stats.size=this.cache.size),this._onEvent("set",String(e),r),this.config.persistence&&this.saveToPersistence()}delete(e){if(this.isDestroyed)return console.warn("[SmartCache] 缓存已销毁，无法删除值"),!1;const t=this.cache.get(e),i=this.cache.delete(e);return i&&(this.config.enableStats&&(this.stats.size=this.cache.size),this._onEvent("delete",String(e),t)),i}clear(){if(this.isDestroyed){console.warn("[SmartCache] 缓存已销毁，无法清空");return}this.cache.clear(),this.config.enableStats&&(this.stats.size=0),this.config.persistence&&this.clearPersistence(),this._onEvent("clear","",void 0)}has(e){if(this.isDestroyed)return!1;const t=this.cache.get(e);return t?Date.now()>t.expiresAt?(this.delete(e),!1):!0:!1}keys(){if(this.isDestroyed)return[];const e=[],t=Date.now();return this.cache.forEach((i,s)=>{t<=i.expiresAt&&e.push(s)}),e}values(){if(this.isDestroyed)return[];const e=[],t=Date.now();return this.cache.forEach(i=>{t<=i.expiresAt&&e.push(i.value)}),e}size(){if(this.isDestroyed)return 0;let e=0;const t=Date.now();return this.cache.forEach(i=>{t<=i.expiresAt&&e++}),e}evict(e={}){if(!this.isDestroyed){if(e.checkExpired!==!1){const t=Date.now();for(const[i,s]of this.cache.entries())t>s.expiresAt&&(this.cache.delete(i),this.config.enableStats&&this.stats.evictionCount++,this._onEvent("expire",String(i),s))}if(this.cache.size>=this.config.maxSize){const t=this.strategy.getEvictionKey();if(t){const i=this.cache.get(t);this.cache.delete(t),this.config.enableStats&&this.stats.evictionCount++,this._onEvent("evict",t,i)}}this.config.enableStats&&(this.stats.size=this.cache.size)}}on(e,t){const i=this.eventListeners.get(e);i&&i.add(t)}off(e,t){const i=this.eventListeners.get(e);i&&i.delete(t)}getStats(){return{...this.stats}}resetStats(){this.stats={hits:0,misses:0,size:this.cache.size,hitRate:0,evictionCount:0,totalRequests:0,avgResponseTime:0},this.responseTimeHistory=[]}getHealthStatus(){const e=this.stats.hitRate,t=this.cache.size/this.config.maxSize,i=e>.5&&t<.9,s=[];return e<.5&&s.push("缓存命中率较低，建议增加TTL或调整缓存大小"),t>.9&&s.push("缓存使用率过高，建议增加缓存大小"),this.stats.evictionCount>this.stats.hits*.2&&s.push("淘汰频率过高，建议调整缓存策略"),{isHealthy:i,hitRate:e,memoryUsageRate:t,recommendations:s}}destroy(){this.isDestroyed||(this.isDestroyed=!0,this.cleanupTimer!==null&&(clearInterval(this.cleanupTimer),this.cleanupTimer=null),this.clear(),this.strategy.clear(),this.eventListeners.clear())}startCleanup(){this.cleanupTimer!==null&&clearInterval(this.cleanupTimer),this.cleanupTimer=window.setInterval(()=>{this.evict()},this.config.cleanupInterval)}_updateHitRate(){const e=this.stats.hits+this.stats.misses;this.stats.hitRate=e>0?this.stats.hits/e:0}_updateResponseTime(e){const t=Date.now()-e;this.responseTimeHistory.push(t),this.responseTimeHistory.length>100&&this.responseTimeHistory.shift();const i=this.responseTimeHistory.reduce((s,n)=>s+n,0);this.stats.avgResponseTime=i/this.responseTimeHistory.length}_onEvent(e,t,i){const s=this.eventListeners.get(e);s&&s.forEach(n=>{try{n(e,t,i)}catch(a){console.error(`[SmartCache] 事件监听器执行失败 [${e}]:`,a)}})}_calculateSize(e){try{if(e==null)return 0;if(typeof e=="string")return e.length*2;if(typeof e=="number")return 8;if(typeof e=="boolean")return 4;const t=JSON.stringify(e);return t?t.length*2:0}catch{return 1024}}loadFromPersistence(){try{const e=localStorage.getItem(this.config.storageKey);if(e){const t=JSON.parse(e);for(const[i,s]of Object.entries(t))Date.now()<=s.expiresAt&&this.cache.set(i,s);this.config.enableStats&&(this.stats.size=this.cache.size)}}catch(e){console.error("[SmartCache] 加载持久化缓存失败:",e)}}saveToPersistence(){try{const e={};this.cache.forEach((t,i)=>{e[String(i)]=t}),localStorage.setItem(this.config.storageKey,JSON.stringify(e))}catch(e){console.error("[SmartCache] 保存持久化缓存失败:",e)}}clearPersistence(){try{localStorage.removeItem(this.config.storageKey)}catch(e){console.error("[SmartCache] 清除持久化缓存失败:",e)}}}})),Li,Cs=f((()=>{Ss(),Li=class{constructor(e={},t={},i){this.promotionCount=0,this.isDestroyed=!1,this.ttlStore=new Map,this.memoryCache=new nt({maxSize:e.maxSize||50,ttl:e.ttl||300*1e3,strategy:e.strategy||"lru",persistence:!1,enableStats:!0}),this.diskCache=new nt({maxSize:t.maxSize||500,ttl:t.ttl||3600*1e3,strategy:t.strategy||"lfu",persistence:!0,storageKey:t.storageKey||"disk-cache",enableStats:!0}),this.memoryToDiskPromoter=new Map,this.enableAutoPromote=i?.enableAutoPromote!==!1,this.promoteThreshold=i?.promoteThreshold||3,this.memoryCache.on("hit",(s,n)=>{this._trackAccess(n)})}async get(e){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法获取值");return}let t=this.memoryCache.get(e);if(t!==void 0)return t;if(t=this.diskCache.get(e),t!==void 0)return this.enableAutoPromote&&await this.promoteToMemory(e,t),t}async set(e,t,i){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法设置值");return}this.memoryCache.set(e,t),this.diskCache.set(e,t),i&&this.ttlStore.set(e,Date.now()+i),this.memoryToDiskPromoter.set(e,0)}async delete(e){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法删除值");return}this.memoryCache.delete(e),this.diskCache.delete(e),this.memoryToDiskPromoter.delete(e)}async clear(){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法清空");return}this.memoryCache.clear(),this.diskCache.clear(),this.memoryToDiskPromoter.clear(),this.promotionCount=0}async has(e){return this.isDestroyed?!1:this.memoryCache.has(e)||this.diskCache.has(e)}keys(){if(this.isDestroyed)return[];const e=this.memoryCache.keys(),t=this.diskCache.keys(),i=new Set([...e,...t]);return Array.from(i)}size(){return this.isDestroyed?0:(this.memoryCache.size(),this.diskCache.size(),new Set([...this.memoryCache.keys(),...this.diskCache.keys()]).size)}async promoteToMemory(e,t){this.isDestroyed||(t===void 0&&(t=this.diskCache.get(e)),t!==void 0&&(this.memoryCache.set(e,t),this.promotionCount++))}async demoteToDisk(e){if(this.isDestroyed)return;const t=this.memoryCache.get(e);t!==void 0&&(this.diskCache.set(e,t),this.memoryCache.delete(e),this.memoryToDiskPromoter.set(e,0))}getStats(){const e=this.memoryCache.getStats(),t=this.diskCache.getStats(),i=e.hits+t.hits,s=e.misses+t.misses,n=i+s;return{memory:e,disk:t,total:{hits:i,misses:s,size:this.size(),hitRate:n>0?i/n:0,evictionCount:e.evictionCount+t.evictionCount,totalRequests:e.totalRequests+t.totalRequests,avgResponseTime:this._calculateAvgResponseTime(e,t)},promotionCount:this.promotionCount}}resetStats(){this.memoryCache.resetStats(),this.diskCache.resetStats(),this.promotionCount=0}async warmup(e){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法预热");return}console.log(`[TwoLevelCache] 开始预热 ${e.size} 条数据...`);for(const[t,i]of e.entries())await this.set(t,i);console.log("[TwoLevelCache] 预热完成")}async invalidatePattern(e){if(this.isDestroyed){console.warn("[TwoLevelCache] 缓存已销毁，无法失效");return}const t=new RegExp(e),i=this.keys();for(const s of i)t.test(String(s))&&await this.delete(s)}getMemoryHealth(){return this.memoryCache.getHealthStatus()}getDiskHealth(){return this.diskCache.getHealthStatus()}getPromotionStats(){const e=Array.from(this.memoryToDiskPromoter.entries()).filter(([,t])=>t>=this.promoteThreshold).map(([t,i])=>({key:t,accessCount:i})).sort((t,i)=>i.accessCount-t.accessCount).slice(0,10);return{totalPromotions:this.promotionCount,hotKeys:e}}destroy(){this.isDestroyed||(this.isDestroyed=!0,this.memoryCache.destroy(),this.diskCache.destroy(),this.memoryToDiskPromoter.clear())}_trackAccess(e){const t=this.memoryToDiskPromoter.get(e)||0;this.memoryToDiskPromoter.set(e,t+1)}_calculateAvgResponseTime(e,t){const i=e.totalRequests+t.totalRequests;return i===0?0:(e.avgResponseTime*e.totalRequests+t.avgResponseTime*t.totalRequests)/i}}})),v,w,ki=f((()=>{v=(function(e){return e.NETWORK="network",e.VALIDATION="validation",e.AUTHENTICATION="authentication",e.AUTHORIZATION="authorization",e.NOT_FOUND="not_found",e.SERVER="server",e.PLUGIN="plugin",e.CACHE="cache",e.UNKNOWN="unknown",e})({}),w=(function(e){return e.LOW="low",e.MEDIUM="medium",e.HIGH="high",e.CRITICAL="critical",e})({})})),_,Pi,Ti,at,Ri,_i,Ii=f((()=>{ki(),_=class extends Error{constructor(e,t,i,s=w.MEDIUM,n,a,r){super(i),this.name=this.constructor.name,this.type=e,this.severity=s,this.code=t,this.details=n,this.context={timestamp:new Date,...a},this.originalError=r,this.isOperational=!0,typeof Error.captureStackTrace=="function"&&Error.captureStackTrace(this,this.constructor)}toJSON(){return{type:this.type,code:this.code,message:this.message,severity:this.severity,details:this.details,context:this.context,originalError:this.originalError?.message,stack:this.stack}}},Pi=class extends _{constructor(e,t,i){super(v.NETWORK,"NETWORK_ERROR",e,w.HIGH,t,i)}},Ti=class extends _{constructor(e,t,i){super(v.VALIDATION,"VALIDATION_ERROR",e,w.MEDIUM,t,i)}},at=class extends _{constructor(e,t,i){super(v.AUTHENTICATION,"AUTHENTICATION_ERROR",e,w.HIGH,t,i)}},Ri=class extends _{constructor(e,t,i){super(v.NOT_FOUND,"NOT_FOUND",e,w.MEDIUM,t,i)}},_i=class extends _{constructor(e,t,i){super(v.SERVER,"SERVER_ERROR",e,w.CRITICAL,t,i)}}}));function Es(){const e=[],t=Object.create(null);let i;return t.get=(s,n)=>(i?.revoke?.(),n===ht?e:(e.push(n),i=Proxy.revocable(s,t),i.proxy)),Proxy.revocable(Object.create(null),t).proxy}function oe(e,t){const{[ht]:i}=e(Es()),s=t?.keySeparator??".",n=t?.nsSeparator??":";if(i.length>1&&n){const a=t?.ns;if((a?Array.isArray(a)?a:[a]:[]).includes(i[0]))return`${i[0]}${n}${i.slice(1).join(s)}`}return i.join(s)}var m,X,_e,xt,St,Ie,Me,Z,$e,Ct,le,Et,Oe,B,Lt,kt,Pt,Tt,Rt,_t,ye,ee,It,Mt,O,ce,Ae,Ne,ht,De,ve,He,ze,qe,Be,$t,je,be,Fe,Ot,Ue,At,Nt,Dt,Ht,we,Ve,de,zt,Ke,qt,Bt,jt,Ft,S,Ls,ks,Ps,Ts,Rs,_s,Is,Ms,$s,Os,As,Ns,Ds,Hs,zs=f((()=>{m=e=>typeof e=="string",X=()=>{let e,t;const i=new Promise((s,n)=>{e=s,t=n});return i.resolve=e,i.reject=t,i},_e=e=>e==null?"":""+e,xt=(e,t,i)=>{e.forEach(s=>{t[s]&&(i[s]=t[s])})},St=/###/g,Ie=e=>e&&e.indexOf("###")>-1?e.replace(St,"."):e,Me=e=>!e||m(e),Z=(e,t,i)=>{const s=m(t)?t.split("."):t;let n=0;for(;n<s.length-1;){if(Me(e))return{};const a=Ie(s[n]);!e[a]&&i&&(e[a]=new i),Object.prototype.hasOwnProperty.call(e,a)?e=e[a]:e={},++n}return Me(e)?{}:{obj:e,k:Ie(s[n])}},$e=(e,t,i)=>{const{obj:s,k:n}=Z(e,t,Object);if(s!==void 0||t.length===1){s[n]=i;return}let a=t[t.length-1],r=t.slice(0,t.length-1),o=Z(e,r,Object);for(;o.obj===void 0&&r.length;)a=`${r[r.length-1]}.${a}`,r=r.slice(0,r.length-1),o=Z(e,r,Object),o?.obj&&typeof o.obj[`${o.k}.${a}`]<"u"&&(o.obj=void 0);o.obj[`${o.k}.${a}`]=i},Ct=(e,t,i,s)=>{const{obj:n,k:a}=Z(e,t,Object);n[a]=n[a]||[],n[a].push(i)},le=(e,t)=>{const{obj:i,k:s}=Z(e,t);if(i&&Object.prototype.hasOwnProperty.call(i,s))return i[s]},Et=(e,t,i)=>{const s=le(e,i);return s!==void 0?s:le(t,i)},Oe=(e,t,i)=>{for(const s in t)s!=="__proto__"&&s!=="constructor"&&(s in e?m(e[s])||e[s]instanceof String||m(t[s])||t[s]instanceof String?i&&(e[s]=t[s]):Oe(e[s],t[s],i):e[s]=t[s]);return e},B=e=>e.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g,"\\$&"),Lt={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;","/":"&#x2F;"},kt=e=>m(e)?e.replace(/[&<>"'\/]/g,t=>Lt[t]):e,Pt=class{constructor(e){this.capacity=e,this.regExpMap=new Map,this.regExpQueue=[]}getRegExp(e){const t=this.regExpMap.get(e);if(t!==void 0)return t;const i=new RegExp(e);return this.regExpQueue.length===this.capacity&&this.regExpMap.delete(this.regExpQueue.shift()),this.regExpMap.set(e,i),this.regExpQueue.push(e),i}},Tt=[" ",",","?","!",";"],Rt=new Pt(20),_t=(e,t,i)=>{t=t||"",i=i||"";const s=Tt.filter(r=>t.indexOf(r)<0&&i.indexOf(r)<0);if(s.length===0)return!0;const n=Rt.getRegExp(`(${s.map(r=>r==="?"?"\\?":r).join("|")})`);let a=!n.test(e);if(!a){const r=e.indexOf(i);r>0&&!n.test(e.substring(0,r))&&(a=!0)}return a},ye=(e,t,i=".")=>{if(!e)return;if(e[t])return Object.prototype.hasOwnProperty.call(e,t)?e[t]:void 0;const s=t.split(i);let n=e;for(let a=0;a<s.length;){if(!n||typeof n!="object")return;let r,o="";for(let l=a;l<s.length;++l)if(l!==a&&(o+=i),o+=s[l],r=n[o],r!==void 0){if(["string","number","boolean"].indexOf(typeof r)>-1&&l<s.length-1)continue;a+=l-a+1;break}n=r}return n},ee=e=>e?.replace(/_/g,"-"),It={type:"logger",log(e){this.output("log",e)},warn(e){this.output("warn",e)},error(e){this.output("error",e)},output(e,t){console?.[e]?.apply?.(console,t)}},Mt=class rt{constructor(t,i={}){this.init(t,i)}init(t,i={}){this.prefix=i.prefix||"i18next:",this.logger=t||It,this.options=i,this.debug=i.debug}log(...t){return this.forward(t,"log","",!0)}warn(...t){return this.forward(t,"warn","",!0)}error(...t){return this.forward(t,"error","")}deprecate(...t){return this.forward(t,"warn","WARNING DEPRECATED: ",!0)}forward(t,i,s,n){return n&&!this.debug?null:(m(t[0])&&(t[0]=`${s}${this.prefix} ${t[0]}`),this.logger[i](t))}create(t){return new rt(this.logger,{prefix:`${this.prefix}:${t}:`,...this.options})}clone(t){return t=t||this.options,t.prefix=t.prefix||this.prefix,new rt(this.logger,t)}},O=new Mt,ce=class{constructor(){this.observers={}}on(e,t){return e.split(" ").forEach(i=>{this.observers[i]||(this.observers[i]=new Map);const s=this.observers[i].get(t)||0;this.observers[i].set(t,s+1)}),this}off(e,t){if(this.observers[e]){if(!t){delete this.observers[e];return}this.observers[e].delete(t)}}emit(e,...t){this.observers[e]&&Array.from(this.observers[e].entries()).forEach(([i,s])=>{for(let n=0;n<s;n++)i(...t)}),this.observers["*"]&&Array.from(this.observers["*"].entries()).forEach(([i,s])=>{for(let n=0;n<s;n++)i.apply(i,[e,...t])})}},Ae=class extends ce{constructor(e,t={ns:["translation"],defaultNS:"translation"}){super(),this.data=e||{},this.options=t,this.options.keySeparator===void 0&&(this.options.keySeparator="."),this.options.ignoreJSONStructure===void 0&&(this.options.ignoreJSONStructure=!0)}addNamespaces(e){this.options.ns.indexOf(e)<0&&this.options.ns.push(e)}removeNamespaces(e){const t=this.options.ns.indexOf(e);t>-1&&this.options.ns.splice(t,1)}getResource(e,t,i,s={}){const n=s.keySeparator!==void 0?s.keySeparator:this.options.keySeparator,a=s.ignoreJSONStructure!==void 0?s.ignoreJSONStructure:this.options.ignoreJSONStructure;let r;e.indexOf(".")>-1?r=e.split("."):(r=[e,t],i&&(Array.isArray(i)?r.push(...i):m(i)&&n?r.push(...i.split(n)):r.push(i)));const o=le(this.data,r);return!o&&!t&&!i&&e.indexOf(".")>-1&&(e=r[0],t=r[1],i=r.slice(2).join(".")),o||!a||!m(i)?o:ye(this.data?.[e]?.[t],i,n)}addResource(e,t,i,s,n={silent:!1}){const a=n.keySeparator!==void 0?n.keySeparator:this.options.keySeparator;let r=[e,t];i&&(r=r.concat(a?i.split(a):i)),e.indexOf(".")>-1&&(r=e.split("."),s=t,t=r[1]),this.addNamespaces(t),$e(this.data,r,s),n.silent||this.emit("added",e,t,i,s)}addResources(e,t,i,s={silent:!1}){for(const n in i)(m(i[n])||Array.isArray(i[n]))&&this.addResource(e,t,n,i[n],{silent:!0});s.silent||this.emit("added",e,t,i)}addResourceBundle(e,t,i,s,n,a={silent:!1,skipCopy:!1}){let r=[e,t];e.indexOf(".")>-1&&(r=e.split("."),s=i,i=t,t=r[1]),this.addNamespaces(t);let o=le(this.data,r)||{};a.skipCopy||(i=JSON.parse(JSON.stringify(i))),s?Oe(o,i,n):o={...o,...i},$e(this.data,r,o),a.silent||this.emit("added",e,t,i)}removeResourceBundle(e,t){this.hasResourceBundle(e,t)&&delete this.data[e][t],this.removeNamespaces(t),this.emit("removed",e,t)}hasResourceBundle(e,t){return this.getResource(e,t)!==void 0}getResourceBundle(e,t){return t||(t=this.options.defaultNS),this.getResource(e,t)}getDataByLanguage(e){return this.data[e]}hasLanguageSomeTranslations(e){const t=this.getDataByLanguage(e);return!!(t&&Object.keys(t)||[]).find(i=>t[i]&&Object.keys(t[i]).length>0)}toJSON(){return this.data}},Ne={processors:{},addPostProcessor(e){this.processors[e.name]=e},handle(e,t,i,s,n){return e.forEach(a=>{t=this.processors[a]?.process(t,i,s,n)??t}),t}},ht=Symbol("i18next/PATH_KEY"),De={},ve=e=>!m(e)&&typeof e!="boolean"&&typeof e!="number",He=class Mi extends ce{constructor(t,i={}){super(),xt(["resourceStore","languageUtils","pluralResolver","interpolator","backendConnector","i18nFormat","utils"],t,this),this.options=i,this.options.keySeparator===void 0&&(this.options.keySeparator="."),this.logger=O.create("translator")}changeLanguage(t){t&&(this.language=t)}exists(t,i={interpolation:{}}){const s={...i};if(t==null)return!1;const n=this.resolve(t,s);if(n?.res===void 0)return!1;const a=ve(n.res);return!(s.returnObjects===!1&&a)}extractFromKey(t,i){let s=i.nsSeparator!==void 0?i.nsSeparator:this.options.nsSeparator;s===void 0&&(s=":");const n=i.keySeparator!==void 0?i.keySeparator:this.options.keySeparator;let a=i.ns||this.options.defaultNS||[];const r=s&&t.indexOf(s)>-1,o=!this.options.userDefinedKeySeparator&&!i.keySeparator&&!this.options.userDefinedNsSeparator&&!i.nsSeparator&&!_t(t,s,n);if(r&&!o){const l=t.match(this.interpolator.nestingRegexp);if(l&&l.length>0)return{key:t,namespaces:m(a)?[a]:a};const c=t.split(s);(s!==n||s===n&&this.options.ns.indexOf(c[0])>-1)&&(a=c.shift()),t=c.join(n)}return{key:t,namespaces:m(a)?[a]:a}}translate(t,i,s){let n=typeof i=="object"?{...i}:i;if(typeof n!="object"&&this.options.overloadTranslationOptionHandler&&(n=this.options.overloadTranslationOptionHandler(arguments)),typeof n=="object"&&(n={...n}),n||(n={}),t==null)return"";typeof t=="function"&&(t=oe(t,{...this.options,...n})),Array.isArray(t)||(t=[String(t)]),t=t.map(E=>typeof E=="function"?oe(E,{...this.options,...n}):String(E));const a=n.returnDetails!==void 0?n.returnDetails:this.options.returnDetails,r=n.keySeparator!==void 0?n.keySeparator:this.options.keySeparator,{key:o,namespaces:l}=this.extractFromKey(t[t.length-1],n),c=l[l.length-1];let u=n.nsSeparator!==void 0?n.nsSeparator:this.options.nsSeparator;u===void 0&&(u=":");const d=n.lng||this.language,p=n.appendNamespaceToCIMode||this.options.appendNamespaceToCIMode;if(d?.toLowerCase()==="cimode")return p?a?{res:`${c}${u}${o}`,usedKey:o,exactUsedKey:o,usedLng:d,usedNS:c,usedParams:this.getUsedParamsDetails(n)}:`${c}${u}${o}`:a?{res:o,usedKey:o,exactUsedKey:o,usedLng:d,usedNS:c,usedParams:this.getUsedParamsDetails(n)}:o;const y=this.resolve(t,n);let g=y?.res;const b=y?.usedKey||o,k=y?.exactUsedKey||o,D=["[object Number]","[object Function]","[object RegExp]"],P=n.joinArrays!==void 0?n.joinArrays:this.options.joinArrays,F=!this.i18nFormat||this.i18nFormat.handleAsObject,M=n.count!==void 0&&!m(n.count),z=Mi.hasDefaultValue(n),Y=M?this.pluralResolver.getSuffix(d,n.count,n):"",Q=n.ordinal&&M?this.pluralResolver.getSuffix(d,n.count,{ordinal:!1}):"",mt=M&&!n.ordinal&&n.count===0,q=mt&&n[`defaultValue${this.options.pluralSeparator}zero`]||n[`defaultValue${Y}`]||n[`defaultValue${Q}`]||n.defaultValue;let A=g;F&&!g&&z&&(A=q);const rs=ve(A),os=Object.prototype.toString.apply(A);if(F&&A&&rs&&D.indexOf(os)<0&&!(m(P)&&Array.isArray(A))){if(!n.returnObjects&&!this.options.returnObjects){this.options.returnedObjectHandler||this.logger.warn("accessing an object - but returnObjects options is not enabled!");const E=this.options.returnedObjectHandler?this.options.returnedObjectHandler(b,A,{...n,ns:l}):`key '${o} (${this.language})' returned an object instead of string.`;return a?(y.res=E,y.usedParams=this.getUsedParamsDetails(n),y):E}if(r){const E=Array.isArray(A),$=E?[]:{},Ee=E?k:b;for(const L in A)if(Object.prototype.hasOwnProperty.call(A,L)){const H=`${Ee}${r}${L}`;z&&!g?$[L]=this.translate(H,{...n,defaultValue:ve(q)?q[L]:void 0,joinArrays:!1,ns:l}):$[L]=this.translate(H,{...n,joinArrays:!1,ns:l}),$[L]===H&&($[L]=A[L])}g=$}}else if(F&&m(P)&&Array.isArray(g))g=g.join(P),g&&(g=this.extendTranslation(g,t,n,s));else{let E=!1,$=!1;!this.isValidLookup(g)&&z&&(E=!0,g=q),this.isValidLookup(g)||($=!0,g=o);const Ee=(n.missingKeyNoValueFallbackToKey||this.options.missingKeyNoValueFallbackToKey)&&$?void 0:g,L=z&&q!==g&&this.options.updateMissing;if($||E||L){if(this.logger.log(L?"updateKey":"missingKey",d,c,o,L?q:g),r){const T=this.resolve(o,{...n,keySeparator:!1});T&&T.res&&this.logger.warn("Seems the loaded translations were in flat JSON format instead of nested. Either set keySeparator: false on init or make sure your translations are published in nested format.")}let H=[];const fe=this.languageUtils.getFallbackCodes(this.options.fallbackLng,n.lng||this.language);if(this.options.saveMissingTo==="fallback"&&fe&&fe[0])for(let T=0;T<fe.length;T++)H.push(fe[T]);else this.options.saveMissingTo==="all"?H=this.languageUtils.toResolveHierarchy(n.lng||this.language):H.push(n.lng||this.language);const gt=(T,U,ae)=>{const ft=z&&ae!==g?ae:Ee;this.options.missingKeyHandler?this.options.missingKeyHandler(T,c,U,ft,L,n):this.backendConnector?.saveMissing&&this.backendConnector.saveMissing(T,c,U,ft,L,n),this.emit("missingKey",T,c,U,g)};this.options.saveMissing&&(this.options.saveMissingPlurals&&M?H.forEach(T=>{const U=this.pluralResolver.getSuffixes(T,n);mt&&n[`defaultValue${this.options.pluralSeparator}zero`]&&U.indexOf(`${this.options.pluralSeparator}zero`)<0&&U.push(`${this.options.pluralSeparator}zero`),U.forEach(ae=>{gt([T],o+ae,n[`defaultValue${ae}`]||q)})}):gt(H,o,q))}g=this.extendTranslation(g,t,n,y,s),$&&g===o&&this.options.appendNamespaceToMissingKey&&(g=`${c}${u}${o}`),($||E)&&this.options.parseMissingKeyHandler&&(g=this.options.parseMissingKeyHandler(this.options.appendNamespaceToMissingKey?`${c}${u}${o}`:o,E?g:void 0,n))}return a?(y.res=g,y.usedParams=this.getUsedParamsDetails(n),y):g}extendTranslation(t,i,s,n,a){if(this.i18nFormat?.parse)t=this.i18nFormat.parse(t,{...this.options.interpolation.defaultVariables,...s},s.lng||this.language||n.usedLng,n.usedNS,n.usedKey,{resolved:n});else if(!s.skipInterpolation){s.interpolation&&this.interpolator.init({...s,interpolation:{...this.options.interpolation,...s.interpolation}});const l=m(t)&&(s?.interpolation?.skipOnVariables!==void 0?s.interpolation.skipOnVariables:this.options.interpolation.skipOnVariables);let c;if(l){const d=t.match(this.interpolator.nestingRegexp);c=d&&d.length}let u=s.replace&&!m(s.replace)?s.replace:s;if(this.options.interpolation.defaultVariables&&(u={...this.options.interpolation.defaultVariables,...u}),t=this.interpolator.interpolate(t,u,s.lng||this.language||n.usedLng,s),l){const d=t.match(this.interpolator.nestingRegexp),p=d&&d.length;c<p&&(s.nest=!1)}!s.lng&&n&&n.res&&(s.lng=this.language||n.usedLng),s.nest!==!1&&(t=this.interpolator.nest(t,(...d)=>a?.[0]===d[0]&&!s.context?(this.logger.warn(`It seems you are nesting recursively key: ${d[0]} in key: ${i[0]}`),null):this.translate(...d,i),s)),s.interpolation&&this.interpolator.reset()}const r=s.postProcess||this.options.postProcess,o=m(r)?[r]:r;return t!=null&&o?.length&&s.applyPostProcessor!==!1&&(t=Ne.handle(o,t,i,this.options&&this.options.postProcessPassResolved?{i18nResolved:{...n,usedParams:this.getUsedParamsDetails(s)},...s}:s,this)),t}resolve(t,i={}){let s,n,a,r,o;return m(t)&&(t=[t]),Array.isArray(t)&&(t=t.map(l=>typeof l=="function"?oe(l,{...this.options,...i}):l)),t.forEach(l=>{if(this.isValidLookup(s))return;const c=this.extractFromKey(l,i),u=c.key;n=u;let d=c.namespaces;this.options.fallbackNS&&(d=d.concat(this.options.fallbackNS));const p=i.count!==void 0&&!m(i.count),y=p&&!i.ordinal&&i.count===0,g=i.context!==void 0&&(m(i.context)||typeof i.context=="number")&&i.context!=="",b=i.lngs?i.lngs:this.languageUtils.toResolveHierarchy(i.lng||this.language,i.fallbackLng);d.forEach(k=>{this.isValidLookup(s)||(o=k,!De[`${b[0]}-${k}`]&&this.utils?.hasLoadedNamespace&&!this.utils?.hasLoadedNamespace(o)&&(De[`${b[0]}-${k}`]=!0,this.logger.warn(`key "${n}" for languages "${b.join(", ")}" won't get resolved as namespace "${o}" was not yet loaded`,"This means something IS WRONG in your setup. You access the t function before i18next.init / i18next.loadNamespace / i18next.changeLanguage was done. Wait for the callback or Promise to resolve before accessing it!!!")),b.forEach(D=>{if(this.isValidLookup(s))return;r=D;const P=[u];if(this.i18nFormat?.addLookupKeys)this.i18nFormat.addLookupKeys(P,u,D,k,i);else{let M;p&&(M=this.pluralResolver.getSuffix(D,i.count,i));const z=`${this.options.pluralSeparator}zero`,Y=`${this.options.pluralSeparator}ordinal${this.options.pluralSeparator}`;if(p&&(i.ordinal&&M.indexOf(Y)===0&&P.push(u+M.replace(Y,this.options.pluralSeparator)),P.push(u+M),y&&P.push(u+z)),g){const Q=`${u}${this.options.contextSeparator||"_"}${i.context}`;P.push(Q),p&&(i.ordinal&&M.indexOf(Y)===0&&P.push(Q+M.replace(Y,this.options.pluralSeparator)),P.push(Q+M),y&&P.push(Q+z))}}let F;for(;F=P.pop();)this.isValidLookup(s)||(a=F,s=this.getResource(D,k,F,i))}))})}),{res:s,usedKey:n,exactUsedKey:a,usedLng:r,usedNS:o}}isValidLookup(t){return t!==void 0&&!(!this.options.returnNull&&t===null)&&!(!this.options.returnEmptyString&&t==="")}getResource(t,i,s,n={}){return this.i18nFormat?.getResource?this.i18nFormat.getResource(t,i,s,n):this.resourceStore.getResource(t,i,s,n)}getUsedParamsDetails(t={}){const i=["defaultValue","ordinal","context","replace","lng","lngs","fallbackLng","ns","keySeparator","nsSeparator","returnObjects","returnDetails","joinArrays","postProcess","interpolation"],s=t.replace&&!m(t.replace);let n=s?t.replace:t;if(s&&typeof t.count<"u"&&(n.count=t.count),this.options.interpolation.defaultVariables&&(n={...this.options.interpolation.defaultVariables,...n}),!s){n={...n};for(const a of i)delete n[a]}return n}static hasDefaultValue(t){const i="defaultValue";for(const s in t)if(Object.prototype.hasOwnProperty.call(t,s)&&i===s.substring(0,12)&&t[s]!==void 0)return!0;return!1}},ze=class{constructor(e){this.options=e,this.supportedLngs=this.options.supportedLngs||!1,this.logger=O.create("languageUtils")}getScriptPartFromCode(e){if(e=ee(e),!e||e.indexOf("-")<0)return null;const t=e.split("-");return t.length===2||(t.pop(),t[t.length-1].toLowerCase()==="x")?null:this.formatLanguageCode(t.join("-"))}getLanguagePartFromCode(e){if(e=ee(e),!e||e.indexOf("-")<0)return e;const t=e.split("-");return this.formatLanguageCode(t[0])}formatLanguageCode(e){if(m(e)&&e.indexOf("-")>-1){let t;try{t=Intl.getCanonicalLocales(e)[0]}catch{}return t&&this.options.lowerCaseLng&&(t=t.toLowerCase()),t||(this.options.lowerCaseLng?e.toLowerCase():e)}return this.options.cleanCode||this.options.lowerCaseLng?e.toLowerCase():e}isSupportedCode(e){return(this.options.load==="languageOnly"||this.options.nonExplicitSupportedLngs)&&(e=this.getLanguagePartFromCode(e)),!this.supportedLngs||!this.supportedLngs.length||this.supportedLngs.indexOf(e)>-1}getBestMatchFromCodes(e){if(!e)return null;let t;return e.forEach(i=>{if(t)return;const s=this.formatLanguageCode(i);(!this.options.supportedLngs||this.isSupportedCode(s))&&(t=s)}),!t&&this.options.supportedLngs&&e.forEach(i=>{if(t)return;const s=this.getScriptPartFromCode(i);if(this.isSupportedCode(s))return t=s;const n=this.getLanguagePartFromCode(i);if(this.isSupportedCode(n))return t=n;t=this.options.supportedLngs.find(a=>{if(a===n)return a;if(!(a.indexOf("-")<0&&n.indexOf("-")<0)&&(a.indexOf("-")>0&&n.indexOf("-")<0&&a.substring(0,a.indexOf("-"))===n||a.indexOf(n)===0&&n.length>1))return a})}),t||(t=this.getFallbackCodes(this.options.fallbackLng)[0]),t}getFallbackCodes(e,t){if(!e)return[];if(typeof e=="function"&&(e=e(t)),m(e)&&(e=[e]),Array.isArray(e))return e;if(!t)return e.default||[];let i=e[t];return i||(i=e[this.getScriptPartFromCode(t)]),i||(i=e[this.formatLanguageCode(t)]),i||(i=e[this.getLanguagePartFromCode(t)]),i||(i=e.default),i||[]}toResolveHierarchy(e,t){const i=this.getFallbackCodes((t===!1?[]:t)||this.options.fallbackLng||[],e),s=[],n=a=>{a&&(this.isSupportedCode(a)?s.push(a):this.logger.warn(`rejecting language code not found in supportedLngs: ${a}`))};return m(e)&&(e.indexOf("-")>-1||e.indexOf("_")>-1)?(this.options.load!=="languageOnly"&&n(this.formatLanguageCode(e)),this.options.load!=="languageOnly"&&this.options.load!=="currentOnly"&&n(this.getScriptPartFromCode(e)),this.options.load!=="currentOnly"&&n(this.getLanguagePartFromCode(e))):m(e)&&n(this.formatLanguageCode(e)),i.forEach(a=>{s.indexOf(a)<0&&n(this.formatLanguageCode(a))}),s}},qe={zero:0,one:1,two:2,few:3,many:4,other:5},Be={select:e=>e===1?"one":"other",resolvedOptions:()=>({pluralCategories:["one","other"]})},$t=class{constructor(e,t={}){this.languageUtils=e,this.options=t,this.logger=O.create("pluralResolver"),this.pluralRulesCache={}}clearCache(){this.pluralRulesCache={}}getRule(e,t={}){const i=ee(e==="dev"?"en":e),s=t.ordinal?"ordinal":"cardinal",n=JSON.stringify({cleanedCode:i,type:s});if(n in this.pluralRulesCache)return this.pluralRulesCache[n];let a;try{a=new Intl.PluralRules(i,{type:s})}catch{if(typeof Intl>"u")return this.logger.error("No Intl support, please use an Intl polyfill!"),Be;if(!e.match(/-|_/))return Be;const o=this.languageUtils.getLanguagePartFromCode(e);a=this.getRule(o,t)}return this.pluralRulesCache[n]=a,a}needsPlural(e,t={}){let i=this.getRule(e,t);return i||(i=this.getRule("dev",t)),i?.resolvedOptions().pluralCategories.length>1}getPluralFormsOfKey(e,t,i={}){return this.getSuffixes(e,i).map(s=>`${t}${s}`)}getSuffixes(e,t={}){let i=this.getRule(e,t);return i||(i=this.getRule("dev",t)),i?i.resolvedOptions().pluralCategories.sort((s,n)=>qe[s]-qe[n]).map(s=>`${this.options.prepend}${t.ordinal?`ordinal${this.options.prepend}`:""}${s}`):[]}getSuffix(e,t,i={}){const s=this.getRule(e,i);return s?`${this.options.prepend}${i.ordinal?`ordinal${this.options.prepend}`:""}${s.select(t)}`:(this.logger.warn(`no plural rule found for: ${e}`),this.getSuffix("dev",t,i))}},je=(e,t,i,s=".",n=!0)=>{let a=Et(e,t,i);return!a&&n&&m(i)&&(a=ye(e,i,s),a===void 0&&(a=ye(t,i,s))),a},be=e=>e.replace(/\$/g,"$$$$"),Fe=class{constructor(e={}){this.logger=O.create("interpolator"),this.options=e,this.format=e?.interpolation?.format||(t=>t),this.init(e)}init(e={}){e.interpolation||(e.interpolation={escapeValue:!0});const{escape:t,escapeValue:i,useRawValueToEscape:s,prefix:n,prefixEscaped:a,suffix:r,suffixEscaped:o,formatSeparator:l,unescapeSuffix:c,unescapePrefix:u,nestingPrefix:d,nestingPrefixEscaped:p,nestingSuffix:y,nestingSuffixEscaped:g,nestingOptionsSeparator:b,maxReplaces:k,alwaysFormat:D}=e.interpolation;this.escape=t!==void 0?t:kt,this.escapeValue=i!==void 0?i:!0,this.useRawValueToEscape=s!==void 0?s:!1,this.prefix=n?B(n):a||"{{",this.suffix=r?B(r):o||"}}",this.formatSeparator=l||",",this.unescapePrefix=c?"":u||"-",this.unescapeSuffix=this.unescapePrefix?"":c||"",this.nestingPrefix=d?B(d):p||B("$t("),this.nestingSuffix=y?B(y):g||B(")"),this.nestingOptionsSeparator=b||",",this.maxReplaces=k||1e3,this.alwaysFormat=D!==void 0?D:!1,this.resetRegExp()}reset(){this.options&&this.init(this.options)}resetRegExp(){const e=(t,i)=>t?.source===i?(t.lastIndex=0,t):new RegExp(i,"g");this.regexp=e(this.regexp,`${this.prefix}(.+?)${this.suffix}`),this.regexpUnescape=e(this.regexpUnescape,`${this.prefix}${this.unescapePrefix}(.+?)${this.unescapeSuffix}${this.suffix}`),this.nestingRegexp=e(this.nestingRegexp,`${this.nestingPrefix}((?:[^()"']+|"[^"]*"|'[^']*'|\\((?:[^()]|"[^"]*"|'[^']*')*\\))*?)${this.nestingSuffix}`)}interpolate(e,t,i,s){let n,a,r;const o=this.options&&this.options.interpolation&&this.options.interpolation.defaultVariables||{},l=d=>{if(d.indexOf(this.formatSeparator)<0){const b=je(t,o,d,this.options.keySeparator,this.options.ignoreJSONStructure);return this.alwaysFormat?this.format(b,void 0,i,{...s,...t,interpolationkey:d}):b}const p=d.split(this.formatSeparator),y=p.shift().trim(),g=p.join(this.formatSeparator).trim();return this.format(je(t,o,y,this.options.keySeparator,this.options.ignoreJSONStructure),g,i,{...s,...t,interpolationkey:y})};this.resetRegExp();const c=s?.missingInterpolationHandler||this.options.missingInterpolationHandler,u=s?.interpolation?.skipOnVariables!==void 0?s.interpolation.skipOnVariables:this.options.interpolation.skipOnVariables;return[{regex:this.regexpUnescape,safeValue:d=>be(d)},{regex:this.regexp,safeValue:d=>this.escapeValue?be(this.escape(d)):be(d)}].forEach(d=>{for(r=0;n=d.regex.exec(e);){const p=n[1].trim();if(a=l(p),a===void 0)if(typeof c=="function"){const g=c(e,n,s);a=m(g)?g:""}else if(s&&Object.prototype.hasOwnProperty.call(s,p))a="";else if(u){a=n[0];continue}else this.logger.warn(`missed to pass in variable ${p} for interpolating ${e}`),a="";else!m(a)&&!this.useRawValueToEscape&&(a=_e(a));const y=d.safeValue(a);if(e=e.replace(n[0],y),u?(d.regex.lastIndex+=a.length,d.regex.lastIndex-=n[0].length):d.regex.lastIndex=0,r++,r>=this.maxReplaces)break}}),e}nest(e,t,i={}){let s,n,a;const r=(o,l)=>{const c=this.nestingOptionsSeparator;if(o.indexOf(c)<0)return o;const u=o.split(new RegExp(`${B(c)}[ ]*{`));let d=`{${u[1]}`;o=u[0],d=this.interpolate(d,a);const p=d.match(/'/g),y=d.match(/"/g);((p?.length??0)%2===0&&!y||(y?.length??0)%2!==0)&&(d=d.replace(/'/g,'"'));try{a=JSON.parse(d),l&&(a={...l,...a})}catch(g){return this.logger.warn(`failed parsing options string in nesting for key ${o}`,g),`${o}${c}${d}`}return a.defaultValue&&a.defaultValue.indexOf(this.prefix)>-1&&delete a.defaultValue,o};for(;s=this.nestingRegexp.exec(e);){let o=[];a={...i},a=a.replace&&!m(a.replace)?a.replace:a,a.applyPostProcessor=!1,delete a.defaultValue;const l=/{.*}/.test(s[1])?s[1].lastIndexOf("}")+1:s[1].indexOf(this.formatSeparator);if(l!==-1&&(o=s[1].slice(l).split(this.formatSeparator).map(c=>c.trim()).filter(Boolean),s[1]=s[1].slice(0,l)),n=t(r.call(this,s[1].trim(),a),a),n&&s[0]===e&&!m(n))return n;m(n)||(n=_e(n)),n||(this.logger.warn(`missed to resolve ${s[1]} for nesting ${e}`),n=""),o.length&&(n=o.reduce((c,u)=>this.format(c,u,i.lng,{...i,interpolationkey:s[1].trim()}),n.trim())),e=e.replace(s[0],n),this.regexp.lastIndex=0}return e}},Ot=e=>{let t=e.toLowerCase().trim();const i={};if(e.indexOf("(")>-1){const s=e.split("(");t=s[0].toLowerCase().trim();const n=s[1].substring(0,s[1].length-1);t==="currency"&&n.indexOf(":")<0?i.currency||(i.currency=n.trim()):t==="relativetime"&&n.indexOf(":")<0?i.range||(i.range=n.trim()):n.split(";").forEach(a=>{if(a){const[r,...o]=a.split(":"),l=o.join(":").trim().replace(/^'+|'+$/g,""),c=r.trim();i[c]||(i[c]=l),l==="false"&&(i[c]=!1),l==="true"&&(i[c]=!0),isNaN(l)||(i[c]=parseInt(l,10))}})}return{formatName:t,formatOptions:i}},Ue=e=>{const t={};return(i,s,n)=>{let a=n;n&&n.interpolationkey&&n.formatParams&&n.formatParams[n.interpolationkey]&&n[n.interpolationkey]&&(a={...a,[n.interpolationkey]:void 0});const r=s+JSON.stringify(a);let o=t[r];return o||(o=e(ee(s),n),t[r]=o),o(i)}},At=e=>(t,i,s)=>e(ee(i),s)(t),Nt=class{constructor(e={}){this.logger=O.create("formatter"),this.options=e,this.init(e)}init(e,t={interpolation:{}}){this.formatSeparator=t.interpolation.formatSeparator||",";const i=t.cacheInBuiltFormats?Ue:At;this.formats={number:i((s,n)=>{const a=new Intl.NumberFormat(s,{...n});return r=>a.format(r)}),currency:i((s,n)=>{const a=new Intl.NumberFormat(s,{...n,style:"currency"});return r=>a.format(r)}),datetime:i((s,n)=>{const a=new Intl.DateTimeFormat(s,{...n});return r=>a.format(r)}),relativetime:i((s,n)=>{const a=new Intl.RelativeTimeFormat(s,{...n});return r=>a.format(r,n.range||"day")}),list:i((s,n)=>{const a=new Intl.ListFormat(s,{...n});return r=>a.format(r)})}}add(e,t){this.formats[e.toLowerCase().trim()]=t}addCached(e,t){this.formats[e.toLowerCase().trim()]=Ue(t)}format(e,t,i,s={}){const n=t.split(this.formatSeparator);if(n.length>1&&n[0].indexOf("(")>1&&n[0].indexOf(")")<0&&n.find(a=>a.indexOf(")")>-1)){const a=n.findIndex(r=>r.indexOf(")")>-1);n[0]=[n[0],...n.splice(1,a)].join(this.formatSeparator)}return n.reduce((a,r)=>{const{formatName:o,formatOptions:l}=Ot(r);if(this.formats[o]){let c=a;try{const u=s?.formatParams?.[s.interpolationkey]||{},d=u.locale||u.lng||s.locale||s.lng||i;c=this.formats[o](a,d,{...l,...s,...u})}catch(u){this.logger.warn(u)}return c}else this.logger.warn(`there was no format function for ${o}`);return a},e)}},Dt=(e,t)=>{e.pending[t]!==void 0&&(delete e.pending[t],e.pendingCount--)},Ht=class extends ce{constructor(e,t,i,s={}){super(),this.backend=e,this.store=t,this.services=i,this.languageUtils=i.languageUtils,this.options=s,this.logger=O.create("backendConnector"),this.waitingReads=[],this.maxParallelReads=s.maxParallelReads||10,this.readingCalls=0,this.maxRetries=s.maxRetries>=0?s.maxRetries:5,this.retryTimeout=s.retryTimeout>=1?s.retryTimeout:350,this.state={},this.queue=[],this.backend?.init?.(i,s.backend,s)}queueLoad(e,t,i,s){const n={},a={},r={},o={};return e.forEach(l=>{let c=!0;t.forEach(u=>{const d=`${l}|${u}`;!i.reload&&this.store.hasResourceBundle(l,u)?this.state[d]=2:this.state[d]<0||(this.state[d]===1?a[d]===void 0&&(a[d]=!0):(this.state[d]=1,c=!1,a[d]===void 0&&(a[d]=!0),n[d]===void 0&&(n[d]=!0),o[u]===void 0&&(o[u]=!0)))}),c||(r[l]=!0)}),(Object.keys(n).length||Object.keys(a).length)&&this.queue.push({pending:a,pendingCount:Object.keys(a).length,loaded:{},errors:[],callback:s}),{toLoad:Object.keys(n),pending:Object.keys(a),toLoadLanguages:Object.keys(r),toLoadNamespaces:Object.keys(o)}}loaded(e,t,i){const s=e.split("|"),n=s[0],a=s[1];t&&this.emit("failedLoading",n,a,t),!t&&i&&this.store.addResourceBundle(n,a,i,void 0,void 0,{skipCopy:!0}),this.state[e]=t?-1:2,t&&i&&(this.state[e]=0);const r={};this.queue.forEach(o=>{Ct(o.loaded,[n],a),Dt(o,e),t&&o.errors.push(t),o.pendingCount===0&&!o.done&&(Object.keys(o.loaded).forEach(l=>{r[l]||(r[l]={});const c=o.loaded[l];c.length&&c.forEach(u=>{r[l][u]===void 0&&(r[l][u]=!0)})}),o.done=!0,o.errors.length?o.callback(o.errors):o.callback())}),this.emit("loaded",r),this.queue=this.queue.filter(o=>!o.done)}read(e,t,i,s=0,n=this.retryTimeout,a){if(!e.length)return a(null,{});if(this.readingCalls>=this.maxParallelReads){this.waitingReads.push({lng:e,ns:t,fcName:i,tried:s,wait:n,callback:a});return}this.readingCalls++;const r=(l,c)=>{if(this.readingCalls--,this.waitingReads.length>0){const u=this.waitingReads.shift();this.read(u.lng,u.ns,u.fcName,u.tried,u.wait,u.callback)}if(l&&c&&s<this.maxRetries){setTimeout(()=>{this.read.call(this,e,t,i,s+1,n*2,a)},n);return}a(l,c)},o=this.backend[i].bind(this.backend);if(o.length===2){try{const l=o(e,t);l&&typeof l.then=="function"?l.then(c=>r(null,c)).catch(r):r(null,l)}catch(l){r(l)}return}return o(e,t,r)}prepareLoading(e,t,i={},s){if(!this.backend)return this.logger.warn("No backend was added via i18next.use. Will not load resources."),s&&s();m(e)&&(e=this.languageUtils.toResolveHierarchy(e)),m(t)&&(t=[t]);const n=this.queueLoad(e,t,i,s);if(!n.toLoad.length)return n.pending.length||s(),null;n.toLoad.forEach(a=>{this.loadOne(a)})}load(e,t,i){this.prepareLoading(e,t,{},i)}reload(e,t,i){this.prepareLoading(e,t,{reload:!0},i)}loadOne(e,t=""){const i=e.split("|"),s=i[0],n=i[1];this.read(s,n,"read",void 0,void 0,(a,r)=>{a&&this.logger.warn(`${t}loading namespace ${n} for language ${s} failed`,a),!a&&r&&this.logger.log(`${t}loaded namespace ${n} for language ${s}`,r),this.loaded(e,a,r)})}saveMissing(e,t,i,s,n,a={},r=()=>{}){if(this.services?.utils?.hasLoadedNamespace&&!this.services?.utils?.hasLoadedNamespace(t)){this.logger.warn(`did not save key "${i}" as the namespace "${t}" was not yet loaded`,"This means something IS WRONG in your setup. You access the t function before i18next.init / i18next.loadNamespace / i18next.changeLanguage was done. Wait for the callback or Promise to resolve before accessing it!!!");return}if(!(i==null||i==="")){if(this.backend?.create){const o={...a,isUpdate:n},l=this.backend.create.bind(this.backend);if(l.length<6)try{let c;l.length===5?c=l(e,t,i,s,o):c=l(e,t,i,s),c&&typeof c.then=="function"?c.then(u=>r(null,u)).catch(r):r(null,c)}catch(c){r(c)}else l(e,t,i,s,r,o)}!e||!e[0]||this.store.addResource(e[0],t,i,s)}}},we=()=>({debug:!1,initAsync:!0,ns:["translation"],defaultNS:["translation"],fallbackLng:["dev"],fallbackNS:!1,supportedLngs:!1,nonExplicitSupportedLngs:!1,load:"all",preload:!1,simplifyPluralSuffix:!0,keySeparator:".",nsSeparator:":",pluralSeparator:"_",contextSeparator:"_",partialBundledLanguages:!1,saveMissing:!1,updateMissing:!1,saveMissingTo:"fallback",saveMissingPlurals:!0,missingKeyHandler:!1,missingInterpolationHandler:!1,postProcess:!1,postProcessPassResolved:!1,returnNull:!1,returnEmptyString:!0,returnObjects:!1,joinArrays:!1,returnedObjectHandler:!1,parseMissingKeyHandler:!1,appendNamespaceToMissingKey:!1,appendNamespaceToCIMode:!1,overloadTranslationOptionHandler:e=>{let t={};if(typeof e[1]=="object"&&(t=e[1]),m(e[1])&&(t.defaultValue=e[1]),m(e[2])&&(t.tDescription=e[2]),typeof e[2]=="object"||typeof e[3]=="object"){const i=e[3]||e[2];Object.keys(i).forEach(s=>{t[s]=i[s]})}return t},interpolation:{escapeValue:!0,format:e=>e,prefix:"{{",suffix:"}}",formatSeparator:",",unescapePrefix:"-",nestingPrefix:"$t(",nestingSuffix:")",nestingOptionsSeparator:",",maxReplaces:1e3,skipOnVariables:!0},cacheInBuiltFormats:!0}),Ve=e=>(m(e.ns)&&(e.ns=[e.ns]),m(e.fallbackLng)&&(e.fallbackLng=[e.fallbackLng]),m(e.fallbackNS)&&(e.fallbackNS=[e.fallbackNS]),e.supportedLngs?.indexOf?.("cimode")<0&&(e.supportedLngs=e.supportedLngs.concat(["cimode"])),typeof e.initImmediate=="boolean"&&(e.initAsync=e.initImmediate),e),de=()=>{},zt=e=>{Object.getOwnPropertyNames(Object.getPrototypeOf(e)).forEach(t=>{typeof e[t]=="function"&&(e[t]=e[t].bind(e))})},Ke="__i18next_supportNoticeShown",qt=()=>typeof globalThis<"u"&&!!globalThis[Ke],Bt=()=>{typeof globalThis<"u"&&(globalThis[Ke]=!0)},jt=e=>!!(e?.modules?.backend?.name?.indexOf("Locize")>0||e?.modules?.backend?.constructor?.name?.indexOf("Locize")>0||e?.options?.backend?.backends&&e.options.backend.backends.some(t=>t?.name?.indexOf("Locize")>0||t?.constructor?.name?.indexOf("Locize")>0)||e?.options?.backend?.projectId||e?.options?.backend?.backendOptions&&e.options.backend.backendOptions.some(t=>t?.projectId)),Ft=class xe extends ce{constructor(t={},i){if(super(),this.options=Ve(t),this.services={},this.logger=O,this.modules={external:[]},zt(this),i&&!this.isInitialized&&!t.isClone){if(!this.options.initAsync)return this.init(t,i),this;setTimeout(()=>{this.init(t,i)},0)}}init(t={},i){this.isInitializing=!0,typeof t=="function"&&(i=t,t={}),t.defaultNS==null&&t.ns&&(m(t.ns)?t.defaultNS=t.ns:t.ns.indexOf("translation")<0&&(t.defaultNS=t.ns[0]));const s=we();this.options={...s,...this.options,...Ve(t)},this.options.interpolation={...s.interpolation,...this.options.interpolation},t.keySeparator!==void 0&&(this.options.userDefinedKeySeparator=t.keySeparator),t.nsSeparator!==void 0&&(this.options.userDefinedNsSeparator=t.nsSeparator),typeof this.options.overloadTranslationOptionHandler!="function"&&(this.options.overloadTranslationOptionHandler=s.overloadTranslationOptionHandler),this.options.showSupportNotice!==!1&&!jt(this)&&!qt()&&(typeof console<"u"&&typeof console.info<"u"&&console.info("🌐 i18next is made possible by our own product, Locize — consider powering your project with managed localization (AI, CDN, integrations): https://locize.com 💙"),Bt());const n=o=>o?typeof o=="function"?new o:o:null;if(!this.options.isClone){this.modules.logger?O.init(n(this.modules.logger),this.options):O.init(null,this.options);let o;this.modules.formatter?o=this.modules.formatter:o=Nt;const l=new ze(this.options);this.store=new Ae(this.options.resources,this.options);const c=this.services;c.logger=O,c.resourceStore=this.store,c.languageUtils=l,c.pluralResolver=new $t(l,{prepend:this.options.pluralSeparator,simplifyPluralSuffix:this.options.simplifyPluralSuffix}),this.options.interpolation.format&&this.options.interpolation.format!==s.interpolation.format&&this.logger.deprecate("init: you are still using the legacy format function, please use the new approach: https://www.i18next.com/translation-function/formatting"),o&&(!this.options.interpolation.format||this.options.interpolation.format===s.interpolation.format)&&(c.formatter=n(o),c.formatter.init&&c.formatter.init(c,this.options),this.options.interpolation.format=c.formatter.format.bind(c.formatter)),c.interpolator=new Fe(this.options),c.utils={hasLoadedNamespace:this.hasLoadedNamespace.bind(this)},c.backendConnector=new Ht(n(this.modules.backend),c.resourceStore,c,this.options),c.backendConnector.on("*",(u,...d)=>{this.emit(u,...d)}),this.modules.languageDetector&&(c.languageDetector=n(this.modules.languageDetector),c.languageDetector.init&&c.languageDetector.init(c,this.options.detection,this.options)),this.modules.i18nFormat&&(c.i18nFormat=n(this.modules.i18nFormat),c.i18nFormat.init&&c.i18nFormat.init(this)),this.translator=new He(this.services,this.options),this.translator.on("*",(u,...d)=>{this.emit(u,...d)}),this.modules.external.forEach(u=>{u.init&&u.init(this)})}if(this.format=this.options.interpolation.format,i||(i=de),this.options.fallbackLng&&!this.services.languageDetector&&!this.options.lng){const o=this.services.languageUtils.getFallbackCodes(this.options.fallbackLng);o.length>0&&o[0]!=="dev"&&(this.options.lng=o[0])}!this.services.languageDetector&&!this.options.lng&&this.logger.warn("init: no languageDetector is used and no lng is defined"),["getResource","hasResourceBundle","getResourceBundle","getDataByLanguage"].forEach(o=>{this[o]=(...l)=>this.store[o](...l)}),["addResource","addResources","addResourceBundle","removeResourceBundle"].forEach(o=>{this[o]=(...l)=>(this.store[o](...l),this)});const a=X(),r=()=>{const o=(l,c)=>{this.isInitializing=!1,this.isInitialized&&!this.initializedStoreOnce&&this.logger.warn("init: i18next is already initialized. You should call init just once!"),this.isInitialized=!0,this.options.isClone||this.logger.log("initialized",this.options),this.emit("initialized",this.options),a.resolve(c),i(l,c)};if(this.languages&&!this.isInitialized)return o(null,this.t.bind(this));this.changeLanguage(this.options.lng,o)};return this.options.resources||!this.options.initAsync?r():setTimeout(r,0),a}loadResources(t,i=de){let s=i;const n=m(t)?t:this.language;if(typeof t=="function"&&(s=t),!this.options.resources||this.options.partialBundledLanguages){if(n?.toLowerCase()==="cimode"&&(!this.options.preload||this.options.preload.length===0))return s();const a=[],r=o=>{o&&o!=="cimode"&&this.services.languageUtils.toResolveHierarchy(o).forEach(l=>{l!=="cimode"&&a.indexOf(l)<0&&a.push(l)})};n?r(n):this.services.languageUtils.getFallbackCodes(this.options.fallbackLng).forEach(o=>r(o)),this.options.preload?.forEach?.(o=>r(o)),this.services.backendConnector.load(a,this.options.ns,o=>{!o&&!this.resolvedLanguage&&this.language&&this.setResolvedLanguage(this.language),s(o)})}else s(null)}reloadResources(t,i,s){const n=X();return typeof t=="function"&&(s=t,t=void 0),typeof i=="function"&&(s=i,i=void 0),t||(t=this.languages),i||(i=this.options.ns),s||(s=de),this.services.backendConnector.reload(t,i,a=>{n.resolve(),s(a)}),n}use(t){if(!t)throw new Error("You are passing an undefined module! Please check the object you are passing to i18next.use()");if(!t.type)throw new Error("You are passing a wrong module! Please check the object you are passing to i18next.use()");return t.type==="backend"&&(this.modules.backend=t),(t.type==="logger"||t.log&&t.warn&&t.error)&&(this.modules.logger=t),t.type==="languageDetector"&&(this.modules.languageDetector=t),t.type==="i18nFormat"&&(this.modules.i18nFormat=t),t.type==="postProcessor"&&Ne.addPostProcessor(t),t.type==="formatter"&&(this.modules.formatter=t),t.type==="3rdParty"&&this.modules.external.push(t),this}setResolvedLanguage(t){if(!(!t||!this.languages)&&!(["cimode","dev"].indexOf(t)>-1)){for(let i=0;i<this.languages.length;i++){const s=this.languages[i];if(!(["cimode","dev"].indexOf(s)>-1)&&this.store.hasLanguageSomeTranslations(s)){this.resolvedLanguage=s;break}}!this.resolvedLanguage&&this.languages.indexOf(t)<0&&this.store.hasLanguageSomeTranslations(t)&&(this.resolvedLanguage=t,this.languages.unshift(t))}}changeLanguage(t,i){this.isLanguageChangingTo=t;const s=X();this.emit("languageChanging",t);const n=o=>{this.language=o,this.languages=this.services.languageUtils.toResolveHierarchy(o),this.resolvedLanguage=void 0,this.setResolvedLanguage(o)},a=(o,l)=>{l?this.isLanguageChangingTo===t&&(n(l),this.translator.changeLanguage(l),this.isLanguageChangingTo=void 0,this.emit("languageChanged",l),this.logger.log("languageChanged",l)):this.isLanguageChangingTo=void 0,s.resolve((...c)=>this.t(...c)),i&&i(o,(...c)=>this.t(...c))},r=o=>{!t&&!o&&this.services.languageDetector&&(o=[]);const l=m(o)?o:o&&o[0],c=this.store.hasLanguageSomeTranslations(l)?l:this.services.languageUtils.getBestMatchFromCodes(m(o)?[o]:o);c&&(this.language||n(c),this.translator.language||this.translator.changeLanguage(c),this.services.languageDetector?.cacheUserLanguage?.(c)),this.loadResources(c,u=>{a(u,c)})};return!t&&this.services.languageDetector&&!this.services.languageDetector.async?r(this.services.languageDetector.detect()):!t&&this.services.languageDetector&&this.services.languageDetector.async?this.services.languageDetector.detect.length===0?this.services.languageDetector.detect().then(r):this.services.languageDetector.detect(r):r(t),s}getFixedT(t,i,s){const n=(a,r,...o)=>{let l;typeof r!="object"?l=this.options.overloadTranslationOptionHandler([a,r].concat(o)):l={...r},l.lng=l.lng||n.lng,l.lngs=l.lngs||n.lngs,l.ns=l.ns||n.ns,l.keyPrefix!==""&&(l.keyPrefix=l.keyPrefix||s||n.keyPrefix);const c=this.options.keySeparator||".";let u;return l.keyPrefix&&Array.isArray(a)?u=a.map(d=>(typeof d=="function"&&(d=oe(d,{...this.options,...r})),`${l.keyPrefix}${c}${d}`)):(typeof a=="function"&&(a=oe(a,{...this.options,...r})),u=l.keyPrefix?`${l.keyPrefix}${c}${a}`:a),this.t(u,l)};return m(t)?n.lng=t:n.lngs=t,n.ns=i,n.keyPrefix=s,n}t(...t){return this.translator?.translate(...t)}exists(...t){return this.translator?.exists(...t)}setDefaultNamespace(t){this.options.defaultNS=t}hasLoadedNamespace(t,i={}){if(!this.isInitialized)return this.logger.warn("hasLoadedNamespace: i18next was not initialized",this.languages),!1;if(!this.languages||!this.languages.length)return this.logger.warn("hasLoadedNamespace: i18n.languages were undefined or empty",this.languages),!1;const s=i.lng||this.resolvedLanguage||this.languages[0],n=this.options?this.options.fallbackLng:!1,a=this.languages[this.languages.length-1];if(s.toLowerCase()==="cimode")return!0;const r=(o,l)=>{const c=this.services.backendConnector.state[`${o}|${l}`];return c===-1||c===0||c===2};if(i.precheck){const o=i.precheck(this,r);if(o!==void 0)return o}return!!(this.hasResourceBundle(s,t)||!this.services.backendConnector.backend||this.options.resources&&!this.options.partialBundledLanguages||r(s,t)&&(!n||r(a,t)))}loadNamespaces(t,i){const s=X();return this.options.ns?(m(t)&&(t=[t]),t.forEach(n=>{this.options.ns.indexOf(n)<0&&this.options.ns.push(n)}),this.loadResources(n=>{s.resolve(),i&&i(n)}),s):(i&&i(),Promise.resolve())}loadLanguages(t,i){const s=X();m(t)&&(t=[t]);const n=this.options.preload||[],a=t.filter(r=>n.indexOf(r)<0&&this.services.languageUtils.isSupportedCode(r));return a.length?(this.options.preload=n.concat(a),this.loadResources(r=>{s.resolve(),i&&i(r)}),s):(i&&i(),Promise.resolve())}dir(t){if(t||(t=this.resolvedLanguage||(this.languages?.length>0?this.languages[0]:this.language)),!t)return"rtl";try{const n=new Intl.Locale(t);if(n&&n.getTextInfo){const a=n.getTextInfo();if(a&&a.direction)return a.direction}}catch{}const i=["ar","shu","sqr","ssh","xaa","yhd","yud","aao","abh","abv","acm","acq","acw","acx","acy","adf","ads","aeb","aec","afb","ajp","apc","apd","arb","arq","ars","ary","arz","auz","avl","ayh","ayl","ayn","ayp","bbz","pga","he","iw","ps","pbt","pbu","pst","prp","prd","ug","ur","ydd","yds","yih","ji","yi","hbo","men","xmn","fa","jpr","peo","pes","prs","dv","sam","ckb"],s=this.services?.languageUtils||new ze(we());return t.toLowerCase().indexOf("-latn")>1?"ltr":i.indexOf(s.getLanguagePartFromCode(t))>-1||t.toLowerCase().indexOf("-arab")>1?"rtl":"ltr"}static createInstance(t={},i){const s=new xe(t,i);return s.createInstance=xe.createInstance,s}cloneInstance(t={},i=de){const s=t.forkResourceStore;s&&delete t.forkResourceStore;const n={...this.options,...t,isClone:!0},a=new xe(n);if((t.debug!==void 0||t.prefix!==void 0)&&(a.logger=a.logger.clone(t)),["store","services","language"].forEach(r=>{a[r]=this[r]}),a.services={...this.services},a.services.utils={hasLoadedNamespace:a.hasLoadedNamespace.bind(a)},s&&(a.store=new Ae(Object.keys(this.store.data).reduce((r,o)=>(r[o]={...this.store.data[o]},r[o]=Object.keys(r[o]).reduce((l,c)=>(l[c]={...r[o][c]},l),r[o]),r),{}),n),a.services.resourceStore=a.store),t.interpolation){const r={...we().interpolation,...this.options.interpolation,...t.interpolation},o={...n,interpolation:r};a.services.interpolator=new Fe(o)}return a.translator=new He(a.services,n),a.translator.on("*",(r,...o)=>{a.emit(r,...o)}),a.init(n,i),a.translator.options=n,a.translator.backendConnector.services.utils={hasLoadedNamespace:a.hasLoadedNamespace.bind(a)},a}toJSON(){return{options:this.options,store:this.store,language:this.language,languages:this.languages,resolvedLanguage:this.resolvedLanguage}}},S=Ft.createInstance(),Ls=S.createInstance,ks=S.dir,Ps=S.init,Ts=S.loadResources,Rs=S.reloadResources,_s=S.use,Is=S.changeLanguage,Ms=S.getFixedT,$s=S.t,Os=S.exists,As=S.setDefaultNamespace,Ns=S.hasLoadedNamespace,Ds=S.loadNamespaces,Hs=S.loadLanguages})),Ut,Vt,Kt,$i,qs=f((()=>{Ut=/&(?:amp|#38|lt|#60|gt|#62|apos|#39|quot|#34|nbsp|#160|copy|#169|reg|#174|hellip|#8230|#x2F|#47);/g,Vt={"&amp;":"&","&#38;":"&","&lt;":"<","&#60;":"<","&gt;":">","&#62;":">","&apos;":"'","&#39;":"'","&quot;":'"',"&#34;":'"',"&nbsp;":" ","&#160;":" ","&copy;":"©","&#169;":"©","&reg;":"®","&#174;":"®","&hellip;":"…","&#8230;":"…","&#x2F;":"/","&#47;":"/"},Kt=e=>Vt[e],$i=e=>e.replace(Ut,Kt)})),Ge,Oi,Bs=f((()=>{qs(),Ge={bindI18n:"languageChanged",bindI18nStore:"",transEmptyNodeValue:"",transSupportBasicHtmlNodes:!0,transWrapTextNodes:"",transKeepBasicHtmlNodesFor:["br","strong","i","p"],useSuspense:!0,unescape:$i,transDefaultProps:void 0},Oi=(e={})=>{Ge={...Ge,...e}}})),js,Ai,Fs=f((()=>{Ai=e=>{js=e}})),Ni,Us=f((()=>{Bs(),Fs(),Ni={type:"3rdParty",init(e){Oi(e.options.react),Ai(e)}}})),Vs=f((()=>{Us()}));function Ks(e){return Hi.call(Di.call(arguments,1),t=>{if(t)for(const i in t)e[i]===void 0&&(e[i]=t[i])}),e}function Gs(e){return typeof e!="string"?!1:[/<\s*script.*?>/i,/<\s*\/\s*script\s*>/i,/<\s*img.*?on\w+\s*=/i,/<\s*\w+\s*on\w+\s*=.*?>/i,/javascript\s*:/i,/vbscript\s*:/i,/expression\s*\(/i,/eval\s*\(/i,/alert\s*\(/i,/document\.cookie/i,/document\.write\s*\(/i,/window\.location/i,/innerHTML/i].some(t=>t.test(e))}var Di,Hi,We,Gt,Je,Wt,Jt,Yt,V,Ye,Qt,K,Qe,Xt,Zt,ei,ti,ii,Xe,Ze,si,ot,Ws=f((()=>{({slice:Di,forEach:Hi}=[]),We=/^[\u0009\u0020-\u007e\u0080-\u00ff]+$/,Gt=function(e,t){const i=arguments.length>2&&arguments[2]!==void 0?arguments[2]:{path:"/"};let s=`${e}=${encodeURIComponent(t)}`;if(i.maxAge>0){const n=i.maxAge-0;if(Number.isNaN(n))throw new Error("maxAge should be a Number");s+=`; Max-Age=${Math.floor(n)}`}if(i.domain){if(!We.test(i.domain))throw new TypeError("option domain is invalid");s+=`; Domain=${i.domain}`}if(i.path){if(!We.test(i.path))throw new TypeError("option path is invalid");s+=`; Path=${i.path}`}if(i.expires){if(typeof i.expires.toUTCString!="function")throw new TypeError("option expires is invalid");s+=`; Expires=${i.expires.toUTCString()}`}if(i.httpOnly&&(s+="; HttpOnly"),i.secure&&(s+="; Secure"),i.sameSite)switch(typeof i.sameSite=="string"?i.sameSite.toLowerCase():i.sameSite){case!0:s+="; SameSite=Strict";break;case"lax":s+="; SameSite=Lax";break;case"strict":s+="; SameSite=Strict";break;case"none":s+="; SameSite=None";break;default:throw new TypeError("option sameSite is invalid")}return i.partitioned&&(s+="; Partitioned"),s},Je={create(e,t,i,s){let n=arguments.length>4&&arguments[4]!==void 0?arguments[4]:{path:"/",sameSite:"strict"};i&&(n.expires=new Date,n.expires.setTime(n.expires.getTime()+i*60*1e3)),s&&(n.domain=s),document.cookie=Gt(e,t,n)},read(e){const t=`${e}=`,i=document.cookie.split(";");for(let s=0;s<i.length;s++){let n=i[s];for(;n.charAt(0)===" ";)n=n.substring(1,n.length);if(n.indexOf(t)===0)return n.substring(t.length,n.length)}return null},remove(e,t){this.create(e,"",-1,t)}},Wt={name:"cookie",lookup(e){let{lookupCookie:t}=e;if(t&&typeof document<"u")return Je.read(t)||void 0},cacheUserLanguage(e,t){let{lookupCookie:i,cookieMinutes:s,cookieDomain:n,cookieOptions:a}=t;i&&typeof document<"u"&&Je.create(i,e,s,n,a)}},Jt={name:"querystring",lookup(e){let{lookupQuerystring:t}=e,i;if(typeof window<"u"){let{search:s}=window.location;!window.location.search&&window.location.hash?.indexOf("?")>-1&&(s=window.location.hash.substring(window.location.hash.indexOf("?")));const n=s.substring(1).split("&");for(let a=0;a<n.length;a++){const r=n[a].indexOf("=");r>0&&n[a].substring(0,r)===t&&(i=n[a].substring(r+1))}}return i}},Yt={name:"hash",lookup(e){let{lookupHash:t,lookupFromHashIndex:i}=e,s;if(typeof window<"u"){const{hash:n}=window.location;if(n&&n.length>2){const a=n.substring(1);if(t){const r=a.split("&");for(let o=0;o<r.length;o++){const l=r[o].indexOf("=");l>0&&r[o].substring(0,l)===t&&(s=r[o].substring(l+1))}}if(s)return s;if(!s&&i>-1){const r=n.match(/\/([a-zA-Z-]*)/g);return Array.isArray(r)?r[typeof i=="number"?i:0]?.replace("/",""):void 0}}}return s}},V=null,Ye=()=>{if(V!==null)return V;try{if(V=typeof window<"u"&&window.localStorage!==null,!V)return!1;const e="i18next.translate.boo";window.localStorage.setItem(e,"foo"),window.localStorage.removeItem(e)}catch{V=!1}return V},Qt={name:"localStorage",lookup(e){let{lookupLocalStorage:t}=e;if(t&&Ye())return window.localStorage.getItem(t)||void 0},cacheUserLanguage(e,t){let{lookupLocalStorage:i}=t;i&&Ye()&&window.localStorage.setItem(i,e)}},K=null,Qe=()=>{if(K!==null)return K;try{if(K=typeof window<"u"&&window.sessionStorage!==null,!K)return!1;const e="i18next.translate.boo";window.sessionStorage.setItem(e,"foo"),window.sessionStorage.removeItem(e)}catch{K=!1}return K},Xt={name:"sessionStorage",lookup(e){let{lookupSessionStorage:t}=e;if(t&&Qe())return window.sessionStorage.getItem(t)||void 0},cacheUserLanguage(e,t){let{lookupSessionStorage:i}=t;i&&Qe()&&window.sessionStorage.setItem(i,e)}},Zt={name:"navigator",lookup(e){const t=[];if(typeof navigator<"u"){const{languages:i,userLanguage:s,language:n}=navigator;if(i)for(let a=0;a<i.length;a++)t.push(i[a]);s&&t.push(s),n&&t.push(n)}return t.length>0?t:void 0}},ei={name:"htmlTag",lookup(e){let{htmlTag:t}=e,i;const s=t||(typeof document<"u"?document.documentElement:null);return s&&typeof s.getAttribute=="function"&&(i=s.getAttribute("lang")),i}},ti={name:"path",lookup(e){let{lookupFromPathIndex:t}=e;if(typeof window>"u")return;const i=window.location.pathname.match(/\/([a-zA-Z-]*)/g);if(Array.isArray(i))return i[typeof t=="number"?t:0]?.replace("/","")}},ii={name:"subdomain",lookup(e){let{lookupFromSubdomainIndex:t}=e;const i=typeof t=="number"?t+1:1,s=typeof window<"u"&&window.location?.hostname?.match(/^(\w{2,5})\.(([a-z0-9-]{1,63}\.[a-z]{2,6})|localhost)/i);if(s)return s[i]}},Xe=!1;try{document.cookie,Xe=!0}catch{}Ze=["querystring","cookie","localStorage","sessionStorage","navigator","htmlTag"],Xe||Ze.splice(1,1),si=()=>({order:Ze,lookupQuerystring:"lng",lookupCookie:"i18next",lookupLocalStorage:"i18nextLng",lookupSessionStorage:"i18nextLng",caches:["localStorage"],excludeCacheFor:["cimode"],convertDetectedLanguage:e=>e}),ot=class{constructor(e){let t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{};this.type="languageDetector",this.detectors={},this.init(e,t)}init(){let e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:{languageUtils:{}},t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:{},i=arguments.length>2&&arguments[2]!==void 0?arguments[2]:{};this.services=e,this.options=Ks(t,this.options||{},si()),typeof this.options.convertDetectedLanguage=="string"&&this.options.convertDetectedLanguage.indexOf("15897")>-1&&(this.options.convertDetectedLanguage=s=>s.replace("-","_")),this.options.lookupFromUrlIndex&&(this.options.lookupFromPathIndex=this.options.lookupFromUrlIndex),this.i18nOptions=i,this.addDetector(Wt),this.addDetector(Jt),this.addDetector(Qt),this.addDetector(Xt),this.addDetector(Zt),this.addDetector(ei),this.addDetector(ti),this.addDetector(ii),this.addDetector(Yt)}addDetector(e){return this.detectors[e.name]=e,this}detect(){let e=arguments.length>0&&arguments[0]!==void 0?arguments[0]:this.options.order,t=[];return e.forEach(i=>{if(this.detectors[i]){let s=this.detectors[i].lookup(this.options);s&&typeof s=="string"&&(s=[s]),s&&(t=t.concat(s))}}),t=t.filter(i=>i!=null&&!Gs(i)).map(i=>this.options.convertDetectedLanguage(i)),this.services&&this.services.languageUtils&&this.services.languageUtils.getBestMatchFromCodes?t:t.length>0?t[0]:null}cacheUserLanguage(e){let t=arguments.length>1&&arguments[1]!==void 0?arguments[1]:this.options.caches;t&&(this.options.excludeCacheFor&&this.options.excludeCacheFor.indexOf(e)>-1||t.forEach(i=>{this.detectors[i]&&this.detectors[i].cacheUserLanguage(e,this.options)}))}},ot.type="languageDetector"})),ni,ai,ri,oi,li,zi,Js=f((()=>{ni={loading:"加载中...",saving:"保存中...",success:"成功",error:"错误",confirm:"确认",cancel:"取消",submit:"提交",reset:"重置",delete:"删除",edit:"编辑",view:"查看",search:"搜索",filter:"筛选",export:"导出",import:"导入"},ai={network:"网络连接失败，请检查网络设置",validation:"输入数据无效，请检查后重试",authentication:"登录已过期，请重新登录",authorization:"您没有权限执行此操作",notFound:"请求的资源不存在",server:"服务器错误，请稍后重试",plugin:"插件错误，请检查插件配置",cache:"缓存错误，请清除缓存后重试",unknown:"发生未知错误，请稍后重试"},ri={title:"地图",zoomIn:"放大",zoomOut:"缩小",resetView:"重置视图",addMarker:"添加标记",removeMarker:"移除标记",measureDistance:"测量距离",measureArea:"测量面积"},oi={title:"采样",addPoint:"添加采样点",removePoint:"移除采样点",clearPoints:"清空采样点",generateRecommendations:"生成采样建议",optimizeSampling:"优化采样"},li={title:"克里金插值",parameters:"参数",variogram:"变异函数",crossValidation:"交叉验证",result:"结果",runInterpolation:"运行插值",exportResult:"导出结果"},zi={common:ni,errors:ai,map:ri,sampling:oi,kriging:li}})),ci,di,hi,ui,pi,qi,Ys=f((()=>{ci={loading:"Loading...",saving:"Saving...",success:"Success",error:"Error",confirm:"Confirm",cancel:"Cancel",submit:"Submit",reset:"Reset",delete:"Delete",edit:"Edit",view:"View",search:"Search",filter:"Filter",export:"Export",import:"Import"},di={network:"Network connection failed, please check your network settings",validation:"Invalid input data, please check and try again",authentication:"Login expired, please log in again",authorization:"You don't have permission to perform this operation",notFound:"Requested resource not found",server:"Server error, please try again later",plugin:"Plugin error, please check plugin configuration",cache:"Cache error, please clear cache and try again",unknown:"An unknown error occurred, please try again later"},hi={title:"Map",zoomIn:"Zoom In",zoomOut:"Zoom Out",resetView:"Reset View",addMarker:"Add Marker",removeMarker:"Remove Marker",measureDistance:"Measure Distance",measureArea:"Measure Area"},ui={title:"Sampling",addPoint:"Add Sampling Point",removePoint:"Remove Sampling Point",clearPoints:"Clear Sampling Points",generateRecommendations:"Generate Recommendations",optimizeSampling:"Optimize Sampling"},pi={title:"Kriging Interpolation",parameters:"Parameters",variogram:"Variogram",crossValidation:"Cross Validation",result:"Result",runInterpolation:"Run Interpolation",exportResult:"Export Result"},qi={common:ci,errors:di,map:hi,sampling:ui,kriging:pi}})),mi,N,Qs=f((()=>{zs(),Vs(),Ws(),Js(),Ys(),mi={"zh-CN":{translation:zi},"en-US":{translation:qi}},S.use(ot).use(Ni).init({resources:mi,fallbackLng:"zh-CN",debug:!1,interpolation:{escapeValue:!1},detection:{order:["localStorage","navigator"],caches:["localStorage"]}}),N=S})),gi,W,Xs=f((()=>{ki(),Ii(),Qs(),gi=class{constructor(e={}){this.config={enableLogging:!0,enableReporting:!0,enableUserNotification:!0,logLevel:w.MEDIUM,...e},this.errorHandlers=new Map,this.globalHandlers=[],this.initializeDefaultHandlers(),this.setupGlobalErrorHandlers()}initializeDefaultHandlers(){this.errorHandlers.set(v.NETWORK,this.handleNetworkError.bind(this)),this.errorHandlers.set(v.VALIDATION,this.handleValidationError.bind(this)),this.errorHandlers.set(v.AUTHENTICATION,this.handleAuthenticationError.bind(this)),this.errorHandlers.set(v.AUTHORIZATION,this.handleAuthorizationError.bind(this)),this.errorHandlers.set(v.NOT_FOUND,this.handleNotFoundError.bind(this)),this.errorHandlers.set(v.SERVER,this.handleServerError.bind(this)),this.errorHandlers.set(v.PLUGIN,this.handlePluginError.bind(this)),this.errorHandlers.set(v.CACHE,this.handleCacheError.bind(this))}setupGlobalErrorHandlers(){window.addEventListener("unhandledrejection",e=>{this.handle(new _(v.UNKNOWN,"UNHANDLED_PROMISE_REJECTION","未处理的 Promise 拒绝",w.HIGH,{reason:e.reason}))}),window.addEventListener("error",e=>{this.handle(new _(v.UNKNOWN,"GLOBAL_ERROR",e.message,w.HIGH,{filename:e.filename,lineno:e.lineno},e.error))})}handle(e){let t;e instanceof _?t=e:t=this.convertToAppError(e),this.shouldLog(t)&&this.logError(t),this.shouldReport(t)&&this.reportError(t),this.shouldNotifyUser(t)&&this.notifyUser(t);const i=this.errorHandlers.get(t.type);i&&i(t),this.globalHandlers.forEach(s=>s(t))}convertToAppError(e){const t=e.message.toLowerCase();let i=v.UNKNOWN;return t.includes("network")||t.includes("fetch")?i=v.NETWORK:t.includes("validation")||t.includes("invalid")?i=v.VALIDATION:t.includes("authentication")||t.includes("unauthorized")?i=v.AUTHENTICATION:(t.includes("not found")||t.includes("404"))&&(i=v.NOT_FOUND),new _(i,"UNKNOWN_ERROR",e.message,w.MEDIUM,void 0,void 0,e)}shouldLog(e){return this.config.enableLogging&&this.compareSeverity(e.severity,this.config.logLevel)>=0}shouldReport(e){return this.config.enableReporting&&e.isOperational&&this.compareSeverity(e.severity,w.HIGH)>=0}shouldNotifyUser(e){return this.config.enableUserNotification&&this.compareSeverity(e.severity,w.MEDIUM)>=0}compareSeverity(e,t){const i={[w.LOW]:0,[w.MEDIUM]:1,[w.HIGH]:2,[w.CRITICAL]:3};return i[e]-i[t]}logError(e){this.getLogMethod(e.severity)(`[${e.type.toUpperCase()}] ${e.code}: ${e.message}`,e.details,e.context)}getLogMethod(e){switch(e){case w.LOW:return console.debug;case w.MEDIUM:return console.info;case w.HIGH:return console.warn;case w.CRITICAL:return console.error;default:return console.log}}reportError(e){console.log("报告错误:",e.toJSON?e.toJSON():e)}notifyUser(e){const t=this.getUserFriendlyMessage(e);console.log("通知用户:",t)}getUserFriendlyMessage(e){return{[v.NETWORK]:N.t("errors.network"),[v.VALIDATION]:N.t("errors.validation"),[v.AUTHENTICATION]:N.t("errors.authentication"),[v.AUTHORIZATION]:N.t("errors.authorization"),[v.NOT_FOUND]:N.t("errors.notFound"),[v.SERVER]:N.t("errors.server"),[v.PLUGIN]:N.t("errors.plugin"),[v.CACHE]:N.t("errors.cache"),[v.UNKNOWN]:N.t("errors.unknown")}[e.type]||e.message}handleNetworkError(e){console.log("处理网络错误:",e)}handleValidationError(e){console.log("处理验证错误:",e)}handleAuthenticationError(e){console.log("处理认证错误:",e)}handleAuthorizationError(e){console.log("处理授权错误:",e)}handleNotFoundError(e){console.log("处理未找到错误:",e)}handleServerError(e){console.log("处理服务器错误:",e)}handlePluginError(e){console.log("处理插件错误:",e)}handleCacheError(e){console.log("处理缓存错误:",e)}registerHandler(e,t){this.errorHandlers.set(e,t)}registerGlobalHandler(e){return this.globalHandlers.push(e),()=>{const t=this.globalHandlers.indexOf(e);t>-1&&this.globalHandlers.splice(t,1)}}updateConfig(e){this.config={...this.config,...e}}},W=new gi})),ut,Bi=f((()=>{dt(),Cs(),Xs(),Ii(),ut=class{constructor(e="",t){this.maxRetries=t?.maxRetries??3,this.retryDelay=t?.retryDelay??1e3,this.retryableStatusCodes=new Set([408,429,500,502,503,504]),this.baseURL=e,this.pendingRequests=new Map,this.cache=new Li({maxSize:100,ttl:300*1e3,strategy:"lru"},{maxSize:500,ttl:3600*1e3,strategy:"lfu",storageKey:"api-cache"},{enableAutoPromote:!0,promoteThreshold:3}),this.cacheConfig=new Map([["/api/data/list",60*1e3],["/api/config",600*1e3],["/api/results",300*1e3],["/config",600*1e3]])}_delay(e){return new Promise(t=>setTimeout(t,e))}_getCacheKey(e,t={}){const i=t.method||"GET",s=t.body||"",n=JSON.stringify({method:i,url:e,body:typeof s=="string"?s:JSON.stringify(s)});let a=0;for(let r=0;r<n.length;r++){const o=n.charCodeAt(r);a=(a<<5)-a+o,a=a&a}return`${i}_${Math.abs(a)}`}async _getFromCache(e){const t=await this.cache.get(e);return t!==void 0?(console.log(`[缓存] 命中: ${e}`),t):null}async _setCache(e,t,i){await this.cache.set(e,t,i)}async clearCache(){await this.cache.clear(),console.log("[缓存] 已清除所有缓存")}async clearCacheFor(e){await this.cache.invalidatePattern(e)}getCacheStats(){return this.cache.getStats()}resetCacheStats(){this.cache.resetStats()}_shouldUseCache(e,t){if(e!=="GET")return!1;for(const[i]of this.cacheConfig)if(t.includes(i))return!0;return!1}_getCacheTTL(e){for(const[t,i]of this.cacheConfig)if(e.includes(t))return i;return 300*1e3}_getErrorMessage(e,t,i){const s={400:"请求参数错误，请检查输入数据",401:"未授权，请检查登录状态",403:"访问被拒绝，权限不足",404:"请求的资源不存在",409:"数据冲突，请检查是否重复提交",422:"数据验证失败，请检查输入格式",429:"请求过于频繁，请稍后重试",500:"服务器处理请求时出现问题，请稍后重试",502:"网关错误，请稍后重试",503:"服务暂时不可用，请稍后重试",504:"请求超时，请稍后重试"};return i||(s[e]?s[e]:`请求失败 (${e}): ${t}，请稍后重试`)}convertToAppError(e,t){if(e.response){const i=e.response.status,s=e.response.data,n={url:t.url,method:t.method||"GET",status:i,timestamp:new Date};return i===401?new at(s?.message||"认证失败",s,n):i===403?new at(s?.message||"权限不足",s,n):i===404?new Ri(s?.message||"资源不存在",s,n):i>=500?new _i(s?.message||"服务器错误",s,n):i===422?new Ti(s?.message||"数据验证失败",s,n):new _("validation","REQUEST_ERROR",s?.message||`请求错误 (${i})`,"medium",s,n,e)}else return e.request?new Pi("网络连接失败",{message:e.message},{url:t.url,method:t.method||"GET",timestamp:new Date}):new _("unknown","UNKNOWN_ERROR",e.message,"high",{url:t.url,method:t.method||"GET"},void 0,e)}async request(e,t={}){const i=t.method||"GET",s=`${i}_${e}`;if(!I.isOnline)if(i==="GET"){const a=this._getCacheKey(e,t),r=this._getFromCache(a);if(r!==null)return console.log(`[离线模式] 从缓存返回数据: ${e}`),r;const o=e.match(/task-status\/([^\/]+)/);if(o){const l=o[1];try{const c=await I.getCachedResult(l);if(c)return console.log(`[离线模式] 从 IndexedDB 返回结果: ${l}`),c}catch{}}throw new Error("离线模式：无缓存数据可用")}else throw console.log(`[离线模式] 请求已加入队列: ${i} ${e}`),e.includes("upload-data")?await I.enqueue({type:"upload",payload:t.body}):e.includes("start-kriging")&&await I.enqueue({type:"kriging",payload:JSON.parse(t.body)}),new Error("离线模式：操作已加入队列，将在恢复在线后自动执行");if(i==="GET"&&this._shouldUseCache(i,e)){const a=this._getCacheKey(e,t),r=await this._getFromCache(a);if(r!==null)return r}if(this.pendingRequests.has(s))return console.warn(`请求已在进行中: ${s}`),this.pendingRequests.get(s);const n=(async()=>{let a=null;for(let r=0;r<=this.maxRetries;r++)try{const o=await fetch(e,{...t,mode:"cors",credentials:"omit"});if(!o){const c=new Error("网络连接失败，请检查后端服务是否启动"),u=this.convertToAppError(c,{url:e,method:i});throw W.handle(u),u}if(!o.ok){const c=await o.json().catch(()=>({})),u=this._getErrorMessage(o.status,o.statusText,c.detail);if(this.retryableStatusCodes.has(o.status)&&r<this.maxRetries){console.warn(`请求失败 [${o.status}]，${this.retryDelay}ms 后重试 (${r+1}/${this.maxRetries})`),await this._delay(this.retryDelay*(r+1));continue}console.error(`API请求失败 [${o.status}]:`,c);const d=new Error(u),p=this.convertToAppError(d,{url:e,method:i});throw W.handle(p),p}const l=await o.json();if(i==="GET"&&this._shouldUseCache(i,e)){const c=this._getCacheKey(e,t),u=this._getCacheTTL(e);await this._setCache(c,l,u)}if(e.includes("task-status")||e.includes("result")){const c=e.match(/task-status\/([^\/]+)|result\/prediction\/([^\/]+)/);if(c){const u=c[1]||c[2];try{await I.cacheResult(u,l)}catch{}}}return l}catch(o){if(a=o instanceof Error?o:new Error(String(o)),o instanceof TypeError&&o.message.includes("fetch")&&r<this.maxRetries){console.warn(`网络连接失败，${this.retryDelay}ms 后重试 (${r+1}/${this.maxRetries})`),await this._delay(this.retryDelay*(r+1));continue}if(o instanceof TypeError&&o.message.includes("fetch")){const l=this.convertToAppError(new Error("网络连接失败，请检查后端服务是否启动"),{url:e,method:i});throw W.handle(l),l}if(o instanceof _)W.handle(o);else{const l=this.convertToAppError(o instanceof Error?o:new Error(String(o)),{url:e,method:i});throw W.handle(l),l}throw o}if(a){const r=this.convertToAppError(a,{url:e,method:i});throw W.handle(r),r}throw new Error("请求失败，已达到最大重试次数")})();return this.pendingRequests.set(s,n),n.finally(()=>{this.pendingRequests.delete(s)}),n}async uploadData(e){const t=new FormData;return t.append("file",e),this.request(`${this.baseURL}/upload-data`,{method:"POST",body:t})}async startKriging(e){return this.request(`${this.baseURL}/start-kriging`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}async getTaskStatus(e){return this.request(`${this.baseURL}/task-status/${e}`)}async getPredictionResult(e){return this.request(`${this.baseURL}/result/prediction/${e}`)}async getVarianceResult(e){return this.request(`${this.baseURL}/result/variance/${e}`)}async getReport(e){return this.request(`${this.baseURL}/result/report/${e}`)}async downloadExportFile(e,t){const i=`${this.baseURL}/result/download/${e}/${t}`,s=await fetch(i,{mode:"cors",credentials:"omit"});if(!s.ok)throw new Error(`下载失败: HTTP ${s.status}`);const n=await s.blob(),a=document.createElement("a");a.href=URL.createObjectURL(n),a.download=t,document.body.appendChild(a),a.click(),document.body.removeChild(a),URL.revokeObjectURL(a.href)}async get(e){return this.request(`${this.baseURL}${e}`)}async post(e,t){return this.request(`${this.baseURL}${e}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(t)})}cancelAllRequests(){this.pendingRequests.clear()}async evaluateSamplingCandidates(e,t,i="impact_optimized",s=50){return this.request(`${this.baseURL}/api/sampling-impact/evaluate-candidates`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id:e,candidate_points:t,strategy:i,grid_resolution:s})})}async previewSamplingEffect(e,t,i=50){return this.request(`${this.baseURL}/api/sampling-impact/preview-effect`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id:e,new_point:t,grid_resolution:i})})}async recommendOptimalPoints(e,t=20,i="impact_optimized",s=null){return this.request(`${this.baseURL}/api/sampling-impact/recommend-optimal`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id:e,n_recommendations:t,strategy:i,constraints:s})})}async batchSimulateSampling(e,t,i=50){return this.request(`${this.baseURL}/api/sampling-impact/batch-simulate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task_id:e,sampling_plans:t,grid_resolution:i})})}async submitInterpolation(e){return this.request(`${this.baseURL}/api/interpolation`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}async getInterpolationResult(e){return this.request(`${this.baseURL}/api/interpolation/${e}`)}async generateSamplingPoints(e){return this.request(`${this.baseURL}/api/sampling`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}async performAnalysis(e){return this.request(`${this.baseURL}/api/analysis`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}async generateReport(e){return this.request(`${this.baseURL}/api/analysis/${e}/report`)}async exportData(e){return this.request(`${this.baseURL}/api/export`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}async parseImportFile(e){return this.request(`${this.baseURL}/api/import/parse`,{method:"POST",body:this._formDataFromFile(e)})}async importData(e){return this.request(`${this.baseURL}/api/import`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(e)})}_formDataFromFile(e){const t=new FormData;return t.append("file",e),t}}})),te,et,tt,lt,Zs=f((()=>{Se(),et="udake_history",tt=200,lt=class{static init(){this._load()}static record(e){const t={...e,id:`${Date.now()}_${Math.random().toString(36).slice(2,6)}`,timestamp:Date.now()};this._entries.unshift(t),this._entries.length>tt&&this._entries.pop(),t.undoable&&(this._undoStack.push(t),this._redoStack.length=0),this._save(),this._notify()}static async undo(){const e=this._undoStack.pop();if(!e)return!1;const t=this._undoHandlers.get(e.type);return t&&e.undoData?(await t(e.undoData),this._redoStack.push(e),this.record({action:h.t("history.undoAction",{action:e.action}),type:e.type,detail:h.t("history.undone",{action:e.action}),undoable:!1}),!0):!1}static async redo(){const e=this._redoStack.pop();return e?(this._undoStack.push(e),this.record({action:h.t("history.redoAction",{action:e.action}),type:e.type,detail:h.t("history.redone",{action:e.action}),undoable:!1}),!0):!1}static registerUndoHandler(e,t){this._undoHandlers.set(e,t)}static getAll(){return[...this._entries]}static search(e){const t=e.toLowerCase();return this._entries.filter(i=>i.action.toLowerCase().includes(t)||i.detail.toLowerCase().includes(t))}static filterByType(e){return this._entries.filter(t=>t.type===e)}static clear(){this._entries=[],this._undoStack=[],this._redoStack=[],this._save(),this._notify()}static canUndo(){return this._undoStack.length>0}static canRedo(){return this._redoStack.length>0}static onChange(e){return this._listeners.add(e),()=>{this._listeners.delete(e)}}static createPanel(){const e=document.createElement("div");e.className="panel",e.id="history-panel-"+Date.now(),e.innerHTML=`
            <h2 class="panel-title" data-i18n="history.title">${h.t("history.title")}</h2>
            <div class="panel-content">
                <div style="display:flex;gap:8px;margin-bottom:8px;">
                    <button class="btn btn-export" id="history-undo-btn" disabled style="flex:1;height:32px;font-size:12px;" data-i18n="history.undo">${h.t("history.undo")}</button>
                    <button class="btn btn-export" id="history-redo-btn" disabled style="flex:1;height:32px;font-size:12px;" data-i18n="history.redo">${h.t("history.redo")}</button>
                    <button class="btn btn-export" id="history-clear-btn" style="flex:1;height:32px;font-size:12px;" data-i18n="history.clear">${h.t("history.clear")}</button>
                </div>
                <div class="history-list" id="history-list">
                    <p style="color:var(--text-tertiary);font-size:13px;" data-i18n="history.empty">${h.t("history.empty")}</p>
                </div>
            </div>
        `;const t=e.querySelector("#history-list"),i=e.querySelector("#history-undo-btn"),s=e.querySelector("#history-redo-btn"),n=e.querySelector("#history-clear-btn"),a=()=>{const r=this.getAll().slice(0,20);if(i.disabled=!this.canUndo(),s.disabled=!this.canRedo(),r.length===0){t.innerHTML=`<p style="color:var(--text-tertiary);font-size:13px;" data-i18n="history.empty">${h.t("history.empty")}</p>`;return}t.innerHTML=r.map(o=>{const l={upload:"📤",kriging:"🔬",export:"📥",project:"📁",point:"📍",setting:"⚙️"},c=new Date(o.timestamp),u=`${c.getHours().toString().padStart(2,"0")}:${c.getMinutes().toString().padStart(2,"0")}`;return`
                    <div class="history-item">
                        <span class="history-icon ${o.type}">${l[o.type]||"📋"}</span>
                        <div class="history-info">
                            <span class="history-action">${o.action}</span>
                            <span class="history-time">${u}</span>
                        </div>
                    </div>
                `}).join("")};return this.onChange(a),a(),i.addEventListener("click",()=>this.undo()),s.addEventListener("click",()=>this.redo()),n.addEventListener("click",()=>this.clear()),e}static updateUIText(){document.querySelectorAll('[id^="history-panel-"]').forEach(e=>{const t=e.querySelector(".panel-title");t&&(t.textContent=h.t("history.title"));const i=e.querySelector("#history-undo-btn");i&&(i.textContent=h.t("history.undo"));const s=e.querySelector("#history-redo-btn");s&&(s.textContent=h.t("history.redo"));const n=e.querySelector("#history-clear-btn");n&&(n.textContent=h.t("history.clear"));const a=e.querySelector("#history-list p");(a&&a.textContent?.includes("operations recorded")||a?.textContent?.includes("操作记录"))&&(a.textContent=h.t("history.empty"))})}static _save(){try{localStorage.setItem(et,JSON.stringify(this._entries.slice(0,tt)))}catch{}}static _load(){try{const e=localStorage.getItem(et);e&&(this._entries=JSON.parse(e))}catch{}}static _notify(){const e=this.getAll();this._listeners.forEach(t=>{try{t(e)}catch(i){console.error(i)}})}},te=lt,te._entries=[],te._undoStack=[],te._redoStack=[],te._listeners=new Set,te._undoHandlers=new Map})),ji,en=f((()=>{ji=class{constructor(e){this.container=null,this.commonProjections={4326:"WGS 1984",3857:"Web Mercator",2154:"RGF93 / Lambert-93",32633:"WGS 84 / UTM zone 33N",32634:"WGS 84 / UTM zone 34N",32635:"WGS 84 / UTM zone 35N",32636:"WGS 84 / UTM zone 36N",3395:"WGS 84 / World Mercator",4269:"NAD83",4267:"NAD27",2163:"US National Atlas Equal Area",102100:"Web Mercator Auxiliary Sphere"},this.view=e}createPanel(){const e=document.createElement("div");return e.className="panel coordinate-system-panel",e.innerHTML=`
            <h2 class="panel-title">坐标系统信息</h2>
            <div class="panel-content">
                <div class="coordinate-info">
                    <div class="info-item">
                        <span class="info-label">投影坐标系</span>
                        <span class="info-value" id="projection-name">加载中...</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">投影 EPSG</span>
                        <span class="info-value" id="projection-epsg">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">地理坐标系</span>
                        <span class="info-value" id="geographic-name">-</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">地理 EPSG</span>
                        <span class="info-value" id="geographic-epsg">-</span>
                    </div>
                    <div class="info-item wkt-item">
                        <span class="info-label">WKT</span>
                        <button class="btn-collapse" id="wkt-toggle">展开</button>
                    </div>
                    <div class="wkt-content" id="wkt-content" style="display: none;">
                        <pre id="wkt-text">-</pre>
                    </div>
                </div>
            </div>
        `,this.container=e,this.bindEvents(),this.updateInfo(),e}bindEvents(){const e=this.container?.querySelector("#wkt-toggle"),t=this.container?.querySelector("#wkt-content");e&&t&&e.addEventListener("click",()=>{const i=t.style.display!=="none";t.style.display=i?"none":"block",e.textContent=i?"展开":"收起"})}async updateInfo(){const e=this.view.spatialReference;if(!e){this.showUnknown();return}const t=e.wkid||e.latestWkid,i=this.container?.querySelector("#projection-epsg");i&&(i.textContent=t?`EPSG:${t}`:"未识别");try{const a=await this.getProjectionName(t),r=this.container?.querySelector("#projection-name");r&&(r.textContent=a)}catch{const r=this.container?.querySelector("#projection-name");r&&(r.textContent="未识别坐标系")}if(t&&t!==4326&&t!==3857){const a=this.container?.querySelector("#geographic-name"),r=this.container?.querySelector("#geographic-epsg");a&&(a.textContent="WGS 1984"),r&&(r.textContent="EPSG:4326")}else if(t===4326){const a=this.container?.querySelector("#geographic-name"),r=this.container?.querySelector("#geographic-epsg");a&&(a.textContent="WGS 1984"),r&&(r.textContent="EPSG:4326")}else if(t===3857){const a=this.container?.querySelector("#geographic-name"),r=this.container?.querySelector("#geographic-epsg");a&&(a.textContent="WGS 1984"),r&&(r.textContent="EPSG:4326")}const s=e.wkt||"无 WKT 信息",n=this.container?.querySelector("#wkt-text");n&&(n.textContent=s)}async getProjectionName(e){return e?this.commonProjections[e]||`EPSG:${e}`:"未识别"}showUnknown(){const e=this.container?.querySelector("#projection-name"),t=this.container?.querySelector("#projection-epsg"),i=this.container?.querySelector("#geographic-name"),s=this.container?.querySelector("#geographic-epsg"),n=this.container?.querySelector("#wkt-text");e&&(e.textContent="未识别坐标系"),t&&(t.textContent="-"),i&&(i.textContent="-"),s&&(s.textContent="-"),n&&(n.textContent="-")}}})),Fi,tn=f((()=>{ct(),Fi=class{constructor(e,t){this.container=null,this.view=e,this.onPointAdded=t}createPanel(){const e=document.createElement("div");return e.className="panel single-point-panel",e.innerHTML=`
            <h2 class="panel-title">单点采样输入</h2>
            <div class="panel-content">
                <div class="form-group">
                    <label>X 坐标</label>
                    <input type="text" id="point-x" class="input" placeholder="经度或投影X">
                    <span class="error-message" id="error-x"></span>
                </div>
                <div class="form-group">
                    <label>Y 坐标</label>
                    <input type="text" id="point-y" class="input" placeholder="纬度或投影Y">
                    <span class="error-message" id="error-y"></span>
                </div>
                <div class="form-group">
                    <label>Point_Data</label>
                    <input type="text" id="point-data" class="input" placeholder="数值">
                    <span class="error-message" id="error-data"></span>
                </div>
                <button id="add-point-btn" class="btn btn-primary">添加采样点</button>
            </div>
        `,this.container=e,this.bindEvents(),e}bindEvents(){const e=this.container?.querySelector("#add-point-btn");e&&e.addEventListener("click",()=>this.handleAddPoint()),["point-x","point-y","point-data"].forEach(t=>{const i=this.container?.querySelector(`#${t}`);i&&i.addEventListener("input",()=>{this.clearError(t)})})}async handleAddPoint(){const e=this.container?.querySelector("#point-x"),t=this.container?.querySelector("#point-y"),i=this.container?.querySelector("#point-data");if(!e||!t||!i)return;const s=e.value.trim(),n=t.value.trim(),a=i.value.trim();let r=!1;if(s||(this.showError("point-x","请输入X坐标"),r=!0),n||(this.showError("point-y","请输入Y坐标"),r=!0),a?isNaN(parseFloat(a))&&(this.showError("point-data","必须为数值类型"),r=!0):(this.showError("point-data","请输入数值"),r=!0),!r)try{const o=await this.parseCoordinate(s,"x"),l=await this.parseCoordinate(n,"y"),c=parseFloat(a),u=await this.createPoint(o,l);this.onPointAdded&&await this.onPointAdded({x:u.x,y:u.y,value:c,timestamp:new Date().toISOString()}),e.value="",t.value="",i.value=""}catch(o){console.error("添加点失败:",o);const l=o instanceof Error?o.message:"未知错误";this.showError("point-x",l)}}async parseCoordinate(e,t){switch(this.detectFormat(e)){case"dms":return this.parseDMS(e);case"decimal":return parseFloat(e);case"projected":return parseFloat(e);default:throw new Error("坐标格式无法识别")}}detectFormat(e){if(e.includes("°")||e.includes("'")||e.includes('"'))return"dms";const t=parseFloat(e);return isNaN(t)?"unknown":t>=-180&&t<=180&&Math.abs(t)<1e3?"decimal":Math.abs(t)>=1e3?"projected":"unknown"}parseDMS(e){try{const t=e.replace(/[NSEW]/gi,"").trim().split(/[°'"]/),i=parseFloat(t[0]||"0"),s=parseFloat(t[1]||"0"),n=parseFloat(t[2]||"0");let a=i+s/60+n/3600;return e.match(/[SW]/i)&&(a=-a),a}catch{throw new Error("DMS 格式错误")}}async createPoint(e,t){const i=(await R(async()=>{const{default:r}=await import("https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js");return{default:r}},[],import.meta.url)).default,s=await R(()=>import("https://js.arcgis.com/4.28/@arcgis/core/geometry/projection.js"),[],import.meta.url),n=this.detectFormat(String(e)),a=this.detectFormat(String(t));if(n==="decimal"||a==="decimal"){await s.load();const r=new i({x:e,y:t,spatialReference:{wkid:4326}});return s.project(r,this.view.spatialReference)}else return new i({x:e,y:t,spatialReference:this.view.spatialReference})}showError(e,t){const i=this.container?.querySelector(`#${e}`),s=this.container?.querySelector(`#error-${e.split("-")[1]}`);i&&s&&(i.style.borderColor="#ff453a",i.style.transition="border-color 200ms",s.textContent=t,s.style.display="block")}clearError(e){const t=this.container?.querySelector(`#${e}`),i=this.container?.querySelector(`#error-${e.split("-")[1]}`);t&&i&&(t.style.borderColor="",i.textContent="",i.style.display="none")}}})),Ui,sn=f((()=>{ls(),ps(),Bi(),Si(),ys(),Se(),Ui=class{constructor(e,t,i){this.view=e,this.layerManager=t,this.onRecommendationSelect=i,this.apiService=new ut,this.currentTaskId=null,this.recommendations=[],this.markers=[],this.mapProvider=Ce.getProvider(),this.MAX_VISIBLE_MARKERS=50,this.markerPool=[],this.visibleMarkers=[],this._viewChangeTimer=null,this.clusterHint=null,this.markerLayer=null,this.LOCATION_CACHE_TTL_MS=3e4,this.SOURCE_APP_NAME="UDAKE",this.devicePlatform=this._detectDevicePlatform(),this.isMobileDevice=this.devicePlatform!=="web",this.cachedUserLocation=null,this._onDocumentClick=null,this._setupViewportListener()}updateUIText(){const e=document.getElementById("sampling-recommendation-panel");if(!e)return;const t=e.querySelector(".section-title");t&&(t.textContent=h.t("recommendation.title"));const i=e.querySelector(".section-description");i&&(i.textContent=h.t("recommendation.description"));const s=e.querySelector('label[for="recommendation-strategy"]');s&&(s.textContent=h.t("recommendation.strategy"));const n=e.querySelector('label[for="recommendation-count"]');n&&(n.textContent="建议点数量");const a=e.querySelector("#generate-recommendations-btn");a&&(a.textContent=h.t("recommendation.generate"));const r=e.querySelector("#recommendation-strategy");if(r){const o=r.querySelectorAll("option");o[0]&&(o[0].textContent=h.t("recommendation.strategy.hybrid")),o[1]&&(o[1].textContent="基于方差优先"),o[2]&&(o[2].textContent="基于空间覆盖")}}createPanel(){const e=document.createElement("div");return e.className="sampling-recommendation-panel",e.id="sampling-recommendation-panel",e.innerHTML=`
            <div class="panel-header">
                <h3 class="section-title" data-i18n="recommendation.title">${h.t("recommendation.title")}</h3>
                <p class="section-description" data-i18n="recommendation.description">${h.t("recommendation.description")}</p>
            </div>
            <div class="controls-section">
                <div class="form-group">
                    <label for="recommendation-strategy" data-i18n="recommendation.strategy">${h.t("recommendation.strategy")}</label>
                    <select id="recommendation-strategy" class="select">
                        <option value="hybrid">${h.t("recommendation.strategy.hybrid")}</option>
                        <option value="variance_based">基于方差优先</option>
                        <option value="spatial_coverage">基于空间覆盖</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="recommendation-count">建议点数量</label>
                    <input type="number" id="recommendation-count" class="input" value="20" min="5" max="50">
                </div>
                <button id="generate-recommendations-btn" class="btn btn-primary" disabled>
                    生成建议
                </button>
                <div id="recommendation-status" class="status-message" role="status" aria-live="polite" style="display: none;"></div>
            </div>
            <div id="recommendations-container" style="display: none;">
                <div class="recommendations-header">
                    <span class="recommendations-count" aria-live="polite">建议点：0</span>
                    <button id="export-recommendations-btn" class="btn btn-export">导出 GeoJSON</button>
                </div>
                <div id="recommendations-list" class="recommendations-list" role="list" aria-label="采样建议列表"></div>
            </div>
        `,this.bindEvents(e),e}bindEvents(e){const t=e.querySelector("#generate-recommendations-btn"),i=e.querySelector("#recommendation-strategy"),s=e.querySelector("#recommendation-count"),n=e.querySelector("#export-recommendations-btn");t.addEventListener("click",()=>this.generateRecommendations()),i.addEventListener("change",()=>{this.currentTaskId&&this.generateRecommendations()}),s.addEventListener("change",()=>{this.currentTaskId&&this.generateRecommendations()}),n.addEventListener("click",()=>this.exportRecommendations()),this._onDocumentClick&&document.removeEventListener("click",this._onDocumentClick),this._onDocumentClick=a=>{a.target?.closest(".recommendation-card")||this._hideAllNavigationModeSelectors()},document.addEventListener("click",this._onDocumentClick)}setTaskId(e){this.currentTaskId=e;const t=document.getElementById("generate-recommendations-btn");e?(t&&(t.disabled=!1),this.generateRecommendations()):(t&&(t.disabled=!0),this.clearRecommendations())}async generateRecommendations(){if(!this.currentTaskId)return;const e=document.getElementById("recommendation-strategy").value,t=parseInt(document.getElementById("recommendation-count").value),i=document.getElementById("recommendation-status");try{i.style.display="block",i.className="status-message",i.textContent=h.t("recommendation.generating"),this.recommendations=(await this.apiService.post("/sampling-recommendations/generate",{task_id:this.currentTaskId,strategy:e,n_recommendations:t})).recommendations||[],this.displayRecommendations(),this.displayMarkers(),i.className="status-message success",i.textContent=h.t("recommendation.generated",{count:this.recommendations.length})}catch(s){console.error("生成采样建议失败:",s),i.className="status-message error",i.textContent=`${h.t("recommendation.failed")}: ${s.message||"未知错误"}`}}displayRecommendations(){const e=document.getElementById("recommendations-container"),t=document.getElementById("recommendations-list"),i=document.querySelector(".recommendations-count");if(this.recommendations.length===0){e.style.display="none";return}e.style.display="block",i.textContent=`建议点：${this.recommendations.length}`,t.innerHTML="",[...this.recommendations].sort((s,n)=>n.variance-s.variance).forEach((s,n)=>{const a=this.createRecommendationCard(s,n);t.appendChild(a)})}createRecommendationCard(e,t){const i=document.createElement("div");i.className="recommendation-card",i.dataset.id=String(e.id),i.setAttribute("role","listitem"),i.setAttribute("tabindex","0"),i.setAttribute("aria-label",`${h.t("recommendation.title")} #${e.id}, ${h.t("recommendation.priority")} ${this.getPriorityText(e.priority)}, ${h.t("recommendation.uncertainty")} ${e.uncertainty_level}/5`);const s=this.getPriorityColor(e.priority),n=this.getPriorityText(e.priority);i.innerHTML=`
            <div class="card-header">
                <div class="card-title">
                    <span class="card-number">#${e.id}</span>
                    <span class="card-priority" style="background-color: ${s}">
                        ${n}
                    </span>
                </div>
                <div class="card-uncertainty">
                    ${h.t("recommendation.uncertainty")}: ${e.uncertainty_level}/5
                </div>
            </div>
            <div class="card-body">
                <div class="card-info">
                    <span class="info-label">坐标:</span>
                    <span class="info-value">${e.x.toFixed(6)}, ${e.y.toFixed(6)}</span>
                </div>
                <div class="card-info">
                    <span class="info-label">方差:</span>
                    <span class="info-value">${e.variance.toFixed(4)}</span>
                </div>
                <div class="card-info">
                    <span class="info-label">距最近点:</span>
                    <span class="info-value">${e.distance_to_nearest.toFixed(2)}m</span>
                </div>
                <div class="card-reason">
                    <span class="reason-label">${h.t("recommendation.reason")}:</span>
                    <span class="reason-text">${e.sampling_reason}</span>
                </div>
            </div>
            <div class="card-footer">
                <button class="btn btn-card btn-locate" data-id="${e.id}">定位</button>
                <button class="btn btn-card btn-navigate" data-id="${e.id}" ${this.isMobileDevice?"":'disabled title="仅支持移动端设备"'}>
                    ${this.isMobileDevice?"导航":"仅移动端"}
                </button>
                <button class="btn btn-card btn-select" data-id="${e.id}">选择此点</button>
            </div>
            <div class="navigation-mode-selector" aria-label="导航方式选择器">
                <button class="btn-nav-mode" data-mode="driving">驾车</button>
                <button class="btn-nav-mode" data-mode="riding">骑行</button>
                <button class="btn-nav-mode" data-mode="walking">步行</button>
            </div>
            <div class="card-navigation-status" role="status" aria-live="polite"></div>
        `;const a=i.querySelector(".btn-locate"),r=i.querySelector(".btn-select"),o=i.querySelector(".btn-navigate"),l=i.querySelector(".navigation-mode-selector"),c=i.querySelector(".card-navigation-status"),u=i.querySelectorAll(".btn-nav-mode");return a.addEventListener("click",d=>{d.stopPropagation(),this._hideAllNavigationModeSelectors(),this.locateRecommendation(e)}),r.addEventListener("click",d=>{d.stopPropagation(),this._hideAllNavigationModeSelectors(),this.selectRecommendation(e)}),o&&l&&c&&(o.addEventListener("click",d=>{d.stopPropagation(),this._toggleNavigationModeSelector(l,e.id),l.classList.contains("visible")&&this._setNavigationStatus(c,"请选择导航方式","info")}),u.forEach(d=>{d.addEventListener("click",async p=>{p.stopPropagation();const y=d.dataset.mode;this._isNavigationMode(y)&&(l.classList.remove("visible"),await this._startNavigation(e,y,c))})})),i.addEventListener("mouseenter",()=>this.highlightMarker(e.id,!0)),i.addEventListener("mouseleave",()=>this.highlightMarker(e.id,!1)),i.addEventListener("focus",()=>this.highlightMarker(e.id,!0)),i.addEventListener("blur",()=>this.highlightMarker(e.id,!1)),i.addEventListener("keydown",d=>{d.key==="Enter"&&this.selectRecommendation(e)}),i}_detectDevicePlatform(){const e=yt.getPlatform();if(e==="android"||e==="ios")return e;const t=navigator.userAgent||"";return/iPhone|iPad|iPod/i.test(t)?"ios":/Android/i.test(t)?"android":"web"}_toggleNavigationModeSelector(e,t){const i=e.classList.contains("visible");this._hideAllNavigationModeSelectors(t),i||e.classList.add("visible")}_hideAllNavigationModeSelectors(e){document.querySelectorAll(".navigation-mode-selector.visible").forEach(t=>{const i=t.closest(".recommendation-card"),s=i?.dataset.id?parseInt(i.dataset.id,10):NaN;e!==void 0&&s===e||t.classList.remove("visible")})}_isNavigationMode(e){return e==="driving"||e==="riding"||e==="walking"}_setNavigationStatus(e,t,i){e.className=`card-navigation-status ${i}`,e.textContent=t}async _startNavigation(e,t,i){if(!this.isMobileDevice){this._setNavigationStatus(i,"导航仅支持移动端设备","error");return}this._setNavigationStatus(i,"正在获取当前位置...","info");try{const s=await this._getCurrentLocation(),[n,a]=ke.convertCoordinate(s.longitude,s.latitude,"wgs84","gcj02"),[r,o]=this._convertRecommendationToGcj02(e.x,e.y),{appUrl:l,webUrl:c}=this._buildAmapNavigationUrls(n,a,r,o,t,e.id);this._setNavigationStatus(i,`正在打开高德地图（${this._getNavigationModeText(t)}）...`,"success"),this._openNavigationWithFallback(l,c)}catch(s){this._setNavigationStatus(i,this._formatLocationError(s),"error")}}_getNavigationModeText(e){return{driving:"驾车",riding:"骑行",walking:"步行"}[e]}async _getCurrentLocation(){const e=Date.now();if(this.cachedUserLocation&&e-this.cachedUserLocation.timestamp<=this.LOCATION_CACHE_TTL_MS)return{longitude:this.cachedUserLocation.longitude,latitude:this.cachedUserLocation.latitude};const t=yt.getPlatform();try{const n=await Le.checkPermissions();if(!(n.location==="granted"||n.coarseLocation==="granted")&&t!=="web"){const a=await Le.requestPermissions({permissions:["location"]});if(!(a.location==="granted"||a.coarseLocation==="granted"))throw new Error("定位权限未授权，请在系统设置中开启定位权限后重试")}}catch(n){if(t!=="web")throw n}const i=await Le.getCurrentPosition({enableHighAccuracy:!0,timeout:1e4,maximumAge:0}),s={longitude:i.coords.longitude,latitude:i.coords.latitude};return this.cachedUserLocation={...s,timestamp:e},s}_convertRecommendationToGcj02(e,t){const i=ke.getCoordinateSystem();return ke.convertCoordinate(e,t,i,"gcj02")}_buildAmapNavigationUrls(e,t,i,s,n,a){const r=e.toFixed(6),o=t.toFixed(6),l=i.toFixed(6),c=s.toFixed(6),u="我的位置",d=`采样点#${a}`,p=this._mapNavigationModeToAmapType(n),y=new URLSearchParams({slat:o,slon:r,sname:u,dlat:c,dlon:l,dname:d,dev:"0",t:String(p)});return{appUrl:this.devicePlatform==="ios"?`iosamap://path?sourceApplication=${encodeURIComponent(this.SOURCE_APP_NAME)}&${y.toString()}`:`amapuri://route/plan/?${y.toString()}`,webUrl:`https://uri.amap.com/navigation?${new URLSearchParams({from:`${r},${o},${u}`,to:`${l},${c},${d}`,mode:this._mapNavigationModeToWebMode(n),src:this.SOURCE_APP_NAME,coordinate:"gaode",callnative:"0"}).toString()}`}}_mapNavigationModeToAmapType(e){return{driving:0,riding:3,walking:2}[e]}_mapNavigationModeToWebMode(e){return{driving:"car",riding:"ride",walking:"walk"}[e]}_openNavigationWithFallback(e,t){let i=!1;const s=()=>{document.hidden&&(i=!0)};document.addEventListener("visibilitychange",s),window.location.href=e,window.setTimeout(()=>{document.removeEventListener("visibilitychange",s),i||(window.location.href=t)},1500)}_formatLocationError(e){const t=e instanceof Error?e.message:String(e||"");return t.includes("denied")||t.includes("授权")?"定位权限未授权，请在系统设置中开启定位权限":t.includes("timeout")||t.includes("超时")?"定位超时，请检查网络或 GPS 后重试":t.includes("unavailable")||t.includes("不可用")?"定位服务不可用，请稍后重试":"无法获取当前位置，请稍后重试"}getPriorityColor(e){return{high:"#ff3b30",medium:"#ff9500",low:"#34c759"}[e]||"#ff9500"}getPriorityText(e){return{high:h.t("recommendation.priority.high"),medium:h.t("recommendation.priority.medium"),low:h.t("recommendation.priority.low")}[e]||h.t("recommendation.priority.medium")}_setupViewportListener(){const e=this.view;if(!e)return;const t=()=>{this._viewChangeTimer!==null&&clearTimeout(this._viewChangeTimer),this._viewChangeTimer=setTimeout(()=>{this._refreshVisibleMarkers()},200)};e.watch&&(e.watch("extent",t),e.watch("zoom",t)),e.on&&typeof e.getCenter=="function"&&(e.on("moveend",t),e.on("zoomend",t))}_getViewportBounds(){const e=this.view;if(e.extent){const t=e.extent;return{minLng:t.xmin,minLat:t.ymin,maxLng:t.xmax,maxLat:t.ymax}}if(e.getBounds){const t=e.getBounds(),i=t.getSouthWest(),s=t.getNorthEast();return{minLng:i.lng,minLat:i.lat,maxLng:s.lng,maxLat:s.lat}}return null}_isInViewport(e,t){return t?e.x>=t.minLng&&e.x<=t.maxLng&&e.y>=t.minLat&&e.y<=t.maxLat:!0}_refreshVisibleMarkers(){if(this.recommendations.length===0)return;if(this.recommendations.length<=this.MAX_VISIBLE_MARKERS){this._updateClusterHint(0);return}const e=this._getViewportBounds(),t=this.recommendations.filter(n=>this._isInViewport(n,e)),i=t.slice(0,this.MAX_VISIBLE_MARKERS),s=t.length-i.length;this.clearMarkers(),this.mapProvider==="amap"?this._showMarkersAMap(i):this._showMarkersArcGIS(i),this._updateClusterHint(s)}_updateClusterHint(e){if(!this.clusterHint){this.clusterHint=document.createElement("div"),this.clusterHint.className="cluster-hint recommendation-cluster-hint",this.clusterHint.setAttribute("role","status"),this.clusterHint.setAttribute("aria-live","polite");const t=document.querySelector(".map-container");t&&t.appendChild(this.clusterHint)}e>0?(this.clusterHint.textContent=`视口内还有 ${e} 个建议点未显示，请放大地图查看`,this.clusterHint.style.display="block"):this.clusterHint.style.display="none"}async displayMarkers(){if(this.clearMarkers(),this.recommendations.length===0)return;let e=this.recommendations,t=0;if(this.recommendations.length>this.MAX_VISIBLE_MARKERS){const i=this._getViewportBounds(),s=this.recommendations.filter(n=>this._isInViewport(n,i));e=s.slice(0,this.MAX_VISIBLE_MARKERS),t=s.length-e.length}this.mapProvider==="amap"?await this._showMarkersAMap(e):await this._showMarkersArcGIS(e),this._updateClusterHint(t)}async _showMarkersAMap(e){for(const t of e){const i=this.getPriorityColor(t.priority);let s;this.markerPool.length>0?(s=this.markerPool.pop(),s.setPosition([t.x,t.y]),s.setContent(`<div class="recommendation-marker" style="background-color: ${i};" data-id="${t.id}"></div>`)):s=new window.AMap.Marker({position:[t.x,t.y],content:`<div class="recommendation-marker" style="background-color: ${i};" data-id="${t.id}"></div>`,offset:new window.AMap.Pixel(-8,-8),zIndex:100}),this.view.add(s),this.markers.push({marker:s,rec:t}),s.on("click",()=>{this.selectRecommendation(t)})}}async _showMarkersArcGIS(e){const[t,i,s,n]=await Promise.all([window.esri.require("esri/Graphic"),window.esri.require("esri/layers/GraphicsLayer"),window.esri.require("esri/geometry/Point"),window.esri.require("esri/symbols/SimpleMarkerSymbol")]),a=new i({title:"采样建议"});for(const r of e){const o=this.getPriorityColor(r.priority),l=new t({geometry:new s({longitude:r.x,latitude:r.y}),symbol:new n({color:o,size:16,outline:{color:[255,255,255,1],width:2}})});a.add(l),this.markers.push({marker:l,rec:r})}this.view.map.add(a),this.markerLayer=a,this.view.on("click",r=>{this.view.hitTest(r).then(o=>{if(o.results.length>0){const l=o.results[0].graphic,c=this.markers.find(u=>u.marker===l);c&&this.selectRecommendation(c.rec)}})})}clearMarkers(){this.mapProvider==="amap"?this.markers.forEach(({marker:e})=>{this.view.remove(e),e.clearEvents?.("click"),this.markerPool.push(e)}):this.markerLayer&&(this.view.map.remove(this.markerLayer),this.markerLayer=null),this.markers=[]}highlightMarker(e,t){const i=this.markers.find(s=>s.rec.id===e);if(i)if(this.mapProvider==="amap"){const s=i.marker.getContent().querySelector(".recommendation-marker");s&&(s.style.transform=t?"scale(1.5)":"scale(1)",s.style.zIndex=t?"200":"100")}else{const s=i.marker;t?s.symbol.size=24:s.symbol.size=16}}locateRecommendation(e){this.mapProvider==="amap"?(this.view.setCenter([e.x,e.y]),this.view.setZoom(15)):this.view.goTo({center:[e.x,e.y],zoom:15})}selectRecommendation(e){this.onRecommendationSelect&&this.onRecommendationSelect(e),this.locateRecommendation(e),document.querySelectorAll(".recommendation-card").forEach(t=>{parseInt(t.dataset.id)===e.id?t.classList.add("selected"):t.classList.remove("selected")})}async exportRecommendations(){if(this.currentTaskId)try{const e=await this.apiService.get(`/sampling-recommendations/export/${this.currentTaskId}`),t=new Blob([JSON.stringify(e,null,2)],{type:"application/geo+json"}),i=URL.createObjectURL(t),s=document.createElement("a");s.href=i,s.download=`sampling_recommendations_${this.currentTaskId}.geojson`,s.click(),URL.revokeObjectURL(i)}catch(e){console.error("导出失败:",e),alert("导出失败: "+(e.message||"未知错误"))}}clearRecommendations(){this.recommendations=[],this.clearMarkers(),this.markerPool=[],this._updateClusterHint(0);const e=document.getElementById("recommendations-container");e&&(e.style.display="none");const t=document.getElementById("recommendation-status");t&&(t.style.display="none")}destroy(){this._viewChangeTimer!==null&&clearTimeout(this._viewChangeTimer),this._onDocumentClick&&(document.removeEventListener("click",this._onDocumentClick),this._onDocumentClick=null),this.clearRecommendations(),this.clusterHint&&(this.clusterHint.remove(),this.clusterHint=null)}}})),Vi,nn=f((()=>{Bi(),Se(),Vi=class{constructor(e){this.mapEngine=e,this.apiService=new ut,this.currentTaskId=null,this.currentRecommendations=[],this.currentStrategy="impact_optimized",this.isGenerating=!1,this.element=null}async initialize(e){this.currentTaskId=e,this.render(),this.attachEventListeners()}render(){const e=document.getElementById("enhanced-sampling-panel");e&&e.remove();const t=document.createElement("div");t.id="enhanced-sampling-panel",t.className="enhanced-sampling-panel",t.innerHTML=`
            <div class="enhanced-sampling-panel-header">
                <h3>${h.t("enhancedRecommendation.title")}</h3>
                <button class="close-btn" id="close-enhanced-panel">&times;</button>
            </div>

            <div class="enhanced-sampling-panel-content">
                <!-- 策略选择器 -->
                <div class="strategy-section">
                    <label for="strategy-selector">${h.t("enhancedRecommendation.strategy")}</label>
                    <select id="strategy-selector">
                        <option value="impact_optimized">${h.t("enhancedRecommendation.strategies.impact")}</option>
                        <option value="variance_based">${h.t("enhancedRecommendation.strategies.variance")}</option>
                        <option value="spatial_coverage">${h.t("enhancedRecommendation.strategies.coverage")}</option>
                        <option value="hybrid">${h.t("enhancedRecommendation.strategies.hybrid")}</option>
                    </select>
                </div>

                <!-- 推荐设置 -->
                <div class="settings-section">
                    <div class="setting-item">
                        <label for="recommendation-count">${h.t("enhancedRecommendation.count")}</label>
                        <input type="number" id="recommendation-count" value="20" min="1" max="100">
                    </div>
                    <div class="setting-item">
                        <label for="enable-preview">
                            <input type="checkbox" id="enable-preview" checked>
                            ${h.t("enhancedRecommendation.enablePreview")}
                        </label>
                    </div>
                </div>

                <!-- 操作按钮 -->
                <div class="action-buttons">
                    <button id="generate-btn" class="primary-btn">
                        ${h.t("enhancedRecommendation.generate")}
                    </button>
                    <button id="evaluate-candidates-btn" class="secondary-btn">
                        ${h.t("enhancedRecommendation.evaluate")}
                    </button>
                    <button id="compare-plans-btn" class="secondary-btn">
                        ${h.t("enhancedRecommendation.compare")}
                    </button>
                </div>

                <!-- 加载状态 -->
                <div id="loading-indicator" class="loading-indicator hidden">
                    <div class="spinner"></div>
                    <span>${h.t("enhancedRecommendation.generating")}</span>
                </div>

                <!-- 推荐列表 -->
                <div id="recommendations-list" class="recommendations-list">
                    <div class="empty-state">
                        ${h.t("enhancedRecommendation.empty")}
                    </div>
                </div>

                <!-- 收益摘要 -->
                <div id="benefits-summary" class="benefits-summary hidden">
                    <h4>${h.t("enhancedRecommendation.benefits")}</h4>
                    <div class="benefits-grid">
                        <div class="benefit-item">
                            <span class="benefit-label">${h.t("enhancedRecommendation.varianceReduction")}</span>
                            <span class="benefit-value" id="total-variance-reduction">0%</span>
                        </div>
                        <div class="benefit-item">
                            <span class="benefit-label">${h.t("enhancedRecommendation.rmseImprovement")}</span>
                            <span class="benefit-value" id="rmse-improvement">0%</span>
                        </div>
                        <div class="benefit-item">
                            <span class="benefit-label">${h.t("enhancedRecommendation.coverage")}</span>
                            <span class="benefit-value" id="coverage-area">0 km²</span>
                        </div>
                    </div>
                </div>

                <!-- 预览热力图 -->
                <div id="preview-heatmap" class="preview-heatmap hidden">
                    <h4>${h.t("enhancedRecommendation.preview")}</h4>
                    <canvas id="preview-canvas"></canvas>
                </div>
            </div>
        `,document.body.appendChild(t),this.element=t}attachEventListeners(){this.element&&(this.element.querySelector("#close-enhanced-panel")?.addEventListener("click",()=>this.destroy()),this.element.querySelector("#generate-btn")?.addEventListener("click",()=>this.generateRecommendations()),this.element.querySelector("#evaluate-candidates-btn")?.addEventListener("click",()=>this.openCandidateEvaluator()),this.element.querySelector("#compare-plans-btn")?.addEventListener("click",()=>this.openPlanComparator()),this.element.querySelector("#strategy-selector")?.addEventListener("change",e=>{this.currentStrategy=e.target.value}))}async generateRecommendations(){if(!(!this.currentTaskId||this.isGenerating)){this.isGenerating=!0,this.showLoading(!0);try{const e=this.element?.querySelector("#recommendation-count"),t=parseInt(e?.value||"20",10);this.currentRecommendations=(await this.apiService.post("/api/sampling-impact/recommend-optimal",{task_id:this.currentTaskId,n_recommendations:t,strategy:this.currentStrategy})).recommendations||[],this.renderRecommendations(),this.updateBenefitsSummary()}catch(e){console.error("生成推荐失败:",e),this.showError(h.t("enhancedRecommendation.error"))}finally{this.isGenerating=!1,this.showLoading(!1)}}}renderRecommendations(){const e=this.element?.querySelector("#recommendations-list");if(e){if(this.currentRecommendations.length===0){e.innerHTML=`
                <div class="empty-state">
                    ${h.t("enhancedRecommendation.empty")}
                </div>
            `;return}e.innerHTML=this.currentRecommendations.map((t,i)=>`
            <div class="recommendation-item" data-index="${i}">
                <div class="recommendation-header">
                    <span class="recommendation-id">#${t.id}</span>
                    <span class="recommendation-priority priority-${t.priority}">${t.priority}</span>
                </div>
                <div class="recommendation-details">
                    <div class="detail-row">
                        <span class="detail-label">${h.t("enhancedRecommendation.coordinates")}:</span>
                        <span class="detail-value">(${t.x.toFixed(4)}, ${t.y.toFixed(4)})</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${h.t("enhancedRecommendation.variance")}:</span>
                        <span class="detail-value">${t.variance.toFixed(6)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${h.t("enhancedRecommendation.score")}:</span>
                        <span class="detail-value">${(t.comprehensive_score||0).toFixed(3)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">${h.t("enhancedRecommendation.reason")}:</span>
                        <span class="detail-value">${t.sampling_reason}</span>
                    </div>
                </div>
                <div class="recommendation-actions">
                    <button class="preview-btn" data-index="${i}">
                        ${h.t("enhancedRecommendation.preview")}
                    </button>
                    <button class="select-btn" data-index="${i}">
                        ${h.t("enhancedRecommendation.select")}
                    </button>
                </div>
            </div>
        `).join(""),e.querySelectorAll(".preview-btn").forEach(t=>{t.addEventListener("click",i=>{const s=parseInt(i.target.dataset.index||"0",10);this.previewPointEffect(this.currentRecommendations[s])})}),e.querySelectorAll(".select-btn").forEach(t=>{t.addEventListener("click",i=>{const s=parseInt(i.target.dataset.index||"0",10);this.selectRecommendation(this.currentRecommendations[s])})})}}async previewPointEffect(e){if(this.currentTaskId)try{const t=e.expected_benefit||0,i=await this.apiService.post("/api/sampling-impact/preview-effect",{task_id:this.currentTaskId,new_point:{x:e.x,y:e.y,value:t}});this.renderPreviewHeatmap(i),this.showPreviewSummary(i)}catch(t){console.error("预览失败:",t),this.showError(h.t("enhancedRecommendation.previewError"))}}renderPreviewHeatmap(e){const t=this.element?.querySelector("#preview-heatmap"),i=this.element?.querySelector("#preview-canvas");if(!t||!i)return;t.classList.remove("hidden");const s=i.getContext("2d");if(!s)return;const n=e.variance_reduction_map,a=n.normalized[0].length,r=n.normalized.length;i.width=a,i.height=r;const o=s.createImageData(a,r),l=o.data;for(let c=0;c<r;c++)for(let u=0;u<a;u++){const d=n.normalized[c][u],p=(c*a+u)*4,y=this.getHeatmapColor(d);l[p]=y.r,l[p+1]=y.g,l[p+2]=y.b,l[p+3]=255}s.putImageData(o,0,0)}getHeatmapColor(e){return e<.25?{r:0,g:0,b:Math.floor(e*4*255)}:e<.5?{r:0,g:Math.floor((e-.25)*4*255),b:255}:e<.75?{r:Math.floor((e-.5)*4*255),g:255,b:Math.floor((.75-e)*4*255)}:{r:255,g:Math.floor((1-e)*4*255),b:0}}showPreviewSummary(e){const t=e.quantitative_metrics,i=`
            <div class="preview-summary">
                <div class="summary-item">
                    <span>${h.t("enhancedRecommendation.varianceReduction")}:</span>
                    <strong>${t.variance_reduction_percent.toFixed(2)}%</strong>
                </div>
                <div class="summary-item">
                    <span>${h.t("enhancedRecommendation.rmseImprovement")}:</span>
                    <strong>${t.rmse_improvement.toFixed(2)}%</strong>
                </div>
                <div class="summary-item">
                    <span>${h.t("enhancedRecommendation.influenceRadius")}:</span>
                    <strong>${e.influence_radius.toFixed(2)}m</strong>
                </div>
                <div class="summary-item">
                    <span>${h.t("enhancedRecommendation.improvedRegions")}:</span>
                    <strong>${e.improved_regions.length}</strong>
                </div>
            </div>
        `,s=this.element?.querySelector(".preview-summary");s&&s.remove();const n=this.element?.querySelector("#preview-heatmap");if(n){const a=document.createElement("div");a.innerHTML=i;const r=a.firstElementChild;r&&n.appendChild(r)}}updateBenefitsSummary(){const e=this.element?.querySelector("#benefits-summary");if(e&&(e.classList.remove("hidden"),this.currentRecommendations.length>0)){const t=this.currentRecommendations.reduce((s,n)=>s+(n.variance_reduction||0),0),i=this.currentRecommendations.reduce((s,n)=>s+(n.comprehensive_score||0),0)/this.currentRecommendations.length;document.getElementById("total-variance-reduction").textContent=`${(t*100).toFixed(2)}%`,document.getElementById("rmse-improvement").textContent=`${(i*100).toFixed(2)}%`,document.getElementById("coverage-area").textContent=`${(this.currentRecommendations.length*.01).toFixed(2)} km²`}}async evaluateCustomCandidates(e){if(!this.currentTaskId)return[];try{return(await this.apiService.post("/api/sampling-impact/evaluate-candidates",{task_id:this.currentTaskId,candidate_points:e,strategy:this.currentStrategy})).results||[]}catch(t){return console.error("评估候选点失败:",t),[]}}async compareSamplingPlans(e){if(!this.currentTaskId||e.length===0)return[];try{return(await this.apiService.post("/api/sampling-impact/batch-simulate",{task_id:this.currentTaskId,sampling_plans:e})).results||[]}catch(t){return console.error("对比方案失败:",t),[]}}selectRecommendation(e){this.mapEngine&&this.mapEngine.addMarker({x:e.x,y:e.y,value:e.variance}).catch(i=>{console.error("高亮标记失败:",i)});const t=new CustomEvent("recommendationSelected",{detail:e});document.dispatchEvent(t)}showLoading(e){const t=this.element?.querySelector("#loading-indicator");t&&t.classList.toggle("hidden",!e)}showError(e){alert(e)}openCandidateEvaluator(){console.log("打开候选点评估器")}openPlanComparator(){console.log("打开方案对比器")}destroy(){this.element&&(this.element.remove(),this.element=null),this.currentRecommendations=[],this.currentTaskId=null}updateUIText(){this.element&&(this.render(),this.attachEventListeners(),this.currentRecommendations.length>0&&this.renderRecommendations())}}})),Ki,an=f((()=>{Ki=class{constructor(e){this.onMarkerClick=null,this.onMarkerDrag=null,this.activeMarkerId=null,this.mapEngine=e,this.markers=new Map,this.markerConfig={size:20,showLabel:!0,showScore:!0,enableDrag:!0},this.onMarkerDrag=null,this.activeMarkerId=null}async createRecommendationMarker(e){try{await this.mapEngine.addMarker({x:e.x,y:e.y,value:e.variance}),this.markers.set(e.id,{marker:{position:[e.y,e.x],data:e},recommendation:e,popup:null})}catch(t){console.error("创建标记失败:",t)}}highlightMarker(e){this.markers.forEach((t,i)=>{const s=t.marker.getElement();s&&(s.style.transform=i===e?"scale(1.3)":"scale(1)",s.style.boxShadow=i===e?"0 6px 12px rgba(0,0,0,0.5)":"0 2px 4px rgba(0,0,0,0.3)")}),this.activeMarkerId=e}removeHighlight(){this.markers.forEach(e=>{const t=e.marker.getElement();t&&(t.style.transform="scale(1)",t.style.boxShadow="0 2px 4px rgba(0,0,0,0.3)")}),this.activeMarkerId=null}createMarkers(e){this.clearMarkers(),e.forEach(t=>{this.createRecommendationMarker(t)})}updateMarker(e){const t=this.markers.get(e.id);t&&(t.marker.setLatLng&&t.marker.setLatLng([e.y,e.x]),t.recommendation=e)}removeMarker(e){const t=this.markers.get(e);t&&(t.marker.remove(),t.popup.remove(),this.markers.delete(e))}clearMarkers(){this.markers.forEach(e=>{e.marker.remove(),e.popup.remove()}),this.markers.clear(),this.activeMarkerId=null}setMarkerConfig(e){this.markerConfig={...this.markerConfig,...e}}setOnMarkerClick(e){this.onMarkerClick=e}setOnMarkerDrag(e){this.onMarkerDrag=e}getMarkerCount(){return this.markers.size}getAllMarkers(){return Array.from(this.markers.values())}destroy(){this.clearMarkers(),this.onMarkerClick=null,this.onMarkerDrag=null}}})),Gi,rn=f((()=>{Se(),Gi=class{constructor(){this.element=null,this.currentStrategy="impact_optimized",this.strategyConfig={n_recommendations:20,min_distance:null,enable_preview:!0,threshold_percentile:75},this.onStrategyChange=null,this.strategies=[{id:"impact_optimized",name:h.t("strategy.impact.name"),description:h.t("strategy.impact.description"),icon:"🎯",recommended:!0,features:[h.t("strategy.impact.feature1"),h.t("strategy.impact.feature2"),h.t("strategy.impact.feature3")]},{id:"variance_based",name:h.t("strategy.variance.name"),description:h.t("strategy.variance.description"),icon:"📊",recommended:!1,features:[h.t("strategy.variance.feature1"),h.t("strategy.variance.feature2"),h.t("strategy.variance.feature3")]},{id:"spatial_coverage",name:h.t("strategy.coverage.name"),description:h.t("strategy.coverage.description"),icon:"🗺️",recommended:!1,features:[h.t("strategy.coverage.feature1"),h.t("strategy.coverage.feature2"),h.t("strategy.coverage.feature3")]},{id:"hybrid",name:h.t("strategy.hybrid.name"),description:h.t("strategy.hybrid.description"),icon:"🔄",recommended:!1,features:[h.t("strategy.hybrid.feature1"),h.t("strategy.hybrid.feature2"),h.t("strategy.hybrid.feature3")]}]}initialize(){this.render(),this.attachEventListeners()}render(){const e=document.getElementById("strategy-selector-container");e&&e.remove();const t=document.createElement("div");t.id="strategy-selector-container",t.className="strategy-selector-container",t.innerHTML=`
            <div class="strategy-selector-header">
                <h3>${h.t("strategy.title")}</h3>
                <p class="strategy-description">${h.t("strategy.subtitle")}</p>
            </div>

            <div class="strategy-cards-grid">
                ${this.strategies.map(i=>this.renderStrategyCard(i)).join("")}
            </div>

            <div class="strategy-settings">
                <h4>${h.t("strategy.advancedSettings")}</h4>
                <div class="settings-grid">
                    <div class="setting-item">
                        <label for="recommendation-count">
                            ${h.t("strategy.recommendationCount")}
                        </label>
                        <input
                            type="number"
                            id="recommendation-count"
                            value="${this.strategyConfig.n_recommendations}"
                            min="1"
                            max="100"
                        />
                    </div>
                    <div class="setting-item">
                        <label for="min-distance">
                            ${h.t("strategy.minDistance")}
                        </label>
                        <input
                            type="number"
                            id="min-distance"
                            value="${this.strategyConfig.min_distance||""}"
                            placeholder="${h.t("strategy.noLimit")}"
                            min="0"
                        />
                    </div>
                    <div class="setting-item">
                        <label for="threshold-percentile">
                            ${h.t("strategy.thresholdPercentile")}
                        </label>
                        <input
                            type="number"
                            id="threshold-percentile"
                            value="${this.strategyConfig.threshold_percentile}"
                            min="0"
                            max="100"
                        />
                    </div>
                    <div class="setting-item">
                        <label class="checkbox-label">
                            <input
                                type="checkbox"
                                id="enable-preview"
                                ${this.strategyConfig.enable_preview?"checked":""}
                            />
                            ${h.t("strategy.enablePreview")}
                        </label>
                    </div>
                </div>
            </div>

            <div class="strategy-action">
                <button id="apply-strategy-btn" class="primary-btn">
                    ${h.t("strategy.apply")}
                </button>
            </div>
        `,document.body.appendChild(t),this.element=t}renderStrategyCard(e){const t=e.id===this.currentStrategy,i=e.recommended?`<span class="recommended-badge">${h.t("strategy.recommended")}</span>`:"";return`
            <div
                class="strategy-card ${t?"selected":""}"
                data-strategy="${e.id}"
            >
                ${i}
                <div class="strategy-icon">${e.icon}</div>
                <div class="strategy-info">
                    <h4 class="strategy-name">${e.name}</h4>
                    <p class="strategy-desc">${e.description}</p>
                    <ul class="strategy-features">
                        ${e.features.map(s=>`
                            <li>${s}</li>
                        `).join("")}
                    </ul>
                </div>
                <div class="strategy-select-indicator">
                    <div class="indicator-dot"></div>
                </div>
            </div>
        `}attachEventListeners(){this.element&&(this.element.querySelectorAll(".strategy-card").forEach(e=>{e.addEventListener("click",()=>{const t=e.getAttribute("data-strategy");t&&this.selectStrategy(t)})}),this.element.querySelector("#apply-strategy-btn")?.addEventListener("click",()=>{this.applyStrategy()}),this.element.querySelector("#recommendation-count")?.addEventListener("change",e=>{this.strategyConfig.n_recommendations=parseInt(e.target.value,10)}),this.element.querySelector("#min-distance")?.addEventListener("change",e=>{const t=e.target.value;this.strategyConfig.min_distance=t?parseFloat(t):null}),this.element.querySelector("#threshold-percentile")?.addEventListener("change",e=>{this.strategyConfig.threshold_percentile=parseInt(e.target.value,10)}),this.element.querySelector("#enable-preview")?.addEventListener("change",e=>{this.strategyConfig.enable_preview=e.target.checked}))}selectStrategy(e){this.currentStrategy=e,this.element&&this.element.querySelectorAll(".strategy-card").forEach(t=>{const i=t.getAttribute("data-strategy")===e;t.classList.toggle("selected",i)})}applyStrategy(){this.onStrategyChange?.(this.currentStrategy,this.strategyConfig),this.showAppliedMessage()}showAppliedMessage(){const e=document.createElement("div");e.className="strategy-applied-message",e.textContent=h.t("strategy.applied",{strategy:this.getStrategyName(this.currentStrategy)}),document.body.appendChild(e),setTimeout(()=>{e.remove()},2e3)}getStrategyName(e){const t=this.strategies.find(i=>i.id===e);return t?t.name:e}setOnStrategyChange(e){this.onStrategyChange=e}getCurrentStrategy(){return this.currentStrategy}getCurrentConfig(){return{...this.strategyConfig}}setStrategy(e){this.strategies.some(t=>t.id===e)&&this.selectStrategy(e)}setConfig(e){if(this.strategyConfig={...this.strategyConfig,...e},this.element){const t=this.element.querySelector("#recommendation-count");t&&(t.value=this.strategyConfig.n_recommendations.toString());const i=this.element.querySelector("#min-distance");i&&(i.value=this.strategyConfig.min_distance?.toString()||"");const s=this.element.querySelector("#threshold-percentile");s&&(s.value=this.strategyConfig.threshold_percentile.toString());const n=this.element.querySelector("#enable-preview");n&&(n.checked=this.strategyConfig.enable_preview)}}destroy(){this.element&&(this.element.remove(),this.element=null),this.onStrategyChange=null}updateUIText(){this.element&&(this.render(),this.attachEventListeners(),this.selectStrategy(this.currentStrategy))}}})),Wi,on=f((()=>{Wi=class{constructor(e){this.button=null,this.onCenter=null,this.isVisible=!1,this.isAnimating=!1,this.onCenter=e||null}createButton(){this.button=document.createElement("div"),this.button.className="location-center-button",this.button.title="回到当前位置",this.button.style.display="none",this.button.style.cssText=`
            position: absolute;
            bottom: 24px;
            right: 24px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            z-index: 9999;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            user-select: none;
            -webkit-user-select: none;
        `;const e=document.createElement("span");return e.innerHTML="📍",e.style.fontSize="20px",e.style.lineHeight="1",this.button.appendChild(e),this.button.addEventListener("mouseenter",()=>{!this.isAnimating&&this.button&&(this.button.style.background="rgba(255, 255, 255, 1)",this.button.style.transform="scale(1.1)",this.button.style.boxShadow="0 4px 16px rgba(0, 0, 0, 0.2)")}),this.button.addEventListener("mouseleave",()=>{!this.isAnimating&&this.button&&(this.button.style.background="rgba(255, 255, 255, 0.95)",this.button.style.transform="scale(1)",this.button.style.boxShadow="0 2px 12px rgba(0, 0, 0, 0.15)")}),this.button.addEventListener("click",()=>this.handleClick()),this.button}handleClick(){this.isAnimating||!this.onCenter||(this.addRippleEffect(),this.onCenter&&this.onCenter())}addRippleEffect(){if(!this.button)return;const e=document.createElement("span");e.style.cssText=`
            position: absolute;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(74, 144, 226, 0.3);
            animation: ripple 0.6s ease-out;
            pointer-events: none;
        `;const t=document.createElement("style");t.textContent=`
            @keyframes ripple {
                0% {
                    transform: scale(0);
                    opacity: 1;
                }
                100% {
                    transform: scale(2);
                    opacity: 0;
                }
            }
        `,document.head.querySelector("style[data-ripple]")||(t.setAttribute("data-ripple","true"),document.head.appendChild(t)),this.button.appendChild(e),e.addEventListener("animationend",()=>{e.remove()})}addToContainer(e){this.button||(this.button=this.createButton()),e.appendChild(this.button)}show(){this.button&&(this.button.style.display="flex",this.isVisible=!0,console.log("✅ 回到中心按钮已显示"))}hide(){this.button&&(this.button.style.display="none",this.isVisible=!1,console.log("✅ 回到中心按钮已隐藏"))}setOnCenter(e){this.onCenter=e}destroy(){this.button&&this.button.parentNode&&this.button.parentNode.removeChild(this.button),this.button=null,this.onCenter=null,this.isVisible=!1}getElement(){return this.button}getIsVisible(){return this.isVisible}}})),C,it,st,Ji,ln=f((()=>{C=(function(e){return e[e.VERY_LOW=1]="VERY_LOW",e[e.LOW=2]="LOW",e[e.MEDIUM=3]="MEDIUM",e[e.HIGH=4]="HIGH",e[e.VERY_HIGH=5]="VERY_HIGH",e})({}),it={[C.VERY_LOW]:"#34c759",[C.LOW]:"#30d158",[C.MEDIUM]:"#0a84ff",[C.HIGH]:"#ff9500",[C.VERY_HIGH]:"#ff3b30"},st={[C.VERY_LOW]:"极低",[C.LOW]:"低",[C.MEDIUM]:"中等",[C.HIGH]:"高",[C.VERY_HIGH]:"极高"},Ji=class{constructor(e={}){this.element=null,this.showTimer=null,this.hideTimer=null,this.isVisible=!1,this.config={offset:e.offset??15,animationDuration:e.animationDuration??200,showDelay:e.showDelay??300,hideDelay:e.hideDelay??100,smartPositioning:e.smartPositioning??!0},this.mapContainer=null}init(e){this.mapContainer=e,this.createTooltip(),this.addStyles()}createTooltip(){this.mapContainer&&(this.element=document.createElement("div"),this.element.className="map-tooltip",this.element.style.cssText=`
            position: absolute;
            display: none;
            z-index: 1000;
            pointer-events: none;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            padding: 12px 16px;
            font-size: 13px;
            min-width: 200px;
            max-width: 280px;
            opacity: 0;
            transform: translateY(5px);
            transition: opacity ${this.config.animationDuration}ms ease,
                        transform ${this.config.animationDuration}ms ease;
        `,this.mapContainer.appendChild(this.element))}addStyles(){if(!document.querySelector("#map-tooltip-styles")){const e=document.createElement("style");e.id="map-tooltip-styles",e.textContent=`
                .map-tooltip .tooltip-header {
                    font-weight: 600;
                    color: var(--text-primary, #1d1d1f);
                    margin-bottom: 8px;
                    font-size: 14px;
                }

                .map-tooltip .tooltip-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin: 6px 0;
                    color: var(--text-secondary, #86868b);
                }

                .map-tooltip .tooltip-label {
                    font-weight: 500;
                    color: var(--text-secondary, #86868b);
                }

                .map-tooltip .tooltip-value {
                    font-weight: 600;
                    color: var(--text-primary, #1d1d1f);
                }

                .map-tooltip .tooltip-uncertainty {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid var(--border-color, #e5e5e5);
                }

                .map-tooltip .uncertainty-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    flex-shrink: 0;
                }

                .map-tooltip .uncertainty-text {
                    font-weight: 500;
                    color: var(--text-primary, #1d1d1f);
                }

                .map-tooltip .coordinate-row {
                    font-size: 12px;
                    color: var(--text-tertiary, #aeaeb2);
                    margin-top: 6px;
                }

                .map-tooltip .additional-info {
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid var(--border-color, #e5e5e5);
                    font-size: 12px;
                    color: var(--text-tertiary, #aeaeb2);
                }

                @media (prefers-color-scheme: dark) {
                    .map-tooltip {
                        background: rgba(28, 28, 30, 0.95) !important;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
                    }
                }
            `,document.head.appendChild(e)}}show(e,t,i){!this.element||!this.mapContainer||(this.clearTimers(),this.showTimer=setTimeout(()=>{if(!this.element)return;this.updateContent(e);const s=this.calculatePosition(t,i);this.element.style.left=`${s.x}px`,this.element.style.top=`${s.y}px`,this.element.style.display="block",this.element.offsetHeight,this.element.style.opacity="1",this.element.style.transform="translateY(0)",this.isVisible=!0},this.config.showDelay))}updateContent(e){if(!this.element)return;const{prediction:t,variance:i,uncertaintyLevel:s,coordinate:n,additionalInfo:a}=e;let r=`
            <div class="tooltip-header">预测结果</div>
        `;if(t!==void 0&&(r+=`
                <div class="tooltip-row">
                    <span class="tooltip-label">预测值:</span>
                    <span class="tooltip-value">${t.toFixed(4)}</span>
                </div>
            `),i!==void 0&&(r+=`
                <div class="tooltip-row">
                    <span class="tooltip-label">方差:</span>
                    <span class="tooltip-value">${i.toFixed(4)}</span>
                </div>
            `),s!==void 0){const o=it[s],l=st[s];r+=`
                <div class="tooltip-uncertainty">
                    <div class="uncertainty-dot" style="background-color: ${o};"></div>
                    <span class="uncertainty-text">不确定性: ${l}</span>
                </div>
            `}r+=`
            <div class="coordinate-row">
                坐标: ${n.longitude.toFixed(6)}, ${n.latitude.toFixed(6)}
            </div>
        `,a&&Object.keys(a).length>0&&(r+='<div class="additional-info">',Object.entries(a).forEach(([o,l])=>{r+=`
                    <div class="tooltip-row">
                        <span class="tooltip-label">${o}:</span>
                        <span class="tooltip-value">${l}</span>
                    </div>
                `}),r+="</div>"),this.element.innerHTML=r}calculatePosition(e,t){if(!this.mapContainer||!this.element)return{x:e,y:t};const i=this.mapContainer.getBoundingClientRect(),s=this.element.getBoundingClientRect();let n=e+this.config.offset,a=t-this.config.offset-s.height;return this.config.smartPositioning?(n+s.width>i.width-80&&(n=e-s.width-this.config.offset),n<0&&(n=this.config.offset),a<0&&(a=t+this.config.offset),a+s.height>i.height&&(a=i.height-s.height-this.config.offset),{x:n,y:a}):{x:n,y:a}}hide(){!this.element||!this.isVisible||(this.clearTimers(),this.hideTimer=setTimeout(()=>{this.element&&(this.element.style.opacity="0",this.element.style.transform="translateY(5px)",setTimeout(()=>{this.element&&(this.element.style.display="none"),this.isVisible=!1},this.config.animationDuration))},this.config.hideDelay))}clearTimers(){this.showTimer&&(clearTimeout(this.showTimer),this.showTimer=null),this.hideTimer&&(clearTimeout(this.hideTimer),this.hideTimer=null)}updateConfig(e){this.config={...this.config,...e}}static getUncertaintyColor(e){return it[e]}static getUncertaintyText(e){return st[e]}static calculateUncertaintyLevel(e,t=1){const i=Math.min(e/t,1);return i<.2?C.VERY_LOW:i<.4?C.LOW:i<.6?C.MEDIUM:i<.8?C.HIGH:C.VERY_HIGH}destroy(){this.clearTimers(),this.element&&this.element.parentNode&&this.element.parentNode.removeChild(this.element),this.element=null,this.mapContainer=null,this.isVisible=!1}}})),ie,Yi,cn=f((()=>{ie={default:{name:"默认",colors:["#34c759","#30d158","#0a84ff","#ff9500","#ff3b30"],labels:["极低","低","中等","高","极高"]},heatmap:{name:"热力图",colors:["#3b82f6","#8b5cf6","#ec4899","#f97316","#ef4444"],labels:["低","中低","中","中高","高"]},rainbow:{name:"彩虹",colors:["#ef4444","#f97316","#eab308","#22c55e","#3b82f6","#8b5cf6"],labels:["1","2","3","4","5","6"]},custom:{name:"自定义",colors:[],labels:[]}},Yi=class{constructor(e){this.element=null,this.config={position:"bottom-right",collapsible:!0,collapsed:!1,showValues:!0,...e},this.currentScheme="default",this.customScheme={name:"自定义",colors:[],labels:[]},this.isCollapsed=this.config.collapsed??!1,this.position=this.config.position??"bottom-right"}createLegend(){return this.element=document.createElement("div"),this.element.className="map-legend",this.element.dataset.position=this.position,this.addStyles(),this.render(),this.element}addStyles(){if(document.querySelector("#map-legend-styles"))return;const e=document.createElement("style");e.id="map-legend-styles",e.textContent=`
            .map-legend {
                position: absolute;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                padding: 12px;
                z-index: 1000;
                font-size: 12px;
                color: var(--text-primary, #1d1d1f);
                transition: all 0.3s ease;
            }

            @media (prefers-color-scheme: dark) {
                .map-legend {
                    background: rgba(28, 28, 30, 0.95);
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                }
            }

            .map-legend[data-position="top-left"] {
                top: 60px;
                left: 10px;
            }

            .map-legend[data-position="top-right"] {
                top: 60px;
                right: 80px; /* 380px(侧边栏宽度) + 32px(切换按钮宽度) */
            }

            .map-legend[data-position="bottom-left"] {
                bottom: 20px;
                left: 10px;
            }

            .map-legend[data-position="bottom-right"] {
                bottom: 20px;
                right: 80px; /* 380px(侧边栏宽度) + 32px(切换按钮宽度) */
            }

            .map-legend.collapsed {
                width: auto;
            }

            .map-legend .legend-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .map-legend .legend-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-controls {
                display: flex;
                gap: 4px;
            }

            .map-legend .legend-btn {
                width: 24px;
                height: 24px;
                border: none;
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 4px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                color: var(--text-secondary, #86868b);
                transition: all 0.2s ease;
            }

            .map-legend .legend-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-content {
                transition: all 0.3s ease;
                overflow: hidden;
            }

            .map-legend.collapsed .legend-content {
                max-height: 0;
                opacity: 0;
            }

            .map-legend .color-scale {
                display: flex;
                align-items: center;
                gap: 2px;
                height: 20px;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 8px;
            }

            .map-legend .color-bar {
                flex: 1;
                height: 100%;
            }

            .map-legend .legend-labels {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .map-legend .legend-label {
                font-size: 11px;
                color: var(--text-secondary, #86868b);
            }

            .map-legend .legend-items {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }

            .map-legend .legend-item {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 4px;
                border-radius: 4px;
                transition: background 0.2s ease;
            }

            .map-legend .legend-item:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .map-legend .legend-color {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                flex-shrink: 0;
            }

            .map-legend .legend-item-label {
                flex: 1;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-item-value {
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .map-legend .legend-unit {
                font-size: 11px;
                color: var(--text-tertiary, #aeaeb2);
                margin-left: 4px;
            }

            .map-legend .legend-scheme-selector {
                display: flex;
                gap: 8px;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid var(--border-color, #e5e5e5);
            }

            .map-legend .scheme-btn {
                padding: 4px 8px;
                border: 1px solid var(--border-color, #e5e5e5);
                background: var(--bg-primary, #ffffff);
                color: var(--text-primary, #1d1d1f);
                border-radius: 4px;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .map-legend .scheme-btn:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .map-legend .scheme-btn.active {
                background: var(--primary-color, #007aff);
                color: white;
                border-color: var(--primary-color, #007aff);
            }
        `,document.head.appendChild(e)}render(){if(!this.element)return;const{title:e,unit:t,ranges:i,showValues:s}=this.config;this.element.innerHTML=`
            <div class="legend-header">
                <span class="legend-title">${e}</span>
                <div class="legend-controls">
                    ${this.config.collapsible?`
                        <button class="legend-btn collapse-btn" title="折叠/展开">
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                                <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="2" fill="none"/>
                            </svg>
                        </button>
                    `:""}
                    <button class="legend-btn position-btn" title="更改位置">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                            <rect x="2" y="2" width="4" height="4" rx="1"/>
                            <rect x="8" y="2" width="4" height="4" rx="1"/>
                            <rect x="2" y="8" width="4" height="4" rx="1"/>
                            <rect x="8" y="8" width="4" height="4" rx="1"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="legend-content">
                ${this.renderColorScale()}
                ${this.renderLegendItems(i,s??!1,t)}
                ${this.renderSchemeSelector()}
            </div>
        `,this.bindEvents()}renderColorScale(){const e=ie[this.currentScheme];return`
            <div class="color-scale">
                ${(this.currentScheme==="custom"?this.customScheme.colors:e.colors).map(t=>`<div class="color-bar" style="background-color: ${t};"></div>`).join("")}
            </div>
        `}renderLegendItems(e,t,i){if(e.length===0)return"";const s=ie[this.currentScheme],n=this.currentScheme==="custom"?this.customScheme.labels:s.labels;return`
            <div class="legend-items">
                ${e.map((a,r)=>`
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: ${a.color};"></div>
                        <span class="legend-item-label">${n&&n[r]||`区间 ${r+1}`}</span>
                        ${t?`
                            <span class="legend-item-value">
                                ${a.min.toFixed(2)} - ${a.max.toFixed(2)}
                                ${i?`<span class="legend-unit">${i}</span>`:""}
                            </span>
                        `:""}
                    </div>
                `).join("")}
            </div>
        `}renderSchemeSelector(){return`
            <div class="legend-scheme-selector">
                ${Object.keys(ie).map(e=>`
                    <button class="scheme-btn ${e===this.currentScheme?"active":""}" data-scheme="${e}">
                        ${ie[e].name}
                    </button>
                `).join("")}
            </div>
        `}bindEvents(){if(!this.element)return;const e=this.element.querySelector(".collapse-btn"),t=this.element.querySelector(".position-btn"),i=this.element.querySelectorAll(".scheme-btn");e&&e.addEventListener("click",()=>this.toggleCollapse()),t&&t.addEventListener("click",()=>this.cyclePosition()),i.forEach(s=>{s.addEventListener("click",n=>{const a=n.target.dataset.scheme;a&&this.setColorScheme(a)})})}toggleCollapse(){if(!this.element)return;this.isCollapsed=!this.isCollapsed,this.element.classList.toggle("collapsed",this.isCollapsed);const e=this.element.querySelector(".collapse-btn");e&&(e.style.transform=this.isCollapsed?"rotate(-90deg)":"rotate(0deg)")}cyclePosition(){const e=["top-left","top-right","bottom-left","bottom-right"],t=(e.indexOf(this.position)+1)%e.length;this.setPosition(e[t])}setPosition(e){this.position=e,this.element&&(this.element.dataset.position=e)}setColorScheme(e){this.currentScheme=e,this.render()}setCustomScheme(e){this.customScheme=e,this.currentScheme="custom",this.render()}updateConfig(e){this.config={...this.config,...e},this.render()}getCurrentScheme(){return this.currentScheme}getPresetSchemes(){return ie}saveToStorage(){try{const e={position:this.position,currentScheme:this.currentScheme,customScheme:this.customScheme,isCollapsed:this.isCollapsed};localStorage.setItem("map-legend-config",JSON.stringify(e))}catch(e){console.error("保存图例配置失败:",e)}}loadFromStorage(){try{const e=localStorage.getItem("map-legend-config");if(e){const t=JSON.parse(e);t.position&&this.setPosition(t.position),t.currentScheme&&this.setColorScheme(t.currentScheme),t.customScheme&&(this.customScheme=t.customScheme),t.isCollapsed&&(this.isCollapsed=t.isCollapsed,this.element&&this.element.classList.add("collapsed"))}}catch(e){console.error("加载图例配置失败:",e)}}destroy(){this.element&&this.element.parentNode&&this.element.parentNode.removeChild(this.element),this.element=null}}})),G,Qi,dn=f((()=>{G=(function(e){return e.POINTS="points",e.PREDICTION="prediction",e.VARIANCE="variance",e.UNCERTAINTY="uncertainty",e.BOUNDARY="boundary",e.MARKER="marker",e})({}),Qi=class{constructor(e={}){this.container=null,this.configs=new Map,this.events=e,this.isCollapsed=!1}createPanel(){return this.container=document.createElement("div"),this.container.className="layer-comparison-panel",this.container.innerHTML=`
            <div class="panel-header">
                <h3 class="panel-title">图层对比</h3>
                <button class="collapse-btn" aria-label="收起/展开">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="2" fill="none"/>
                    </svg>
                </button>
            </div>
            <div class="panel-content">
                <div class="layers-list" id="layers-list"></div>
                <div class="panel-actions">
                    <button class="btn btn-secondary btn-sm" id="show-all-btn">显示全部</button>
                    <button class="btn btn-secondary btn-sm" id="hide-all-btn">隐藏全部</button>
                    <button class="btn btn-secondary btn-sm" id="reset-opacity-btn">重置透明度</button>
                </div>
            </div>
        `,this.addStyles(),this.bindEvents(),this.container}addStyles(){if(document.querySelector("#layer-comparison-styles"))return;const e=document.createElement("style");e.id="layer-comparison-styles",e.textContent=`
            .layer-comparison-panel {
                background: var(--bg-primary, #ffffff);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                transition: all 0.3s ease;
            }

            .layer-comparison-panel .panel-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 16px;
                background: var(--bg-secondary, #f5f5f7);
                border-bottom: 1px solid var(--border-color, #e5e5e5);
            }

            .layer-comparison-panel .panel-title {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .layer-comparison-panel .collapse-btn {
                background: none;
                border: none;
                padding: 4px;
                cursor: pointer;
                color: var(--text-secondary, #86868b);
                transition: transform 0.3s ease;
            }

            .layer-comparison-panel .collapse-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
                border-radius: 4px;
            }

            .layer-comparison-panel.collapsed .collapse-btn {
                transform: rotate(-90deg);
            }

            .layer-comparison-panel .panel-content {
                padding: 16px;
                max-height: 400px;
                overflow-y: auto;
                transition: max-height 0.3s ease, padding 0.3s ease;
            }

            .layer-comparison-panel.collapsed .panel-content {
                max-height: 0;
                padding: 0 16px;
                overflow: hidden;
            }

            .layer-comparison-panel .layers-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            .layer-comparison-panel .layer-item {
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 8px;
                padding: 12px;
                transition: all 0.2s ease;
            }

            .layer-comparison-panel .layer-item:hover {
                background: var(--bg-tertiary, #e8e8ed);
            }

            .layer-comparison-panel .layer-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }

            .layer-comparison-panel .layer-name {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 500;
                color: var(--text-primary, #1d1d1f);
            }

            .layer-comparison-panel .layer-visibility {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .layer-comparison-panel .visibility-toggle {
                width: 32px;
                height: 20px;
                background: var(--border-color, #e5e5e5);
                border-radius: 10px;
                position: relative;
                cursor: pointer;
                transition: background 0.2s ease;
            }

            .layer-comparison-panel .visibility-toggle.active {
                background: var(--primary-color, #007aff);
            }

            .layer-comparison-panel .visibility-toggle::after {
                content: '';
                position: absolute;
                width: 16px;
                height: 16px;
                background: white;
                border-radius: 50%;
                top: 2px;
                left: 2px;
                transition: transform 0.2s ease;
            }

            .layer-comparison-panel .visibility-toggle.active::after {
                transform: translateX(12px);
            }

            .layer-comparison-panel .layer-opacity {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .layer-comparison-panel .opacity-label {
                font-size: 12px;
                color: var(--text-secondary, #86868b);
                min-width: 45px;
            }

            .layer-comparison-panel .opacity-slider {
                flex: 1;
                -webkit-appearance: none;
                appearance: none;
                height: 4px;
                background: var(--border-color, #e5e5e5);
                border-radius: 2px;
                outline: none;
                cursor: pointer;
            }

            .layer-comparison-panel .opacity-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                appearance: none;
                width: 16px;
                height: 16px;
                background: var(--primary-color, #007aff);
                border-radius: 50%;
                cursor: pointer;
                transition: transform 0.1s ease;
            }

            .layer-comparison-panel .opacity-slider::-webkit-slider-thumb:hover {
                transform: scale(1.1);
            }

            .layer-comparison-panel .panel-actions {
                display: flex;
                gap: 8px;
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid var(--border-color, #e5e5e5);
            }

            .layer-comparison-panel .btn-sm {
                padding: 6px 12px;
                font-size: 12px;
                height: 28px;
            }

            .layer-comparison-panel .layer-type-badge {
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
                background: var(--bg-tertiary, #e8e8ed);
                color: var(--text-tertiary, #aeaeb2);
            }
        `,document.head.appendChild(e)}bindEvents(){if(!this.container)return;const e=this.container.querySelector(".collapse-btn"),t=this.container.querySelector("#show-all-btn"),i=this.container.querySelector("#hide-all-btn"),s=this.container.querySelector("#reset-opacity-btn");e&&e.addEventListener("click",()=>this.toggleCollapse()),t&&t.addEventListener("click",()=>this.showAllLayers()),i&&i.addEventListener("click",()=>this.hideAllLayers()),s&&s.addEventListener("click",()=>this.resetAllOpacity())}toggleCollapse(){this.container&&(this.isCollapsed=!this.isCollapsed,this.container.classList.toggle("collapsed",this.isCollapsed))}addLayer(e){this.configs.set(e.layerId,e),this.renderLayerList()}removeLayer(e){this.configs.delete(e),this.renderLayerList()}updateLayer(e,t){const i=this.configs.get(e);if(i){const s={...i,...t};this.configs.set(e,s),this.renderLayerList()}}setLayerVisibility(e,t){const i=this.configs.get(e);i&&(i.visible=t,this.configs.set(e,i),this.events.onVisibilityChange&&this.events.onVisibilityChange(e,t),this.renderLayerList())}setLayerOpacity(e,t){const i=this.configs.get(e);i&&(i.opacity=Math.max(0,Math.min(100,t)),this.configs.set(e,i),this.events.onOpacityChange&&this.events.onOpacityChange(e,i.opacity),this.renderLayerList())}moveLayer(e,t){const i=Array.from(this.configs.values()),s=i.findIndex(n=>n.layerId===e);s!==-1&&(t==="up"&&s>0?[i[s],i[s-1]]=[i[s-1],i[s]]:t==="down"&&s<i.length-1&&([i[s],i[s+1]]=[i[s+1],i[s]]),i.forEach((n,a)=>{n.zIndex=i.length-a,this.configs.set(n.layerId,n)}),this.events.onLayerOrderChange&&this.events.onLayerOrderChange(i),this.renderLayerList())}showAllLayers(){this.configs.forEach((e,t)=>{this.setLayerVisibility(t,!0)})}hideAllLayers(){this.configs.forEach((e,t)=>{this.setLayerVisibility(t,!1)})}resetAllOpacity(){this.configs.forEach((e,t)=>{this.setLayerOpacity(t,100)})}renderLayerList(){if(!this.container)return;const e=this.container.querySelector("#layers-list");if(!e)return;const t=Array.from(this.configs.values()).sort((i,s)=>s.zIndex-i.zIndex);if(e.innerHTML="",t.length===0){e.innerHTML=`
                <div style="text-align: center; color: var(--text-tertiary, #aeaeb2); padding: 20px;">
                    暂无图层
                </div>
            `;return}t.forEach(i=>{const s=this.createLayerItem(i);e.appendChild(s)})}createLayerItem(e){const t=document.createElement("div");t.className="layer-item",t.dataset.layerId=e.layerId,t.innerHTML=`
            <div class="layer-header">
                <div class="layer-name">
                    <span>${e.layerName}</span>
                    <span class="layer-type-badge">${this.getLayerTypeText(e.layerType)}</span>
                </div>
                <div class="layer-visibility">
                    <div class="visibility-toggle ${e.visible?"active":""}"></div>
                </div>
            </div>
            <div class="layer-opacity">
                <span class="opacity-label">透明度: ${e.opacity}%</span>
                <input type="range" class="opacity-slider" min="0" max="100" value="${e.opacity}">
            </div>
        `;const i=t.querySelector(".visibility-toggle"),s=t.querySelector(".opacity-slider");return i&&i.addEventListener("click",()=>{this.setLayerVisibility(e.layerId,!e.visible)}),s&&s.addEventListener("input",n=>{const a=parseInt(n.target.value);this.setLayerOpacity(e.layerId,a)}),t}getLayerTypeText(e){return{[G.POINTS]:"采样点",[G.PREDICTION]:"预测",[G.VARIANCE]:"方差",[G.UNCERTAINTY]:"不确定性",[G.BOUNDARY]:"边界",[G.MARKER]:"标记"}[e]||e}getAllConfigs(){return Array.from(this.configs.values())}clearAll(){this.configs.clear(),this.renderLayerList()}destroy(){this.container&&this.container.parentNode&&this.container.parentNode.removeChild(this.container),this.container=null,this.configs.clear()}}})),Xi,hn=f((()=>{ct(),Xi=class{constructor(e={},t={}){this.container=null,this.isActive=!1,this.currentType=null,this.points=[],this.segments=[],this.polygon=null,this.config={defaultUnit:e.defaultUnit??"m",showLabels:e.showLabels??!0,snapToFeatures:e.snapToFeatures??!1},this.events=t,this.mapProvider="arcgis",this.mapEngine=null}init(e,t){this.mapEngine=e,this.mapProvider=t}createPanel(){return this.container=document.createElement("div"),this.container.className="measure-tool-panel",this.container.innerHTML=`
            <div class="measure-header">
                <h3 class="measure-title">测量工具</h3>
                <button class="close-btn" aria-label="关闭">✕</button>
            </div>
            <div class="measure-content">
                <div class="measure-type-selector">
                    <button class="measure-type-btn" data-type="distance">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M2 10h16M10 2v16" stroke="currentColor" stroke-width="2"/>
                        </svg>
                        <span>距离</span>
                    </button>
                    <button class="measure-type-btn" data-type="area">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <rect x="2" y="2" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>
                        </svg>
                        <span>面积</span>
                    </button>
                </div>
                <div class="measure-status" id="measure-status"></div>
                <div class="measure-result" id="measure-result" style="display: none;">
                    <div class="result-item" id="total-result"></div>
                    <div class="result-details" id="result-details"></div>
                </div>
                <div class="measure-actions">
                    <button class="btn btn-secondary btn-sm" id="undo-btn" disabled>撤销上一点</button>
                    <button class="btn btn-secondary btn-sm" id="clear-btn" disabled>清除测量</button>
                    <button class="btn btn-primary btn-sm" id="export-btn" disabled>导出结果</button>
                </div>
            </div>
        `,this.addStyles(),this.bindEvents(),this.container}addStyles(){if(document.querySelector("#measure-tool-styles"))return;const e=document.createElement("style");e.id="measure-tool-styles",e.textContent=`
            .measure-tool-panel {
                position: absolute;
                top: 70px;
                left: 10px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                padding: 16px;
                z-index: 1000;
                min-width: 280px;
            }

            .measure-tool-panel .measure-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }

            .measure-tool-panel .measure-title {
                margin: 0;
                font-size: 16px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
            }

            .measure-tool-panel .close-btn {
                width: 24px;
                height: 24px;
                border: none;
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 4px;
                cursor: pointer;
                color: var(--text-secondary, #86868b);
                transition: all 0.2s ease;
            }

            .measure-tool-panel .close-btn:hover {
                background: var(--bg-tertiary, #e8e8ed);
            }

            .measure-tool-panel .measure-type-selector {
                display: flex;
                gap: 8px;
                margin-bottom: 12px;
            }

            .measure-tool-panel .measure-type-btn {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                padding: 10px;
                border: 1px solid var(--border-color, #e5e5e5);
                background: var(--bg-primary, #ffffff);
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                color: var(--text-primary, #1d1d1f);
            }

            .measure-tool-panel .measure-type-btn:hover {
                background: var(--bg-secondary, #f5f5f7);
            }

            .measure-tool-panel .measure-type-btn.active {
                background: var(--primary-color, #007aff);
                color: white;
                border-color: var(--primary-color, #007aff);
            }

            .measure-tool-panel .measure-status {
                font-size: 13px;
                color: var(--text-secondary, #86868b);
                margin-bottom: 12px;
                min-height: 20px;
            }

            .measure-tool-panel .measure-result {
                background: var(--bg-secondary, #f5f5f7);
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            }

            .measure-tool-panel .result-item {
                font-size: 14px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
                margin-bottom: 8px;
            }

            .measure-tool-panel .result-details {
                font-size: 12px;
                color: var(--text-secondary, #86868b);
            }

            .measure-tool-panel .result-detail-item {
                display: flex;
                justify-content: space-between;
                padding: 4px 0;
            }

            .measure-tool-panel .measure-actions {
                display: flex;
                gap: 8px;
            }

            .measure-tool-panel .btn-sm {
                flex: 1;
                padding: 8px 12px;
                font-size: 12px;
                height: 32px;
            }

            /* 测量标记样式 */
            .measure-marker {
                width: 12px;
                height: 12px;
                background: var(--primary-color, #007aff);
                border: 2px solid white;
                border-radius: 50%;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }

            .measure-label {
                background: rgba(255, 255, 255, 0.9);
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 600;
                color: var(--text-primary, #1d1d1f);
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                white-space: nowrap;
            }

            .measure-line {
                stroke: var(--primary-color, #007aff);
                stroke-width: 2;
                stroke-dasharray: 5, 5;
            }

            .measure-polygon {
                fill: var(--primary-color, #007aff);
                fill-opacity: 0.2;
                stroke: var(--primary-color, #007aff);
                stroke-width: 2;
            }
        `,document.head.appendChild(e)}bindEvents(){if(!this.container)return;const e=this.container.querySelector(".close-btn"),t=this.container.querySelectorAll(".measure-type-btn"),i=this.container.querySelector("#undo-btn"),s=this.container.querySelector("#clear-btn"),n=this.container.querySelector("#export-btn");e&&e.addEventListener("click",()=>this.deactivate()),t.forEach(a=>{a.addEventListener("click",r=>{const o=r.currentTarget.dataset.type;o&&this.activate(o)})}),i&&i.addEventListener("click",()=>this.undoLastPoint()),s&&s.addEventListener("click",()=>this.clear()),n&&n.addEventListener("click",()=>this.exportResult())}activate(e){if(this.isActive&&this.currentType===e){this.deactivate();return}if(this.isActive=!0,this.currentType=e,this.container){this.container.querySelectorAll(".measure-type-btn").forEach(i=>{i.classList.toggle("active",i.dataset.type===e)});const t=this.container.querySelector("#measure-status");t.textContent=e==="distance"?"点击地图添加测量点":"点击地图添加多边形顶点"}this.setupMapClickHandler()}deactivate(){if(this.isActive=!1,this.currentType=null,this.removeMapClickHandler(),this.container){this.container.querySelectorAll(".measure-type-btn").forEach(t=>{t.classList.remove("active")});const e=this.container.querySelector("#measure-status");e.textContent=""}}setupMapClickHandler(){if(!this.mapEngine)return;const e=t=>{if(!this.isActive)return;const i=this.extractMapPoint(t);i&&this.addPoint(i)};if(this.mapProvider==="arcgis"){const t=this.mapEngine.view;t&&(t.on("click",e),t._measureClickHandler=e)}else if(this.mapProvider==="amap"){const t=this.mapEngine.map;t&&(t.on("click",e),t._measureClickHandler=e)}}removeMapClickHandler(){if(this.mapEngine){if(this.mapProvider==="arcgis"){const e=this.mapEngine.view;e&&e._measureClickHandler&&(e.off("click",e._measureClickHandler),delete e._measureClickHandler)}else if(this.mapProvider==="amap"){const e=this.mapEngine.map;e&&e._measureClickHandler&&(e.off("click",e._measureClickHandler),delete e._measureClickHandler)}}}extractMapPoint(e){return this.mapProvider==="arcgis"?{longitude:e.mapPoint.longitude,latitude:e.mapPoint.latitude}:this.mapProvider==="amap"?{longitude:e.lnglat.lng,latitude:e.lnglat.lat}:null}addPoint(e){const t={coordinate:e,marker:this.createMarker(e),label:this.config.showLabels?this.createLabel(`${this.points.length+1}`,e):null};if(this.points.push(t),this.currentType==="distance"&&this.points.length>1){const i=this.points[this.points.length-2],s=this.createSegment(i,t);this.segments.push(s)}this.currentType==="area"&&this.points.length>=3&&this.updatePolygon(),this.updateUI(),this.events.onMeasureUpdate&&this.events.onMeasureUpdate(this.getResult())}createMarker(e){if(this.mapProvider==="arcgis")return R(async()=>{const{default:t}=await import("https://js.arcgis.com/4.28/@arcgis/core/Graphic.js");return{default:t}},[],import.meta.url).then(({default:t})=>R(async()=>{const{default:i}=await import("https://js.arcgis.com/4.28/@arcgis/core/geometry/Point.js");return{default:i}},[],import.meta.url).then(({default:i})=>R(async()=>{const{default:s}=await import("https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleMarkerSymbol.js");return{default:s}},[],import.meta.url).then(({default:s})=>{const n=new t({geometry:new i({longitude:e.longitude,latitude:e.latitude}),symbol:new s({color:[0,122,255],size:12,outline:{color:[255,255,255,1],width:2}})});return this.mapEngine.view.graphics.add(n),n})));if(this.mapProvider==="amap"){const t=new window.AMap.Marker({position:[e.longitude,e.latitude],content:'<div class="measure-marker"></div>',offset:new window.AMap.Pixel(-6,-6)});return this.mapEngine.map.add(t),t}return null}createLabel(e,t){const i=document.createElement("div");i.className="measure-label",i.textContent=e;const s=this.mapPointToScreen(t);if(s){i.style.position="absolute",i.style.left=`${s.x}px`,i.style.top=`${s.y-20}px`,i.style.zIndex="1000";const n=document.querySelector(".map-container");n&&n.appendChild(i)}return i}createSegment(e,t){const i=this.calculateDistance(e.coordinate,t.coordinate);return{from:e,to:t,line:this.createLine(e.coordinate,t.coordinate),distance:i,label:this.config.showLabels?this.createLabel(this.formatDistance(i),t.coordinate):null}}createLine(e,t){if(this.mapProvider==="arcgis")return R(async()=>{const{default:i}=await import("https://js.arcgis.com/4.28/@arcgis/core/Graphic.js");return{default:i}},[],import.meta.url).then(({default:i})=>R(async()=>{const{default:s}=await import("https://js.arcgis.com/4.28/@arcgis/core/geometry/Polyline.js");return{default:s}},[],import.meta.url).then(({default:s})=>R(async()=>{const{default:n}=await import("https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleLineSymbol.js");return{default:n}},[],import.meta.url).then(({default:n})=>{const a=new i({geometry:new s({paths:[[[e.longitude,e.latitude],[t.longitude,t.latitude]]]}),symbol:new n({color:[0,122,255],width:2,style:"dash"})});return this.mapEngine.view.graphics.add(a),a})));if(this.mapProvider==="amap"){const i=new window.AMap.Polyline({path:[[e.longitude,e.latitude],[t.longitude,t.latitude]],strokeColor:"#007aff",strokeWeight:2,strokeStyle:"dashed"});return this.mapEngine.map.add(i),i}return null}updatePolygon(){this.polygon&&this.polygon.polygon&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(this.polygon.polygon):this.mapProvider==="amap"&&this.mapEngine.map.remove(this.polygon.polygon));const e=this.points.map(n=>[n.coordinate.longitude,n.coordinate.latitude]),t=this.createPolygon(e),i=this.calculateArea(this.points.map(n=>n.coordinate)),s=this.config.showLabels?this.createLabel(this.formatArea(i),this.points[0].coordinate):null;this.polygon={points:this.points,polygon:t,area:i,label:s}}createPolygon(e){if(this.mapProvider==="arcgis")return R(async()=>{const{default:t}=await import("https://js.arcgis.com/4.28/@arcgis/core/Graphic.js");return{default:t}},[],import.meta.url).then(({default:t})=>R(async()=>{const{default:i}=await import("https://js.arcgis.com/4.28/@arcgis/core/geometry/Polygon.js");return{default:i}},[],import.meta.url).then(({default:i})=>R(async()=>{const{default:s}=await import("https://js.arcgis.com/4.28/@arcgis/core/symbols/SimpleFillSymbol.js");return{default:s}},[],import.meta.url).then(({default:s})=>{const n=new t({geometry:new i({rings:[e]}),symbol:new s({color:[0,122,255,.2],outline:{color:[0,122,255],width:2}})});return this.mapEngine.view.graphics.add(n),n})));if(this.mapProvider==="amap"){const t=new window.AMap.Polygon({path:e,strokeColor:"#007aff",strokeWeight:2,fillColor:"#007aff",fillOpacity:.2});return this.mapEngine.map.add(t),t}return null}calculateDistance(e,t){const s=e.latitude*Math.PI/180,n=t.latitude*Math.PI/180,a=(t.latitude-e.latitude)*Math.PI/180,r=(t.longitude-e.longitude)*Math.PI/180,o=Math.sin(a/2)*Math.sin(a/2)+Math.cos(s)*Math.cos(n)*Math.sin(r/2)*Math.sin(r/2);return 6371e3*(2*Math.atan2(Math.sqrt(o),Math.sqrt(1-o)))}calculateArea(e){if(e.length<3)return 0;let t=0;const i=e.length;for(let a=0;a<i;a++){const r=(a+1)%i;t+=e[a].latitude*e[r].longitude,t-=e[r].latitude*e[a].longitude}t=Math.abs(t)/2;const s=e.reduce((a,r)=>a+r.latitude,0)/i,n=111320*Math.cos(s*Math.PI/180);return t*n*n}formatDistance(e){return this.config.defaultUnit==="km"?`${(e/1e3).toFixed(2)} km`:`${e.toFixed(2)} m`}formatArea(e){return e>=1e6?`${(e/1e6).toFixed(2)} km²`:`${e.toFixed(2)} m²`}mapPointToScreen(e){if(!this.mapEngine)return null;if(this.mapProvider==="arcgis"){const t=this.mapEngine.view;if(t&&t.toScreen){const i=t.toScreen({longitude:e.longitude,latitude:e.latitude});return{x:i.x,y:i.y}}}else if(this.mapProvider==="amap"){const t=this.mapEngine.map;if(t&&t.lnglatToContainer){const i=t.lnglatToContainer(new window.AMap.LngLat(e.longitude,e.latitude));return{x:i.getX(),y:i.getY()}}}return null}updateUI(){if(!this.container)return;const e=this.container.querySelector("#undo-btn"),t=this.container.querySelector("#clear-btn"),i=this.container.querySelector("#export-btn"),s=this.container.querySelector("#measure-result"),n=this.container.querySelector("#total-result"),a=this.container.querySelector("#result-details");if(e.disabled=this.points.length===0,t.disabled=this.points.length===0,i.disabled=this.points.length===0,this.points.length>0)if(s.style.display="block",this.currentType==="distance"){const r=this.segments.reduce((o,l)=>o+l.distance,0);n.textContent=`总距离: ${this.formatDistance(r)}`,a.innerHTML=this.segments.map((o,l)=>`
                    <div class="result-detail-item">
                        <span>线段 ${l+1}</span>
                        <span>${this.formatDistance(o.distance)}</span>
                    </div>
                `).join("")}else this.currentType==="area"&&this.polygon&&(n.textContent=`面积: ${this.formatArea(this.polygon.area)}`,a.innerHTML=`
                    <div class="result-detail-item">
                        <span>顶点数</span>
                        <span>${this.points.length}</span>
                    </div>
                `);else s.style.display="none"}undoLastPoint(){if(this.points.length===0)return;const e=this.points.pop();if(e&&(e.marker&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(e.marker):this.mapProvider==="amap"&&this.mapEngine.map.remove(e.marker)),e.label&&e.label.parentNode&&e.label.parentNode.removeChild(e.label)),this.currentType==="distance"&&this.segments.length>0){const t=this.segments.pop();t&&(t.line&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(t.line):this.mapProvider==="amap"&&this.mapEngine.map.remove(t.line)),t.label&&t.label.parentNode&&t.label.parentNode.removeChild(t.label))}this.currentType==="area"&&this.points.length>=3?this.updatePolygon():this.currentType==="area"&&this.polygon&&(this.polygon.polygon&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(this.polygon.polygon):this.mapProvider==="amap"&&this.mapEngine.map.remove(this.polygon.polygon)),this.polygon.label&&this.polygon.label.parentNode&&this.polygon.label.parentNode.removeChild(this.polygon.label),this.polygon=null),this.updateUI(),this.events.onMeasureUpdate&&this.events.onMeasureUpdate(this.getResult())}clear(){this.points.forEach(e=>{e.marker&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(e.marker):this.mapProvider==="amap"&&this.mapEngine.map.remove(e.marker)),e.label&&e.label.parentNode&&e.label.parentNode.removeChild(e.label)}),this.segments.forEach(e=>{e.line&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(e.line):this.mapProvider==="amap"&&this.mapEngine.map.remove(e.line)),e.label&&e.label.parentNode&&e.label.parentNode.removeChild(e.label)}),this.polygon&&(this.polygon.polygon&&(this.mapProvider==="arcgis"?this.mapEngine.view.graphics.remove(this.polygon.polygon):this.mapProvider==="amap"&&this.mapEngine.map.remove(this.polygon.polygon)),this.polygon.label&&this.polygon.label.parentNode&&this.polygon.label.parentNode.removeChild(this.polygon.label)),this.points=[],this.segments=[],this.polygon=null,this.updateUI(),this.events.onMeasureClear&&this.events.onMeasureClear()}getResult(){const e=this.points.map(t=>t.coordinate);if(this.currentType==="distance"){const t=this.segments.reduce((i,s)=>i+s.distance,0);return{type:"distance",unit:this.config.defaultUnit==="km"?"km":"m",totalDistance:t,segments:this.segments,points:e}}else if(this.currentType==="area"&&this.polygon)return{type:"area",unit:this.polygon.area>=1e6?"km²":"m²",area:this.polygon.area,points:e};return{type:this.currentType,unit:this.config.defaultUnit==="km"?"km":"m",points:e}}exportResult(){const e=this.getResult();let t="";if(e.type==="distance"){t=`点序号,经度,纬度,距离
`;let a=0;e.points.forEach((r,o)=>{o>0&&e.segments&&e.segments[o-1]&&(a+=e.segments[o-1].distance),t+=`${o+1},${r.longitude},${r.latitude},${a.toFixed(2)}
`}),t+=`
总距离,${(e.totalDistance/(e.unit==="km"?1e3:1)).toFixed(2)} ${e.unit}
`}else e.type==="area"&&(t=`点序号,经度,纬度
`,e.points.forEach((a,r)=>{t+=`${r+1},${a.longitude},${a.latitude}
`}),t+=`
面积,${(e.area/(e.unit==="km²"?1e6:1)).toFixed(2)} ${e.unit}
`);const i=new Blob([t],{type:"text/csv;charset=utf-8;"}),s=URL.createObjectURL(i),n=document.createElement("a");n.href=s,n.download=`measure_${e.type}_${Date.now()}.csv`,n.click(),URL.revokeObjectURL(s)}destroy(){this.clear(),this.removeMapClickHandler(),this.container&&this.container.parentNode&&this.container.parentNode.removeChild(this.container),this.container=null}}})),J,pt=f((()=>{J=class he{constructor(){this.parameters=new Map,this.initialize()}static getInstance(){return he.instance||(he.instance=new he),he.instance}initialize(){this.bindSlider("grid-resolution",50,500),this.bindSlider("nlags",6,24),this.bindSlider("nugget",0,1),this.bindSlider("sill",0,10),this.bindSlider("range",0,100),this.loadSavedParameters()}bindSlider(t,i,s){const n=document.getElementById(`${t}-slider`),a=document.getElementById(t),r=document.getElementById(`${t}-value`);if(!n||!a){console.warn(`Slider or input not found for parameter: ${t}`);return}n.addEventListener("input",()=>{const l=parseFloat(n.value);a.value=n.value,r&&(r.textContent=n.value),this.parameters.set(t,l),this.validateParameter(t,l,i,s)}),a.addEventListener("input",()=>{const l=parseFloat(a.value);isNaN(l)||(n.value=a.value,r&&(r.textContent=a.value),this.parameters.set(t,l),this.validateParameter(t,l,i,s))});const o=parseFloat(a.value);this.parameters.set(t,o)}validateParameter(t,i,s,n){const a=document.getElementById(t);i<s||i>n?(a.classList.add("error"),this.showParameterWarning(t,`参数值必须在 ${s} 到 ${n} 之间`)):(a.classList.remove("error"),this.hideParameterWarning(t)),(t==="nugget"||t==="sill")&&((this.parameters.get("nugget")||0)>=(this.parameters.get("sill")||1)?this.showParameterWarning("sill","基台值应该大于变差值"):this.hideParameterWarning("sill"))}showParameterWarning(t,i){let s=document.getElementById(`${t}-warning`);if(!s){s=document.createElement("div"),s.id=`${t}-warning`,s.className="parameter-warning",s.style.cssText=`
                color: #ff3b30;
                font-size: 12px;
                margin-top: 4px;
                display: none;
            `;const n=document.getElementById(t);n&&n.parentElement?.appendChild(s)}s.textContent=i,s.style.display="block"}hideParameterWarning(t){const i=document.getElementById(`${t}-warning`);i&&(i.style.display="none")}getParameters(){return Object.fromEntries(this.parameters)}setParameter(t,i){const s=document.getElementById(`${t}-slider`),n=document.getElementById(t),a=document.getElementById(`${t}-value`);s&&(s.value=i.toString()),n&&(n.value=i.toString()),a&&(a.textContent=i.toString()),this.parameters.set(t,i)}resetToDefaults(){this.setParameter("grid-resolution",100),this.setParameter("nlags",12),this.setParameter("nugget",0),this.setParameter("sill",1),this.setParameter("range",10)}saveParameters(t){const i=JSON.parse(localStorage.getItem("savedParameters")||"[]");i.push({id:Date.now().toString(),name:t||`参数组合 ${i.length+1}`,parameters:this.getParameters(),timestamp:new Date().toISOString()}),localStorage.setItem("savedParameters",JSON.stringify(i))}loadSavedParameters(){const t=localStorage.getItem("lastUsedParameters");if(t)try{const i=JSON.parse(t);Object.entries(i).forEach(([s,n])=>{typeof n=="number"&&this.setParameter(s,n)})}catch(i){console.warn("Failed to load saved parameters:",i)}}saveAsLastUsed(){localStorage.setItem("lastUsedParameters",JSON.stringify(this.getParameters()))}validateAll(){const t=[];return(this.parameters.get("nugget")||0)>=(this.parameters.get("sill")||1)&&t.push("基台值应该大于变差值"),{valid:t.length===0,errors:t}}}})),j,Zi=f((()=>{j=class ue{constructor(){this.records=[],this.loadRecords()}static getInstance(){return ue.instance||(ue.instance=new ue),ue.instance}loadRecords(){try{const t=localStorage.getItem("parameterHistory");t&&(this.records=JSON.parse(t))}catch(t){console.error("Failed to load parameter history:",t),this.records=[]}}saveRecords(){try{localStorage.setItem("parameterHistory",JSON.stringify(this.records))}catch(t){console.error("Failed to save parameter history:",t)}}addRecord(t,i,s){const n={id:Date.now().toString(),name:t||`参数组合 ${this.records.length+1}`,parameters:i,score:s,timestamp:new Date().toISOString(),favorite:!1};return this.records.unshift(n),this.saveRecords(),n}getAllRecords(){return[...this.records]}getRecord(t){return this.records.find(i=>i.id===t)}updateRecord(t,i){const s=this.records.findIndex(n=>n.id===t);s!==-1&&(this.records[s]={...this.records[s],...i},this.saveRecords())}deleteRecord(t){this.records=this.records.filter(i=>i.id!==t),this.saveRecords()}toggleFavorite(t){const i=this.getRecord(t);i&&(i.favorite=!i.favorite,this.saveRecords())}getFavorites(){return this.records.filter(t=>t.favorite)}searchRecords(t){const i=t.toLowerCase();return this.records.filter(s=>s.name.toLowerCase().includes(i)||Object.entries(s.parameters).some(([n,a])=>`${n}:${a}`.toLowerCase().includes(i)))}filterRecords(t){return this.records.filter(i=>!(t.favorite!==void 0&&i.favorite!==t.favorite||t.minScore!==void 0&&i.score?.rmse&&i.score.rmse<t.minScore||t.maxScore!==void 0&&i.score?.rmse&&i.score.rmse>t.maxScore||t.startDate&&new Date(i.timestamp)<t.startDate||t.endDate&&new Date(i.timestamp)>t.endDate))}exportRecords(t){const i=t||this.records;return JSON.stringify(i,null,2)}importRecords(t){try{const i=JSON.parse(t);let s=0,n=0;return i.forEach(a=>{this.validateRecord(a)?(this.records.push(a),s++):n++}),this.saveRecords(),{success:s,failed:n}}catch(i){return console.error("Failed to import records:",i),{success:0,failed:0}}}validateRecord(t){return t&&typeof t.id=="string"&&typeof t.name=="string"&&typeof t.parameters=="object"&&typeof t.timestamp=="string"&&typeof t.favorite=="boolean"}clearAll(){this.records=[],this.saveRecords()}getStatistics(){const t=this.records.filter(a=>a.favorite).length,i=this.records.filter(a=>a.score?.rmse);let s,n;return i.length>0&&(s=i.reduce((a,r)=>a+(r.score?.rmse||0),0)/i.length,n=i.reduce((a,r)=>!a||(r.score?.rmse||0)<(a.score?.rmse||0)?r:a)),{total:this.records.length,favorites:t,avgRMSE:s,bestRMSE:n}}}})),es,un=f((()=>{pt(),Zi(),es=class pe{constructor(){this.combinations=[],this.container=null,this.initialize()}static getInstance(){return pe.instance||(pe.instance=new pe),pe.instance}initialize(){this.createContainer(),this.render()}createContainer(){const t=document.querySelector(".right-sidebar-content");if(!t){console.warn("Right sidebar content not found");return}this.container=document.createElement("div"),this.container.className="parameter-comparison-panel",this.container.innerHTML=`
            <div class="comparison-header">
                <h3 class="comparison-title">参数建议对比</h3>
                <div class="comparison-actions">
                    <button class="btn-small" id="refresh-comparison">刷新</button>
                    <button class="btn-small" id="auto-optimize">自动优化</button>
                </div>
            </div>
            <div id="comparison-table-container"></div>
        `,t.appendChild(this.container);const i=document.getElementById("refresh-comparison");i&&i.addEventListener("click",()=>this.refresh());const s=document.getElementById("auto-optimize");s&&s.addEventListener("click",()=>this.autoOptimize())}render(){if(!this.container)return;const t=this.container.querySelector("#comparison-table-container");if(!t)return;if(this.combinations.length===0){t.innerHTML=`
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    暂无参数建议，点击"刷新"获取
                </p>
            `;return}const i=document.createElement("table");i.className="comparison-table",i.innerHTML=`
            <thead>
                <tr>
                    <th>名称</th>
                    <th>RMSE</th>
                    <th>MAE</th>
                    <th>R²</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                ${this.combinations.map(s=>`
                    <tr class="${s.isBest?"best":""}" data-id="${s.id}">
                        <td>${s.name}</td>
                        <td class="score-cell ${s.isBest?"best":""}">${s.score.rmse.toFixed(4)}</td>
                        <td class="score-cell">${s.score.mae.toFixed(4)}</td>
                        <td class="score-cell">${s.score.r2.toFixed(4)}</td>
                        <td>
                            <button class="btn-small" data-action="apply" data-id="${s.id}">应用</button>
                            <button class="btn-small" data-action="save" data-id="${s.id}">保存</button>
                        </td>
                    </tr>
                `).join("")}
            </tbody>
        `,t.innerHTML="",t.appendChild(i),i.querySelectorAll("button[data-action]").forEach(s=>{s.addEventListener("click",n=>{const a=n.target,r=a.dataset.action,o=a.dataset.id;r==="apply"?this.applyCombination(o):r==="save"&&this.saveCombination(o)})})}setCombinations(t){this.combinations=t,this.markBest(),this.render()}markBest(){if(this.combinations.length===0)return;const t=Math.min(...this.combinations.map(i=>i.score.rmse));this.combinations.forEach(i=>{i.isBest=i.score.rmse===t})}applyCombination(t){const i=this.combinations.find(n=>n.id===t);if(!i)return;const s=J.getInstance();Object.entries(i.parameters).forEach(([n,a])=>{s.setParameter(n,a)}),alert(`已应用参数组合: ${i.name}`)}saveCombination(t){const i=this.combinations.find(s=>s.id===t);i&&(j.getInstance().addRecord(i.name,i.parameters,i.score),alert(`已保存参数组合: ${i.name}`))}refresh(){this.generateMockData()}autoOptimize(){this.generateMockData()}generateMockData(){this.setCombinations([{id:"1",name:"默认参数",parameters:{grid_resolution:100,nlags:12,nugget:0,sill:1,range:10},score:{rmse:.1234,mae:.0987,r2:.8765},isBest:!1},{id:"2",name:"优化参数1",parameters:{grid_resolution:150,nlags:15,nugget:.1,sill:1.2,range:12},score:{rmse:.0987,mae:.0765,r2:.9012},isBest:!1},{id:"3",name:"优化参数2",parameters:{grid_resolution:120,nlags:14,nugget:.05,sill:1.1,range:11},score:{rmse:.0876,mae:.0654,r2:.9234},isBest:!1}])}clear(){this.combinations=[],this.render()}}})),ts,pn=f((()=>{ts=class me{constructor(){this.container=null,this.parameters=new Map,this.initialize()}static getInstance(){return me.instance||(me.instance=new me),me.instance}initialize(){this.initializeParameterInfo(),this.createContainer(),this.render(),this.bindEvents()}initializeParameterInfo(){this.parameters.set("grid_resolution",{name:"grid_resolution",displayName:"网格分辨率",description:"控制输出栅格的精细程度。较大的值会产生更精细的网格，但会增加计算时间和内存使用。",range:{min:50,max:500},impact:"直接影响输出结果的精度和性能。分辨率越高，细节越丰富，但计算成本也越高。",warning:"超过300可能导致计算时间显著增加或内存不足。"}),this.parameters.set("nlags",{name:"nlags",displayName:"滞后数",description:"变异函数计算时将距离分组的数量。每个滞后代表一个距离范围，用于计算该范围内的变异值。",range:{min:6,max:24},impact:"影响变异函数的拟合质量。滞后数太少会导致拟合不准确，太多会增加计算负担。",relatedTo:["range"]}),this.parameters.set("nugget",{name:"nugget",displayName:"变差值",description:'表示距离为零时的变异值，通常由测量误差或微观变异引起。也称为"块金效应"。',range:{min:0,max:1},impact:"影响插值的平滑程度。变差值越大，插值结果越平滑，但可能忽略局部变异。",warning:"应该小于基台值(sill)。",relatedTo:["sill"]}),this.parameters.set("sill",{name:"sill",displayName:"基台值",description:"变异函数的渐近值，表示总方差。当距离超过范围值(range)时，变异值趋近于基台值。",range:{min:0,max:10},impact:"影响插值的整体变化幅度。基台值越大，空间变异越大。",warning:"应该大于变差值(nugget)。",relatedTo:["nugget"]}),this.parameters.set("range",{name:"range",displayName:"范围值",description:"变异函数达到基台值时的距离，表示空间相关的最大距离。超过这个距离的点相关性很弱。",range:{min:0,max:100},impact:"影响插值的影响范围。范围值越大，远距离的点对插值结果影响越大。",relatedTo:["nlags"]})}createContainer(){const t=document.querySelector(".right-sidebar-content");if(!t){console.warn("Right sidebar content not found");return}this.container=document.createElement("div"),this.container.className="parameter-info-panel",this.container.innerHTML=`
            <div class="info-panel-header">
                <h3 class="info-panel-title">参数说明</h3>
            </div>
            <div id="parameter-info-list"></div>
        `,t.appendChild(this.container)}render(){if(!this.container)return;const t=this.container.querySelector("#parameter-info-list");t&&(t.innerHTML=Array.from(this.parameters.values()).map(i=>`
            <div class="parameter-info-item" data-param="${i.name}">
                <div class="parameter-info-item-header">
                    <span class="parameter-info-name">${i.displayName}</span>
                    <span class="parameter-info-badge">${i.range.min} - ${i.range.max}</span>
                </div>
                <div class="parameter-info-description">${i.description}</div>
                <div class="parameter-info-range">取值范围: ${i.range.min} ~ ${i.range.max}</div>
                <div class="parameter-info-impact">
                    <strong>影响:</strong> ${i.impact}
                </div>
                ${i.warning?`
                    <div class="parameter-info-warning">
                        <strong>⚠️ 注意:</strong> ${i.warning}
                    </div>
                `:""}
                ${i.relatedTo&&i.relatedTo.length>0?`
                    <div class="parameter-info-related" style="font-size: 12px; color: var(--text-tertiary); margin-top: 4px;">
                        <strong>相关参数:</strong> ${i.relatedTo.map(s=>this.parameters.get(s)?.displayName||s).join(", ")}
                    </div>
                `:""}
            </div>
        `).join(""))}bindEvents(){document.querySelectorAll('input[type="range"], input[type="number"]').forEach(t=>{t.addEventListener("input",()=>{this.updateWarnings()})})}updateWarnings(){if(!this.container)return;const t=parseFloat(document.getElementById("grid-resolution")?.value||"100"),i=parseFloat(document.getElementById("nugget")?.value||"0"),s=parseFloat(document.getElementById("sill")?.value||"1"),n=this.container.querySelector('.parameter-info-item[data-param="grid_resolution"]');n&&t>300?n.classList.add("warning"):n?.classList.remove("warning");const a=this.container.querySelector('.parameter-info-item[data-param="nugget"]'),r=this.container.querySelector('.parameter-info-item[data-param="sill"]');i>=s?(a?.classList.add("warning"),r?.classList.add("warning")):(a?.classList.remove("warning"),r?.classList.remove("warning"))}getParameterInfo(t){return this.parameters.get(t)}getAllParameterInfo(){return Array.from(this.parameters.values())}showParameterDetail(t){if(!this.parameters.get(t))return;const i=this.container?.querySelector(`.parameter-info-item[data-param="${t}"]`);i&&(i.scrollIntoView({behavior:"smooth",block:"center"}),i.classList.add("highlight"),setTimeout(()=>{i.classList.remove("highlight")},2e3))}getOptimizationSuggestions(t){const i=[];return(t.grid_resolution||100)>300&&i.push("网格分辨率较高，建议降低至200以下以提高性能。"),(t.nugget||0)>=(t.sill||1)&&i.push("变差值应小于基台值，建议调整参数。"),(t.nlags||12)<10&&i.push("滞后数较少，建议增加至12-15以提高拟合精度。"),i}}})),is,mn=f((()=>{pt(),Zi(),un(),pn(),is=class ge{constructor(){this.container=null,this.activeTab="adjustment",this.initialize()}static getInstance(){return ge.instance||(ge.instance=new ge),ge.instance}initialize(){this.createContainer(),this.render(),this.bindEvents()}createContainer(){const t=document.querySelector(".right-sidebar-content");if(!t){console.warn("Right sidebar content not found");return}this.container=document.createElement("div"),this.container.className="tab-container",this.container.innerHTML=`
            <div class="tab-header">
                <button class="tab-btn active" data-tab="adjustment">参数调整</button>
                <button class="tab-btn" data-tab="comparison">参数对比</button>
                <button class="tab-btn" data-tab="history">历史记录</button>
                <button class="tab-btn" data-tab="info">参数说明</button>
            </div>
            <div class="tab-content active" id="tab-adjustment">
                <div id="adjustment-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-comparison">
                <div id="comparison-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-history">
                <div id="history-panel-content"></div>
            </div>
            <div class="tab-content" id="tab-info">
                <div id="info-panel-content"></div>
            </div>
        `,t.appendChild(this.container)}render(){this.initializeAdjustmentPanel(),this.initializeComparisonPanel(),this.initializeHistoryPanel(),this.initializeInfoPanel()}initializeAdjustmentPanel(){const t=document.getElementById("adjustment-panel-content");if(!t)return;t.innerHTML=`
            <div style="padding: 12px;">
                <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600;">快速操作</h4>
                <div style="display: flex; gap: 8px; margin-bottom: 16px;">
                    <button class="btn-small" id="reset-params">重置默认</button>
                    <button class="btn-small" id="save-params">保存参数</button>
                    <button class="btn-small" id="load-params">加载参数</button>
                </div>
                <div id="param-validation-status"></div>
            </div>
        `;const i=document.getElementById("reset-params");i&&i.addEventListener("click",()=>this.resetParameters());const s=document.getElementById("save-params");s&&s.addEventListener("click",()=>this.saveParameters());const n=document.getElementById("load-params");n&&n.addEventListener("click",()=>this.loadParameters())}initializeComparisonPanel(){const t=document.getElementById("comparison-panel-content");t&&(t.innerHTML=`
            <div id="comparison-panel-wrapper"></div>
        `,es.getInstance())}initializeHistoryPanel(){const t=document.getElementById("history-panel-content");t&&(t.innerHTML=`
            <div style="padding: 12px;">
                <div class="history-controls">
                    <input type="text" class="history-search" id="history-search" placeholder="搜索历史记录...">
                    <button class="btn-small" id="export-history">导出</button>
                    <button class="btn-small" id="import-history">导入</button>
                </div>
                <div id="history-list" class="history-list"></div>
            </div>
        `,document.getElementById("history-search")?.addEventListener("input",i=>{this.searchHistory(i.target.value)}),document.getElementById("export-history")?.addEventListener("click",()=>{this.exportHistory()}),document.getElementById("import-history")?.addEventListener("click",()=>{this.importHistory()}),this.loadHistoryList())}initializeInfoPanel(){const t=document.getElementById("info-panel-content");t&&(t.innerHTML=`
            <div id="info-panel-wrapper"></div>
        `,ts.getInstance())}bindEvents(){this.container?.querySelectorAll(".tab-btn").forEach(t=>{t.addEventListener("click",i=>{const s=i.target;this.switchTab(s.dataset.tab||"adjustment")})})}switchTab(t){this.activeTab=t,this.container?.querySelectorAll(".tab-btn").forEach(i=>{i.dataset.tab===t?i.classList.add("active"):i.classList.remove("active")}),this.container?.querySelectorAll(".tab-content").forEach(i=>{i.id===`tab-${t}`?i.classList.add("active"):i.classList.remove("active")})}resetParameters(){J.getInstance().resetToDefaults(),this.updateValidationStatus()}saveParameters(){const t=prompt("请输入参数组合名称:");if(!t)return;const i=J.getInstance();i.saveParameters(t),j.getInstance().addRecord(t,i.getParameters()),alert("参数已保存"),this.loadHistoryList()}loadParameters(){this.switchTab("history")}updateValidationStatus(){const t=document.getElementById("param-validation-status");if(!t)return;const i=J.getInstance().validateAll();i.valid?t.innerHTML=`
                <div style="padding: 8px 12px; background-color: rgba(52, 199, 89, 0.1); border-radius: 6px; color: #34c759; font-size: 12px;">
                    ✓ 所有参数有效
                </div>
            `:t.innerHTML=`
                <div style="padding: 8px 12px; background-color: rgba(255, 59, 48, 0.1); border-radius: 6px; color: #ff3b30; font-size: 12px;">
                    ✗ ${i.errors.join("; ")}
                </div>
            `}loadHistoryList(){const t=document.getElementById("history-list");if(!t)return;const i=j.getInstance(),s=i.getAllRecords();if(s.length===0){t.innerHTML=`
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    暂无历史记录
                </p>
            `;return}t.innerHTML=s.map(n=>`
            <div class="history-item ${n.favorite?"favorite":""}">
                <div class="history-item-header">
                    <span class="history-item-title">${n.name}</span>
                    <div class="history-item-actions">
                        <button class="history-btn-icon ${n.favorite?"favorite":""}" data-action="favorite" data-id="${n.id}">
                            ${n.favorite?"★":"☆"}
                        </button>
                        <button class="history-btn-icon" data-action="apply" data-id="${n.id}">应用</button>
                        <button class="history-btn-icon" data-action="delete" data-id="${n.id}">×</button>
                    </div>
                </div>
                <div class="history-item-body">
                    ${Object.entries(n.parameters).map(([a,r])=>`
                        <div class="history-param-row">
                            <span>${a}:</span>
                            <span class="history-param-value">${r}</span>
                        </div>
                    `).join("")}
                </div>
                <div class="history-item-footer">
                    <span class="history-item-time">${new Date(n.timestamp).toLocaleString()}</span>
                    ${n.score?`<span class="history-item-score">RMSE: ${n.score.rmse?.toFixed(4)}</span>`:""}
                </div>
            </div>
        `).join(""),t.querySelectorAll("button[data-action]").forEach(n=>{n.addEventListener("click",a=>{const r=a.target,o=r.dataset.action,l=r.dataset.id;o==="favorite"?(i.toggleFavorite(l),this.loadHistoryList()):o==="apply"?this.applyHistoryRecord(l):o==="delete"&&confirm("确定要删除这条记录吗？")&&(i.deleteRecord(l),this.loadHistoryList())})})}applyHistoryRecord(t){const i=j.getInstance().getRecord(t);if(!i)return;const s=J.getInstance();Object.entries(i.parameters).forEach(([n,a])=>{s.setParameter(n,a)}),alert(`已应用参数组合: ${i.name}`),this.switchTab("adjustment")}searchHistory(t){const i=j.getInstance().searchRecords(t),s=document.getElementById("history-list");if(s){if(i.length===0){s.innerHTML=`
                <p style="color: var(--text-tertiary); text-align: center; padding: 20px;">
                    未找到匹配的记录
                </p>
            `;return}this.loadHistoryList()}}exportHistory(){const t=j.getInstance().exportRecords(),i=new Blob([t],{type:"application/json"}),s=URL.createObjectURL(i),n=document.createElement("a");n.href=s,n.download=`parameter-history-${Date.now()}.json`,n.click(),URL.revokeObjectURL(s)}importHistory(){const t=document.createElement("input");t.type="file",t.accept=".json",t.onchange=i=>{const s=i.target.files?.[0];if(!s)return;const n=new FileReader;n.onload=a=>{const r=a.target?.result,o=j.getInstance().importRecords(r);alert(`导入成功: ${o.success} 条，失败: ${o.failed} 条`),this.loadHistoryList()},n.readAsText(s)},t.click()}}})),fi,ss,gn=f((()=>{dt(),fi=class{constructor(){this.panel=null,this.backdrop=null,this.isInitialized=!1}async init(){this.isInitialized||(this.createPanel(),this.createBackdrop(),this.bindEvents(),this.isInitialized=!0)}createPanel(){const e=document.createElement("div");e.id="cache-management-panel",e.className="cache-management-panel",e.innerHTML=`
            <div class="cache-panel-header">
                <h2 class="cache-panel-title">缓存管理</h2>
                <button class="cache-panel-close" aria-label="关闭面板">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="cache-panel-content">
                <div class="cache-status-section">
                    <h3 class="cache-section-title">网络状态</h3>
                    <div class="cache-status-indicator">
                        <span class="cache-status-icon"></span>
                        <span class="cache-status-text">检测中...</span>
                    </div>
                </div>

                <div class="cache-usage-section">
                    <h3 class="cache-section-title">存储使用情况</h3>
                    <div class="cache-usage-bar">
                        <div class="cache-usage-fill"></div>
                    </div>
                    <div class="cache-usage-info">
                        <span class="cache-usage-used">0 B</span>
                        <span class="cache-usage-total">/ 50 MB</span>
                    </div>
                </div>

                <div class="cache-list-section">
                    <h3 class="cache-section-title">缓存详情</h3>
                    <div class="cache-list"></div>
                </div>

                <div class="cache-actions-section">
                    <button class="cache-btn cache-btn-primary" id="cache-clean-expired">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                        </svg>
                        清理过期缓存
                    </button>
                    <button class="cache-btn cache-btn-danger" id="cache-clear-all">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                        清除所有缓存
                    </button>
                </div>

                <div class="cache-pending-section">
                    <h3 class="cache-section-title">待同步操作</h3>
                    <div class="cache-pending-info">
                        <span class="cache-pending-count">0</span>
                        <span class="cache-pending-text">个操作等待同步</span>
                    </div>
                    <button class="cache-btn cache-btn-secondary" id="cache-sync-now">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                        立即同步
                    </button>
                </div>
            </div>
        `,document.body.appendChild(e),this.panel=e}createBackdrop(){const e=document.createElement("div");e.id="cache-management-backdrop",e.className="cache-panel-backdrop",document.body.appendChild(e),this.backdrop=e}bindEvents(){!this.panel||!this.backdrop||(this.panel.querySelector(".cache-panel-close")?.addEventListener("click",()=>this.hide()),this.backdrop.addEventListener("click",()=>this.hide()),this.panel.querySelector("#cache-clean-expired")?.addEventListener("click",()=>this.cleanExpiredCache()),this.panel.querySelector("#cache-clear-all")?.addEventListener("click",()=>this.clearAllCache()),this.panel.querySelector("#cache-sync-now")?.addEventListener("click",()=>this.syncNow()))}async show(){this.isInitialized||await this.init(),!(!this.panel||!this.backdrop)&&(this.panel.classList.add("show"),this.backdrop.classList.add("show"),await this.refreshData())}hide(){!this.panel||!this.backdrop||(this.panel.classList.remove("show"),this.backdrop.classList.remove("show"))}async refreshData(){if(!this.panel)return;const e=this.panel.querySelector(".cache-status-icon"),t=this.panel.querySelector(".cache-status-text");if(e&&t){const i=I.isOnline;e.className=`cache-status-icon ${i?"online":"offline"}`,t.textContent=i?"已连接网络":"离线模式"}await this.updateStorageUsage(),await this.updateCacheList(),await this.updatePendingCount()}async updateStorageUsage(){if(this.panel)try{const e=await this.estimateStorageSize(),t=e/(50*1024*1024)*100,i=this.panel.querySelector(".cache-usage-fill"),s=this.panel.querySelector(".cache-usage-used");i&&(i.style.width=`${t}%`,i.className=`cache-usage-fill ${t>80?"warning":""}`),s&&(s.textContent=this.formatBytes(e))}catch(e){console.error("更新存储使用情况失败:",e)}}async updateCacheList(){if(!this.panel)return;const e=this.panel.querySelector(".cache-list");if(e)try{e.innerHTML=(await this.getCacheInfo()).map(t=>`
                <div class="cache-item">
                    <div class="cache-item-header">
                        <span class="cache-item-name">${t.name}</span>
                        <span class="cache-item-size">${this.formatBytes(t.size)}</span>
                    </div>
                    <div class="cache-item-details">
                        <span class="cache-item-count">${t.count} 项</span>
                        <span class="cache-item-desc">${t.description}</span>
                    </div>
                </div>
            `).join("")}catch(t){console.error("更新缓存列表失败:",t)}}async updatePendingCount(){if(!this.panel)return;const e=this.panel.querySelector(".cache-pending-count");if(e)try{e.textContent=(await I.getPendingCount()).toString()}catch(t){console.error("更新待同步操作数失败:",t)}}async cleanExpiredCache(){if(!this.panel)return;const e=this.panel.querySelector("#cache-clean-expired"),t=e.innerHTML;try{e.disabled=!0,e.innerHTML='<span class="cache-btn-loading"></span> 清理中...',console.log("清理过期缓存..."),await new Promise(i=>setTimeout(i,1e3)),await this.refreshData(),this.showToast("过期缓存已清理")}catch(i){console.error("清理过期缓存失败:",i),this.showToast("清理失败，请重试","error")}finally{e.disabled=!1,e.innerHTML=t}}async clearAllCache(){if(!confirm("确定要清除所有缓存吗？此操作不可撤销。")||!this.panel)return;const e=this.panel.querySelector("#cache-clear-all"),t=e.innerHTML;try{e.disabled=!0,e.innerHTML='<span class="cache-btn-loading"></span> 清除中...',await I.clearAll(),await this.refreshData(),this.showToast("所有缓存已清除")}catch(i){console.error("清除缓存失败:",i),this.showToast("清除失败，请重试","error")}finally{e.disabled=!1,e.innerHTML=t}}async syncNow(){if(!this.panel)return;const e=this.panel.querySelector("#cache-sync-now"),t=e.innerHTML;try{e.disabled=!0,e.innerHTML='<span class="cache-btn-loading"></span> 同步中...',await I.sync(),await this.refreshData(),this.showToast("同步完成")}catch(i){console.error("同步失败:",i),this.showToast("同步失败，请重试","error")}finally{e.disabled=!1,e.innerHTML=t}}async getCacheInfo(){return[{name:"项目数据",size:await this.estimateStoreSize("projects"),count:await this.estimateStoreCount("projects"),description:"本地保存的项目信息"},{name:"采样点",size:await this.estimateStoreSize("points"),count:await this.estimateStoreCount("points"),description:"离线采样的点位数据"},{name:"结果缓存",size:await this.estimateStoreSize("results"),count:await this.estimateStoreCount("results"),description:"插值和计算结果"}]}async estimateStorageSize(){return(await this.getCacheInfo()).reduce((e,t)=>e+t.size,0)}async estimateStoreSize(e){return{projects:1024*1024,points:5*1024*1024,results:10*1024*1024}[e]||0}async estimateStoreCount(e){return{projects:3,points:150,results:8}[e]||0}formatBytes(e){if(e===0)return"0 B";const t=1024,i=["B","KB","MB","GB"],s=Math.floor(Math.log(e)/Math.log(t));return parseFloat((e/Math.pow(t,s)).toFixed(2))+" "+i[s]}showToast(e,t="success"){const i=document.createElement("div");i.className=`cache-toast cache-toast-${t}`,i.textContent=e,i.style.cssText=`
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            border-radius: 8px;
            background: ${t==="success"?"rgba(52,199,89,0.9)":"rgba(255,59,48,0.9)"};
            color: white;
            font-size: 14px;
            font-weight: 500;
            z-index: 10001;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            animation: slideUp 0.3s ease-out;
        `,document.body.appendChild(i),setTimeout(()=>{i.style.animation="slideDown 0.3s ease-out",setTimeout(()=>i.remove(),300)},2e3)}destroy(){this.panel&&(this.panel.remove(),this.panel=null),this.backdrop&&(this.backdrop.remove(),this.backdrop=null),this.isInitialized=!1}},ss=new fi})),yi,ns,fn=f((()=>{dt(),yi=class{constructor(){this.banner=null,this.isInitialized=!1,this.isOnline=!0,this.removeListener=null}async init(){this.isInitialized||(this.createBanner(),this.bindEvents(),this.isInitialized=!0,this.removeListener=I.onStatusChange(e=>{this.handleNetworkChange(e)}),this.isOnline=I.isOnline,this.updateBannerVisibility())}createBanner(){const e=document.createElement("div");e.id="offline-mode-banner",e.className="offline-mode-banner",e.innerHTML=`
            <div class="offline-banner-content">
                <div class="offline-banner-header">
                    <div class="offline-banner-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0119 12.55M5 12.55a10.94 10.94 0 015.17-2.39M10.71 5.05A16 16 0 0122.58 9M1.42 9a15.91 15.91 0 014.7-2.88M8.53 16.11a6 6 0 016.95 0M12 20h.01"/>
                        </svg>
                    </div>
                    <div class="offline-banner-title">
                        <h3>离线模式</h3>
                        <p class="offline-banner-subtitle">您当前处于离线状态，部分功能受限</p>
                    </div>
                    <button class="offline-banner-close" aria-label="关闭提示">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <div class="offline-banner-features">
                    <div class="offline-feature-list"></div>
                </div>

                <div class="offline-banner-actions">
                    <button class="offline-btn offline-btn-primary" id="offline-view-cache">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        查看缓存数据
                    </button>
                    <button class="offline-btn offline-btn-secondary" id="offline-manage-cache">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
                            <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        </svg>
                        管理缓存
                    </button>
                </div>
            </div>
        `,document.body.appendChild(e),this.banner=e,this.updateFeatureList()}bindEvents(){this.banner&&(this.banner.querySelector(".offline-banner-close")?.addEventListener("click",()=>this.dismiss()),this.banner.querySelector("#offline-view-cache")?.addEventListener("click",()=>this.handleViewCache()),this.banner.querySelector("#offline-manage-cache")?.addEventListener("click",()=>this.handleManageCache()))}handleNetworkChange(e){this.isOnline=e,this.updateBannerVisibility()}updateBannerVisibility(){this.banner&&(this.isOnline?(this.banner.classList.add("hidden"),setTimeout(()=>{this.isOnline&&(this.banner.style.display="none")},2e3)):(this.banner.style.display="block",setTimeout(()=>{this.isOnline||this.banner.classList.remove("hidden")},100)))}updateFeatureList(){if(!this.banner)return;const e=this.banner.querySelector(".offline-feature-list");e&&(e.innerHTML=[{name:"查看已有项目",available:!0,icon:"📁",description:"可以浏览和查看本地缓存的项目信息"},{name:"数据采样",available:!0,icon:"📍",description:"支持离线单点采样和区域采样"},{name:"地图浏览",available:!0,icon:"🗺️",description:"可以查看已缓存的地图数据"},{name:"参数调整",available:!0,icon:"⚙️",description:"可以调整插值参数配置"},{name:"数据上传",available:!1,icon:"📤",description:"需要网络连接，操作已加入离线队列"},{name:"插值计算",available:!1,icon:"🔄",description:"需要网络连接，请求已缓存"},{name:"结果导出",available:!0,icon:"💾",description:"可以导出已缓存的计算结果"},{name:"新建项目",available:!1,icon:"➕",description:"需要网络连接"}].map(t=>`
            <div class="offline-feature-item ${t.available?"available":"unavailable"}">
                <div class="offline-feature-icon">${t.icon}</div>
                <div class="offline-feature-info">
                    <span class="offline-feature-name">${t.name}</span>
                    <span class="offline-feature-desc">${t.description}</span>
                </div>
                <div class="offline-feature-status">
                    ${t.available?"✅":"❌"}
                </div>
            </div>
        `).join(""))}handleViewCache(){const e=new CustomEvent("offline-view-cache",{bubbles:!0,detail:{source:"offline-banner"}});document.dispatchEvent(e)}handleManageCache(){const e=new CustomEvent("offline-manage-cache",{bubbles:!0,detail:{source:"offline-banner"}});document.dispatchEvent(e)}dismiss(){this.banner&&(this.banner.classList.add("dismissed"),this.isOnline||setTimeout(()=>{this.isOnline||this.banner.classList.remove("dismissed")},300*1e3))}show(){this.banner&&(this.banner.classList.remove("hidden","dismissed"),this.banner.style.display="block")}hide(){this.banner&&this.banner.classList.add("hidden")}destroy(){this.removeListener&&(this.removeListener(),this.removeListener=null),this.banner&&(this.banner.remove(),this.banner=null),this.isInitialized=!1}},ns=new yi})),as,yn=f((()=>{as=class{constructor(e="arcgis",t){this.button=null,this.currentProvider="arcgis",this.onSwitch=null,this.isSwitching=!1,this.currentProvider=e,this.onSwitch=t||null}createButton(){this.button=document.createElement("div"),this.button.className="map-engine-switcher",this.button.title="切换地图引擎",this.button.style.cssText=`
            position: absolute;
            top: 16px;
            right: 100px;
            padding: 8px 16px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            color: #333;
            z-index: 9999;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            gap: 6px;
        `;const e=document.createElement("span");e.innerHTML="🗺️",e.style.fontSize="16px";const t=document.createElement("span");return t.className="switcher-text",this.updateButtonText(t),this.button.appendChild(e),this.button.appendChild(t),this.button.addEventListener("mouseenter",()=>{!this.isSwitching&&this.button&&(this.button.style.background="rgba(255, 255, 255, 1)",this.button.style.transform="translateY(-2px)",this.button.style.boxShadow="0 4px 12px rgba(0, 0, 0, 0.2)")}),this.button.addEventListener("mouseleave",()=>{!this.isSwitching&&this.button&&(this.button.style.background="rgba(255, 255, 255, 0.95)",this.button.style.transform="translateY(0)",this.button.style.boxShadow="0 2px 8px rgba(0, 0, 0, 0.15)")}),this.button.addEventListener("click",()=>this.handleClick()),this.button}updateButtonText(e){e.textContent=`${this.currentProvider==="arcgis"?"ArcGIS":"高德"}`}async handleClick(){if(this.isSwitching||!this.onSwitch)return;const e=this.currentProvider==="arcgis"?"amap":"arcgis";this.isSwitching=!0,this.updateButtonState();try{await this.onSwitch(e),this.currentProvider=e;const t=this.button?.querySelector(".switcher-text");t&&this.updateButtonText(t),this.showSuccessState(),setTimeout(()=>{this.isSwitching=!1,this.updateButtonState()},2e3)}catch(t){console.error("地图引擎切换失败:",t),this.showErrorState(),setTimeout(()=>{this.isSwitching=!1,this.updateButtonState()},2e3)}}updateButtonState(){this.button&&(this.isSwitching?(this.button.style.opacity="0.6",this.button.style.cursor="not-allowed"):(this.button.style.opacity="1",this.button.style.cursor="pointer"))}showSuccessState(){if(!this.button)return;const e=this.button.querySelector(".switcher-text");e&&(e.textContent="✅ 已切换",e.style.color="#10B981"),this.button.style.borderColor="#10B981"}showErrorState(){if(!this.button)return;const e=this.button.querySelector(".switcher-text");e&&(e.textContent="❌ 失败",e.style.color="#EF4444"),this.button.style.borderColor="#EF4444"}setOnSwitch(e){this.onSwitch=e}setCurrentProvider(e){this.currentProvider=e;const t=this.button?.querySelector(".switcher-text");t&&this.updateButtonText(t)}addToContainer(e){const t=typeof e=="string"?document.getElementById(e):e;if(!t){console.error("找不到容器元素");return}console.log("🗺️ 创建地图引擎切换按钮...");const i=this.createButton();t.appendChild(i),console.log("✅ 地图引擎切换按钮已添加到容器")}destroy(){this.button&&this.button.parentNode&&this.button.parentNode.removeChild(this.button),this.button=null,this.onSwitch=null}}})),vn,En=f((()=>{en(),tn(),sn(),nn(),an(),rn(),cs(),hs(),us(),fs(),on(),ln(),cn(),dn(),hn(),pt(),mn(),gn(),fn(),Zs(),yn(),ws(),vn=class{constructor(){this.components=new Map,this.config=null}async initialize(e){return this.config=e,console.log("[ComponentInitializer] 开始初始化组件..."),await this.initializeBasicComponents(),await this.initializeMapInteractionComponents(),await this.initializeParameterComponents(),await this.initializeAdvancedComponents(),console.log("[ComponentInitializer] 组件初始化完成"),this.getComponentRegistry()}async initializeBasicComponents(){console.log("[ComponentInitializer] 初始化基础UI组件...");const e=document.querySelector(".sidebar");if(!e){console.warn("[ComponentInitializer] 侧边栏不存在");return}const t=new ji(this.config.view),i=t.createPanel();this.components.set("coordSystemInfo",t);const s=new Fi(this.config.view,async p=>{this.config.layerManager&&await this.config.layerManager.addSamplingPoint(p)}),n=s.createPanel();this.components.set("singlePointSampling",s);const a=new Ui(this.config.view,this.config.layerManager,p=>this.handleRecommendationSelect(p)),r=a.createPanel();if(this.components.set("recommendationPanel",a),this.config.apiService&&this.config.layerManager){const p=new Vi(this.config.layerManager.adapter),y=new Ki(this.config.layerManager.adapter),g=new Gi;this.components.set("enhancedRecommendationPanel",p),this.components.set("interactiveMarkers",y),this.components.set("strategySelector",g),g.setOnStrategyChange((b,k)=>{console.log("策略变化:",b,k)}),y.setOnMarkerClick(b=>{console.log("标记点击:",b),p.previewPointEffect(b)}),y.setOnMarkerDrag((b,k)=>{console.log("标记拖拽:",b,k)})}else this.components.set("enhancedRecommendationPanel",null),this.components.set("interactiveMarkers",null),this.components.set("strategySelector",null);const o=e.querySelector(".panel");o&&e.insertBefore(i,o);const l=e.querySelectorAll(".panel")[2];l&&l.parentNode&&l.parentNode.insertBefore(n,l.nextSibling);const c=e.querySelectorAll(".panel")[1];if(c&&c.parentNode){const p=document.createElement("div");p.className="panel",p.appendChild(gs.createPanel()),c.parentNode.insertBefore(p,c.nextSibling)}if(c&&c.parentNode){const p=document.createElement("div");p.className="panel",p.innerHTML=`
                <div class="panel-header">
                    <h3>行业配置</h3>
                </div>
                <div id="industry-selector-container"></div>
            `,c.parentNode.insertBefore(p,c.nextSibling);const y=new ds("#industry-selector-container",this.config.apiService?.baseURL||"/api");this.components.set("industrySelector",y);const g=new vs("body",{onLanguageChange:b=>{console.log("语言已切换到:",b),this.updateUIText()}});this.components.set("settingsPanel",g),y.setIndustrySelectCallback(b=>{console.log("选择了行业:",b)}),y.setTemplateDownloadCallback(b=>{console.log("下载模板:",b)})}const u=lt.createPanel();e.appendChild(u);const d=document.querySelector(".right-sidebar-content");d&&d.appendChild(r),console.log("[ComponentInitializer] 基础UI组件初始化完成")}async initializeMapInteractionComponents(){console.log("[ComponentInitializer] 初始化地图交互组件...");const e=document.querySelector(".map-container");if(!e){console.error("[ComponentInitializer] 找不到地图容器");return}const t=await bs(),i=new as(t,async d=>await this.handleMapEngineSwitch(d));i.addToContainer(e),this.components.set("mapEngineSwitcher",i);const s=new Wi(()=>this.handleLocationCenter());s.addToContainer(e),this.components.set("locationCenterButton",s);const n=new Ji({offset:15,animationDuration:200,showDelay:300,hideDelay:100,smartPositioning:!0});n.init(e),this.components.set("mapTooltip",n);const a=new Yi({title:"预测值",unit:"",ranges:[{min:0,max:.2,color:"#34c759",label:"极低"},{min:.2,max:.4,color:"#30d158",label:"低"},{min:.4,max:.6,color:"#0a84ff",label:"中等"},{min:.6,max:.8,color:"#ff9500",label:"高"},{min:.8,max:1,color:"#ff3b30",label:"极高"}],position:"bottom-right",collapsible:!0,collapsed:!1,showValues:!0}),r=a.createLegend();e.appendChild(r),a.loadFromStorage(),this.components.set("mapLegend",a);const o=new Qi({onVisibilityChange:(d,p)=>{this.config.layerManager&&this.config.layerManager.toggleLayer(d,p)},onOpacityChange:(d,p)=>{this.config.layerManager&&this.config.layerManager.setLayerOpacity(d,p/100)},onLayerOrderChange:d=>{this.config.layerManager&&d.forEach(p=>{this.config.layerManager.setLayerZIndex(p.layerId,p.zIndex)})}}),l=o.createPanel();l.style.position="absolute",l.style.top="70px",l.style.right="80px",l.style.zIndex="999",e.appendChild(l),this.components.set("layerComparisonPanel",o);const c=new Xi({defaultUnit:"m",showLabels:!0,snapToFeatures:!1},{onMeasureComplete:d=>{console.log("测量完成:",d)},onMeasureUpdate:d=>{console.log("测量更新:",d)},onMeasureClear:()=>{console.log("测量已清除")}});c.init(this.config.view,t);const u=c.createPanel();u.style.display="none",e.appendChild(u),this.components.set("measureTool",c),this.addToolbarButtons(),console.log("[ComponentInitializer] 地图交互组件初始化完成")}async initializeParameterComponents(){console.log("[ComponentInitializer] 初始化参数组件...");const e=J.getInstance();this.components.set("parameterAdjustmentPanel",e);const t=is.getInstance();this.components.set("parameterTabPanel",t),console.log("[ComponentInitializer] 参数组件初始化完成")}async initializeAdvancedComponents(){console.log("[ComponentInitializer] 初始化高级功能组件...");const e=new ms;e.autoStart(),this.components.set("onboardingGuide",e),this.components.set("preferencesPanel",null),this.components.set("feedbackCollector",null),this.components.set("cacheManagementPanel",ss),this.components.set("offlineModeBanner",ns),console.log("[ComponentInitializer] 高级功能组件初始化完成")}addToolbarButtons(){const e=document.querySelector(".map-toolbar");if(!e){console.warn("[ComponentInitializer] 找不到地图工具栏");return}const t=document.createElement("button");t.className="toolbar-btn",t.title="测量工具",t.innerHTML=`
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <path d="M2 10h16M10 2v16" stroke="currentColor" stroke-width="2"/>
            </svg>
        `,t.addEventListener("click",()=>{const s=document.querySelector(".measure-tool-panel");s&&(s.style.display=s.style.display==="none"?"block":"none")}),e.appendChild(t);const i=document.createElement("button");i.className="toolbar-btn",i.title="图层对比",i.innerHTML=`
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <rect x="2" y="2" width="16" height="16" rx="2" stroke="currentColor" stroke-width="2" fill="none"/>
                <line x1="2" y1="10" x2="18" y2="10" stroke="currentColor" stroke-width="2"/>
            </svg>
        `,i.addEventListener("click",()=>{const s=document.querySelector(".layer-comparison-panel");s&&(s.style.display=s.style.display==="none"?"block":"none")}),e.appendChild(i)}getComponentRegistry(){return{coordSystemInfo:this.components.get("coordSystemInfo"),singlePointSampling:this.components.get("singlePointSampling"),recommendationPanel:this.components.get("recommendationPanel"),enhancedRecommendationPanel:this.components.get("enhancedRecommendationPanel"),interactiveMarkers:this.components.get("interactiveMarkers"),strategySelector:this.components.get("strategySelector"),mapEngineSwitcher:this.components.get("mapEngineSwitcher"),locationCenterButton:this.components.get("locationCenterButton"),mapTooltip:this.components.get("mapTooltip"),mapLegend:this.components.get("mapLegend"),layerComparisonPanel:this.components.get("layerComparisonPanel"),measureTool:this.components.get("measureTool"),templateDownloader:this.components.get("templateDownloader"),industrySelector:this.components.get("industrySelector"),settingsPanel:this.components.get("settingsPanel"),preferencesPanel:this.components.get("preferencesPanel"),feedbackCollector:this.components.get("feedbackCollector"),onboardingGuide:this.components.get("onboardingGuide"),cacheManagementPanel:this.components.get("cacheManagementPanel"),offlineModeBanner:this.components.get("offlineModeBanner"),parameterAdjustmentPanel:this.components.get("parameterAdjustmentPanel"),parameterTabPanel:this.components.get("parameterTabPanel")}}getComponent(e){return this.components.get(e)}handleRecommendationSelect(e){console.log("选中建议点:",e);const t=new CustomEvent("recommendation-selected",{detail:e});document.dispatchEvent(t)}async handleMapEngineSwitch(e){console.log("切换地图引擎:",e);const t=new CustomEvent("map-engine-switch",{detail:e});document.dispatchEvent(t)}handleLocationCenter(){console.log("回到中心");const e=new CustomEvent("location-center");document.dispatchEvent(e)}updateUIText(){const e=new CustomEvent("update-ui-text");document.dispatchEvent(e)}destroy(){console.log("[ComponentInitializer] 销毁所有组件..."),this.components.forEach((e,t)=>{if(e&&typeof e.destroy=="function")try{e.destroy()}catch(i){console.error(`[ComponentInitializer] 销毁组件 ${t} 失败:`,i)}}),this.components.clear()}}})),vi,bi,Ln=f((()=>{bi=class se{constructor(){this.eventHandlers=new Map,this.eventGroups=new Map}static getInstance(){return se.instance||(se.instance=new se),se.instance}bind(t,i,s,n){t.addEventListener(i,s,n);const a={target:t,type:i,handler:s,options:n};this.trackHandler(a)}bindBySelector(t,i,s,n){const a=document.querySelector(t);a?this.bind(a,i,s,n):console.warn(`[EventBinder] 未找到元素: ${t}`)}bindAllBySelector(t,i,s,n){document.querySelectorAll(t).forEach(a=>{this.bind(a,i,s,n)})}bindGlobal(t,i,s){this.bind(window,t,i,s)}bindDocument(t,i,s){this.bind(document,t,i,s)}createGroup(t){if(this.eventGroups.has(t)){console.warn(`[EventBinder] 事件组 ${t} 已存在`);return}this.eventGroups.set(t,{name:t,handlers:[]})}bindToGroup(t,i,s,n,a){this.eventGroups.has(t)||this.createGroup(t),i.addEventListener(s,n,a);const r={target:i,type:s,handler:n,options:a};this.eventGroups.get(t).handlers.push(r),this.trackHandler(r)}unbind(t,i,s,n){t.removeEventListener(i,s,n),this.removeHandler(t,i,s)}unbindBySelector(t,i,s,n){const a=document.querySelector(t);a&&this.unbind(a,i,s,n)}unbindAll(t,i){this.getHandlers(t,i).forEach(s=>{t.removeEventListener(i,s.handler,s.options)}),this.removeAllHandlers(t,i)}unbindGlobal(t,i){this.unbind(window,t,i)}unbindDocument(t,i){this.unbind(document,t,i)}unbindGroup(t){const i=this.eventGroups.get(t);if(!i){console.warn(`[EventBinder] 事件组 ${t} 不存在`);return}i.handlers.forEach(s=>{s.target.removeEventListener(s.type,s.handler,s.options)}),i.handlers.forEach(s=>{this.removeHandler(s.target,s.type,s.handler)}),i.handlers=[]}unbindAllEvents(){this.eventHandlers.forEach((t,i)=>{t.forEach(s=>{s.target.removeEventListener(s.type,s.handler,s.options)})}),this.eventHandlers.clear(),this.eventGroups.clear()}trackHandler(t){const i=this.getHandlerKey(t.target,t.type);this.eventHandlers.has(i)||this.eventHandlers.set(i,[]),this.eventHandlers.get(i).push(t)}removeHandler(t,i,s){const n=this.getHandlerKey(t,i),a=this.eventHandlers.get(n);if(a){const r=a.findIndex(o=>o.handler===s);r>-1&&a.splice(r,1),a.length===0&&this.eventHandlers.delete(n)}}getHandlers(t,i){const s=this.getHandlerKey(t,i);return this.eventHandlers.get(s)||[]}removeAllHandlers(t,i){const s=this.getHandlerKey(t,i);this.eventHandlers.delete(s)}getHandlerKey(t,i){return t===window?`window:${i}`:t===document?`document:${i}`:`${t.id||t.className||"unknown"}:${i}`}getStats(){const t={total:0,byType:new Map,byTarget:new Map};return this.eventHandlers.forEach((i,s)=>{t.total+=i.length;const[n,a]=s.split(":");t.byType.set(a,(t.byType.get(a)||0)+i.length),t.byTarget.set(n,(t.byTarget.get(n)||0)+i.length)}),t}destroy(){this.unbindAllEvents(),se.instance=null}},vi=bi,vi.instance=null})),wi,xi,kn=f((()=>{xi=class ne{constructor(){this.state=new Map,this.listeners=new Map,this.stateConfigs=new Map,this.history=new Map,this.maxHistorySize=50,this.loadPersistedState()}static getInstance(){return ne.instance||(ne.instance=new ne),ne.instance}initializeState(t){t.forEach(i=>{const{key:s,defaultValue:n,config:a}=i;this.state.has(s)||this.state.set(s,n),a&&this.stateConfigs.set(s,a),this.listeners.has(s)||this.listeners.set(s,new Set),this.history.has(s)||this.history.set(s,[])})}setState(t,i){const s=this.state.get(t),n=this.stateConfigs.get(t);if(n&&n.validate&&!n.validate(i)){console.warn(`[StateManager] 状态 ${t} 验证失败`);return}this.state.set(t,i),this.recordHistory(t,i),this.notifyListeners(t,i,s),n&&n.persist&&this.persistState(t,i)}getState(t){return this.state.get(t)}getAllState(){return Object.fromEntries(this.state.entries())}hasState(t){return this.state.has(t)}removeState(t){const i=this.state.get(t);this.state.delete(t),this.listeners.delete(t),this.stateConfigs.delete(t),this.history.delete(t),localStorage.removeItem(`state_${t}`),this.notifyListeners(t,null,i)}subscribe(t,i){return this.listeners.has(t)||this.listeners.set(t,new Set),this.listeners.get(t).add(i),()=>this.unsubscribe(t,i)}unsubscribe(t,i){const s=this.listeners.get(t);s&&s.delete(i)}batchUpdate(t){Object.entries(t).forEach(([i,s])=>{this.setState(i,s)})}resetState(t){const i=this.stateConfigs.get(t);if(i&&i.validate){console.warn(`[StateManager] 无法重置状态 ${t}，没有默认值`);return}this.setState(t,null)}resetAllState(){this.state.forEach((t,i)=>{this.resetState(i)})}getHistory(t){return this.history.get(t)||[]}undo(t){const i=this.history.get(t);if(!i||i.length<2)return!1;i.pop();const s=i[i.length-1];return this.state.set(t,s),this.notifyListeners(t,s,this.state.get(t)),!0}clearHistory(t){const i=this.history.get(t);i&&(i.length=0,i.push(this.state.get(t)))}notifyListeners(t,i,s){const n=this.listeners.get(t);n&&n.forEach(a=>{try{a(i,s)}catch(r){console.error(`[StateManager] 监听器执行失败 (${t}):`,r)}})}recordHistory(t,i){this.history.has(t)||this.history.set(t,[]);const s=this.history.get(t);(s.length===0||s[s.length-1]!==i)&&(s.push(i),s.length>this.maxHistorySize&&s.shift())}persistState(t,i){try{const s=`state_${t}`;localStorage.setItem(s,JSON.stringify(i))}catch(s){console.error(`[StateManager] 持久化状态失败 (${t}):`,s)}}loadPersistedState(){for(let t=0;t<localStorage.length;t++){const i=localStorage.key(t);if(i&&i.startsWith("state_")){const s=i.replace("state_","");try{const n=JSON.parse(localStorage.getItem(i)||"null");this.state.set(s,n),this.history.has(s)||this.history.set(s,[]),this.history.get(s).push(n)}catch(n){console.error(`[StateManager] 加载持久化状态失败 (${s}):`,n)}}}}exportState(){const t={state:Object.fromEntries(this.state.entries()),timestamp:Date.now()};return JSON.stringify(t)}importState(t){try{const i=JSON.parse(t);return i.state?(Object.entries(i.state).forEach(([s,n])=>{this.setState(s,n)}),!0):!1}catch(i){return console.error("[StateManager] 导入状态失败:",i),!1}}clearAllState(){this.state.clear(),this.listeners.clear(),this.stateConfigs.clear(),this.history.clear();for(let t=localStorage.length-1;t>=0;t--){const i=localStorage.key(t);i&&i.startsWith("state_")&&localStorage.removeItem(i)}}getStats(){let t=0,i=0,s=0;return this.state.forEach((n,a)=>{this.listeners.has(a)&&this.listeners.get(a).size>0&&t++,this.history.has(a)&&this.history.get(a).length>1&&i++,localStorage.getItem(`state_${a}`)&&s++}),{total:this.state.size,withListeners:t,withHistory:i,persisted:s}}destroy(){this.clearAllState(),ne.instance=null}},wi=xi,wi.instance=null}));export{Si as _,vn as a,Zs as c,I as d,dt as f,Ce as g,Cn as h,Ln as i,ut as l,Sn as m,kn as n,En as o,ws as p,bi as r,lt as s,xi as t,Bi as u};
