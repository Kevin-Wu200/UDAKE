const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["./web-BMiXxaTK.js","./rolldown-runtime-DQCMaF4_.js","./web-CbpULHLt.js"])))=>i.map(i=>d[i]);
import{n as y}from"./rolldown-runtime-DQCMaF4_.js";var ne,se,V,Q,Te=y((()=>{ne="modulepreload",se=function(t,e){return new URL(t,e).href},V={},Q=function(e,i,n){let s=Promise.resolve();if(i&&i.length>0){let u=function(p){return Promise.all(p.map(d=>Promise.resolve(d).then(h=>({status:"fulfilled",value:h}),h=>({status:"rejected",reason:h}))))};const r=document.getElementsByTagName("link"),a=document.querySelector("meta[property=csp-nonce]"),l=a?.nonce||a?.getAttribute("nonce");s=u(i.map(p=>{if(p=se(p,n),p in V)return;V[p]=!0;const d=p.endsWith(".css"),h=d?'[rel="stylesheet"]':"";if(n)for(let g=r.length-1;g>=0;g--){const f=r[g];if(f.href===p&&(!d||f.rel==="stylesheet"))return}else if(document.querySelector(`link[href="${p}"]${h}`))return;const m=document.createElement("link");if(m.rel=d?"stylesheet":ne,d||(m.as="script"),m.crossOrigin="",m.href=p,l&&m.setAttribute("nonce",l),document.head.appendChild(m),d)return new Promise((g,f)=>{m.addEventListener("load",g),m.addEventListener("error",()=>f(new Error(`Unable to preload CSS for ${p}`)))})}))}function o(r){const a=new Event("vite:preloadError",{cancelable:!0});if(a.payload=r,window.dispatchEvent(a),!a.defaultPrevented)throw r}return s.then(r=>{for(const a of r||[])a.status==="rejected"&&o(a.reason);return e().catch(o)})}})),J,oe,ae,A,c,Fe=y((()=>{oe={"app.title":"智能不确定性驱动空间决策平台","app.subtitle":"UDAKE","nav.newProject":"新建项目","nav.preferences":"偏好设置","nav.feedback":"反馈建议","nav.guide":"查看引导","nav.themeToggle":"切换主题","upload.title":"数据上传","upload.selectFile":"点击选择 GeoJSON 文件","upload.button":"上传数据","upload.success":"数据导入成功！点数: {count}","upload.noFile":"请选择文件","upload.invalidType":"仅支持 .geojson 或 .json 文件","kriging.title":"插值参数","kriging.method":"克里金方法","kriging.ordinary":"普通克里金","kriging.universal":"泛克里金","kriging.block":"分块克里金","kriging.variogram":"变异函数模型","kriging.spherical":"球状模型","kriging.exponential":"指数模型","kriging.gaussian":"高斯模型","kriging.resolution":"网格分辨率","kriging.start":"开始插值","kriging.resolutionError":"网格分辨率必须为大于0的整数","task.title":"任务状态","task.noTask":"暂无任务","task.status":"状态","task.progress":"进度","task.started":"任务已启动","task.completed":"插值完成！","task.failed":"任务失败","export.title":"结果导出","export.prediction":"预测结果","export.variance":"方差结果","export.enhanced":"增强导出","export.csv":"导出 CSV","export.report":"生成报告","export.downloading":"正在下载 {filename}...","export.done":"{filename} 下载完成","export.failed":"导出失败","layer.title":"图层控制","layer.points":"采样点","layer.prediction":"预测栅格","layer.variance":"方差栅格","template.title":"模板下载","template.desc":"下载 GeoJSON 模板文件，按格式填写数据后上传","template.download":"下载","template.rules":"数据格式要求","history.title":"操作历史","history.undo":"撤销","history.redo":"重做","history.clear":"清除","history.empty":"暂无操作记录","history.undoAction":"撤销{action}","history.undone":"已撤销: {action}","history.redoAction":"重做{action}","history.redone":"已重做: {action}","prefs.title":"偏好设置","prefs.appearance":"外观","prefs.theme":"主题模式","prefs.themeAuto":"跟随系统","prefs.themeLight":"浅色","prefs.themeDark":"深色","prefs.animations":"启用动画","prefs.map":"地图","prefs.mapEngine":"地图引擎","prefs.showCoords":"显示坐标信息","prefs.data":"数据","prefs.defaultResolution":"默认网格分辨率","prefs.defaultFormat":"默认导出格式","prefs.autoSave":"自动保存","prefs.notifications":"通知","prefs.enableNotifications":"启用通知","prefs.reset":"恢复默认","prefs.save":"保存","feedback.title":"反馈与建议","feedback.bug":"问题反馈","feedback.feature":"功能建议","feedback.improvement":"体验优化","feedback.other":"其他","feedback.placeholder":"请描述您的反馈内容...","feedback.contact":"联系方式（可选）","feedback.submit":"提交反馈","feedback.cancel":"取消","feedback.stats":"已提交 {count} 条反馈","offline.online":"已恢复在线","offline.offline":"当前处于离线模式","common.confirm":"确认","common.cancel":"取消","common.close":"关闭","common.loading":"加载中...","common.error":"错误","common.success":"成功","settings.title":"设置","settings.language":"语言","settings.language.zh-CN":"简体中文","settings.language.en-US":"English","settings.save":"保存","settings.reset":"重置","industry.title":"选择行业类型","industry.description":"选择适合您数据特点的行业，系统将自动推荐最优插值参数","industry.select":"行业类型","industry.placeholder":"-- 请选择行业 --","industry.dataId":"数据ID","industry.dataIdHint":"填入您已上传数据集的唯一标识符，用于系统识别和引用该数据","industry.getRecommendation":"获取推荐参数","industry.downloadTemplate":"下载模板","industry.recommendationTitle":"推荐参数","industry.recommendation.industry":"行业","industry.recommendation.method":"克里金方法","industry.recommendation.variogram":"变异函数模型","industry.recommendation.resolution":"网格分辨率","industry.recommendation.nlags":"滞后数","industry.recommendation.anisotropy":"各向异性","industry.recommendation.trend":"趋势检测","industry.recommendation.enabled":"启用","industry.recommendation.disabled":"禁用","industry.mining":"矿业","industry.geology":"地质","industry.hydrology":"水文","industry.meteorology":"气象","industry.pollution":"污染","industry.soil":"土壤","industry.environment":"环境","industry.topography":"地形测绘","industry.custom":"自定义","template.downloadComplete":"下载完成","template.downloadMessage":"模板文件已成功保存到:","template.openLocation":"打开位置","template.openLocationQuestion":"是否要打开文件所在位置？","template.downloadDialog":"下载模板","template.downloadQuestion":"是否下载 {industry} 的 GeoJSON 模板文件？模板文件名为: {filename}","template.downloadSuccess":"模板下载成功！","template.downloadFailed":"下载模板失败，请稍后重试","template.savedTo":'模板文件 "{filename}" 已下载到您的下载文件夹。',"panel.project":"当前项目","panel.upload":"数据上传","panel.kriging":"插值参数","panel.task":"任务状态","panel.export":"结果导出","panel.layer":"图层控制","recommendation.title":"采样建议","recommendation.description":"基于不确定性分析的智能采样点推荐","recommendation.strategy":"采样策略","recommendation.strategy.hybrid":"混合策略（推荐）","recommendation.strategy.uncertainty":"不确定性优先","recommendation.strategy.uniform":"均匀分布","recommendation.generate":"生成建议","recommendation.generating":"正在生成采样建议...","recommendation.generated":"成功生成 {count} 个采样建议","recommendation.failed":"生成采样建议失败","recommendation.uncertainty":"不确定性等级","recommendation.reason":"采样理由","recommendation.priority":"优先级","recommendation.priority.high":"高","recommendation.priority.medium":"中","recommendation.priority.low":"低","recommendation.noData":"暂无采样建议","recommendation.error":"加载行业配置失败，请检查后端服务是否正常启动","project.info":"项目信息","project.name":"项目名称","project.mode":"采样模式","project.mode.free":"自由采样","project.mode.region":"区域采样","project.points":"采样点数","project.created":"创建时间","project.status":"项目状态","project.status.active":"活跃","project.status.completed":"已完成"},ae={"app.title":"Uncertainty-Driven Adaptive Kriging Engine","app.subtitle":"UDAKE","nav.newProject":"New Project","nav.preferences":"Preferences","nav.feedback":"Feedback","nav.guide":"Guide","nav.themeToggle":"Toggle Theme","upload.title":"Data Upload","upload.selectFile":"Click to select GeoJSON file","upload.button":"Upload Data","upload.success":"Data imported! Points: {count}","upload.noFile":"Please select a file","upload.invalidType":"Only .geojson or .json files supported","kriging.title":"Interpolation Parameters","kriging.method":"Kriging Method","kriging.ordinary":"Ordinary Kriging","kriging.universal":"Universal Kriging","kriging.block":"Block Kriging","kriging.variogram":"Variogram Model","kriging.spherical":"Spherical","kriging.exponential":"Exponential","kriging.gaussian":"Gaussian","kriging.resolution":"Grid Resolution","kriging.start":"Start Interpolation","kriging.resolutionError":"Grid resolution must be a positive integer","task.title":"Task Status","task.noTask":"No tasks","task.status":"Status","task.progress":"Progress","task.started":"Task started","task.completed":"Interpolation complete!","task.failed":"Task failed","export.title":"Export Results","export.prediction":"Prediction","export.variance":"Variance","export.enhanced":"Enhanced Export","export.csv":"Export CSV","export.report":"Generate Report","export.downloading":"Downloading {filename}...","export.done":"{filename} downloaded","export.failed":"Export failed","layer.title":"Layer Control","layer.points":"Sample Points","layer.prediction":"Prediction Raster","layer.variance":"Variance Raster","template.title":"Template Download","template.desc":"Download GeoJSON templates, fill in data and upload","template.download":"Download","template.rules":"Data Format Requirements","history.title":"Operation History","history.undo":"Undo","history.redo":"Redo","history.clear":"Clear","history.empty":"No operations recorded","history.undoAction":"Undo {action}","history.undone":"Undone: {action}","history.redoAction":"Redo {action}","history.redone":"Redone: {action}","prefs.title":"Preferences","prefs.appearance":"Appearance","prefs.theme":"Theme","prefs.themeAuto":"System","prefs.themeLight":"Light","prefs.themeDark":"Dark","prefs.animations":"Enable Animations","prefs.map":"Map","prefs.mapEngine":"Map Engine","prefs.showCoords":"Show Coordinates","prefs.data":"Data","prefs.defaultResolution":"Default Grid Resolution","prefs.defaultFormat":"Default Export Format","prefs.autoSave":"Auto Save","prefs.notifications":"Notifications","prefs.enableNotifications":"Enable Notifications","prefs.reset":"Reset","prefs.save":"Save","feedback.title":"Feedback","feedback.bug":"Bug Report","feedback.feature":"Feature Request","feedback.improvement":"Improvement","feedback.other":"Other","feedback.placeholder":"Describe your feedback...","feedback.contact":"Contact (optional)","feedback.submit":"Submit","feedback.cancel":"Cancel","feedback.stats":"{count} feedback submitted","offline.online":"Back online","offline.offline":"Offline mode","common.confirm":"Confirm","common.cancel":"Cancel","common.close":"Close","common.loading":"Loading...","common.error":"Error","common.success":"Success","settings.title":"Settings","settings.language":"Language","settings.language.zh-CN":"简体中文","settings.language.en-US":"English","settings.save":"Save","settings.reset":"Reset","industry.title":"Select Industry","industry.description":"Select an industry that matches your data characteristics, and the system will automatically recommend optimal interpolation parameters","industry.select":"Industry Type","industry.placeholder":"-- Select Industry --","industry.dataId":"Data ID","industry.dataIdHint":"Enter the unique identifier of your uploaded dataset for system identification and reference","industry.getRecommendation":"Get Recommendations","industry.downloadTemplate":"Download Template","industry.recommendationTitle":"Recommended Parameters","industry.recommendation.industry":"Industry","industry.recommendation.method":"Kriging Method","industry.recommendation.variogram":"Variogram Model","industry.recommendation.resolution":"Grid Resolution","industry.recommendation.nlags":"Number of Lags","industry.recommendation.anisotropy":"Anisotropy","industry.recommendation.trend":"Trend Detection","industry.recommendation.enabled":"Enabled","industry.recommendation.disabled":"Disabled","industry.mining":"Mining","industry.geology":"Geology","industry.hydrology":"Hydrology","industry.meteorology":"Meteorology","industry.pollution":"Pollution","industry.soil":"Soil","industry.environment":"Environment","industry.topography":"Topographic Mapping","industry.custom":"Custom","template.downloadComplete":"Download Complete","template.downloadMessage":"Template file has been saved to:","template.openLocation":"Open Location","template.openLocationQuestion":"Do you want to open the file location?","template.downloadDialog":"Download Template","template.downloadQuestion":"Do you want to download the GeoJSON template for {industry}? Template filename: {filename}","template.downloadSuccess":"Template downloaded successfully!","template.downloadFailed":"Failed to download template, please try again later","template.savedTo":'Template file "{filename}" has been downloaded to your Downloads folder.',"panel.project":"Current Project","panel.upload":"Data Upload","panel.kriging":"Interpolation Parameters","panel.task":"Task Status","panel.export":"Export Results","panel.layer":"Layer Control","recommendation.title":"Sampling Recommendations","recommendation.description":"Intelligent sampling point recommendations based on uncertainty analysis","recommendation.strategy":"Sampling Strategy","recommendation.strategy.hybrid":"Hybrid (Recommended)","recommendation.strategy.uncertainty":"Uncertainty Priority","recommendation.strategy.uniform":"Uniform Distribution","recommendation.generate":"Generate","recommendation.generating":"Generating sampling recommendations...","recommendation.generated":"Successfully generated {count} sampling recommendations","recommendation.failed":"Failed to generate sampling recommendations","recommendation.uncertainty":"Uncertainty Level","recommendation.reason":"Sampling Reason","recommendation.priority":"Priority","recommendation.priority.high":"High","recommendation.priority.medium":"Medium","recommendation.priority.low":"Low","recommendation.noData":"No sampling recommendations available","recommendation.error":"Failed to load industry configuration, please check if the backend service is running","project.info":"Project Information","project.name":"Project Name","project.mode":"Sampling Mode","project.mode.free":"Free Sampling","project.mode.region":"Region Sampling","project.points":"Sample Points","project.created":"Created","project.status":"Status","project.status.active":"Active","project.status.completed":"Completed"},A={"zh-CN":oe,"en-US":ae},c=class{static init(t){const e=localStorage.getItem("udake_locale");this._locale=t||e||navigator.language||"zh-CN",A[this._locale]||(this._locale=this._locale.startsWith("zh")?"zh-CN":"en-US")}static get locale(){return this._locale}static setLocale(t){A[t]&&(this._locale=t,localStorage.setItem("udake_locale",t),this._listeners.forEach(e=>{try{e(t)}catch(i){console.error(i)}}),document.documentElement.lang=t.startsWith("zh")?"zh-CN":"en")}static t(t,e){let i=(A[this._locale]||A["zh-CN"])[t]||A["zh-CN"][t]||t;return e&&Object.entries(e).forEach(([n,s])=>{i=i.replace(`{${n}}`,String(s))}),i}static getAvailableLocales(){return[{code:"zh-CN",name:"简体中文"},{code:"en-US",name:"English"}]}static onChange(t){return this._listeners.add(t),()=>{this._listeners.delete(t)}}static registerLocale(t,e){A[t]={...A[t]||{},...e}}static getTemplateFilename(t){const e={mining:{"zh-CN":"矿业模版.geojson","en-US":"mining_template.geojson"},geology:{"zh-CN":"地质模版.geojson","en-US":"geology_template.geojson"},hydrology:{"zh-CN":"水文模版.geojson","en-US":"hydrology_template.geojson"},meteorology:{"zh-CN":"气象模版.geojson","en-US":"meteorology_template.geojson"},pollution:{"zh-CN":"污染模版.geojson","en-US":"pollution_template.geojson"},soil:{"zh-CN":"土壤模版.geojson","en-US":"soil_template.geojson"},environment:{"zh-CN":"环境模版.geojson","en-US":"environment_template.geojson"},topography:{"zh-CN":"地形测绘模版.geojson","en-US":"topography_template.geojson"},custom:{"zh-CN":"自定义模版.geojson","en-US":"custom_template.geojson"}};return e[t]?.[this._locale]||e[t]?.["en-US"]||`${t}_template.geojson`}static getIndustryName(t){const e={mining:{"zh-CN":"矿业","en-US":"Mining"},geology:{"zh-CN":"地质","en-US":"Geology"},hydrology:{"zh-CN":"水文","en-US":"Hydrology"},meteorology:{"zh-CN":"气象","en-US":"Meteorology"},pollution:{"zh-CN":"污染","en-US":"Pollution"},soil:{"zh-CN":"土壤","en-US":"Soil"},environment:{"zh-CN":"环境","en-US":"Environment"},topography:{"zh-CN":"地形测绘","en-US":"Topographic Mapping"},custom:{"zh-CN":"自定义","en-US":"Custom"}};return e[t]?.[this._locale]||e[t]?.["en-US"]||t}},J=c,J._locale="zh-CN",J._listeners=new Set})),_,re,le,Re,nt=y((()=>{_="udake_feedback",re=[{value:"bug",label:"问题反馈",icon:"🐛",color:"#ff3b30"},{value:"feature",label:"功能建议",icon:"💡",color:"#007aff"},{value:"improvement",label:"体验优化",icon:"✨",color:"#5856d6"},{value:"other",label:"其他",icon:"💬",color:"#8e8e93"}],le=[{value:"low",label:"低优先级",icon:"🟢"},{value:"medium",label:"中优先级",icon:"🟡"},{value:"high",label:"高优先级",icon:"🟠"},{value:"critical",label:"紧急",icon:"🔴"}],Re=class X{constructor(){this.overlay=null,this.selectedType="bug",this.selectedPriority="medium",this.selectedFiles=[]}show(){this.overlay||(this.overlay=this._createOverlay(),document.body.appendChild(this.overlay),requestAnimationFrame(()=>this.overlay?.classList.add("modal-show")),setTimeout(()=>{const e=this.overlay?.querySelector("textarea");e&&e.focus()},100))}hide(){this.overlay&&(this.overlay.classList.remove("modal-show"),setTimeout(()=>{this.overlay?.remove(),this.overlay=null,this.selectedFiles=[]},300))}_createOverlay(){const e=document.createElement("div");return e.className="modal-overlay",e.setAttribute("role","dialog"),e.setAttribute("aria-modal","true"),e.setAttribute("aria-labelledby","feedback-title"),e.setAttribute("aria-describedby","feedback-description"),e.innerHTML=`
            <div class="modal feedback-modal" role="document">
                <div class="modal-header">
                    <h2 class="modal-title" id="feedback-title">反馈与建议</h2>
                    <button class="modal-close" aria-label="关闭" tabindex="0">&times;</button>
                </div>
                <div class="modal-body feedback-body">
                    <p id="feedback-description" style="margin-bottom:16px;color:var(--text-secondary);font-size:14px;">
                        您的反馈对我们非常重要，请详细描述您遇到的问题或建议。
                    </p>

                    <!-- 反馈类型 -->
                    <fieldset style="border:none;padding:0;margin:0 0 16px 0;">
                        <legend style="font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;padding:0;">
                            反馈类型
                        </legend>
                        <div class="feedback-type-group" role="radiogroup" aria-label="反馈类型">
                            ${re.map((i,n)=>`
                                <button class="feedback-type-btn${n===0?" active":""}" 
                                        data-type="${i.value}" 
                                        role="radio" 
                                        aria-checked="${n===0}"
                                        aria-label="${i.label}"
                                        tabindex="0">
                                    <span style="margin-right:4px;">${i.icon}</span>
                                    ${i.label}
                                </button>
                            `).join("")}
                        </div>
                    </fieldset>

                    <!-- 优先级 -->
                    <fieldset style="border:none;padding:0;margin:0 0 16px 0;">
                        <legend style="font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;padding:0;">
                            优先级
                        </legend>
                        <div class="feedback-priority-group" role="radiogroup" aria-label="优先级">
                            ${le.map((i,n)=>`
                                <button class="feedback-priority-btn${n===1?" active":""}" 
                                        data-priority="${i.value}" 
                                        role="radio" 
                                        aria-checked="${n===1}"
                                        aria-label="${i.label}"
                                        tabindex="0">
                                    <span style="margin-right:4px;">${i.icon}</span>
                                    ${i.label}
                                </button>
                            `).join("")}
                        </div>
                    </fieldset>

                    <!-- 反馈内容 -->
                    <div style="margin-bottom:16px;">
                        <label for="feedback-content" style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            反馈内容 <span style="color:var(--error-color);">*</span>
                        </label>
                        <textarea id="feedback-content" 
                                  placeholder="请详细描述您的问题或建议..." 
                                  aria-label="反馈内容"
                                  aria-required="true"
                                  rows="5"
                                  style="width:100%;min-height:120px;resize:vertical;"></textarea>
                        <div id="feedback-content-counter" style="text-align:right;font-size:12px;color:var(--text-tertiary);margin-top:4px;">
                            0 / 1000
                        </div>
                    </div>

                    <!-- 联系方式 -->
                    <div style="margin-bottom:16px;">
                        <label for="feedback-contact" style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            联系方式（可选）
                        </label>
                        <input type="text" 
                               id="feedback-contact" 
                               class="input" 
                               placeholder="邮箱或手机号" 
                               aria-label="联系方式">
                    </div>

                    <!-- 附件上传 -->
                    <div style="margin-bottom:16px;">
                        <label style="display:block;font-size:14px;font-weight:600;color:var(--text-secondary);margin-bottom:8px;">
                            附件（可选，最多3个，每个不超过5MB）
                        </label>
                        <div id="feedback-file-drop" 
                             class="feedback-file-drop"
                             role="button"
                             tabindex="0"
                             aria-label="点击或拖拽上传附件">
                            <input type="file" 
                                   id="feedback-file-input" 
                                   multiple 
                                   accept="image/*,.pdf,.doc,.docx,.txt"
                                   style="display:none;"
                                   aria-label="选择文件">
                            <div class="feedback-file-drop-content">
                                <span style="font-size:24px;margin-bottom:8px;display:block;">📎</span>
                                <span>点击或拖拽文件到此处</span>
                            </div>
                        </div>
                        <div id="feedback-file-list" style="margin-top:8px;"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <span id="feedback-stats" style="font-size:12px;color:var(--text-tertiary);flex:1;"></span>
                    <button class="btn" id="feedback-cancel" tabindex="0">取消</button>
                    <button class="btn btn-primary" id="feedback-submit" tabindex="0">提交反馈</button>
                </div>
            </div>
        `,this._bindEvents(e),this._updateStats(e),e}_bindEvents(e){e.querySelectorAll(".feedback-type-btn").forEach(a=>{a.addEventListener("click",()=>this._selectType(e,a)),a.addEventListener("keydown",l=>{(l.key==="Enter"||l.key===" ")&&(l.preventDefault(),this._selectType(e,a))})}),e.querySelectorAll(".feedback-priority-btn").forEach(a=>{a.addEventListener("click",()=>this._selectPriority(e,a)),a.addEventListener("keydown",l=>{(l.key==="Enter"||l.key===" ")&&(l.preventDefault(),this._selectPriority(e,a))})});const i=e.querySelector("#feedback-content"),n=e.querySelector("#feedback-content-counter");i.addEventListener("input",()=>{const a=i.value.length;n.textContent=`${a} / 1000`,a>1e3?(n.style.color="var(--error-color)",i.value=i.value.substring(0,1e3),n.textContent="1000 / 1000"):n.style.color="var(--text-tertiary)"});const s=e.querySelector("#feedback-file-drop"),o=e.querySelector("#feedback-file-input"),r=e.querySelector("#feedback-file-list");s.addEventListener("click",()=>o.click()),s.addEventListener("keydown",a=>{(a.key==="Enter"||a.key===" ")&&(a.preventDefault(),o.click())}),s.addEventListener("dragover",a=>{a.preventDefault(),s.classList.add("drag-over")}),s.addEventListener("dragleave",()=>{s.classList.remove("drag-over")}),s.addEventListener("drop",a=>{a.preventDefault(),s.classList.remove("drag-over");const l=a.dataTransfer?.files;l&&this._handleFiles(l,r)}),o.addEventListener("change",()=>{const a=o.files;a&&this._handleFiles(a,r)}),e.querySelector(".modal-close").addEventListener("click",()=>this.hide()),e.querySelector("#feedback-cancel").addEventListener("click",()=>this.hide()),e.addEventListener("click",a=>{a.target===e&&this.hide()}),e.addEventListener("keydown",a=>{a.key==="Escape"&&this.hide()}),e.querySelector("#feedback-submit").addEventListener("click",()=>this._submit(e))}_selectType(e,i){e.querySelectorAll(".feedback-type-btn").forEach(n=>{n.classList.remove("active"),n.setAttribute("aria-checked","false")}),i.classList.add("active"),i.setAttribute("aria-checked","true"),this.selectedType=i.dataset.type}_selectPriority(e,i){e.querySelectorAll(".feedback-priority-btn").forEach(n=>{n.classList.remove("active"),n.setAttribute("aria-checked","false")}),i.classList.add("active"),i.setAttribute("aria-checked","true"),this.selectedPriority=i.dataset.priority}_handleFiles(e,i){for(let o=0;o<e.length;o++){const r=e[o];if(this.selectedFiles.length>=3){alert("最多只能上传 3 个文件");break}if(r.size>5242880){alert(`文件 ${r.name} 超过 5MB 限制`);continue}this.selectedFiles.push(r)}this._renderFileList(i)}_renderFileList(e){e.innerHTML=this.selectedFiles.map((i,n)=>`
            <div class="feedback-file-item" style="display:flex;align-items:center;justify-content:space-between;padding:8px;background:var(--bg-secondary);border-radius:8px;margin-bottom:4px;">
                <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;">${i.name}</span>
                <button class="feedback-file-remove" data-index="${n}" aria-label="删除文件" style="background:none;border:none;color:var(--error-color);cursor:pointer;padding:4px;">✕</button>
            </div>
        `).join(""),e.querySelectorAll(".feedback-file-remove").forEach(i=>{i.addEventListener("click",()=>{const n=parseInt(i.dataset.index);this.selectedFiles.splice(n,1),this._renderFileList(e)})})}_updateStats(e){const i=X.getStats(),n=e.querySelector("#feedback-stats");n.textContent=`已提交 ${i.total} 条反馈`}_submit(e){const i=e.querySelector("#feedback-content").value.trim();if(!i){e.querySelector("#feedback-content").focus(),alert("请填写反馈内容");return}const n=e.querySelector("#feedback-contact").value.trim(),s=[];this.selectedFiles.forEach(o=>{s.push(o.name)}),X.save({type:this.selectedType,priority:this.selectedPriority,content:i,contact:n||void 0,attachments:s.length>0?s:void 0,deviceInfo:this._getDeviceInfo(),browserInfo:this._getBrowserInfo()}),alert("反馈已提交，感谢您的建议！"),this.hide()}_getDeviceInfo(){return`${navigator.platform} - ${screen.width}x${screen.height}`}_getBrowserInfo(){return navigator.userAgent}static save(e){const i=this.getAll();i.push({id:`fb_${Date.now()}_${Math.random().toString(36).slice(2,6)}`,type:"bug",priority:"medium",...e,timestamp:Date.now(),status:"pending"}),localStorage.setItem(_,JSON.stringify(i)),console.log("[Feedback] 反馈已保存")}static getAll(){try{const e=localStorage.getItem(_);return e?JSON.parse(e):[]}catch{return[]}}static getStats(){const e=this.getAll(),i={},n={};return e.forEach(s=>{i[s.type]=(i[s.type]||0)+1,n[s.priority]=(n[s.priority]||0)+1}),{total:e.length,byType:i,byPriority:n}}static exportJSON(){const e=this.getAll(),i=new Blob([JSON.stringify(e,null,2)],{type:"application/json"}),n=URL.createObjectURL(i),s=document.createElement("a");s.href=n,s.download=`feedback_export_${Date.now()}.json`,s.click(),URL.revokeObjectURL(n)}static exportCSV(){const e=this.getAll(),i=["ID","Type","Priority","Content","Contact","Timestamp","Status"],n=e.map(l=>[l.id,l.type,l.priority,`"${l.content.replace(/"/g,'""')}"`,l.contact||"",new Date(l.timestamp).toISOString(),l.status]),s=[i.join(","),...n.map(l=>l.join(","))].join(`
`),o=new Blob([s],{type:"text/csv;charset=utf-8;"}),r=URL.createObjectURL(o),a=document.createElement("a");a.href=r,a.download=`feedback_export_${Date.now()}.csv`,a.click(),URL.revokeObjectURL(r)}static clearAll(){confirm("确定要清除所有反馈吗？此操作不可恢复。")&&localStorage.removeItem(_)}static updateStatus(e,i){const n=this.getAll(),s=n.findIndex(o=>o.id===e);s!==-1&&(n[s].status=i,localStorage.setItem(_,JSON.stringify(n)))}}})),I,je,st=y((()=>{I="/api",je=class{constructor(t){this.dataId=null,this.taskId=null,this.pollTimer=null;const e=document.getElementById(t);if(!e)throw new Error(`容器 ${t} 不存在`);this.container=e,this.config={method:"ordinary",variogramModel:"spherical",gridResolutionX:50,gridResolutionY:50,gridResolutionZ:20,nlags:12,nClosest:16,enableAnisotropy:!1,enableCrossValidation:!0},this.render(),this.bindEvents()}render(){this.container.innerHTML=`
            <div class="kriging3d-panel">
                <div class="panel">
                    <h2 class="panel-title">3D数据上传</h2>
                    <div class="panel-content">
                        <div class="file-picker" id="file-picker-3d">
                            <span id="file-name-3d">选择3D数据文件 (GeoJSON/CSV/钻孔数据)</span>
                            <input type="file" id="file-input-3d" accept=".geojson,.json,.csv" class="file-input">
                        </div>
                        <button id="upload-btn-3d" class="btn btn-primary">上传3D数据</button>
                        <div id="upload-status-3d" class="status-message"></div>
                        <div id="data-stats-3d" style="display:none;"></div>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">3D插值参数</h2>
                    <div class="panel-content">
                        <div class="form-group">
                            <label>克里金方法</label>
                            <select id="kriging3d-method" class="select">
                                <option value="ordinary">普通克里金</option>
                                <option value="universal">泛克里金</option>
                                <option value="indicator">指示克里金</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>变异函数模型</label>
                            <select id="kriging3d-variogram" class="select">
                                <option value="spherical">球状模型</option>
                                <option value="exponential">指数模型</option>
                                <option value="gaussian">高斯模型</option>
                                <option value="linear">线性模型</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>X分辨率 <span id="res-x-val">${this.config.gridResolutionX}</span></label>
                            <input type="range" id="kriging3d-res-x" class="slider" min="10" max="100" value="${this.config.gridResolutionX}" step="5">
                        </div>
                        <div class="form-group slider-group">
                            <label>Y分辨率 <span id="res-y-val">${this.config.gridResolutionY}</span></label>
                            <input type="range" id="kriging3d-res-y" class="slider" min="10" max="100" value="${this.config.gridResolutionY}" step="5">
                        </div>
                        <div class="form-group slider-group">
                            <label>Z分辨率 <span id="res-z-val">${this.config.gridResolutionZ}</span></label>
                            <input type="range" id="kriging3d-res-z" class="slider" min="5" max="50" value="${this.config.gridResolutionZ}" step="1">
                        </div>
                        <div class="form-group slider-group">
                            <label>滞后数 <span id="nlags3d-val">${this.config.nlags}</span></label>
                            <input type="range" id="kriging3d-nlags" class="slider" min="6" max="24" value="${this.config.nlags}" step="1">
                        </div>
                        <div class="form-group slider-group">
                            <label>搜索邻点数 <span id="nclosest-val">${this.config.nClosest}</span></label>
                            <input type="range" id="kriging3d-nclosest" class="slider" min="8" max="32" value="${this.config.nClosest}" step="1">
                        </div>
                        <div class="form-group" id="indicator-threshold-group" style="display:none;">
                            <label>指示阈值</label>
                            <input type="number" id="kriging3d-threshold" class="input" value="0" step="0.1">
                        </div>
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="kriging3d-anisotropy">
                                <span>启用各向异性</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="kriging3d-cv" checked>
                                <span>启用交叉验证</span>
                            </label>
                        </div>
                        <button id="start-kriging3d-btn" class="btn btn-primary" disabled>开始3D插值</button>
                    </div>
                </div>

                <div class="panel">
                    <h2 class="panel-title">3D任务状态</h2>
                    <div class="panel-content">
                        <div id="task-status-3d">暂无任务</div>
                        <div id="progress-bar-3d" class="progress-bar" style="display:none;">
                            <div class="progress-fill" id="progress-fill-3d"></div>
                        </div>
                    </div>
                </div>

                <div class="panel" id="result-panel-3d" style="display:none;">
                    <h2 class="panel-title">3D结果查看</h2>
                    <div class="panel-content">
                        <div id="result-stats-3d"></div>
                        <div class="form-group">
                            <label>切片轴</label>
                            <select id="slice-axis" class="select">
                                <option value="z">Z轴（水平切片）</option>
                                <option value="x">X轴（纵向切片）</option>
                                <option value="y">Y轴（横向切片）</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>切片位置 <span id="slice-pos-val">0</span></label>
                            <input type="range" id="slice-position" class="slider" min="0" max="100" value="50" step="1">
                        </div>
                        <button id="get-slice-btn" class="btn btn-secondary">获取切片</button>
                        <div id="slice-container-3d"></div>
                        <div class="export-buttons" style="margin-top:8px;">
                            <button class="btn btn-export" id="export-3d-json">导出JSON</button>
                            <button class="btn btn-export" id="export-3d-npz">导出NPZ</button>
                        </div>
                    </div>
                </div>

                <div class="panel" id="viz-panel-3d" style="display:none;">
                    <h2 class="panel-title">3D可视化</h2>
                    <div class="panel-content">
                        <div id="threejs-container" style="width:100%;height:400px;background:#1a1a2e;border-radius:8px;"></div>
                        <div class="form-group" style="margin-top:8px;">
                            <label>显示模式</label>
                            <select id="viz-mode-3d" class="select">
                                <option value="points">点云</option>
                                <option value="isosurface">等值面</option>
                                <option value="volume">体渲染</option>
                                <option value="slice">切片</option>
                            </select>
                        </div>
                        <div class="form-group slider-group">
                            <label>透明度 <span id="opacity-val">0.8</span></label>
                            <input type="range" id="viz-opacity" class="slider" min="0" max="1" value="0.8" step="0.05">
                        </div>
                    </div>
                </div>
            </div>
        `}bindEvents(){const t=this.container.querySelector("#file-input-3d");this.container.querySelector("#file-picker-3d")?.addEventListener("click",()=>t?.click()),t?.addEventListener("change",()=>{const e=t.files?.[0]?.name||"选择3D数据文件",i=this.container.querySelector("#file-name-3d");i&&(i.textContent=e)}),this.container.querySelector("#upload-btn-3d")?.addEventListener("click",()=>this.uploadData()),this.bindSlider("kriging3d-res-x","res-x-val",e=>{this.config.gridResolutionX=e}),this.bindSlider("kriging3d-res-y","res-y-val",e=>{this.config.gridResolutionY=e}),this.bindSlider("kriging3d-res-z","res-z-val",e=>{this.config.gridResolutionZ=e}),this.bindSlider("kriging3d-nlags","nlags3d-val",e=>{this.config.nlags=e}),this.bindSlider("kriging3d-nclosest","nclosest-val",e=>{this.config.nClosest=e}),this.bindSlider("viz-opacity","opacity-val",()=>{}),this.container.querySelector("#kriging3d-method")?.addEventListener("change",e=>{const i=e.target.value;this.config.method=i;const n=this.container.querySelector("#indicator-threshold-group");n&&(n.style.display=i==="indicator"?"block":"none")}),this.container.querySelector("#kriging3d-variogram")?.addEventListener("change",e=>{this.config.variogramModel=e.target.value}),this.container.querySelector("#kriging3d-anisotropy")?.addEventListener("change",e=>{this.config.enableAnisotropy=e.target.checked}),this.container.querySelector("#kriging3d-cv")?.addEventListener("change",e=>{this.config.enableCrossValidation=e.target.checked}),this.container.querySelector("#start-kriging3d-btn")?.addEventListener("click",()=>this.startKriging()),this.container.querySelector("#get-slice-btn")?.addEventListener("click",()=>this.getSlice()),this.bindSlider("slice-position","slice-pos-val",()=>{}),this.container.querySelector("#export-3d-json")?.addEventListener("click",()=>this.exportResult("json")),this.container.querySelector("#export-3d-npz")?.addEventListener("click",()=>this.exportResult("npz"))}bindSlider(t,e,i){const n=this.container.querySelector(`#${t}`),s=this.container.querySelector(`#${e}`);n?.addEventListener("input",()=>{s&&(s.textContent=n.value),i(Number(n.value))})}async uploadData(){const t=this.container.querySelector("#file-input-3d"),e=this.container.querySelector("#upload-status-3d"),i=t?.files?.[0];if(!i){e&&(e.textContent="请先选择文件");return}const n=new FormData;n.append("file",i);try{e&&(e.textContent="上传中...");const s=await fetch(`${I}/kriging3d/upload`,{method:"POST",body:n});if(!s.ok)throw new Error(`上传失败: ${s.status}`);const o=await s.json();this.dataId=o.data_id,e&&(e.textContent=`上传成功: ${o.point_count} 个3D点`);const r=await fetch(`${I}/kriging3d/data/${this.dataId}/stats`);if(r.ok){const l=await r.json(),u=this.container.querySelector("#data-stats-3d");u&&(u.style.display="block",u.innerHTML=`
                        <div class="stats-grid">
                            <div>点数: ${l.point_count}</div>
                            <div>X: [${l.x_range[0].toFixed(2)}, ${l.x_range[1].toFixed(2)}]</div>
                            <div>Y: [${l.y_range[0].toFixed(2)}, ${l.y_range[1].toFixed(2)}]</div>
                            <div>Z: [${l.z_range[0].toFixed(2)}, ${l.z_range[1].toFixed(2)}]</div>
                            <div>值: ${l.value_stats.min.toFixed(2)} ~ ${l.value_stats.max.toFixed(2)}</div>
                            <div>均值: ${l.value_stats.mean.toFixed(2)}, 标准差: ${l.value_stats.std.toFixed(2)}</div>
                        </div>
                    `)}const a=this.container.querySelector("#start-kriging3d-btn");a&&(a.disabled=!1)}catch(s){e&&(e.textContent=`上传失败: ${s.message}`)}}async startKriging(){if(!this.dataId)return;const t=this.container.querySelector("#task-status-3d"),e=this.container.querySelector("#progress-bar-3d"),i={data_id:this.dataId,method:this.config.method,variogram_model:this.config.variogramModel,grid_resolution_x:this.config.gridResolutionX,grid_resolution_y:this.config.gridResolutionY,grid_resolution_z:this.config.gridResolutionZ,nlags:this.config.nlags,n_closest:this.config.nClosest,enable_anisotropy:this.config.enableAnisotropy,enable_cross_validation:this.config.enableCrossValidation};if(this.config.method==="indicator"){const n=this.container.querySelector("#kriging3d-threshold");i.indicator_threshold=Number(n?.value||0)}try{t&&(t.textContent="启动中..."),e&&(e.style.display="block");const n=await fetch(`${I}/kriging3d/start`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)});if(!n.ok)throw new Error(`启动失败: ${n.status}`);this.taskId=(await n.json()).task_id,t&&(t.textContent=`任务已启动: ${this.taskId?.slice(0,8)}...`),this.startPolling()}catch(n){t&&(t.textContent=`启动失败: ${n.message}`)}}startPolling(){this.pollTimer&&clearInterval(this.pollTimer),this.pollTimer=window.setInterval(()=>this.pollStatus(),2e3)}async pollStatus(){if(this.taskId)try{const t=await fetch(`${I}/kriging3d/status/${this.taskId}`);if(!t.ok)return;const e=await t.json(),i=this.container.querySelector("#task-status-3d"),n=this.container.querySelector("#progress-fill-3d");n&&(n.style.width=`${e.progress||0}%`),e.status==="completed"?(this.pollTimer&&clearInterval(this.pollTimer),i&&(i.textContent="3D插值完成"),this.showResults(e)):e.status==="failed"?(this.pollTimer&&clearInterval(this.pollTimer),i&&(i.textContent=`失败: ${e.error||"未知错误"}`)):i&&(i.textContent=`计算中... ${(e.progress||0).toFixed(1)}%`)}catch{}}showResults(t){const e=this.container.querySelector("#result-panel-3d"),i=this.container.querySelector("#viz-panel-3d");e&&(e.style.display="block"),i&&(i.style.display="block");const n=this.container.querySelector("#result-stats-3d");if(n&&t.predictionStats){const s=t.predictionStats,o=t.varianceStats||{};n.innerHTML=`
                <div class="stats-grid">
                    <div><strong>网格:</strong> ${t.gridShape?.join(" x ")}</div>
                    <div><strong>预测均值:</strong> ${(s.mean||0).toFixed(4)}</div>
                    <div><strong>预测范围:</strong> ${(s.min||0).toFixed(4)} ~ ${(s.max||0).toFixed(4)}</div>
                    <div><strong>方差均值:</strong> ${(o.mean||0).toFixed(4)}</div>
                </div>
            `}this.init3DVisualization()}async getSlice(){if(!this.taskId)return;const t=this.container.querySelector("#slice-axis")?.value||"z",e=this.container.querySelector("#slice-position"),i=Number(e?.value||50);try{const n=await fetch(`${I}/kriging3d/slice/${this.taskId}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({axis:t,position:i,resolution:100})});if(!n.ok)throw new Error("获取切片失败");const s=await n.json();this.renderSlice(s)}catch(n){const s=this.container.querySelector("#slice-container-3d");s&&(s.innerHTML=`<p style="color:red;">${n.message}</p>`)}}renderSlice(t){const e=this.container.querySelector("#slice-container-3d");if(!e)return;const i=300,n=300,s=document.createElement("canvas");s.width=i,s.height=n,s.style.width="100%",s.style.borderRadius="4px";const o=s.getContext("2d");if(!o)return;const r=t.values,a=r.length,l=r[0]?.length||0;if(a===0||l===0)return;let u=1/0,p=-1/0;for(const g of r)for(const f of g)f<u&&(u=f),f>p&&(p=f);const d=p-u||1,h=i/l,m=n/a;for(let g=0;g<a;g++)for(let f=0;f<l;f++){const x=(r[g][f]-u)/d;o.fillStyle=`rgb(${Math.round(255*Math.min(1,2*x))},${Math.round(255*Math.min(1,2*(1-x)))},${Math.round(100*(1-x))})`,o.fillRect(f*h,g*m,h+1,m+1)}e.innerHTML=`<p style="font-size:12px;color:#888;">${t.axis.toUpperCase()}轴切片 @ ${t.position.toFixed(2)}</p>`,e.appendChild(s)}async exportResult(t){if(this.taskId)try{const e=await fetch(`${I}/kriging3d/export/${this.taskId}?format=${t}`);if(!e.ok)throw new Error("导出失败");const i=await e.json();alert(`导出成功: ${i.path}`)}catch(e){alert(`导出失败: ${e.message}`)}}init3DVisualization(){const t=this.container.querySelector("#threejs-container");t&&(t.innerHTML=`
            <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#8888aa;flex-direction:column;">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
                <p style="margin-top:12px;">3D可视化区域</p>
                <p style="font-size:12px;opacity:0.6;">使用切片功能查看2D截面</p>
            </div>
        `)}destroy(){this.pollTimer&&clearInterval(this.pollTimer),this.container.innerHTML=""}}})),D,z,ce,de,ue,N,M,U,K,Y,he,ze,pe,me,ge,fe,ye,Ne,ve,be,we,Ue,Ee=y((()=>{(function(t){t.Unimplemented="UNIMPLEMENTED",t.Unavailable="UNAVAILABLE"})(D||(D={})),z=class extends Error{constructor(t,e,i){super(t),this.message=t,this.code=e,this.data=i}},ce=t=>{var e,i;return t?.androidBridge?"android":!((i=(e=t?.webkit)===null||e===void 0?void 0:e.messageHandlers)===null||i===void 0)&&i.bridge?"ios":"web"},de=t=>{const e=t.CapacitorCustomPlatform||null,i=t.Capacitor||{},n=i.Plugins=i.Plugins||{},s=()=>e!==null?e.name:ce(t),o=()=>s()!=="web",r=d=>{const h=u.get(d);return!!(h?.platforms.has(s())||a(d))},a=d=>{var h;return(h=i.PluginHeaders)===null||h===void 0?void 0:h.find(m=>m.name===d)},l=d=>t.console.error(d),u=new Map,p=(d,h={})=>{const m=u.get(d);if(m)return console.warn(`Capacitor plugin "${d}" already registered. Cannot register plugins twice.`),m.proxy;const g=s(),f=a(d);let x;const Oe=async()=>(!x&&g in h?x=typeof h[g]=="function"?x=await h[g]():x=h[g]:e!==null&&!x&&"web"in h&&(x=typeof h.web=="function"?x=await h.web():x=h.web),x),Ge=(v,k)=>{var L,C;if(f){const $=f?.methods.find(T=>k===T.name);if($)return $.rtype==="promise"?T=>i.nativePromise(d,k.toString(),T):(T,R)=>i.nativeCallback(d,k.toString(),T,R);if(v)return(L=v[k])===null||L===void 0?void 0:L.bind(v)}else{if(v)return(C=v[k])===null||C===void 0?void 0:C.bind(v);throw new z(`"${d}" plugin is not implemented on ${g}`,D.Unimplemented)}},B=v=>{let k;const L=(...C)=>{const $=Oe().then(T=>{const R=Ge(T,v);if(R){const j=R(...C);return k=j?.remove,j}else throw new z(`"${d}.${v}()" is not implemented on ${g}`,D.Unimplemented)});return v==="addListener"&&($.remove=async()=>k()),$};return L.toString=()=>`${v.toString()}() { [capacitor code] }`,Object.defineProperty(L,"name",{value:v,writable:!1,configurable:!1}),L},te=B("addListener"),ie=B("removeListener"),qe=(v,k)=>{const L=te({eventName:v},k),C=async()=>{ie({eventName:v,callbackId:await L},k)},$=new Promise(T=>L.then(()=>T({remove:C})));return $.remove=async()=>{console.warn("Using addListener() without 'await' is deprecated."),await C()},$},W=new Proxy({},{get(v,k){switch(k){case"$$typeof":return;case"toJSON":return()=>({});case"addListener":return f?qe:te;case"removeListener":return ie;default:return B(k)}}});return n[d]=W,u.set(d,{name:d,proxy:W,platforms:new Set([...Object.keys(h),...f?[g]:[]])}),W};return i.convertFileSrc||(i.convertFileSrc=d=>d),i.getPlatform=s,i.handleError=l,i.isNativePlatform=o,i.isPluginAvailable=r,i.registerPlugin=p,i.Exception=z,i.DEBUG=!!i.DEBUG,i.isLoggingEnabled=!!i.isLoggingEnabled,i},ue=t=>t.Capacitor=de(t),N=ue(typeof globalThis<"u"?globalThis:typeof self<"u"?self:typeof window<"u"?window:typeof global<"u"?global:{}),M=N.registerPlugin,U=class{constructor(){this.listeners={},this.retainedEventArguments={},this.windowListeners={}}addListener(t,e){let i=!1;this.listeners[t]||(this.listeners[t]=[],i=!0),this.listeners[t].push(e);const n=this.windowListeners[t];n&&!n.registered&&this.addWindowListener(n),i&&this.sendRetainedArgumentsForEvent(t);const s=async()=>this.removeListener(t,e);return Promise.resolve({remove:s})}async removeAllListeners(){this.listeners={};for(const t in this.windowListeners)this.removeWindowListener(this.windowListeners[t]);this.windowListeners={}}notifyListeners(t,e,i){const n=this.listeners[t];if(!n){if(i){let s=this.retainedEventArguments[t];s||(s=[]),s.push(e),this.retainedEventArguments[t]=s}return}n.forEach(s=>s(e))}hasListeners(t){var e;return!!(!((e=this.listeners[t])===null||e===void 0)&&e.length)}registerWindowListener(t,e){this.windowListeners[e]={registered:!1,windowEventName:t,pluginEventName:e,handler:i=>{this.notifyListeners(e,i)}}}unimplemented(t="not implemented"){return new N.Exception(t,D.Unimplemented)}unavailable(t="not available"){return new N.Exception(t,D.Unavailable)}async removeListener(t,e){const i=this.listeners[t];if(!i)return;const n=i.indexOf(e);this.listeners[t].splice(n,1),this.listeners[t].length||this.removeWindowListener(this.windowListeners[t])}addWindowListener(t){window.addEventListener(t.windowEventName,t.handler),t.registered=!0}removeWindowListener(t){t&&(window.removeEventListener(t.windowEventName,t.handler),t.registered=!1)}sendRetainedArgumentsForEvent(t){const e=this.retainedEventArguments[t];e&&(delete this.retainedEventArguments[t],e.forEach(i=>{this.notifyListeners(t,i)}))}},K=t=>encodeURIComponent(t).replace(/%(2[346B]|5E|60|7C)/g,decodeURIComponent).replace(/[()]/g,escape),Y=t=>t.replace(/(%[\dA-F]{2})+/gi,decodeURIComponent),he=class extends U{async getCookies(){const t=document.cookie,e={};return t.split(";").forEach(i=>{if(i.length<=0)return;let[n,s]=i.replace(/=/,"CAP_COOKIE").split("CAP_COOKIE");n=Y(n).trim(),s=Y(s).trim(),e[n]=s}),e}async setCookie(t){try{const e=K(t.key),i=K(t.value),n=t.expires?`; expires=${t.expires.replace("expires=","")}`:"",s=(t.path||"/").replace("path=",""),o=t.url!=null&&t.url.length>0?`domain=${t.url}`:"";document.cookie=`${e}=${i||""}${n}; path=${s}; ${o};`}catch(e){return Promise.reject(e)}}async deleteCookie(t){try{document.cookie=`${t.key}=; Max-Age=0`}catch(e){return Promise.reject(e)}}async clearCookies(){try{const t=document.cookie.split(";")||[];for(const e of t)document.cookie=e.replace(/^ +/,"").replace(/=.*/,`=;expires=${new Date().toUTCString()};path=/`)}catch(t){return Promise.reject(t)}}async clearAllCookies(){try{await this.clearCookies()}catch(t){return Promise.reject(t)}}},ze=M("CapacitorCookies",{web:()=>new he}),pe=async t=>new Promise((e,i)=>{const n=new FileReader;n.onload=()=>{const s=n.result;e(s.indexOf(",")>=0?s.split(",")[1]:s)},n.onerror=s=>i(s),n.readAsDataURL(t)}),me=(t={})=>{const e=Object.keys(t);return Object.keys(t).map(i=>i.toLocaleLowerCase()).reduce((i,n,s)=>(i[n]=t[e[s]],i),{})},ge=(t,e=!0)=>t?Object.entries(t).reduce((i,n)=>{const[s,o]=n;let r,a;return Array.isArray(o)?(a="",o.forEach(l=>{r=e?encodeURIComponent(l):l,a+=`${s}=${r}&`}),a.slice(0,-1)):(r=e?encodeURIComponent(o):o,a=`${s}=${r}`),`${i}&${a}`},"").substr(1):null,fe=(t,e={})=>{const i=Object.assign({method:t.method||"GET",headers:t.headers},e),n=me(t.headers)["content-type"]||"";if(typeof t.data=="string")i.body=t.data;else if(n.includes("application/x-www-form-urlencoded")){const s=new URLSearchParams;for(const[o,r]of Object.entries(t.data||{}))s.set(o,r);i.body=s.toString()}else if(n.includes("multipart/form-data")||t.data instanceof FormData){const s=new FormData;if(t.data instanceof FormData)t.data.forEach((r,a)=>{s.append(a,r)});else for(const r of Object.keys(t.data))s.append(r,t.data[r]);i.body=s;const o=new Headers(i.headers);o.delete("content-type"),i.headers=o}else(n.includes("application/json")||typeof t.data=="object")&&(i.body=JSON.stringify(t.data));return i},ye=class extends U{async request(t){const e=fe(t,t.webFetchExtra),i=ge(t.params,t.shouldEncodeUrlParams),n=i?`${t.url}?${i}`:t.url,s=await fetch(n,e),o=s.headers.get("content-type")||"";let{responseType:r="text"}=s.ok?t:{};o.includes("application/json")&&(r="json");let a,l;switch(r){case"arraybuffer":case"blob":l=await s.blob(),a=await pe(l);break;case"json":a=await s.json();break;default:a=await s.text()}const u={};return s.headers.forEach((p,d)=>{u[d]=p}),{data:a,headers:u,status:s.status,url:s.url}}async get(t){return this.request(Object.assign(Object.assign({},t),{method:"GET"}))}async post(t){return this.request(Object.assign(Object.assign({},t),{method:"POST"}))}async put(t){return this.request(Object.assign(Object.assign({},t),{method:"PUT"}))}async patch(t){return this.request(Object.assign(Object.assign({},t),{method:"PATCH"}))}async delete(t){return this.request(Object.assign(Object.assign({},t),{method:"DELETE"}))}},Ne=M("CapacitorHttp",{web:()=>new ye}),(function(t){t.Dark="DARK",t.Light="LIGHT",t.Default="DEFAULT"})(ve||(ve={})),(function(t){t.StatusBar="StatusBar",t.NavigationBar="NavigationBar"})(be||(be={})),we=class extends U{async setStyle(){this.unavailable("not available for web")}async setAnimation(){this.unavailable("not available for web")}async show(){this.unavailable("not available for web")}async hide(){this.unavailable("not available for web")}},Ue=M("SystemBars",{web:()=>new we})}));function He(t){t.CapacitorUtils.Synapse=new Proxy({},{get(e,i){return new Proxy({},{get(n,s){return(o,r,a)=>{const l=t.Capacitor.Plugins[i];if(l===void 0){a(new Error(`Capacitor plugin ${i} not found`));return}if(typeof l[s]!="function"){a(new Error(`Method ${s} not found in Capacitor plugin ${i}`));return}(async()=>{try{r(await l[s](o))}catch(u){a(u)}})()}}})}})}function Be(t){t.CapacitorUtils.Synapse=new Proxy({},{get(e,i){return t.cordova.plugins[i]}})}function We(t=!1){typeof window>"u"||(window.CapacitorUtils=window.CapacitorUtils||{},window.Capacitor!==void 0&&!t?He(window):window.cordova!==void 0&&Be(window))}var Ve=y((()=>{})),Je=y((()=>{})),P,Ke=y((()=>{Ee(),Ve(),Je(),Te(),P=M("Geolocation",{web:()=>Q(()=>import("./web-BMiXxaTK.js").then(t=>new t.GeolocationWeb),__vite__mapDeps([0,1]),import.meta.url)}),We()})),Ye,ot=y((()=>{Ye=class{constructor(){this.currentStep=0,this.overlay=null,this.tooltip=null,this.steps=this._defineSteps(),this.STORAGE_KEY="udake_onboarding_completed",this.resizeHandler=null,this.scrollHandler=null}_defineSteps(){return[{target:null,title:"欢迎使用 UDAKE",content:"智能不确定性驱动空间决策平台，帮助您进行高效的空间插值分析。接下来将为您介绍核心功能。",position:"center"},{target:"#new-project-btn",title:"新建项目",content:"点击此按钮创建新的采样项目，支持自由采样和区域采样两种模式。",position:"bottom"},{target:".sidebar .panel:nth-child(2)",title:"数据上传",content:"上传 GeoJSON 格式的采样数据文件，系统将自动解析坐标和属性字段。",position:"right"},{target:"#kriging-method",title:"插值参数",content:"选择克里金方法和变异函数模型，设置网格分辨率后即可开始插值计算。",position:"right"},{target:"#viewDiv",title:"地图交互",content:"地图区域支持缩放、平移操作，插值完成后可查看预测结果和方差分布。",position:"center"}]}shouldShow(){return!localStorage.getItem(this.STORAGE_KEY)}autoStart(){this.shouldShow()&&setTimeout(()=>this.start(),1e3)}start(){this.currentStep=0,this._createOverlay(),this._createTooltip(),this._showStep(0),this.resizeHandler=()=>{if(this.tooltip&&this.overlay){const e=this.steps[this.currentStep];this._updateHighlight(e),this._positionTooltip(e)}},window.addEventListener("resize",this.resizeHandler);let t=null;this.scrollHandler=()=>{t&&clearTimeout(t),t=window.setTimeout(()=>{if(this.tooltip&&this.overlay){const e=this.steps[this.currentStep];this._updateHighlight(e),this._positionTooltip(e)}},100)},window.addEventListener("scroll",this.scrollHandler)}_createOverlay(){this.overlay&&this.overlay.remove(),this.overlay=document.createElement("div"),this.overlay.className="onboarding-overlay",this.overlay.innerHTML='<svg class="onboarding-svg" width="100%" height="100%"><defs><mask id="onboarding-mask"><rect width="100%" height="100%" fill="white"/><rect class="onboarding-hole" rx="12" ry="12" fill="black"/></mask></defs><rect width="100%" height="100%" fill="rgba(0,0,0,0.5)" mask="url(#onboarding-mask)"/></svg>',document.body.appendChild(this.overlay),this.overlay.addEventListener("click",t=>{t.target===this.overlay||t.target.tagName==="svg"||t.target.tagName})}_createTooltip(){this.tooltip&&this.tooltip.remove(),this.tooltip=document.createElement("div"),this.tooltip.className="onboarding-tooltip",this.tooltip.setAttribute("role","dialog"),this.tooltip.setAttribute("aria-modal","true"),this.tooltip.setAttribute("aria-label","新手引导"),document.body.appendChild(this.tooltip)}_showStep(t){const e=this.steps[t];if(!e)return;const i=this.steps.length,n=t===0,s=t===i-1;this._updateHighlight(e),this.tooltip.setAttribute("aria-label",`新手引导：${e.title}`),this.tooltip.innerHTML=`
            <div class="onboarding-header">
                <span class="onboarding-step-count" aria-label="步骤 ${t+1}，共 ${i} 步">${t+1} / ${i}</span>
            </div>
            <h3 class="onboarding-title">${e.title}</h3>
            <p class="onboarding-content">${e.content}</p>
            <div class="onboarding-progress" role="progressbar" aria-valuenow="${t+1}" aria-valuemin="1" aria-valuemax="${i}" aria-label="引导进度">
                ${this.steps.map((r,a)=>`<span class="onboarding-dot ${a===t?"active":a<t?"done":""}" aria-hidden="true"></span>`).join("")}
            </div>
            <div class="onboarding-actions">
                <button class="onboarding-btn onboarding-btn-skip" aria-label="跳过引导">跳过</button>
                <div class="onboarding-nav">
                    ${n?"":'<button class="onboarding-btn onboarding-btn-prev" aria-label="上一步">上一步</button>'}
                    <button class="onboarding-btn onboarding-btn-next" aria-label="${s?"完成引导":"下一步"}">${s?"完成":"下一步"}</button>
                </div>
            </div>
        `,this._positionTooltip(e),this.tooltip.querySelector(".onboarding-btn-skip").addEventListener("click",()=>this.finish()),n||this.tooltip.querySelector(".onboarding-btn-prev").addEventListener("click",()=>{this.currentStep--,this._showStep(this.currentStep)}),this.tooltip.querySelector(".onboarding-btn-next").addEventListener("click",()=>{s?this.finish():(this.currentStep++,this._showStep(this.currentStep))}),this.tooltip.addEventListener("keydown",r=>{r.key==="Escape"&&this.finish()});const o=this.tooltip.querySelector(".onboarding-btn-next");o&&o.focus(),this.tooltip.style.opacity="0",this.tooltip.style.transform="translateY(8px)",requestAnimationFrame(()=>{this.tooltip.style.transition="opacity 240ms ease, transform 240ms ease",this.tooltip.style.opacity="1",this.tooltip.style.transform="translateY(0)"})}_updateHighlight(t){const e=this.overlay.querySelector(".onboarding-hole");if(!t.target||t.position==="center"){e.setAttribute("width","0"),e.setAttribute("height","0");return}const i=document.querySelector(t.target);if(!i){e.setAttribute("width","0"),e.setAttribute("height","0");return}const n=i.getBoundingClientRect(),s=8;e.setAttribute("x",String(n.left-s)),e.setAttribute("y",String(n.top-s)),e.setAttribute("width",String(n.width+s*2)),e.setAttribute("height",String(n.height+s*2))}_positionTooltip(t){const e=this.tooltip;if(e.style.position="fixed",!t.target||t.position==="center"){e.style.top="50%",e.style.left="50%",e.style.transform="translate(-50%, -50%)",this._ensureTooltipInViewport();return}const i=document.querySelector(t.target);if(!i){e.style.top="50%",e.style.left="50%",e.style.transform="translate(-50%, -50%)",this._ensureTooltipInViewport();return}const n=i.getBoundingClientRect();window.innerWidth,window.innerHeight;const s=16;switch(t.position){case"bottom":e.style.top=`${n.bottom+s}px`,e.style.left=`${n.left+n.width/2}px`,e.style.transform="translate(-50%, 0)";break;case"right":e.style.top=`${n.top+n.height/2}px`,e.style.left=`${n.right+s}px`,e.style.transform="translate(0, -50%)";break;default:e.style.top=`${n.bottom+s}px`,e.style.left=`${n.left+n.width/2}px`,e.style.transform="translate(-50%, 0)"}this._ensureTooltipInViewport()}_ensureTooltipInViewport(){if(!this.tooltip)return;this.tooltip.style.visibility="hidden",this.tooltip.style.display="block";const t=this.tooltip.getBoundingClientRect();this.tooltip.style.visibility="visible";const e=window.innerWidth,i=window.innerHeight,n=16,s=8;let o=parseFloat(this.tooltip.style.top),r=parseFloat(this.tooltip.style.left),a=this.tooltip.style.transform;if(r+t.width+s>e){const l=e-t.width-s;r=Math.max(n,l),a.includes("translateX")&&(a=a.replace(/translateX\([^)]+\)/,"translateX(0)"))}if(r-s<0&&(r=s,a.includes("translateX")&&(a=a.replace(/translateX\([^)]+\)/,"translateX(0)"))),o+t.height+s>i){const l=this.steps[this.currentStep].target,u=l?document.querySelector(l):null;u?o=u.getBoundingClientRect().top-t.height-n:o=i-t.height-s,a.includes("translateY")&&(a=a.replace(/translateY\([^)]+\)/,"translateY(0)"))}o-s<0&&(o=s,a.includes("translateY")&&(a=a.replace(/translateY\([^)]+\)/,"translateY(0)"))),this.tooltip.style.top=`${o}px`,this.tooltip.style.left=`${r}px`,this.tooltip.style.transform=a}finish(){localStorage.setItem(this.STORAGE_KEY,"true"),this.resizeHandler&&(window.removeEventListener("resize",this.resizeHandler),this.resizeHandler=null),this.scrollHandler&&(window.removeEventListener("scroll",this.scrollHandler),this.scrollHandler=null),this.overlay&&(this.overlay.style.opacity="0",this.overlay.style.transition="opacity 240ms ease"),this.tooltip&&(this.tooltip.style.opacity="0",this.tooltip.style.transition="opacity 240ms ease"),setTimeout(()=>{this.overlay&&this.overlay.remove(),this.tooltip&&this.tooltip.remove(),this.overlay=null,this.tooltip=null},250)}reset(){localStorage.removeItem(this.STORAGE_KEY)}}})),H,Z,Xe=y((()=>{H=[{name:"基础采样点模板",description:"包含经纬度的基础采样点模板",filename:"template_basic.geojson",data:{type:"FeatureCollection",features:[{type:"Feature",geometry:{type:"Point",coordinates:[116.39,39.9]},properties:{name:"采样点1",value:10.5}}]}},{name:"土壤采样模板",description:"包含多种土壤属性的采样点模板",filename:"template_soil.geojson",data:{type:"FeatureCollection",features:[{type:"Feature",geometry:{type:"Point",coordinates:[116.4,39.91]},properties:{name:"采样点1",ph:6.5,organic_matter:2.3,nitrogen:15.2,phosphorus:8.7,potassium:120.5}}]}},{name:"区域边界模板",description:"用于定义采样区域边界的多边形模板",filename:"template_boundary.geojson",data:{type:"FeatureCollection",features:[{type:"Feature",geometry:{type:"Polygon",coordinates:[[[116.38,39.89],[116.42,39.89],[116.42,39.93],[116.38,39.93],[116.38,39.89]]]},properties:{name:"采样区域A"}}]}}],Z=class Ce{static download(e){const i=H[e];if(!i)return;const n=JSON.stringify(i.data,null,2),s=new Blob([n],{type:"application/geo+json"}),o=URL.createObjectURL(s),r=document.createElement("a");r.href=o,r.download=i.filename,document.body.appendChild(r),r.click(),document.body.removeChild(r),URL.revokeObjectURL(o),this.showOpenLocationDialog(i.filename)}static showOpenLocationDialog(e){const i=document.createElement("div");i.className="template-download-dialog",i.innerHTML=`
            <div class="dialog-content">
                <h3>下载完成</h3>
                <p>模板文件已成功保存到:</p>
                <p style="font-family: monospace; font-size: 12px; color: var(--primary-color); word-break: break-all;">${e}</p>
                <p>是否要打开文件所在位置？</p>
                <div class="dialog-buttons">
                    <button class="btn btn-primary open-location-btn">打开位置</button>
                    <button class="btn btn-secondary close-dialog-btn">关闭</button>
                </div>
            </div>
        `,document.body.appendChild(i),i.querySelector(".open-location-btn").addEventListener("click",()=>{window.electronAPI&&window.electronAPI.openDownloadFolder?window.electronAPI.openDownloadFolder():alert("请在浏览器的下载历史中找到下载的文件"),document.body.removeChild(i)}),i.querySelector(".close-dialog-btn").addEventListener("click",()=>{document.body.removeChild(i)})}static getTemplates(){return H.map(e=>({name:e.name,description:e.description}))}static createPanel(){const e=document.createElement("div");return e.className="template-download-panel",e.innerHTML=`
            <h3 class="panel-title">模板下载</h3>
            <p style="font-size:13px;color:var(--text-secondary);margin-bottom:12px;">
                下载 GeoJSON 模板文件，按格式填写数据后上传
            </p>
            <div class="template-list">
                ${H.map((i,n)=>`
                    <div class="template-item" data-index="${n}">
                        <div class="template-info">
                            <span class="template-name">${i.name}</span>
                            <span class="template-desc">${i.description}</span>
                        </div>
                        <button class="btn btn-export template-dl-btn" data-index="${n}">下载</button>
                    </div>
                `).join("")}
            </div>
            <details class="template-rules" style="margin-top:12px;">
                <summary style="cursor:pointer;font-size:13px;font-weight:500;">数据格式要求</summary>
                <ul style="font-size:12px;color:var(--text-secondary);padding-left:20px;margin-top:8px;">
                    <li>文件格式：GeoJSON (.geojson 或 .json)</li>
                    <li>坐标系：WGS84 (EPSG:4326)</li>
                    <li>几何类型：Point（采样点）或 Polygon（区域边界）</li>
                    <li>必须包含 properties 中的数值字段作为插值目标</li>
                    <li>坐标格式：[经度, 纬度]，经度范围 -180~180，纬度范围 -90~90</li>
                    <li>至少需要 3 个采样点才能进行插值计算</li>
                </ul>
            </details>
        `,e.querySelectorAll(".template-dl-btn").forEach(i=>{i.addEventListener("click",()=>{const n=parseInt(i.dataset.index,10);Ce.download(n)})}),e}}})),Ze,at=y((()=>{Xe(),Fe(),Ze=class{constructor(t,e="/api"){this.industries=[],this.selectedIndustry=null,this.onIndustrySelect=null,this.onTemplateDownload=null,this.currentDataId="",this.container=typeof t=="string"?document.querySelector(t):t,this.apiURL=e,this.init()}init(){this.render(),this.loadIndustries(),this.bindEvents()}async loadIndustries(){for(let i=1;i<=8;i++)try{console.log(`正在加载行业配置（尝试 ${i}/8）... URL: ${this.apiURL}/industries`),this.industries=(await(await fetch(`${this.apiURL}/industries`)).json()).industries,this.renderIndustryOptions(),console.log(`✓ 成功加载 ${this.industries.length} 个行业配置`);return}catch(n){if(console.error(`加载行业配置失败（尝试 ${i}/8）:`,n),i<8)await new Promise(s=>setTimeout(s,2e3));else{console.error("加载行业配置失败: 已达到最大重试次数");const s=this.container.querySelector(".industry-selector");if(s){const o=document.createElement("div");o.className="error-message",o.textContent=c.t("recommendation.error"),o.style.cssText="color: #ff3b30; padding: 12px; background: rgba(255, 59, 48, 0.1); border-radius: 8px; margin-top: 12px;",s.appendChild(o)}}}}render(){this.container.innerHTML=`
      <div class="industry-selector">
        <div class="industry-header">
          <h3 data-i18n="industry.title">${c.t("industry.title")}</h3>
          <p class="industry-description" data-i18n="industry.description">${c.t("industry.description")}</p>
        </div>

        <div class="industry-input-group">
          <label for="data-id" data-i18n="industry.dataId">${c.t("industry.dataId")}</label>
          <input
            type="text"
            id="data-id"
            class="industry-input"
            placeholder="${c.t("industry.dataId")}"
          />
          <div class="input-hint" data-i18n="industry.dataIdHint">
            ${c.t("industry.dataIdHint")}
          </div>
        </div>

        <div class="industry-input-group">
          <label for="industry-select" data-i18n="industry.select">${c.t("industry.select")}</label>
          <select id="industry-select" class="industry-select">
            <option value="">${c.t("industry.placeholder")}</option>
          </select>
        </div>

        <div class="industry-actions">
          <button id="recommend-btn" class="industry-btn recommend-btn" disabled>
            ${c.t("industry.getRecommendation")}
          </button>
          <button id="download-template-btn" class="industry-btn template-btn" disabled>
            ${c.t("industry.downloadTemplate")}
          </button>
        </div>

        <div id="recommendation-panel" class="recommendation-panel hidden">
          <h4 data-i18n="industry.recommendationTitle">${c.t("industry.recommendationTitle")}</h4>
          <div class="recommendation-content"></div>
        </div>

        <div id="template-dialog" class="template-dialog hidden">
          <div class="template-dialog-content">
            <h4 data-i18n="template.downloadDialog">${c.t("template.downloadDialog")}</h4>
            <p class="template-description"></p>
            <div class="template-actions">
              <button class="template-dialog-btn confirm-btn" data-i18n="common.confirm">${c.t("common.confirm")}</button>
              <button class="template-dialog-btn cancel-btn" data-i18n="common.cancel">${c.t("common.cancel")}</button>
            </div>
          </div>
        </div>
      </div>
    `}renderIndustryOptions(){const t=this.container.querySelector("#industry-select");t.innerHTML=`<option value="">${c.t("industry.placeholder")}</option>`,this.industries.forEach(e=>{const i=document.createElement("option");i.value=e.industry,i.textContent=c.getIndustryName(e.industry),t.appendChild(i)})}updateUIText(){if(!this.container)return;const t=this.container.querySelector(".industry-header h3");t&&(t.textContent=c.t("industry.title"));const e=this.container.querySelector(".industry-description");e&&(e.textContent=c.t("industry.description"));const i=this.container.querySelector('label[for="data-id"]');i&&(i.textContent=c.t("industry.dataId"));const n=this.container.querySelector('label[for="industry-select"]');n&&(n.textContent=c.t("industry.select"));const s=this.container.querySelector(".input-hint");s&&(s.textContent=c.t("industry.dataIdHint"));const o=this.container.querySelector("#recommend-btn");o&&(o.textContent=c.t("industry.getRecommendation"));const r=this.container.querySelector("#download-template-btn");r&&(r.textContent=c.t("industry.downloadTemplate"));const a=this.container.querySelector("#data-id");a&&(a.placeholder=c.t("industry.dataId")),this.renderIndustryOptions();const l=this.container.querySelector(".confirm-btn");l&&(l.textContent=c.t("common.confirm"));const u=this.container.querySelector(".cancel-btn");u&&(u.textContent=c.t("common.cancel"));const p=this.container.querySelector("#recommendation-panel h4");p&&(p.textContent=c.t("industry.recommendationTitle"))}bindEvents(){const t=this.container.querySelector("#data-id"),e=this.container.querySelector("#industry-select"),i=this.container.querySelector("#recommend-btn"),n=this.container.querySelector("#download-template-btn"),s=this.container.querySelector(".confirm-btn"),o=this.container.querySelector(".cancel-btn");t.addEventListener("input",r=>{this.currentDataId=r.target.value,this.updateButtons()}),e.addEventListener("change",r=>{const a=r.target.value;this.selectedIndustry=this.industries.find(l=>l.industry===a)||null,this.updateButtons(),this.showIndustryDescription()}),i.addEventListener("click",()=>{this.getRecommendation()}),n.addEventListener("click",()=>{this.selectedIndustry&&this.onTemplateDownload&&this.showTemplateDialog(this.selectedIndustry)}),s.addEventListener("click",()=>{this.selectedIndustry&&(this.downloadTemplate(this.selectedIndustry.template_filename),this.hideTemplateDialog())}),o.addEventListener("click",()=>{this.hideTemplateDialog()})}updateButtons(){const t=this.container.querySelector("#recommend-btn"),e=this.container.querySelector("#download-template-btn");t.disabled=!(this.currentDataId&&this.selectedIndustry),e.disabled=!this.selectedIndustry}showIndustryDescription(){if(!this.selectedIndustry)return;const t=this.container.querySelector(".industry-description");t.textContent=`${c.getIndustryName(this.selectedIndustry.industry)} - ${this.selectedIndustry.description}`}async getRecommendation(){if(!(!this.currentDataId||!this.selectedIndustry))try{const t=await(await fetch(`${this.apiURL}/recommend-by-industry`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({data_id:this.currentDataId,industry:this.selectedIndustry.industry,enable_cross_validation:!0})})).json();this.showRecommendation(t),this.onIndustrySelect&&this.onIndustrySelect(this.selectedIndustry)}catch(t){console.error("获取推荐参数失败:",t),alert("获取推荐参数失败，请稍后重试")}}showRecommendation(t){const e=this.container.querySelector("#recommendation-panel"),i=this.container.querySelector(".recommendation-content");i.innerHTML=`
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.industry")}:</span>
        <span class="recommendation-value">${t.industry_name}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.method")}:</span>
        <span class="recommendation-value">${t.recommended_method}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.variogram")}:</span>
        <span class="recommendation-value">${t.recommended_variogram}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.resolution")}:</span>
        <span class="recommendation-value">${t.recommended_grid_resolution}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.nlags")}:</span>
        <span class="recommendation-value">${t.recommended_nlags}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.anisotropy")}:</span>
        <span class="recommendation-value">${t.enable_anisotropy?c.t("industry.recommendation.enabled"):c.t("industry.recommendation.disabled")}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${c.t("industry.recommendation.trend")}:</span>
        <span class="recommendation-value">${t.enable_trend_detection?c.t("industry.recommendation.enabled"):c.t("industry.recommendation.disabled")}</span>
      </div>
      <div class="recommendation-message">${t.message}</div>
    `,e.classList.remove("hidden")}showTemplateDialog(t){const e=this.container.querySelector("#template-dialog"),i=this.container.querySelector(".template-description"),n=c.getTemplateFilename(t.industry),s=c.getIndustryName(t.industry);i.textContent=c.t("template.downloadQuestion",{industry:s,filename:n}),e.classList.remove("hidden")}hideTemplateDialog(){this.container.querySelector("#template-dialog").classList.add("hidden")}async downloadTemplate(t){try{const e=await fetch(`${this.apiURL}/templates/${t}`);if(!e.ok)throw new Error("下载模板失败");const i=await e.blob(),n=await i.arrayBuffer(),s=new Uint8Array(n),o=this.selectedIndustry?c.getTemplateFilename(this.selectedIndustry.industry):t;if(window.electronAPI&&window.electronAPI.saveFile){const r=await window.electronAPI.saveFile({title:c.t("template.downloadDialog"),defaultPath:o,filters:[{name:"GeoJSON 文件",extensions:["geojson","json"]},{name:"所有文件",extensions:["*"]}],data:s});r.success&&r.filePath&&Z.showOpenLocationDialog(r.filePath)}else{const r=window.URL.createObjectURL(i),a=document.createElement("a");a.href=r,a.download=o,document.body.appendChild(a),a.click(),document.body.removeChild(a),window.URL.revokeObjectURL(r),Z.showOpenLocationDialog(o)}}catch(e){console.error("下载模板失败:",e),alert(c.t("template.downloadFailed"))}}setIndustrySelectCallback(t){this.onIndustrySelect=t}setTemplateDownloadCallback(t){this.onTemplateDownload=t}getSelectedIndustry(){return this.selectedIndustry}getCurrentDataId(){return this.currentDataId}setDataId(t){const e=this.container.querySelector("#data-id");e.value=t,this.currentDataId=t,this.updateButtons()}destroy(){this.container.innerHTML=""}}})),Qe,rt=y((()=>{Qe=class{constructor(t,e){this.container=typeof t=="string"?document.querySelector(t):t,this.name=e.name||"",this.options=e.options,this.currentValue=e.value||e.options[0]?.value||"",this.onChange=e.onChange||null,this.isOpen=!1,this.focusedIndex=-1,this.init()}init(){this.createSelect(),this.bindEvents()}createSelect(){const t=document.createElement("div");t.className=`custom-select-wrapper ${this.name?`custom-select-${this.name}`:""}`,this.select=document.createElement("div"),this.select.className="custom-select",this.select.setAttribute("role","combobox"),this.select.setAttribute("aria-expanded","false"),this.select.setAttribute("tabindex","0"),this.selectedText=document.createElement("div"),this.selectedText.className="custom-select-value",this.selectedText.textContent=this.getLabel(this.currentValue);const e=document.createElement("div");e.className="custom-select-arrow",e.innerHTML=`
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="2 4 6 8 10 4"></polyline>
            </svg>
        `,this.select.appendChild(this.selectedText),this.select.appendChild(e),this.dropdown=document.createElement("div"),this.dropdown.className="custom-select-dropdown",this.dropdown.setAttribute("role","listbox"),this.options.forEach((i,n)=>{const s=document.createElement("div");s.className="custom-select-option",s.setAttribute("role","option"),s.setAttribute("data-value",i.value),s.setAttribute("data-index",n.toString()),s.textContent=i.label,i.value===this.currentValue&&s.classList.add("custom-select-option-selected"),this.dropdown.appendChild(s)}),this.dropdown.style.display="none",t.appendChild(this.select),t.appendChild(this.dropdown),this.container.appendChild(t)}bindEvents(){this.select.addEventListener("click",t=>{t.stopPropagation(),this.toggle()}),this.dropdown.addEventListener("click",t=>{const e=t.target;if(e.classList.contains("custom-select-option")){const i=e.getAttribute("data-value");this.setValue(i),this.close()}}),this.select.addEventListener("keydown",t=>{this.handleKeyDown(t)}),document.addEventListener("click",t=>{this.container.contains(t.target)||this.close()}),this.observeThemeChange()}handleKeyDown(t){switch(t.key){case"Enter":case" ":if(t.preventDefault(),this.isOpen&&this.focusedIndex>=0){const e=this.options[this.focusedIndex];e&&(this.setValue(e.value),this.close())}else this.toggle();break;case"Escape":t.preventDefault(),this.close();break;case"ArrowDown":t.preventDefault(),this.isOpen?this.focusNextOption():this.open();break;case"ArrowUp":t.preventDefault(),this.isOpen&&this.focusPreviousOption();break;case"Home":t.preventDefault(),this.isOpen&&this.focusOption(0);break;case"End":t.preventDefault(),this.isOpen&&this.focusOption(this.options.length-1);break}}focusNextOption(){const t=this.focusedIndex<this.options.length-1?this.focusedIndex+1:0;this.focusOption(t)}focusPreviousOption(){const t=this.focusedIndex>0?this.focusedIndex-1:this.options.length-1;this.focusOption(t)}focusOption(t){this.focusedIndex=t;const e=this.dropdown.querySelectorAll(".custom-select-option");e.forEach(n=>n.classList.remove("custom-select-option-focused"));const i=e[t];i&&(i.classList.add("custom-select-option-focused"),i.scrollIntoView({block:"nearest"}))}observeThemeChange(){new MutationObserver(t=>{t.forEach(e=>{e.type==="attributes"&&e.attributeName==="data-theme"&&this.updateTheme()})}).observe(document.documentElement,{attributes:!0,attributeFilter:["data-theme","class"]}),window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>{this.updateTheme()})}updateTheme(){}toggle(){this.isOpen?this.close():this.open()}open(){this.isOpen=!0,this.dropdown.style.display="block",this.select.setAttribute("aria-expanded","true"),this.select.classList.add("custom-select-open");const t=this.options.findIndex(e=>e.value===this.currentValue);this.focusOption(t>=0?t:0),this.adjustDropdownPosition()}close(){this.isOpen=!1,this.dropdown.style.display="none",this.select.setAttribute("aria-expanded","false"),this.select.classList.remove("custom-select-open"),this.focusedIndex=-1,this.dropdown.querySelectorAll(".custom-select-option").forEach(t=>t.classList.remove("custom-select-option-focused"))}adjustDropdownPosition(){const t=this.select.getBoundingClientRect(),e=this.dropdown.getBoundingClientRect(),i=window.innerHeight;t.bottom+e.height>i?t.top>=e.height?(this.dropdown.style.top="auto",this.dropdown.style.bottom="100%",this.dropdown.style.marginTop="0",this.dropdown.style.marginBottom="4px"):(this.dropdown.style.maxHeight=`${i-t.bottom-10}px`,this.dropdown.style.overflowY="auto"):(this.dropdown.style.top="100%",this.dropdown.style.bottom="auto",this.dropdown.style.marginTop="4px",this.dropdown.style.marginBottom="0",this.dropdown.style.maxHeight="",this.dropdown.style.overflowY="")}getLabel(t){const e=this.options.find(i=>i.value===t);return e?e.label:""}setValue(t){this.currentValue!==t&&(this.currentValue=t,this.selectedText.textContent=this.getLabel(t),this.dropdown.querySelectorAll(".custom-select-option").forEach(e=>{e.getAttribute("data-value")===t?e.classList.add("custom-select-option-selected"):e.classList.remove("custom-select-option-selected")}),this.onChange&&this.onChange(t))}getValue(){return this.currentValue}setOptions(t){this.options=t,this.dropdown.innerHTML="",this.options.forEach((e,i)=>{const n=document.createElement("div");n.className="custom-select-option",n.setAttribute("role","option"),n.setAttribute("data-value",e.value),n.setAttribute("data-index",i.toString()),n.textContent=e.label,e.value===this.currentValue&&n.classList.add("custom-select-option-selected"),this.dropdown.appendChild(n)}),this.options.find(e=>e.value===this.currentValue)||this.setValue(this.options[0]?.value||"")}enable(){this.select.setAttribute("tabindex","0"),this.select.classList.remove("custom-select-disabled")}disable(){this.select.setAttribute("tabindex","-1"),this.select.classList.add("custom-select-disabled")}destroy(){const t=this.container.querySelector(".custom-select-wrapper");t&&t.remove()}}})),et=y((()=>{})),$e,tt=y((()=>{Ee(),et(),Te(),$e=M("Device",{web:()=>Q(()=>import("./web-CbpULHLt.js").then(t=>new t.DeviceWeb),__vite__mapDeps([2,1]),import.meta.url)})})),ke,E,Ae=y((()=>{Ke(),tt(),ke=class O{constructor(){this.status={gpsAvailable:!1,locationPermission:"prompt",accelerometerAvailable:!1,gyroscopeAvailable:!1,orientationAvailable:!1,currentLocation:null,isRecording:!1,activeTracks:0,activeGeofences:0},this.locationWatchId=null,this.locationCallback=null,this.accelerometerCallback=null,this.gyroscopeCallback=null,this.orientationCallback=null,this.config={location:{enableHighAccuracy:!0,timeout:1e4,distanceFilter:10},updateInterval:1e3},this.lastAccelerometerData=null,this.lastGyroscopeData=null,this.lastOrientationData=null,this.accelerometer=null,this.gyroscope=null,this.absoluteOrientationSensor=null,this.initializeSensors()}static getInstance(){return O.instance||(O.instance=new O),O.instance}async initializeSensors(){try{const e=await P.checkPermissions();this.status.locationPermission=e?.location??"prompt";const i=await $e.getInfo();this.status.gpsAvailable=i?.platform!=="web",this.initializeWebSensors()}catch(e){console.error("初始化传感器失败:",e)}}initializeWebSensors(){const e=globalThis;typeof e.Accelerometer<"u"&&(this.status.accelerometerAvailable=!0),typeof e.Gyroscope<"u"&&(this.status.gyroscopeAvailable=!0),typeof e.AbsoluteOrientationSensor<"u"&&(this.status.orientationAvailable=!0)}async requestLocationPermission(){try{const e=await P.requestPermissions({permissions:["location"]});return this.status.locationPermission=e.location,this.status.locationPermission==="granted"}catch(e){return console.error("请求位置权限失败:",e),!1}}async getCurrentLocation(){try{const e=await P.getCurrentPosition({enableHighAccuracy:this.config.location.enableHighAccuracy,timeout:this.config.location.timeout}),i={latitude:e.coords.latitude,longitude:e.coords.longitude,accuracy:e.coords.accuracy,altitude:e.coords.altitude??null,altitudeAccuracy:e.coords.altitudeAccuracy??null,heading:e.coords.heading,speed:e.coords.speed,timestamp:Date.now()};return this.status.currentLocation=i,i}catch(e){return console.error("获取当前位置失败:",e),null}}async startLocationWatch(e){try{if(this.status.locationPermission!=="granted"&&!await this.requestLocationPermission())throw new Error("位置权限被拒绝");return this.locationCallback=e,this.locationWatchId=await P.watchPosition({enableHighAccuracy:this.config.location.enableHighAccuracy,timeout:this.config.location.timeout,distanceFilter:this.config.location.distanceFilter},(i,n)=>{if(n){console.error("位置监听错误:",n);return}if(i){const s={latitude:i.coords.latitude,longitude:i.coords.longitude,accuracy:i.coords.accuracy,altitude:i.coords.altitude??null,altitudeAccuracy:i.coords.altitudeAccuracy??null,heading:i.coords.heading,speed:i.coords.speed,timestamp:Date.now()};this.status.currentLocation=s,this.locationCallback&&this.locationCallback(s)}}),this.status.gpsAvailable=!0,!0}catch(i){return console.error("启动位置监听失败:",i),!1}}async stopLocationWatch(){this.locationWatchId&&(await P.clearWatch({id:this.locationWatchId}),this.locationWatchId=null,this.locationCallback=null)}async startAccelerometer(e){const i=globalThis.Accelerometer;if(!this.status.accelerometerAvailable&&typeof i<"u"&&(this.status.accelerometerAvailable=!0),!this.status.accelerometerAvailable)return console.warn("加速度传感器不可用"),!1;try{return this.accelerometer=this.createSensorInstance(i,{frequency:1e3/this.config.updateInterval}),this.accelerometerCallback=e,this.accelerometer.addEventListener("reading",()=>{const n={x:this.accelerometer.x,y:this.accelerometer.y,z:this.accelerometer.z,timestamp:Date.now()};this.lastAccelerometerData=n,this.accelerometerCallback&&this.accelerometerCallback(n)}),this.accelerometer.start(),!0}catch(n){return console.error("启动加速度传感器失败:",n),!1}}stopAccelerometer(){this.accelerometer&&(this.accelerometer.stop(),this.accelerometer=null,this.accelerometerCallback=null)}async startGyroscope(e){const i=globalThis.Gyroscope;if(!this.status.gyroscopeAvailable&&typeof i<"u"&&(this.status.gyroscopeAvailable=!0),!this.status.gyroscopeAvailable)return console.warn("陀螺仪不可用"),!1;try{return this.gyroscope=this.createSensorInstance(i,{frequency:1e3/this.config.updateInterval}),this.gyroscopeCallback=e,this.gyroscope.addEventListener("reading",()=>{const n={x:this.gyroscope.x,y:this.gyroscope.y,z:this.gyroscope.z,timestamp:Date.now()};this.lastGyroscopeData=n,this.gyroscopeCallback&&this.gyroscopeCallback(n)}),this.gyroscope.start(),!0}catch(n){return console.error("启动陀螺仪失败:",n),!1}}stopGyroscope(){this.gyroscope&&(this.gyroscope.stop(),this.gyroscope=null,this.gyroscopeCallback=null)}async startOrientation(e){const i=globalThis.AbsoluteOrientationSensor;if(!this.status.orientationAvailable&&typeof i<"u"&&(this.status.orientationAvailable=!0),!this.status.orientationAvailable)return console.warn("方向传感器不可用"),!1;try{return this.absoluteOrientationSensor=this.createSensorInstance(i,{frequency:1e3/this.config.updateInterval}),this.orientationCallback=e,this.absoluteOrientationSensor.addEventListener("reading",()=>{const n=this.absoluteOrientationSensor.quaternion,s=this.quaternionToEuler(n),o={absolute:s.yaw,alpha:s.yaw,beta:s.pitch,gamma:s.roll,timestamp:Date.now()};this.lastOrientationData=o,this.orientationCallback&&this.orientationCallback(o)}),this.absoluteOrientationSensor.start(),!0}catch(n){return console.error("启动方向传感器失败:",n),!1}}stopOrientation(){this.absoluteOrientationSensor&&(this.absoluteOrientationSensor.stop(),this.absoluteOrientationSensor=null,this.orientationCallback=null)}quaternionToEuler(e){const[i,n,s,o]=e,r=2*(i*o+n*s),a=1-2*(s*s+o*o),l=Math.atan2(r,a),u=2*(i*s-o*n),p=Math.abs(u)>=1?Math.sign(u)*Math.PI/2:Math.asin(u),d=2*(i*n+s*o),h=1-2*(n*n+s*s),m=Math.atan2(d,h);return{yaw:(l*180/Math.PI+360)%360,pitch:p*180/Math.PI,roll:m*180/Math.PI}}createSensorInstance(e,i){if(typeof e!="function")throw new Error("传感器构造器不可用");try{return new e(i)}catch{return e(i)}}configure(e){this.config={...this.config,...e}}getStatus(){return{...this.status}}stopAll(){this.stopLocationWatch(),this.stopAccelerometer(),this.stopGyroscope(),this.stopOrientation()}dispose(){this.stopAll()}},E=ke.getInstance()})),xe,b,ee=y((()=>{Ae(),xe=class G{constructor(){this.locationListeners=new Set,this.errorListeners=new Set,this.lastLocation=null,this.isWatching=!1,this.options={enableHighAccuracy:!0,timeout:1e4,distanceFilter:10}}static getInstance(){return G.instance||(G.instance=new G),G.instance}configure(e){this.options={...this.options,...e},E.configure({location:this.options})}async requestPermission(){return await E.requestLocationPermission()}checkPermission(){return E.getStatus().locationPermission}async getCurrentLocation(){const e=await E.getCurrentLocation();if(!e)throw new Error("无法获取当前位置");return this.lastLocation=e,e}async startWatch(){if(this.isWatching)return console.warn("位置监听已经在运行"),!0;const e=await E.startLocationWatch(i=>{this.lastLocation=i,this.notifyLocationListeners(i)});return e&&(this.isWatching=!0),e}async stopWatch(){this.isWatching&&(await E.stopLocationWatch(),this.isWatching=!1)}addLocationListener(e){this.locationListeners.add(e),this.lastLocation&&e(this.lastLocation)}removeLocationListener(e){this.locationListeners.delete(e)}addErrorListener(e){this.errorListeners.add(e)}removeErrorListener(e){this.errorListeners.delete(e)}notifyLocationListeners(e){this.locationListeners.forEach(i=>{try{i(e)}catch(n){console.error("位置监听器错误:",n)}})}notifyErrorListeners(e){this.errorListeners.forEach(i=>{try{i(e)}catch(n){console.error("错误监听器错误:",n)}})}getLastLocation(){return this.lastLocation}calculateDistance(e,i){const s=e.latitude*Math.PI/180,o=i.latitude*Math.PI/180,r=(i.latitude-e.latitude)*Math.PI/180,a=(i.longitude-e.longitude)*Math.PI/180,l=Math.sin(r/2)*Math.sin(r/2)+Math.cos(s)*Math.cos(o)*Math.sin(a/2)*Math.sin(a/2);return 6371e3*(2*Math.atan2(Math.sqrt(l),Math.sqrt(1-l)))}calculateBearing(e,i){const n=e.latitude*Math.PI/180,s=i.latitude*Math.PI/180,o=(i.longitude-e.longitude)*Math.PI/180,r=Math.sin(o)*Math.cos(s),a=Math.cos(n)*Math.sin(s)-Math.sin(n)*Math.cos(s)*Math.cos(o);return(Math.atan2(r,a)*180/Math.PI+360)%360}formatLocation(e){return`${e.latitude.toFixed(6)}, ${e.longitude.toFixed(6)}`}formatAccuracy(e){return e<10?`高精度 (±${e.toFixed(1)}m)`:e<50?`中等精度 (±${e.toFixed(1)}m)`:`低精度 (±${e.toFixed(1)}m)`}isValidLocation(e){return e?e.latitude>=-90&&e.latitude<=90&&e.longitude>=-180&&e.longitude<=180&&e.accuracy>=0:!1}dispose(){this.stopWatch(),this.locationListeners.clear(),this.errorListeners.clear()}},b=xe.getInstance()})),Se,S,Ie=y((()=>{ee(),Ae(),Se=class q{constructor(){this.tracks=new Map,this.currentTrack=null,this.pointBuffer=[],this.BUFFER_SIZE=100,this.trackUpdateListeners=new Set,this.trackStartListeners=new Set,this.trackEndListeners=new Set,this.lastAccelerometer=null,this.lastOrientation=null,this.initializeSensorListeners(),this.loadTracksFromStorage()}static getInstance(){return q.instance||(q.instance=new q),q.instance}initializeSensorListeners(){E.startAccelerometer(e=>{this.lastAccelerometer=e}),E.startOrientation(e=>{this.lastOrientation=e})}async loadTracksFromStorage(){try{const e=localStorage.getItem("udake_tracks");e&&JSON.parse(e).forEach(i=>{this.tracks.set(i.id,i)})}catch(e){console.error("加载轨迹失败:",e)}}async saveTracksToStorage(){try{const e=Array.from(this.tracks.values());localStorage.setItem("udake_tracks",JSON.stringify(e))}catch(e){console.error("保存轨迹失败:",e)}}async createTrack(e,i,n=!1){const s={id:`track_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,name:e,description:i,points:[],startTime:Date.now(),endTime:null,totalDistance:0,averageSpeed:0};return this.tracks.set(s.id,s),n&&(this.currentTrack=s,this.pointBuffer=[]),await this.saveTracksToStorage(),this.trackStartListeners.forEach(o=>{try{o(s)}catch(r){console.error("轨迹开始监听器错误:",r)}}),s}async startRecording(e,i){if(this.currentTrack)return console.warn("已经在记录轨迹"),this.currentTrack;const n=await this.createTrack(e,i,!0);return await b.startWatch()?(b.addLocationListener(s=>{this.addTrackPoint(s)}),n):(console.error("启动位置监听失败"),null)}async stopRecording(){if(!this.currentTrack){console.warn("没有正在记录的轨迹");return}await this.flushBuffer(),this.currentTrack.endTime=Date.now(),this.calculateTrackStatistics(this.currentTrack),await this.saveTracksToStorage(),this.trackEndListeners.forEach(e=>{try{e(this.currentTrack)}catch(i){console.error("轨迹结束监听器错误:",i)}}),await b.stopWatch(),this.currentTrack=null,this.pointBuffer=[]}addTrackPoint(e){if(!this.currentTrack)return;const i={location:e,accelerometer:this.lastAccelerometer?{...this.lastAccelerometer}:void 0,orientation:this.lastOrientation?{...this.lastOrientation}:void 0,index:this.currentTrack.points.length+this.pointBuffer.length,timestamp:Date.now()};this.pointBuffer.push(i),this.pointBuffer.length>=this.BUFFER_SIZE&&this.flushBuffer(),this.trackUpdateListeners.forEach(n=>{try{n(this.currentTrack)}catch(s){console.error("轨迹更新监听器错误:",s)}})}async flushBuffer(){!this.currentTrack||this.pointBuffer.length===0||(this.currentTrack.points.push(...this.pointBuffer),this.pointBuffer=[],await this.saveTracksToStorage())}calculateTrackStatistics(e){if(e.points.length<2)return;let i=0;for(let s=1;s<e.points.length;s++){const o=e.points[s-1].location,r=e.points[s].location;i+=b.calculateDistance(o,r)}e.totalDistance=i;let n=(e.endTime||Date.now())-e.startTime;if(n<=0&&e.points.length>=2){const s=e.points[0].timestamp,o=e.points[e.points.length-1].timestamp;n=Math.max(0,o-s)}n>0&&(e.averageSpeed=i/(n/1e3))}getAllTracks(){return Array.from(this.tracks.values()).sort((e,i)=>i.startTime-e.startTime)}getTrack(e){return this.tracks.get(e)}async deleteTrack(e){this.tracks.delete(e),await this.saveTracksToStorage()}getCurrentTrack(){return this.currentTrack}isRecording(){return this.currentTrack!==null}exportToGeoJSON(e){const i=this.tracks.get(e);if(!i)return null;const n={type:"Feature",properties:{name:i.name,description:i.description,startTime:i.startTime,endTime:i.endTime,totalDistance:i.totalDistance,averageSpeed:i.averageSpeed},geometry:{type:"LineString",coordinates:i.points.map(s=>[s.location.longitude,s.location.latitude,s.location.altitude||0])}};return JSON.stringify(n,null,2)}exportToGPX(e){const i=this.tracks.get(e);return i?`<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="UDAKE" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${i.name}</name>
    <desc>${i.description||""}</desc>
    <time>${new Date(i.startTime).toISOString()}</time>
  </metadata>
  <trk>
    <name>${i.name}</name>
    <trkseg>
${i.points.map(n=>`      <trkpt lat="${n.location.latitude}" lon="${n.location.longitude}">
        <ele>${n.location.altitude||0}</ele>
        <time>${new Date(n.timestamp).toISOString()}</time>
        <speed>${n.location.speed||0}</speed>
      </trkpt>`).join(`
`)}
    </trkseg>
  </trk>
</gpx>`:null}async importTrack(e,i){try{return i==="geojson"?this.importFromGeoJSON(e):i==="gpx"?this.importFromGPX(e):null}catch(n){return console.error("导入轨迹失败:",n),null}}importFromGeoJSON(e){const i=JSON.parse(e);if(i.type!=="Feature"||i.geometry.type!=="LineString")throw new Error("无效的 GeoJSON 格式");const n={id:`track_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,name:i.properties.name||"导入的轨迹",description:i.properties.description,points:i.geometry.coordinates.map((s,o)=>({location:{latitude:s[1],longitude:s[0],altitude:s[2]||null,accuracy:0,altitudeAccuracy:null,heading:null,speed:null,timestamp:Date.now()},index:o,timestamp:Date.now()})),startTime:i.properties.startTime||Date.now(),endTime:i.properties.endTime||Date.now(),totalDistance:i.properties.totalDistance||0,averageSpeed:i.properties.averageSpeed||0};return this.calculateTrackStatistics(n),this.tracks.set(n.id,n),this.saveTracksToStorage(),n}importFromGPX(e){const i=new DOMParser().parseFromString(e,"text/xml"),n=i.querySelector("trk > name")?.textContent||"导入的轨迹",s=i.querySelector("trk > desc")?.textContent||void 0,o=i.querySelectorAll("trkpt"),r=[];if(o.forEach((l,u)=>{const p=parseFloat(l.getAttribute("lat")||"0"),d=parseFloat(l.getAttribute("lon")||"0"),h=l.querySelector("ele")?.textContent,m=l.querySelector("time")?.textContent,g=l.querySelector("speed")?.textContent;r.push({location:{latitude:p,longitude:d,altitude:h?parseFloat(h):null,accuracy:0,altitudeAccuracy:null,heading:null,speed:g?parseFloat(g):null,timestamp:m?new Date(m).getTime():Date.now()},index:u,timestamp:m?new Date(m).getTime():Date.now()})}),r.length===0)throw new Error("GPX 文件中没有轨迹点");const a={id:`track_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,name:n,description:s,points:r,startTime:r[0].timestamp,endTime:r[r.length-1].timestamp,totalDistance:0,averageSpeed:0};return this.calculateTrackStatistics(a),this.tracks.set(a.id,a),this.saveTracksToStorage(),a}addTrackUpdateListener(e){this.trackUpdateListeners.add(e)}removeTrackUpdateListener(e){this.trackUpdateListeners.delete(e)}addTrackStartListener(e){this.trackStartListeners.add(e)}removeTrackStartListener(e){this.trackStartListeners.delete(e)}addTrackEndListener(e){this.trackEndListeners.add(e)}removeTrackEndListener(e){this.trackEndListeners.delete(e)}dispose(){this.currentTrack&&this.stopRecording(),this.trackUpdateListeners.clear(),this.trackStartListeners.clear(),this.trackEndListeners.clear()}},S=Se.getInstance()})),Le,w,De=y((()=>{ee(),Le=class F{constructor(){this.geofences=new Map,this.activeGeofences=new Map,this.events=new Array,this.geofenceStates=new Map,this.geofenceListeners=new Set,this.isMonitoring=!1,this.MONITOR_INTERVAL=1e3,this.monitorTimer=null,this.loadGeofencesFromStorage()}static getInstance(){return F.instance||(F.instance=new F),F.instance}async loadGeofencesFromStorage(){try{const e=localStorage.getItem("udake_geofences");e&&JSON.parse(e).forEach(n=>{this.geofences.set(n.id,n)});const i=localStorage.getItem("udake_geofence_events");i&&(this.events=JSON.parse(i))}catch(e){console.error("加载地理围栏失败:",e)}}async saveGeofencesToStorage(){try{const e=Array.from(this.geofences.values());localStorage.setItem("udake_geofences",JSON.stringify(e))}catch(e){console.error("保存地理围栏失败:",e)}}async saveEventsToStorage(){try{const e=this.events.slice(-1e3);localStorage.setItem("udake_geofence_events",JSON.stringify(e))}catch(e){console.error("保存事件失败:",e)}}async createCircularGeofence(e,i,n,s,o={}){const r={id:`geofence_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,name:e,latitude:i,longitude:n,radius:s,type:"circular",enabled:!0,notifyOnEnter:o.notifyOnEnter??!0,notifyOnExit:o.notifyOnExit??!0,notifyOnDwell:o.notifyOnDwell??!1,dwellDelay:o.dwellDelay||3e4,description:o.description};return this.geofences.set(r.id,r),await this.saveGeofencesToStorage(),r.enabled&&this.activateGeofence(r.id),r}async createPolygonGeofence(e,i,n={}){if(i.length<3)throw new Error("多边形至少需要3个顶点");const s=this.calculatePolygonCenter(i),o=this.calculatePolygonMaxRadius(s,i),r={id:`geofence_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,name:e,latitude:s.latitude,longitude:s.longitude,radius:o,type:"polygon",vertices:i,enabled:!0,notifyOnEnter:n.notifyOnEnter??!0,notifyOnExit:n.notifyOnExit??!0,notifyOnDwell:n.notifyOnDwell??!1,dwellDelay:n.dwellDelay||3e4,description:n.description};return this.geofences.set(r.id,r),await this.saveGeofencesToStorage(),r.enabled&&this.activateGeofence(r.id),r}calculatePolygonCenter(e){let i=0,n=0;return e.forEach(s=>{i+=s.latitude,n+=s.longitude}),{latitude:i/e.length,longitude:n/e.length}}calculatePolygonMaxRadius(e,i){let n=0;return i.forEach(s=>{const o=b.calculateDistance(e,s);o>n&&(n=o)}),n}activateGeofence(e){const i=this.geofences.get(e);!i||!i.enabled||(this.activeGeofences.set(e,i),this.geofenceStates.set(e,{inside:!1,dwellTime:0}),this.isMonitoring||this.startMonitoring())}deactivateGeofence(e){this.activeGeofences.delete(e),this.geofenceStates.delete(e),this.activeGeofences.size===0&&this.stopMonitoring()}startMonitoring(){this.isMonitoring||(this.isMonitoring=!0,b.startWatch(),b.addLocationListener(e=>{this.checkGeofences(e)}),this.monitorTimer=window.setInterval(()=>{this.checkDwellGeofences()},this.MONITOR_INTERVAL))}stopMonitoring(){this.isMonitoring&&(this.isMonitoring=!1,b.stopWatch(),this.monitorTimer&&(clearInterval(this.monitorTimer),this.monitorTimer=null))}checkGeofences(e){this.activeGeofences.forEach((i,n)=>{const s=this.isInsideGeofence(e,i),o=this.geofenceStates.get(n);o&&(s&&!o.inside&&i.notifyOnEnter&&(this.triggerEvent(n,"enter",e),o.inside=!0,o.dwellTime=0),!s&&o.inside&&i.notifyOnExit&&(this.triggerEvent(n,"exit",e),o.inside=!1,o.dwellTime=0),s&&o.inside&&(o.dwellTime+=this.MONITOR_INTERVAL),this.geofenceStates.set(n,o))})}checkDwellGeofences(){this.activeGeofences.forEach((e,i)=>{const n=this.geofenceStates.get(i);if(!(!n||!n.inside||!e.notifyOnDwell||!e.dwellDelay)&&n.dwellTime>=e.dwellDelay){const s=b.getLastLocation();s&&(this.triggerEvent(i,"dwell",s),n.dwellTime=0,this.geofenceStates.set(i,n))}})}isInsideGeofence(e,i){return i.type==="circular"?this.isInsideCircle(e,i):i.type==="polygon"?this.isInsidePolygon(e,i):!1}isInsideCircle(e,i){return b.calculateDistance({latitude:e.latitude,longitude:e.longitude},{latitude:i.latitude,longitude:i.longitude})<=i.radius}isInsidePolygon(e,i){if(!i.vertices||i.vertices.length<3)return!1;const n=e.longitude,s=e.latitude,o=i.vertices;let r=!1;for(let a=0,l=o.length-1;a<o.length;l=a++){const u=o[a].longitude,p=o[a].latitude,d=o[l].longitude,h=o[l].latitude;p>s!=h>s&&n<(d-u)*(s-p)/(h-p)+u&&(r=!r)}return r}triggerEvent(e,i,n){const s={id:`event_${Date.now()}_${Math.random().toString(36).substr(2,9)}`,geofenceId:e,type:i,timestamp:Date.now(),location:n};this.events.push(s),this.saveEventsToStorage(),this.geofenceListeners.forEach(o=>{try{o(s)}catch(r){console.error("地理围栏事件监听器错误:",r)}})}getAllGeofences(){return Array.from(this.geofences.values())}getGeofence(e){return this.geofences.get(e)}async updateGeofence(e,i){const n=this.geofences.get(e);if(!n)throw new Error("地理围栏不存在");const s={...n,...i};this.geofences.set(e,s),await this.saveGeofencesToStorage(),s.enabled?this.activateGeofence(e):this.deactivateGeofence(e)}async deleteGeofence(e){this.deactivateGeofence(e),this.geofences.delete(e),await this.saveGeofencesToStorage()}getEvents(e){return e?this.events.filter(i=>i.geofenceId===e):[...this.events]}async clearEvents(e){e?this.events=this.events.filter(i=>i.geofenceId!==e):this.events=[],await this.saveEventsToStorage()}addGeofenceListener(e){this.geofenceListeners.add(e)}removeGeofenceListener(e){this.geofenceListeners.delete(e)}dispose(){this.stopMonitoring(),this.geofenceListeners.clear()}},w=Le.getInstance()}));function lt(){const t=document.createElement("div");return t.className="location-service-panel-container",t.style.cssText=`
    position: fixed;
    top: 80px;
    right: 20px;
    width: 320px;
    max-height: 80vh;
    overflow-y: auto;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    z-index: 1000;
  `,document.body.appendChild(t),new Pe(t)}var Pe,ct=y((()=>{ee(),Ie(),De(),Pe=class{constructor(t){this.currentLocation=null,this.isRecording=!1,this.currentTrack=null,this.container=t,this.render(),this.initializeListeners()}render(){this.container.innerHTML=`
      <div class="location-service-panel">
        <div class="panel-header">
          <h3>位置服务</h3>
          <button class="btn-icon close-btn" title="关闭">
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
            </svg>
          </button>
        </div>

        <div class="panel-content">
          <!-- 当前位置 -->
          <div class="section">
            <h4>当前位置</h4>
            <div class="location-info">
              <div class="location-coordinates">
                <span class="label">纬度:</span>
                <span class="value latitude-value">--</span>
              </div>
              <div class="location-coordinates">
                <span class="label">经度:</span>
                <span class="value longitude-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">精度:</span>
                <span class="value accuracy-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">海拔:</span>
                <span class="value altitude-value">--</span>
              </div>
              <div class="location-details">
                <span class="label">速度:</span>
                <span class="value speed-value">--</span>
              </div>
            </div>
            <div class="location-actions">
              <button class="btn btn-primary" id="get-location-btn">获取位置</button>
              <button class="btn btn-secondary" id="center-on-location-btn">定位到当前位置</button>
            </div>
          </div>

          <!-- 轨迹记录 -->
          <div class="section">
            <h4>轨迹记录</h4>
            <div class="track-info" id="track-info" style="display: none;">
              <div class="track-name">
                <span class="label">轨迹名称:</span>
                <span class="value track-name-value">--</span>
              </div>
              <div class="track-stats">
                <span class="label">点数:</span>
                <span class="value track-points-value">0</span>
              </div>
              <div class="track-stats">
                <span class="label">距离:</span>
                <span class="value track-distance-value">0 m</span>
              </div>
              <div class="track-stats">
                <span class="label">时间:</span>
                <span class="value track-time-value">0:00</span>
              </div>
            </div>
            <div class="track-actions">
              <input type="text" id="track-name-input" placeholder="轨迹名称" class="input-text" />
              <button class="btn btn-success" id="start-track-btn">开始记录</button>
              <button class="btn btn-danger" id="stop-track-btn" style="display: none;">停止记录</button>
            </div>
          </div>

          <!-- 地理围栏 -->
          <div class="section">
            <h4>地理围栏</h4>
            <div class="geofence-list" id="geofence-list">
              <div class="empty-message">暂无地理围栏</div>
            </div>
            <div class="geofence-actions">
              <button class="btn btn-primary" id="add-geofence-btn">添加围栏</button>
            </div>
          </div>
        </div>
      </div>
    `,this.attachEventListeners()}initializeListeners(){b.addLocationListener(t=>{this.updateLocationDisplay(t)}),S.addTrackUpdateListener(t=>{this.updateTrackDisplay(t)}),S.addTrackStartListener(t=>{this.onTrackStart(t)}),S.addTrackEndListener(t=>{this.onTrackEnd(t)}),w.addGeofenceListener(t=>{this.onGeofenceEvent(t)})}attachEventListeners(){this.container.querySelector(".close-btn")?.addEventListener("click",()=>{this.container.remove()}),this.container.querySelector("#get-location-btn")?.addEventListener("click",()=>{this.handleGetLocation()}),this.container.querySelector("#center-on-location-btn")?.addEventListener("click",()=>{this.handleCenterOnLocation()}),this.container.querySelector("#start-track-btn")?.addEventListener("click",()=>{this.handleStartTrack()}),this.container.querySelector("#stop-track-btn")?.addEventListener("click",()=>{this.handleStopTrack()}),this.container.querySelector("#add-geofence-btn")?.addEventListener("click",()=>{this.handleAddGeofence()})}updateLocationDisplay(t){this.currentLocation=t;const e=this.container.querySelector(".latitude-value"),i=this.container.querySelector(".longitude-value"),n=this.container.querySelector(".accuracy-value"),s=this.container.querySelector(".altitude-value"),o=this.container.querySelector(".speed-value");e&&(e.textContent=t.latitude.toFixed(6)),i&&(i.textContent=t.longitude.toFixed(6)),n&&(n.textContent=b.formatAccuracy(t.accuracy)),s&&(s.textContent=t.altitude?`${t.altitude.toFixed(1)} m`:"--"),o&&(o.textContent=t.speed?`${t.speed.toFixed(1)} m/s`:"--")}updateTrackDisplay(t){const e=this.container.querySelector(".track-points-value"),i=this.container.querySelector(".track-distance-value"),n=this.container.querySelector(".track-time-value");if(e&&(e.textContent=t.points.length.toString()),i&&(i.textContent=`${t.totalDistance.toFixed(1)} m`),n){const s=(t.endTime||Date.now())-t.startTime;n.textContent=`${Math.floor(s/6e4)}:${Math.floor(s%6e4/1e3).toString().padStart(2,"0")}`}}onTrackStart(t){this.isRecording=!0,this.currentTrack=t;const e=this.container.querySelector("#track-info"),i=this.container.querySelector("#start-track-btn"),n=this.container.querySelector("#stop-track-btn"),s=this.container.querySelector("#track-name-input");e&&(e.style.display="block"),i&&(i.style.display="none"),n&&(n.style.display="block"),s&&(s.disabled=!0);const o=this.container.querySelector(".track-name-value");o&&(o.textContent=t.name)}onTrackEnd(t){this.isRecording=!1,this.currentTrack=null;const e=this.container.querySelector("#start-track-btn"),i=this.container.querySelector("#stop-track-btn"),n=this.container.querySelector("#track-name-input");e&&(e.style.display="block"),i&&(i.style.display="none"),n&&(n.disabled=!1,n.value=""),alert(`轨迹记录完成：
名称：${t.name}
点数：${t.points.length}
距离：${t.totalDistance.toFixed(1)} m
平均速度：${t.averageSpeed.toFixed(2)} m/s`)}onGeofenceEvent(t){const e=w.getGeofence(t.geofenceId);if(!e)return;let i="";t.type==="enter"?i=`进入地理围栏：${e.name}`:t.type==="exit"?i=`退出地理围栏：${e.name}`:t.type==="dwell"&&(i=`在地理围栏内停留：${e.name}`),this.showNotification(i)}showNotification(t){const e=document.createElement("div");e.className="geofence-notification",e.textContent=t,e.style.cssText=`
      position: fixed;
      top: 20px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 12px 20px;
      border-radius: 4px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      z-index: 10000;
      animation: slideIn 0.3s ease-out;
    `,document.body.appendChild(e),setTimeout(()=>{e.style.animation="slideOut 0.3s ease-out",setTimeout(()=>e.remove(),300)},3e3)}async handleGetLocation(){try{if(b.checkPermission()!=="granted"&&!await b.requestPermission()){alert("位置权限被拒绝");return}const t=await b.getCurrentLocation();this.updateLocationDisplay(t)}catch(t){console.error("获取位置失败:",t),alert("获取位置失败："+t.message)}}async handleCenterOnLocation(){if(!this.currentLocation){alert("请先获取当前位置");return}const t=new CustomEvent("centerOnLocation",{detail:{latitude:this.currentLocation.latitude,longitude:this.currentLocation.longitude}});document.dispatchEvent(t)}async handleStartTrack(){const t=this.container.querySelector("#track-name-input")?.value.trim()||`轨迹_${new Date().toLocaleString()}`;try{await S.startRecording(t)||alert("开始记录轨迹失败")}catch(e){console.error("开始记录轨迹失败:",e),alert("开始记录轨迹失败："+e.message)}}async handleStopTrack(){try{await S.stopRecording()}catch(t){console.error("停止记录轨迹失败:",t),alert("停止记录轨迹失败："+t.message)}}handleAddGeofence(){const t=new CustomEvent("addGeofence");document.dispatchEvent(t)}updateGeofenceList(){const t=this.container.querySelector("#geofence-list");if(!t)return;const e=w.getAllGeofences();if(e.length===0){t.innerHTML='<div class="empty-message">暂无地理围栏</div>';return}t.innerHTML=e.map(i=>`
      <div class="geofence-item">
        <div class="geofence-name">${i.name}</div>
        <div class="geofence-info">
          <span class="label">类型:</span>
          <span class="value">${i.type==="circular"?"圆形":"多边形"}</span>
        </div>
        <div class="geofence-info">
          <span class="label">半径:</span>
          <span class="value">${i.radius.toFixed(0)} m</span>
        </div>
        <div class="geofence-actions">
          <button class="btn btn-sm btn-danger delete-geofence-btn" data-id="${i.id}">删除</button>
        </div>
      </div>
    `).join(""),t.querySelectorAll(".delete-geofence-btn").forEach(i=>{i.addEventListener("click",n=>{const s=n.target.getAttribute("data-id");s&&this.handleDeleteGeofence(s)})})}async handleDeleteGeofence(t){confirm("确定要删除这个地理围栏吗？")&&(await w.deleteGeofence(t),this.updateGeofenceList())}dispose(){this.container.remove()}}}));function dt(t){return new Me(t)}var Me,ut=y((()=>{Ie(),Me=class{constructor(t){this.trackMarkers=new Map,this.currentTrackPolyline=null,this.map=t,this.initializeLayer(),this.initializeListeners()}initializeLayer(){typeof AMap<"u"&&(this.trackLayer=new AMap.LayerGroup,this.map.add(this.trackLayer))}initializeListeners(){S.addTrackUpdateListener(t=>{this.updateCurrentTrack(t)}),S.addTrackStartListener(t=>{this.onTrackStart(t)}),S.addTrackEndListener(t=>{this.onTrackEnd(t)})}onTrackStart(t){typeof AMap<"u"&&(this.currentTrackPolyline=new AMap.Polyline({path:[],strokeColor:"#FF0000",strokeWeight:4,strokeOpacity:.8,showDir:!0}),this.trackLayer.add(this.currentTrackPolyline))}onTrackEnd(t){}updateCurrentTrack(t){if(!this.currentTrackPolyline||t.points.length===0)return;if(typeof AMap<"u"){const i=t.points.map(n=>[n.location.longitude,n.location.latitude]);this.currentTrackPolyline.setPath(i)}const e=t.points[t.points.length-1];this.addTrackMarker(t.id,e)}addTrackMarker(t,e){if(typeof AMap>"u")return;const i=`${t}_${e.index}`;if(this.trackMarkers.has(i)){this.trackMarkers.get(i).setPosition([e.location.longitude,e.location.latitude]);return}const n=new AMap.Marker({position:[e.location.longitude,e.location.latitude],title:`轨迹点 ${e.index}`,content:this.createMarkerContent(e),offset:new AMap.Pixel(-12,-12)});n.on("click",()=>{this.showPointInfo(e)}),this.trackLayer.add(n),this.trackMarkers.set(i,n)}createMarkerContent(t){return t.location.speed&&`${t.location.speed.toFixed(1)}`,t.location.altitude&&`${t.location.altitude.toFixed(1)}`,`
      <div style="
        width: 24px;
        height: 24px;
        background: #FF0000;
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 10px;
        font-weight: bold;
      ">
        ${t.index+1}
      </div>
    `}showPointInfo(t){new AMap.InfoWindow({content:`
        <div style="padding: 10px; min-width: 200px;">
          <h4 style="margin: 0 0 10px 0;">轨迹点 ${t.index+1}</h4>
          <div style="margin-bottom: 5px;">
            <strong>纬度:</strong> ${t.location.latitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>经度:</strong> ${t.location.longitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>海拔:</strong> ${t.location.altitude?t.location.altitude.toFixed(1)+" m":"--"}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>速度:</strong> ${t.location.speed?t.location.speed.toFixed(1)+" m/s":"--"}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>精度:</strong> ${t.location.accuracy.toFixed(1)} m
          </div>
          <div style="margin-bottom: 5px;">
            <strong>时间:</strong> ${new Date(t.timestamp).toLocaleString()}
          </div>
        </div>
      `,offset:new AMap.Pixel(0,-30)}).open(this.map,[t.location.longitude,t.location.latitude])}showTrack(t){const e=S.getTrack(t);if(!(!e||e.points.length===0)&&(this.clearTrack(),typeof AMap<"u")){const i=e.points.map(s=>[s.location.longitude,s.location.latitude]),n=new AMap.Polyline({path:i,strokeColor:"#2196F3",strokeWeight:3,strokeOpacity:.8,showDir:!0});this.trackLayer.add(n),this.addEndpointMarkers(e)}}addEndpointMarkers(t){if(t.points.length===0)return;const e=t.points[0],i=t.points[t.points.length-1],n=new AMap.Marker({position:[e.location.longitude,e.location.latitude],title:"起点",content:`
        <div style="
          width: 24px;
          height: 24px;
          background: #4CAF50;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 12px;
          font-weight: bold;
        ">
          S
        </div>
      `,offset:new AMap.Pixel(-12,-12)}),s=new AMap.Marker({position:[i.location.longitude,i.location.latitude],title:"终点",content:`
        <div style="
          width: 24px;
          height: 24px;
          background: #F44336;
          border: 2px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 12px;
          font-weight: bold;
        ">
          E
        </div>
      `,offset:new AMap.Pixel(-12,-12)});this.trackLayer.add([n,s])}clearTrack(){this.trackLayer&&this.trackLayer.clear(),this.trackMarkers.clear(),this.currentTrackPolyline=null}showAllTracks(){S.getAllTracks().forEach(t=>{this.showTrack(t.id)})}exportTrackAsImage(t){typeof AMap<"u"&&this.map.plugin("AMap.Geolocation",()=>{console.log("导出轨迹图片:",t)})}dispose(){this.clearTrack(),this.trackLayer&&this.map.remove(this.trackLayer)}}}));function ht(t){return new _e(t)}var _e,pt=y((()=>{De(),_e=class{constructor(t){this.geofenceCircles=new Map,this.geofencePolygons=new Map,this.geofenceLabels=new Map,this.map=t,this.initializeLayer(),this.initializeListeners()}initializeLayer(){typeof AMap<"u"&&(this.geofenceLayer=new AMap.LayerGroup,this.map.add(this.geofenceLayer))}initializeListeners(){w.addGeofenceListener(t=>{this.onGeofenceEvent(t)}),typeof AMap<"u"&&this.map.on("click",t=>{this.handleMapClick(t)})}onGeofenceEvent(t){const e=w.getGeofence(t.geofenceId);e&&this.highlightGeofence(e.id,t.type)}highlightGeofence(t,e){let i="#2196F3",n=.3;if(e==="enter"?(i="#4CAF50",n=.5):e==="exit"?(i="#FF9800",n=.5):e==="dwell"&&(i="#F44336",n=.6),this.geofenceCircles.has(t)){const s=this.geofenceCircles.get(t);s.setOptions({fillColor:i,fillOpacity:n}),setTimeout(()=>{s.setOptions({fillColor:"#2196F3",fillOpacity:.3})},2e3)}if(this.geofencePolygons.has(t)){const s=this.geofencePolygons.get(t);s.setOptions({fillColor:i,fillOpacity:n}),setTimeout(()=>{s.setOptions({fillColor:"#2196F3",fillOpacity:.3})},2e3)}}handleMapClick(t){window.isCreatingGeofence&&this.handleCreateGeofence(t.lnglat)}async handleCreateGeofence(t){const e=prompt("请输入围栏半径（米）：","100");if(!e)return;const i=parseFloat(e);if(isNaN(i)||i<=0){alert("请输入有效的半径");return}const n=prompt("请输入围栏名称：",`围栏_${new Date().toLocaleString()}`);if(n)try{const s=await w.createCircularGeofence(n,t.lat,t.lng,i);this.addGeofence(s),alert(`地理围栏 "${n}" 创建成功`),window.isCreatingGeofence=!1}catch(s){console.error("创建地理围栏失败:",s),alert("创建地理围栏失败："+s.message)}}addGeofence(t){t.type==="circular"?this.addCircularGeofence(t):t.type==="polygon"&&this.addPolygonGeofence(t),this.addGeofenceLabel(t)}addCircularGeofence(t){if(typeof AMap>"u")return;const e=new AMap.Circle({center:[t.longitude,t.latitude],radius:t.radius,strokeColor:"#2196F3",strokeWeight:2,strokeOpacity:.8,fillColor:"#2196F3",fillOpacity:.3,zIndex:100});e.on("click",()=>{this.showGeofenceInfo(t)}),e.on("rightclick",()=>{this.showGeofenceContextMenu(t)}),this.geofenceLayer.add(e),this.geofenceCircles.set(t.id,e)}addPolygonGeofence(t){if(typeof AMap>"u")return;if(!t.vertices||t.vertices.length<3){console.error("多边形围栏至少需要3个顶点");return}const e=t.vertices.map(n=>[n.longitude,n.latitude]),i=new AMap.Polygon({path:e,strokeColor:"#2196F3",strokeWeight:2,strokeOpacity:.8,fillColor:"#2196F3",fillOpacity:.3,zIndex:100});i.on("click",()=>{this.showGeofenceInfo(t)}),i.on("rightclick",()=>{this.showGeofenceContextMenu(t)}),this.geofenceLayer.add(i),this.geofencePolygons.set(t.id,i)}addGeofenceLabel(t){if(typeof AMap>"u")return;const e=new AMap.Marker({position:[t.longitude,t.latitude],content:`
        <div style="
          background: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: bold;
          box-shadow: 0 1px 3px rgba(0,0,0,0.2);
          white-space: nowrap;
        ">
          ${t.name}
        </div>
      `,offset:new AMap.Pixel(0,0),zIndex:101});this.geofenceLayer.add(e),this.geofenceLabels.set(t.id,e)}showGeofenceInfo(t){const e=new AMap.InfoWindow({content:`
        <div style="padding: 10px; min-width: 200px;">
          <h4 style="margin: 0 0 10px 0;">${t.name}</h4>
          ${t.description?`<div style="margin-bottom: 10px; color: #666;">${t.description}</div>`:""}
          <div style="margin-bottom: 5px;">
            <strong>类型:</strong> ${t.type==="circular"?"圆形":"多边形"}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>中心:</strong> ${t.latitude.toFixed(6)}, ${t.longitude.toFixed(6)}
          </div>
          <div style="margin-bottom: 5px;">
            <strong>半径:</strong> ${t.radius.toFixed(0)} m
          </div>
          <div style="margin-bottom: 5px;">
            <strong>状态:</strong> ${t.enabled?"启用":"禁用"}
          </div>
          <div style="margin-top: 10px;">
            <button class="btn btn-sm btn-primary edit-geofence-btn" data-id="${t.id}">编辑</button>
            <button class="btn btn-sm btn-danger delete-geofence-btn" data-id="${t.id}">删除</button>
          </div>
        </div>
      `,offset:new AMap.Pixel(0,-30)});e.open(this.map,[t.longitude,t.latitude]),setTimeout(()=>{const i=e.getContent().querySelector(".edit-geofence-btn"),n=e.getContent().querySelector(".delete-geofence-btn");i?.addEventListener("click",()=>{this.handleEditGeofence(t.id),e.close()}),n?.addEventListener("click",()=>{this.handleDeleteGeofence(t.id),e.close()})},100)}showGeofenceContextMenu(t){const e=document.createElement("div");e.className="geofence-context-menu",e.style.cssText=`
      position: absolute;
      background: white;
      border: 1px solid #ddd;
      border-radius: 4px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.2);
      z-index: 1000;
      min-width: 150px;
    `,e.innerHTML=`
      <div class="menu-item" data-action="edit">编辑围栏</div>
      <div class="menu-item" data-action="toggle">启用/禁用</div>
      <div class="menu-item" data-action="delete">删除围栏</div>
    `,document.body.appendChild(e),e.querySelectorAll(".menu-item").forEach(i=>{i.addEventListener("click",n=>{const s=n.target.getAttribute("data-action");s&&this.handleContextMenuAction(t.id,s),e.remove()})}),setTimeout(()=>{document.addEventListener("click",()=>e.remove(),{once:!0})},100)}async handleContextMenuAction(t,e){switch(e){case"edit":this.handleEditGeofence(t);break;case"toggle":this.handleToggleGeofence(t);break;case"delete":this.handleDeleteGeofence(t);break}}handleEditGeofence(t){const e=w.getGeofence(t);if(!e)return;const i=prompt("请输入新的围栏名称：",e.name);i&&(w.updateGeofence(t,{name:i}),this.refreshGeofence(t))}async handleToggleGeofence(t){const e=w.getGeofence(t);e&&(await w.updateGeofence(t,{enabled:!e.enabled}),this.refreshGeofence(t))}async handleDeleteGeofence(t){confirm("确定要删除这个地理围栏吗？")&&(await w.deleteGeofence(t),this.removeGeofence(t))}refreshGeofence(t){this.removeGeofence(t);const e=w.getGeofence(t);e&&this.addGeofence(e)}removeGeofence(t){if(this.geofenceCircles.has(t)){const e=this.geofenceCircles.get(t);this.geofenceLayer.remove(e),this.geofenceCircles.delete(t)}if(this.geofencePolygons.has(t)){const e=this.geofencePolygons.get(t);this.geofenceLayer.remove(e),this.geofencePolygons.delete(t)}if(this.geofenceLabels.has(t)){const e=this.geofenceLabels.get(t);this.geofenceLayer.remove(e),this.geofenceLabels.delete(t)}}showAllGeofences(){w.getAllGeofences().forEach(t=>{this.addGeofence(t)})}clearAllGeofences(){this.geofenceLayer.clear(),this.geofenceCircles.clear(),this.geofencePolygons.clear(),this.geofenceLabels.clear()}dispose(){this.clearAllGeofences(),this.geofenceLayer&&this.map.remove(this.geofenceLayer)}}}));export{Re as A,P as C,Ee as D,U as E,Te as F,c as M,Fe as N,je as O,Q as P,ot as S,N as T,Ze as _,lt as a,Xe as b,De as c,ee as d,b as f,rt as g,Qe as h,ut as i,nt as j,st as k,Ie as l,E as m,pt as n,ct as o,Ae as p,dt as r,w as s,ht as t,S as u,at as v,Ke as w,Ye as x,Z as y};
