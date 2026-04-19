/**
 * 国际化 (i18n) 管理器
 * 支持多语言切换、格式化、懒加载与性能优化
 */

import {
    I18N_AVAILABLE_LOCALE_CODES,
    I18N_DEFAULT_LOCALE as DEFAULT_LOCALE,
    I18N_FALLBACK_LOCALE as FALLBACK_LOCALE,
    I18N_LAZY_LOCALE_LOADERS as LAZY_LOCALE_LOADERS,
    I18N_RTL_LOCALE_PREFIXES as RTL_LOCALE_PREFIXES,
    type LocaleMessages
} from '../i18n/config';

// ========== 语言包 ==========

const ZH_CN: LocaleMessages = {
    // 标题
    'app.title': '智能不确定性驱动空间决策平台',
    'app.subtitle': 'UDAKE',

    // 导航
    'nav.newProject': '新建项目',
    'nav.preferences': '偏好设置',
    'nav.feedback': '反馈建议',
    'nav.guide': '查看引导',
    'nav.themeToggle': '切换主题',
    'nav.language': '语言',
    'nav.mainContent': '跳转到主内容',
    'nav.map': '跳转到地图',
    'nav.projectPanel': '跳转到项目面板',

    // 数据上传
    'upload.title': '数据上传',
    'upload.selectFile': '点击选择 GeoJSON 文件',
    'upload.button': '上传数据',
    'upload.success': '数据导入成功！点数: {count}',
    'upload.noFile': '请选择文件',
    'upload.invalidType': '仅支持 .geojson 或 .json 文件',

    // 插值参数
    'kriging.title': '插值参数',
    'kriging.method': '克里金方法',
    'kriging.ordinary': '普通克里金',
    'kriging.universal': '泛克里金',
    'kriging.block': '分块克里金',
    'kriging.variogram': '变异函数模型',
    'kriging.spherical': '球状模型',
    'kriging.exponential': '指数模型',
    'kriging.gaussian': '高斯模型',
    'kriging.resolution': '网格分辨率',
    'kriging.gridResolution': '网格分辨率',
    'kriging.gridResolution.desc': '影响输出栅格的精细度，值越大越精细但计算越慢',
    'kriging.nlags': '滞后数',
    'kriging.nlags.desc': '变异函数计算时的距离分组数量',
    'kriging.nugget': '变差值',
    'kriging.nugget.desc': '表示测量误差或微观变异，值越小拟合越好',
    'kriging.sill': '基台值',
    'kriging.sill.desc': '变异函数的渐近值，表示总方差',
    'kriging.range': '范围值',
    'kriging.range.desc': '变异函数达到基台值时的距离，表示空间相关范围',
    'kriging.start': '开始插值',
    'kriging.resolutionError': '网格分辨率必须为大于0的整数',
    'advanced.parameters': '高级参数（新手可保持默认）',
    'kriging.help': '参数帮助文档',
    'kriging.help.quick-start': '快速上手',
    'kriging.help.parameter-relations': '参数关系',
    'kriging.help.experience-range': '经验范围',
    'kriging.help.quick-start.suggestion': '先选择“平衡模式”，上传采样点后点击“智能推荐”，最后根据警告做小幅调整。',
    'kriging.help.parameter-relations.suggestion': '建议保持 <code>nugget ≤ sill</code>，且 <code>range</code> 不宜过大，否则容易过平滑。',
    'kriging.help.experience-range.suggestion': '网格分辨率 80~220，滞后数 10~18，块金值通常小于 0.3。',

    // 任务状态
    'task.title': '任务状态',
    'task.noTask': '暂无任务',
    'task.status': '状态',
    'task.progress': '进度',
    'task.started': '任务已启动',
    'task.completed': '插值完成！',
    'task.failed': '任务失败',

    // 导出
    'export.title': '结果导出',
    'export.prediction': '预测结果',
    'export.variance': '方差结果',
    'export.enhanced': '增强导出',
    'export.geojson': '导出 GeoJSON',
    'export.shapefile': '导出 Shapefile',
    'export.geotiff': '导出 GeoTIFF',
    'export.csv': '导出 CSV',
    'export.report': '生成报告',
    'export.downloading': '正在下载 {filename}...',
    'export.done': '{filename} 下载完成',
    'export.failed': '导出失败',

    // 图层
    'layer.title': '图层控制',
    'layer.points': '采样点',
    'layer.prediction': '预测栅格',
    'layer.variance': '方差栅格',

    // 模板
    'template.title': '模板下载',
    'template.desc': '下载 GeoJSON 模板文件，按格式填写数据后上传',
    'template.download': '下载',
    'template.rules': '数据格式要求',
    'template.Parameter': '参数模板',
    'template.balanced': '平衡模式（默认）',
    'template.quick-estimate': '快速估算模式',
    'template.high-precision': '高精度模式',
    'template.large-dataset': '大数据集模式',
    'template.terrain-analysis': '地形分析模式',
    'template.custom': '自定义模板',
    'template.description': '为常见场景提供参数起点，可继续手动微调',
    'template.app': '应用模板',
    'Intelligent.recommend': '智能推荐',
    'template.save': '保存为模板',
    'template.export': '导出模板',
    'template.import': '导入模板',


    // 历史
    'history.title': '操作历史',
    'history.undo': '撤销',
    'history.redo': '重做',
    'history.clear': '清除',
    'history.empty': '暂无操作记录',
    'history.undoAction': '撤销{action}',
    'history.undone': '已撤销: {action}',
    'history.redoAction': '重做{action}',
    'history.redone': '已重做: {action}',

    // 偏好设置
    'prefs.title': '偏好设置',
    'prefs.appearance': '外观',
    'prefs.theme': '主题模式',
    'prefs.themeAuto': '跟随系统',
    'prefs.themeLight': '浅色',
    'prefs.themeDark': '深色',
    'prefs.animations': '启用动画',
    'prefs.map': '地图',
    'prefs.mapEngine': '地图引擎',
    'prefs.showCoords': '显示坐标信息',
    'prefs.data': '数据',
    'prefs.defaultResolution': '默认网格分辨率',
    'prefs.defaultFormat': '默认导出格式',
    'prefs.autoSave': '自动保存',
    'prefs.notifications': '通知',
    'prefs.enableNotifications': '启用通知',
    'prefs.reset': '恢复默认',
    'prefs.save': '保存',

    // 反馈
    'feedback.title': '反馈与建议',
    'feedback.bug': '问题反馈',
    'feedback.feature': '功能建议',
    'feedback.improvement': '体验优化',
    'feedback.other': '其他',
    'feedback.placeholder': '请描述您的反馈内容...',
    'feedback.contact': '联系方式（可选）',
    'feedback.submit': '提交反馈',
    'feedback.cancel': '取消',
    'feedback.stats': '已提交 {count} 条反馈',

    // 离线
    'offline.online': '已恢复在线',
    'offline.offline': '当前处于离线模式',

    // 错误（i18n）
    'error.common.unknown': '未知错误',
    'error.common.retryButton': '重试',
    'error.common.refreshButton': '刷新',
    'error.common.helpButton': '查看帮助',
    'error.common.detailsButton': '查看详情',
    'error.common.icon.error': '⚠️',
    'error.common.icon.warning': '⚠️',
    'error.common.icon.success': '✅',
    'error.geojson_format.message': 'GeoJSON 格式错误',
    'error.geojson_format.suggestion': '请确保文件是标准的 GeoJSON 格式，包含 type 和 features 字段。',
    'error.geojson_format.example': '示例: {"type": "FeatureCollection", "features": [...]}',
    'error.coordinate_format.message': '坐标格式错误',
    'error.coordinate_format.suggestion': '请输入有效的经纬度坐标，经度范围 -180~180，纬度范围 -90~90。',
    'error.coordinate_format.example': '示例: 经度 116.397428, 纬度 39.90923',
    'error.point_out_of_bounds.message': '采样点超出区域边界',
    'error.point_out_of_bounds.suggestion': '请确保采样点在已设定区域边界内，或切换到自由采样模式。',
    'error.geolocation_failed.message': '设备定位失败',
    'error.geolocation_failed.suggestion': '请检查设备 GPS 是否开启，或在室外环境重试。',
    'error.permission_denied.message': '定位权限被拒绝',
    'error.permission_denied.suggestion': '请在浏览器设置中允许本站访问位置信息，然后刷新页面重试。',
    'error.invalid_polygon.message': '无效的多边形数据',
    'error.invalid_polygon.suggestion': '仅支持 Polygon 或 MultiPolygon 类型，请检查 GeoJSON 几何类型。',
    'error.network_error.message': '网络连接失败',
    'error.network_error.suggestion': '请检查网络连接和后端服务是否正常运行。',
    'error.validation_error.message': '数据验证失败',
    'error.validation_error.suggestion': '请检查输入数据是否符合要求。',
    'error.not_found.message': '请求的资源不存在',
    'error.plugin_error.message': '插件执行失败，请稍后重试',
    'error.cache_error.message': '缓存处理失败，请稍后重试',
    'error.solution.check_network': '检查网络连接后再试',
    'error.solution.relogin': '请重新登录后重试',
    'error.solution.request_permission': '请联系管理员开通权限',
    'error.solution.check_resource_path': '请确认资源路径或编号是否正确',
    'error.solution.disable_plugin': '请先禁用相关插件后重试',
    'error.solution.clear_cache': '请清理缓存后重试',
    'error.solution.try_again_later': '请稍后再试',
    'error.server_error.message': '服务器内部错误',
    'error.server_error.suggestion': '服务器处理请求时出错，请稍后重试。如问题持续，请联系管理员。',
    'error.timeout_error.message': '请求超时',
    'error.timeout_error.suggestion': '服务器响应时间过长，请稍后重试或减小数据规模。',
    'error.file_too_large.message': '文件过大',
    'error.file_too_large.suggestion': '上传文件不能超过 50MB，请压缩数据或分批上传。',
    'error.unsupported_format.message': '不支持的文件格式',
    'error.unsupported_format.suggestion': '仅支持 .geojson 和 .json 格式的文件。',
    'error.interpolation_failed.message': '插值计算失败',
    'error.interpolation_failed.suggestion': '可能是采样点分布不合理或参数设置有误，请尝试调整变异函数模型或网格分辨率。',
    'error.insufficient_points.message': '采样点不足',
    'error.insufficient_points.suggestion': '克里金插值至少需要 3 个采样点，请继续添加采样数据。',
    'error.export_failed.message': '导出失败',
    'error.export_failed.suggestion': '文件生成出错，请确认插值任务已完成后重试。',
    'error.validation.geojson_object': 'GeoJSON 必须是一个对象',
    'error.validation.geojson_missing_type': 'GeoJSON 缺少 type 字段',
    'error.validation.geojson_missing_features': 'FeatureCollection 缺少 features 数组',
    'error.validation.geojson_missing_geometry': 'Feature 缺少 geometry 字段',
    'error.validation.geometry_missing_type': '缺少几何类型',
    'error.validation.geometry_unsupported': '不支持的几何类型: {type}，仅支持 Polygon 或 MultiPolygon',
    'error.validation.geometry_missing_coordinates': '缺少坐标数组',
    'error.validation.coordinates_not_number': '经纬度必须是数字',
    'error.validation.coordinates_nan': '经纬度不能是 NaN',
    'error.validation.coordinates_longitude_range': '经度必须在 -180 到 180 之间',
    'error.validation.coordinates_latitude_range': '纬度必须在 -90 到 90 之间',
    'error.geolocation.user_denied': '用户拒绝了定位请求',
    'error.geolocation.position_unavailable': '位置信息不可用',
    'error.geolocation.timeout': '定位请求超时',
    'error.geolocation.unknown': '未知的定位错误',
    'error.grid-resolution': '网格分辨率必须是 1~10000 的正整数',

    // 通用
    'common.confirm': '确认',
    'common.cancel': '取消',
    'common.view': '查看',
    'common.delete': '删除',
    'common.close': '关闭',
    'common.loading': '加载中...',
    'common.error': '错误',
    'common.success': '成功',
    'common.items.one': '{count} 个项目',
    'common.items.other': '{count} 个项目',

    // 设置
    'settings.title': '设置',
    'settings.button': '设置',
    'settings.language': '语言',
    'settings.language.zh-CN': '简体中文',
    'settings.language.en-US': 'English',
    'settings.language.zh-TW': '繁體中文',
    'settings.language.ja-JP': '日本語',
    'settings.language.ko-KR': '한국어',
    'settings.save': '保存',
    'settings.reset': '重置',
    'settings.units': '单位设置',
    'settings.unit.coordinate': '坐标系统',
    'settings.unit.length': '长度单位',
    'settings.unit.area': '面积单位',
    'settings.unit.wgs84': 'WGS84 (经纬度)',
    'settings.unit.gcj02': 'GCJ02 (火星坐标)',
    'settings.unit.bd09': 'BD09 (百度坐标)',
    'settings.unit.m': '米 (m)',
    'settings.unit.km': '千米 (km)',
    'settings.unit.ft': '英尺 (ft)',
    'settings.unit.mi': '英里 (mi)',
    'settings.unit.m2': '平方米 (m²)',
    'settings.unit.km2': '平方千米 (km²)',
    'settings.unit.ha': '公顷 (ha)',
    'settings.unit.ac': '英亩 (ac)',

    // 行业
    'industry.title': '选择行业类型',
    'industry.description': '选择适合您数据特点的行业，系统将自动推荐最优插值参数',
    'industry.select': '行业类型',
    'industry.placeholder': '-- 请选择行业 --',
    'industry.dataId': '数据ID',
    'industry.dataIdHint': '填入您已上传数据集的唯一标识符，用于系统识别和引用该数据',
    'industry.getRecommendation': '获取推荐参数',
    'industry.downloadTemplate': '下载模板',
    'industry.recommendationTitle': '推荐参数',
    'industry.recommendation.industry': '行业',
    'industry.recommendation.method': '克里金方法',
    'industry.recommendation.variogram': '变异函数模型',
    'industry.recommendation.resolution': '网格分辨率',
    'industry.recommendation.nlags': '滞后数',
    'industry.recommendation.anisotropy': '各向异性',
    'industry.recommendation.trend': '趋势检测',
    'industry.recommendation.enabled': '启用',
    'industry.recommendation.disabled': '禁用',

    // 行业名称
    'industry.mining': '矿业',
    'industry.geology': '地质',
    'industry.hydrology': '水文',
    'industry.meteorology': '气象',
    'industry.pollution': '污染',
    'industry.soil': '土壤',
    'industry.environment': '环境',
    'industry.topography': '地形测绘',
    'industry.custom': '自定义',

    // 模版下载
    'template.downloadComplete': '下载完成',
    'template.downloadMessage': '模板文件已成功保存到:',
    'template.openLocation': '打开位置',
    'template.openLocationQuestion': '是否要打开文件所在位置？',
    'template.downloadDialog': '下载模板',
    'template.downloadQuestion': '是否下载 {industry} 的 GeoJSON 模板文件？模板文件名为: {filename}',
    'template.downloadSuccess': '模板下载成功！',
    'template.downloadFailed': '下载模板失败，请稍后重试',
    'template.savedTo': '模板文件 "{filename}" 已下载到您的下载文件夹。',

    // 面板
    'panel.project': '当前项目',
    'panel.upload': '数据上传',
    'panel.kriging': '插值参数',
    'panel.task': '任务状态',
    'panel.export': '结果导出',
    'panel.layer': '图层控制',
    'panel.kriging3d': '3D克里金插值',
    'panel.deepLearning': '深度学习',
    'panel.frontendIntegration': '前端功能集成补齐',
    'explain.panel.title': '模型可解释性增强面板',
    'explain.panel.subtitle': '提交时空解释任务，查看 LIME / SHAP 可视化与对比分析',
    'explain.method.switchAria': '解释方法切换',
    'explain.method.lime': 'LIME',
    'explain.method.shap': 'SHAP',
    'explain.method.hybrid': 'Hybrid',
    'explain.submit.title': '任务提交',
    'explain.task.title': '任务状态',
    'explain.result.title': '解释结果展示',
    'explain.action.submit': '提交解释任务',
    'explain.action.refresh': '刷新队列状态',
    'explain.action.verify': '校验异步后端',
    'explain.result.tab.lime': 'LIME视图',
    'explain.result.tab.shap': 'SHAP视图',
    'explain.result.tab.compare': '对比分析',
    'explain.result.tab.spatiotemporal': '时空视图',
    'explain.status.emptyResult': '暂无结果，请先提交并完成任务。',
    'explain.status.noTask': '暂无任务',
    'explain.status.selectTask': '请选择任务查看结果。',
    'explain.status.taskUnavailable': '任务当前状态：{status}，结果尚不可用。',
    'explain.status.queued': '排队中',
    'explain.status.running': '执行中',
    'explain.status.retrying': '重试中',
    'explain.status.completed': '已完成',
    'explain.status.failed': '失败',
    'explain.status.cancelled': '已取消',
    'explain.task.progress': '进度',
    'explain.task.retry': '重试',
    'explain.task.partial': '已渲染 {visible}/{total} 条任务',
    'explain.task.loadMore': '加载更多',
    'explain.monitor.queue': '队列',
    'explain.monitor.active': '执行中',
    'explain.monitor.successRate': '成功率',
    'explain.monitor.errorRate': '错误率',
    'explain.monitor.avgDuration': '平均耗时',
    'explain.monitor.cache': '缓存',

    // 缓存
    'cache.title': '缓存状态',
    'cache.network': '网络状态',
    'cache.checking': '检测中...',
    'cache.storage': '存储使用',
    'cache.pendingSync': '待同步',
    'cache.manage': '管理缓存',

    // 地图
    'map.clickInfo': '点击信息',
    'sidebar.toggle': '切换侧边栏',
    'map.screenReaderDescription': '地图支持键盘操作。聚焦地图后，可使用方向键平移，+ 或 - 调整缩放。',

    // 采样建议
    'recommendation.title': '采样建议',
    'recommendation.description': '基于不确定性分析的智能采样点推荐',
    'recommendation.strategy': '采样策略',
    'recommendation.strategy.hybrid': '混合策略（推荐）',
    'recommendation.strategy.uncertainty': '不确定性优先',
    'recommendation.strategy.uniform': '均匀分布',
    'recommendation.generate': '生成建议',
    'recommendation.generating': '正在生成采样建议...',
    'recommendation.generated': '成功生成 {count} 个采样建议',
    'recommendation.failed': '生成采样建议失败',
    'recommendation.uncertainty': '不确定性等级',
    'recommendation.reason': '采样理由',
    'recommendation.priority': '优先级',
    'recommendation.priority.high': '高',
    'recommendation.priority.medium': '中',
    'recommendation.priority.low': '低',
    'recommendation.noData': '暂无采样建议',
    'recommendation.error': '加载行业配置失败，请检查后端服务是否正常启动',

    // 对话框
    'dialog.geofence.create.clickMap': '请在地图上点击以创建圆形围栏',
    'dialog.storage.openFolder.unsupported': '当前环境不支持直接打开文件夹，请在系统下载目录中查看。',
    'dialog.template.clear.confirm': '确定要清空已下载模板吗？此操作不可恢复。',
    'dialog.template.cleaned': '已清理 {count} 个模板文件',
    'dialog.template.clearFailed': '清理失败：{error}',
    'dialog.template.fileExistsOverwrite': '文件 "{filename}" 已存在，是否覆盖？',
    'dialog.template.findInBrowserHistory': '请在浏览器的下载历史中找到下载的文件',
    'dialog.template.storagePermissionNotGranted': '存储权限未授予，模板将使用浏览器默认下载方式。您可在系统设置中开启存储权限后重试。',
    'dialog.template.fileDeleteConfirm': '确定要删除模板文件 "{filename}" 吗？',
    'dialog.template.fileDeleteFailed': '删除文件失败：{error}',
    'dialog.template.storagePermissionDenied': '存储权限被拒绝。请在系统设置中开启存储权限后重试。',
    'dialog.template.insufficientStorage': '存储空间不足。请清理设备空间后重试。',
    'dialog.template.downloadFailedWithError': '下载模板失败，请稍后重试。错误信息：{message}',
    'dialog.route.selectStart': '请先选择起点',
    'dialog.route.needMinSamplingPoints': '请至少添加2个采样点',
    'dialog.route.planFailed': '路径规划失败: {error}',
    'dialog.startup.feedbackRecorded': '感谢您的反馈！我们已记录此错误。',
    'dialog.gesture.resetAllConfirm': '确定要重置所有手势设置为默认值吗？',
    'dialog.parameterCombo.applied': '已应用参数组合: {name}',
    'dialog.parameterCombo.saved': '已保存参数组合: {name}',
    'dialog.layout.name.prompt': '请输入布局名称：',
    'dialog.layout.defaultName': '布局_{date}',
    'dialog.layout.saved': '布局 "{name}" 已保存',
    'dialog.layout.none': '没有已保存的布局',
    'dialog.layout.selectToLoad': '请选择要加载的布局：\n{names}',
    'dialog.layout.notFound': '布局不存在',
    'dialog.layout.loaded': '布局 "{name}" 已加载',
    'dialog.layout.resetConfirm': '确定要重置为默认布局吗？',
    'dialog.layout.resetDone': '布局已重置为默认状态',
    'dialog.layout.deleteConfirm': '确定要删除布局 "{name}" 吗？',
    'dialog.location.track.recordCompleted': '轨迹记录完成：\n名称：{name}\n点数：{points}\n距离：{distance} m\n平均速度：{speed} m/s',
    'dialog.location.permissionDenied': '位置权限被拒绝',
    'dialog.location.getCurrentFirst': '请先获取当前位置',
    'dialog.location.getFailed': '获取位置失败：{error}',
    'dialog.location.startTrackFailed': '开始记录轨迹失败',
    'dialog.location.startTrackFailedWithReason': '开始记录轨迹失败：{error}',
    'dialog.location.stopTrackFailed': '停止记录轨迹失败：{error}',
    'dialog.location.deleteGeofenceConfirm': '确定要删除这个地理围栏吗？',
    'dialog.chart.exportFailed': '导出图表失败，请重试',
    'dialog.config.appliedPreset': '已应用 {name} 预设',
    'dialog.config.applied': '已应用配置: {name}',
    'dialog.config.name.prompt': '请输入配置名称：',
    'dialog.config.description.prompt': '请输入配置描述（可选）：',
    'dialog.config.presetType.prompt': '请选择预设类型（environment/agriculture/geology/custom）：',
    'dialog.config.createSuccess': '配置创建成功',
    'dialog.config.createFailed': '创建配置失败: {error}',
    'dialog.config.name.label': '配置名称：',
    'dialog.config.description.label': '配置描述：',
    'dialog.config.updateSuccess': '配置更新成功',
    'dialog.config.updateFailed': '更新配置失败: {error}',
    'dialog.config.copySuccess': '配置复制成功',
    'dialog.config.copyFailed': '复制配置失败: {error}',
    'dialog.config.deleteConfirm': '确定要删除配置 "{name}" 吗？',
    'dialog.config.deleteSuccess': '配置删除成功',
    'dialog.config.deleteFailed': '删除配置失败: {error}',
    'dialog.config.exportSuccess': '配置导出成功',
    'dialog.config.exportFailed': '导出配置失败: {error}',
    'dialog.config.importResult': '导入完成：\n成功: {success}\n失败: {failed}\n错误:\n{errors}',
    'dialog.config.importFailed': '导入配置失败: {error}',
    'dialog.config.resetConfirm': '确定要重置为默认配置吗？这将清除所有自定义配置。',
    'dialog.config.resetSuccess': '已重置为默认配置',
    'dialog.config.resetFailed': '重置失败: {error}',
    'dialog.feedback.maxFiles': '最多只能上传 {maxFiles} 个文件',
    'dialog.feedback.fileTooLarge': '文件 {fileName} 超过 5MB 限制',
    'dialog.feedback.contentRequired': '请填写反馈内容',
    'dialog.feedback.submitSuccess': '反馈已提交，感谢您的建议！',
    'dialog.feedback.clearAllConfirm': '确定要清除所有反馈吗？此操作不可恢复。',
    'dialog.geofence.radius.prompt': '请输入围栏半径（米）：',
    'dialog.geofence.invalidRadius': '请输入有效的半径',
    'dialog.geofence.name.prompt': '请输入围栏名称：',
    'dialog.geofence.defaultName': '围栏_{time}',
    'dialog.geofence.created': '地理围栏 "{name}" 创建成功',
    'dialog.geofence.createFailed': '创建地理围栏失败：{error}',
    'dialog.geofence.rename.prompt': '请输入新的围栏名称：',
    'dialog.industry.getRecommendationFailed': '获取推荐参数失败，请稍后重试',
    'dialog.realtime.subscriptionName.prompt': '请输入订阅名称:',
    'dialog.realtime.updateInterval.prompt': '请输入更新间隔（毫秒）:',
    'dialog.realtime.updateInterval.invalid': '更新间隔必须大于等于1000毫秒',
    'dialog.realtime.clearCacheConfirm': '确定要清空所有缓存吗？',
    'dialog.realtime.resetPerfConfirm': '确定要重置所有性能统计吗？',
    'dialog.recommendation.exportFailed': '导出失败: {error}',
    'dialog.task.result': '任务结果:\n{result}',
    'dialog.task.clearHistoryConfirm': '确定要清空所有历史记录吗？',
    'dialog.parameterTab.name.prompt': '请输入参数组合名称:',
    'dialog.parameterTab.saved': '参数已保存',
    'dialog.parameterTab.deleteConfirm': '确定要删除这条记录吗？',
    'dialog.parameterTab.applied': '已应用参数组合: {name}',
    'dialog.parameterTab.importResult': '导入成功: {success} 条，失败: {failed} 条',
    'dialog.cache.clearAllConfirm': '确定要清除所有缓存吗？此操作不可撤销。',
    'dialog.kriging3d.exportSuccess': '导出成功: {path}',
    'dialog.kriging3d.exportFailed': '导出失败: {error}',

    // 项目信息
    'project.info': '项目信息',
    'project.name': '项目名称',
    'project.mode': '采样模式',
    'project.mode.free': '自由采样',
    'project.mode.region': '区域采样',
    'project.points': '采样点数',
    'project.created': '创建时间',
    'project.status': '项目状态',
    'project.status.active': '活跃',
    'project.status.completed': '已完成',
};

const EN_US: LocaleMessages = {
    'app.title': 'Uncertainty-Driven Adaptive Kriging Engine',
    'app.subtitle': 'UDAKE',
    'nav.newProject': 'New Project',
    'nav.preferences': 'Preferences',
    'nav.feedback': 'Feedback',
    'nav.guide': 'Guide',
    'nav.language': 'Language',
    'nav.mainContent': 'Skip to main content',
    'nav.map': 'Skip to map',
    'nav.projectPanel': 'Skip to project panel',
    'nav.themeToggle': 'Toggle Theme',
    'upload.title': 'Data Upload',
    'upload.selectFile': 'Click to select GeoJSON file',
    'upload.button': 'Upload Data',
    'upload.success': 'Data imported! Points: {count}',
    'upload.noFile': 'Please select a file',
    'upload.invalidType': 'Only .geojson or .json files supported',
    'kriging.title': 'Interpolation Parameters',
    'kriging.method': 'Kriging Method',
    'kriging.ordinary': 'Ordinary Kriging',
    'kriging.universal': 'Universal Kriging',
    'kriging.block': 'Block Kriging',
    'kriging.variogram': 'Variogram Model',
    'kriging.spherical': 'Spherical',
    'kriging.exponential': 'Exponential',
    'kriging.gaussian': 'Gaussian',
    'kriging.resolution': 'Grid Resolution',
    'kriging.gridResolution': 'Grid Resolution',
    'kriging.gridResolution.desc': 'Controls output raster detail. Higher values give finer detail but slower computation',
    'kriging.nlags': 'Number of Lags',
    'kriging.nlags.desc': 'Distance group count used in variogram computation',
    'kriging.nugget': 'Nugget',
    'kriging.nugget.desc': 'Represents measurement error or micro-scale variation; smaller values usually fit better',
    'kriging.sill': 'Sill',
    'kriging.sill.desc': 'Asymptotic variogram value, representing total variance',
    'kriging.range': 'Range',
    'kriging.range.desc': 'Distance where the variogram reaches sill, indicating spatial correlation range',
    'kriging.start': 'Start Interpolation',
    'kriging.resolutionError': 'Grid resolution must be a positive integer',
    'kriging.help': 'Parameter help document',
    'kriging.help.quick-start': 'Quick Start',
    'kriging.help.parameter-relations': 'Parameter Relations',
    'kriging.help.experience-range': 'Experience Range',
    'kriging.help.quick-start.suggestion': 'First, select "Balanced Mode", upload the sampling points, click "Smart Recommendation", and finally make minor adjustments based on the warnings.',
    'kriging.help.parameter-relations.suggest': 'Recommended to maintain',
    'kriging.help.experience-range.suggestion': 'Grid resolution 80~220, lags 10~18, nugget typically less than 0.3.',
    'task.title': 'Task Status',
    'task.noTask': 'No tasks',
    'task.status': 'Status',
    'task.progress': 'Progress',
    'task.started': 'Task started',
    'task.completed': 'Interpolation complete!',
    'task.failed': 'Task failed',
    'export.title': 'Export Results',
    'export.prediction': 'Prediction',
    'export.variance': 'Variance',
    'export.enhanced': 'Enhanced Export',
    'export.geojson': 'Export GeoJSON',
    'export.shapefile': 'Export Shapefile',
    'export.geotiff': 'Export GeoTIFF',
    'export.csv': 'Export CSV',
    'export.report': 'Generate Report',
    'export.downloading': 'Downloading {filename}...',
    'export.done': '{filename} downloaded',
    'export.failed': 'Export failed',
    'layer.title': 'Layer Control',
    'layer.points': 'Sample Points',
    'layer.prediction': 'Prediction Raster',
    'layer.variance': 'Variance Raster',
    'template.title': 'Template Download',
    'template.desc': 'Download GeoJSON templates, fill in data and upload',
    'template.download': 'Download',
    'template.rules': 'Data Format Requirements',
    'history.title': 'Operation History',
    'history.undo': 'Undo',
    'history.redo': 'Redo',
    'history.clear': 'Clear',
    'history.empty': 'No operations recorded',
    'history.undoAction': 'Undo {action}',
    'history.undone': 'Undone: {action}',
    'history.redoAction': 'Redo {action}',
    'history.redone': 'Redone: {action}',
    'prefs.title': 'Preferences',
    'prefs.appearance': 'Appearance',
    'prefs.theme': 'Theme',
    'prefs.themeAuto': 'System',
    'prefs.themeLight': 'Light',
    'prefs.themeDark': 'Dark',
    'prefs.animations': 'Enable Animations',
    'prefs.map': 'Map',
    'prefs.mapEngine': 'Map Engine',
    'prefs.showCoords': 'Show Coordinates',
    'prefs.data': 'Data',
    'prefs.defaultResolution': 'Default Grid Resolution',
    'prefs.defaultFormat': 'Default Export Format',
    'prefs.autoSave': 'Auto Save',
    'prefs.notifications': 'Notifications',
    'prefs.enableNotifications': 'Enable Notifications',
    'prefs.reset': 'Reset',
    'prefs.save': 'Save',
    'feedback.title': 'Feedback',
    'feedback.bug': 'Bug Report',
    'feedback.feature': 'Feature Request',
    'feedback.improvement': 'Improvement',
    'feedback.other': 'Other',
    'feedback.placeholder': 'Describe your feedback...',
    'feedback.contact': 'Contact (optional)',
    'feedback.submit': 'Submit',
    'feedback.cancel': 'Cancel',
    'feedback.stats': '{count} feedback submitted',
    'offline.online': 'Back online',
    'offline.offline': 'Offline mode',
    'advanced.parameters': 'Advanced Parameters (Novices can keep the defaults)',

    // Errors (i18n)
    'error.common.unknown': 'Unknown error',
    'error.common.retryButton': 'Retry',
    'error.common.refreshButton': 'Refresh',
    'error.common.helpButton': 'Help',
    'error.common.detailsButton': 'View details',
    'error.common.icon.error': '⚠️',
    'error.common.icon.warning': '⚠️',
    'error.common.icon.success': '✅',
    'error.geojson_format.message': 'Invalid GeoJSON format',
    'error.geojson_format.suggestion': 'Please provide standard GeoJSON with type and features fields.',
    'error.geojson_format.example': 'Example: {"type":"FeatureCollection","features":[...]}',
    'error.coordinate_format.message': 'Invalid coordinate format',
    'error.coordinate_format.suggestion': 'Please enter valid longitude and latitude. Longitude -180~180, latitude -90~90.',
    'error.coordinate_format.example': 'Example: longitude 116.397428, latitude 39.90923',
    'error.point_out_of_bounds.message': 'Sample point is outside boundary',
    'error.point_out_of_bounds.suggestion': 'Keep points inside the selected boundary or switch to free sampling mode.',
    'error.geolocation_failed.message': 'Geolocation failed',
    'error.geolocation_failed.suggestion': 'Check whether device GPS is enabled and retry in an open area.',
    'error.permission_denied.message': 'Location permission denied',
    'error.permission_denied.suggestion': 'Allow location access in browser settings and refresh this page.',
    'error.invalid_polygon.message': 'Invalid polygon data',
    'error.invalid_polygon.suggestion': 'Only Polygon or MultiPolygon is supported. Please check geometry type.',
    'error.network_error.message': 'Network connection failed',
    'error.network_error.suggestion': 'Check network connectivity and backend service health.',
    'error.validation_error.message': 'Data validation failed',
    'error.validation_error.suggestion': 'Please check whether input data meets requirements.',
    'error.not_found.message': 'Requested resource does not exist',
    'error.plugin_error.message': 'Plugin execution failed. Please try again later.',
    'error.cache_error.message': 'Cache processing failed. Please try again later.',
    'error.solution.check_network': 'Check network connectivity and retry',
    'error.solution.relogin': 'Please sign in again and retry',
    'error.solution.request_permission': 'Please request required permission from administrator',
    'error.solution.check_resource_path': 'Please verify resource path or identifier',
    'error.solution.disable_plugin': 'Disable related plugin and retry',
    'error.solution.clear_cache': 'Clear local cache and retry',
    'error.solution.try_again_later': 'Please try again later',
    'error.server_error.message': 'Internal server error',
    'error.server_error.suggestion': 'Server failed to process the request. Please try again later.',
    'error.timeout_error.message': 'Request timeout',
    'error.timeout_error.suggestion': 'Server response took too long. Retry later or reduce data size.',
    'error.file_too_large.message': 'File too large',
    'error.file_too_large.suggestion': 'Upload size must be under 50MB. Please compress or split the file.',
    'error.unsupported_format.message': 'Unsupported file format',
    'error.unsupported_format.suggestion': 'Only .geojson and .json files are supported.',
    'error.interpolation_failed.message': 'Interpolation failed',
    'error.interpolation_failed.suggestion': 'Sampling distribution or parameters may be invalid. Adjust variogram model or grid resolution.',
    'error.insufficient_points.message': 'Insufficient sample points',
    'error.insufficient_points.suggestion': 'Kriging requires at least 3 sample points. Please add more data.',
    'error.export_failed.message': 'Export failed',
    'error.export_failed.suggestion': 'File generation failed. Please ensure interpolation task is completed and retry.',
    'error.validation.geojson_object': 'GeoJSON must be an object',
    'error.validation.geojson_missing_type': 'GeoJSON is missing type field',
    'error.validation.geojson_missing_features': 'FeatureCollection is missing features array',
    'error.validation.geojson_missing_geometry': 'Feature is missing geometry field',
    'error.validation.geometry_missing_type': 'Missing geometry type',
    'error.validation.geometry_unsupported': 'Unsupported geometry type: {type}. Only Polygon or MultiPolygon is supported',
    'error.validation.geometry_missing_coordinates': 'Missing coordinates array',
    'error.validation.coordinates_not_number': 'Longitude and latitude must be numbers',
    'error.validation.coordinates_nan': 'Longitude and latitude cannot be NaN',
    'error.validation.coordinates_longitude_range': 'Longitude must be between -180 and 180',
    'error.validation.coordinates_latitude_range': 'Latitude must be between -90 and 90',
    'error.geolocation.user_denied': 'User denied the geolocation request',
    'error.geolocation.position_unavailable': 'Position information is unavailable',
    'error.geolocation.timeout': 'Geolocation request timed out',
    'error.geolocation.unknown': 'Unknown geolocation error',
    'error.grid-resolution': 'Grid resolution must be a positive integer between 1 and 10000',

    // 通用
    'common.confirm': 'Confirm',
    'common.cancel': 'Cancel',
    'common.view': 'View',
    'common.delete': 'Delete',
    'common.close': 'Close',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.success': 'Success',
    'common.items.one': '{count} item',
    'common.items.other': '{count} items',

    // 设置
    'settings.title': 'Settings',
    'settings.button': 'Settings',
    'settings.language': 'Language',
    'settings.language.zh-CN': '简体中文',
    'settings.language.en-US': 'English',
    'settings.language.zh-TW': '繁體中文',
    'settings.language.ja-JP': '日本語',
    'settings.language.ko-KR': '한국어',
    'settings.save': 'Save',
    'settings.reset': 'Reset',
    'settings.units': 'Unit Settings',
    'settings.unit.coordinate': 'Coordinate System',
    'settings.unit.length': 'Length Unit',
    'settings.unit.area': 'Area Unit',
    'settings.unit.wgs84': 'WGS84 (Latitude/Longitude)',
    'settings.unit.gcj02': 'GCJ02 (Mars Coordinates)',
    'settings.unit.bd09': 'BD09 (Baidu Coordinates)',
    'settings.unit.m': 'Meter (m)',
    'settings.unit.km': 'Kilometer (km)',
    'settings.unit.ft': 'Foot (ft)',
    'settings.unit.mi': 'Mile (mi)',
    'settings.unit.m2': 'Square Meter (m²)',
    'settings.unit.km2': 'Square Kilometer (km²)',
    'settings.unit.ha': 'Hectare (ha)',
    'settings.unit.ac': 'Acre (ac)',

    // 行业
    'industry.title': 'Select Industry',
    'industry.description': 'Select an industry that matches your data characteristics, and the system will automatically recommend optimal interpolation parameters',
    'industry.select': 'Industry Type',
    'industry.placeholder': '-- Select Industry --',
    'industry.dataId': 'Data ID',
    'industry.dataIdHint': 'Enter the unique identifier of your uploaded dataset for system identification and reference',
    'industry.getRecommendation': 'Get Recommendations',
    'industry.downloadTemplate': 'Download Template',
    'industry.recommendationTitle': 'Recommended Parameters',
    'industry.recommendation.industry': 'Industry',
    'industry.recommendation.method': 'Kriging Method',
    'industry.recommendation.variogram': 'Variogram Model',
    'industry.recommendation.resolution': 'Grid Resolution',
    'industry.recommendation.nlags': 'Number of Lags',
    'industry.recommendation.anisotropy': 'Anisotropy',
    'industry.recommendation.trend': 'Trend Detection',
    'industry.recommendation.enabled': 'Enabled',
    'industry.recommendation.disabled': 'Disabled',

    // 行业名称
    'industry.mining': 'Mining',
    'industry.geology': 'Geology',
    'industry.hydrology': 'Hydrology',
    'industry.meteorology': 'Meteorology',
    'industry.pollution': 'Pollution',
    'industry.soil': 'Soil',
    'industry.environment': 'Environment',
    'industry.topography': 'Topographic Mapping',
    'industry.custom': 'Custom',

    // 模版下载
    'template.downloadComplete': 'Download Complete',
    'template.downloadMessage': 'Template file has been saved to:',
    'template.openLocation': 'Open Location',
    'template.openLocationQuestion': 'Do you want to open the file location?',
    'template.downloadDialog': 'Download Template',
    'template.downloadQuestion': 'Do you want to download the GeoJSON template for {industry}? Template filename: {filename}',
    'template.downloadSuccess': 'Template downloaded successfully!',
    'template.downloadFailed': 'Failed to download template, please try again later',
    'template.savedTo': 'Template file "{filename}" has been downloaded to your Downloads folder.',
    'template.Parameter': 'Parameter Template',
    'template.balanced': 'Balanced Sampling Template',
    'template.quick-estimate': 'Quick Estimate Template',
    'template.high-precision': 'High Precision Template',
    'template.large-dataset': 'Large Dataset Template',
    'template.terrain-analysis': 'Terrain Analysis Template',
    'template.custom': 'Custom Template',
    'template.description': 'Provide the starting point of parameters for common scenarios, and you can continue to manually fine-tune.',
    'template.app': 'Applicate the Template',
    'template.save': 'Save as Template',
    'template.export': 'Export the Template',
    'template.import': 'Import Template',

    // 面板
    'panel.project': 'Current Project',
    'panel.upload': 'Data Upload',
    'panel.kriging': 'Interpolation Parameters',
    'panel.task': 'Task Status',
    'panel.export': 'Export Results',
    'panel.layer': 'Layer Control',
    'panel.kriging3d': '3D Kriging Interpolation',
    'panel.deepLearning': 'Deep Learning',
    'panel.frontendIntegration': 'Frontend Integration Completion',
    'explain.panel.title': 'Model Explainability Enhancement Panel',
    'explain.panel.subtitle': 'Submit spatiotemporal explainability tasks and inspect LIME/SHAP visualizations with comparison analysis',
    'explain.method.switchAria': 'Explainability method switch',
    'explain.method.lime': 'LIME',
    'explain.method.shap': 'SHAP',
    'explain.method.hybrid': 'Hybrid',
    'explain.submit.title': 'Task Submission',
    'explain.task.title': 'Task Status',
    'explain.result.title': 'Explainability Results',
    'explain.action.submit': 'Submit Explain Task',
    'explain.action.refresh': 'Refresh Queue Status',
    'explain.action.verify': 'Verify Async Backend',
    'explain.result.tab.lime': 'LIME View',
    'explain.result.tab.shap': 'SHAP View',
    'explain.result.tab.compare': 'Comparison',
    'explain.result.tab.spatiotemporal': 'Spatiotemporal View',
    'explain.status.emptyResult': 'No result yet. Submit and complete a task first.',
    'explain.status.noTask': 'No tasks',
    'explain.status.selectTask': 'Select a task to view results.',
    'explain.status.taskUnavailable': 'Current task status: {status}. Result is not available yet.',
    'explain.status.queued': 'Queued',
    'explain.status.running': 'Running',
    'explain.status.retrying': 'Retrying',
    'explain.status.completed': 'Completed',
    'explain.status.failed': 'Failed',
    'explain.status.cancelled': 'Cancelled',
    'explain.task.progress': 'Progress',
    'explain.task.retry': 'Retries',
    'explain.task.partial': 'Rendered {visible}/{total} tasks',
    'explain.task.loadMore': 'Load More',
    'explain.monitor.queue': 'Queue',
    'explain.monitor.active': 'Active',
    'explain.monitor.successRate': 'Success Rate',
    'explain.monitor.errorRate': 'Error Rate',
    'explain.monitor.avgDuration': 'Avg Duration',
    'explain.monitor.cache': 'Cache',

    // Cache
    'cache.title': 'Cache Status',
    'cache.network': 'Network Status',
    'cache.checking': 'Checking...',
    'cache.storage': 'Storage Usage',
    'cache.pendingSync': 'Pending Sync',
    'cache.manage': 'Manage Cache',

    // Map
    'map.clickInfo': 'Click Information',
    'sidebar.toggle': 'Toggle Sidebar',
    'map.screenReaderDescription': 'Map supports keyboard navigation. After focusing on the map, you can use arrow keys to pan, and + or - to adjust zoom.',

    // 采样建议
    'recommendation.title': 'Sampling Recommendations',
    'recommendation.description': 'Intelligent sampling point recommendations based on uncertainty analysis',
    'recommendation.strategy': 'Sampling Strategy',
    'recommendation.strategy.hybrid': 'Hybrid (Recommended)',
    'recommendation.strategy.uncertainty': 'Uncertainty Priority',
    'recommendation.strategy.uniform': 'Uniform Distribution',
    'recommendation.generate': 'Generate',
    'recommendation.generating': 'Generating sampling recommendations...',
    'recommendation.generated': 'Successfully generated {count} sampling recommendations',
    'recommendation.failed': 'Failed to generate sampling recommendations',
    'recommendation.uncertainty': 'Uncertainty Level',
    'recommendation.reason': 'Sampling Reason',
    'recommendation.priority': 'Priority',
    'recommendation.priority.high': 'High',
    'recommendation.priority.medium': 'Medium',
    'recommendation.priority.low': 'Low',
    'recommendation.noData': 'No sampling recommendations available',
    'recommendation.error': 'Failed to load industry configuration, please check if the backend service is running',
    'Intelligent.recommend': 'Intelligent Recommend',

    // Dialog
    'dialog.geofence.create.clickMap': 'Please click on the map to create a circular geofence',
    'dialog.storage.openFolder.unsupported': 'Directly opening folders is unsupported in this environment. Please check the system Downloads directory.',
    'dialog.template.clear.confirm': 'Are you sure you want to clear downloaded templates? This action cannot be undone.',
    'dialog.template.cleaned': 'Cleaned {count} template files',
    'dialog.template.clearFailed': 'Cleanup failed: {error}',
    'dialog.template.fileExistsOverwrite': 'File "{filename}" already exists. Overwrite it?',
    'dialog.template.findInBrowserHistory': 'Please find the downloaded file in your browser download history',
    'dialog.template.storagePermissionNotGranted': 'Storage permission is not granted. Templates will use browser download mode. Enable storage permission in system settings and retry.',
    'dialog.template.fileDeleteConfirm': 'Are you sure you want to delete template file "{filename}"?',
    'dialog.template.fileDeleteFailed': 'Failed to delete file: {error}',
    'dialog.template.storagePermissionDenied': 'Storage permission denied. Please enable storage permission in system settings and retry.',
    'dialog.template.insufficientStorage': 'Insufficient storage space. Please free up space and retry.',
    'dialog.template.downloadFailedWithError': 'Template download failed. Please retry later. Error: {message}',
    'dialog.route.selectStart': 'Please select a start point first',
    'dialog.route.needMinSamplingPoints': 'Please add at least 2 sampling points',
    'dialog.route.planFailed': 'Route planning failed: {error}',
    'dialog.startup.feedbackRecorded': 'Thanks for your feedback. We have recorded this error.',
    'dialog.gesture.resetAllConfirm': 'Are you sure you want to reset all gesture settings to defaults?',
    'dialog.parameterCombo.applied': 'Applied parameter combination: {name}',
    'dialog.parameterCombo.saved': 'Saved parameter combination: {name}',
    'dialog.layout.name.prompt': 'Enter layout name:',
    'dialog.layout.defaultName': 'layout_{date}',
    'dialog.layout.saved': 'Layout "{name}" has been saved',
    'dialog.layout.none': 'No saved layouts',
    'dialog.layout.selectToLoad': 'Please choose a layout to load:\n{names}',
    'dialog.layout.notFound': 'Layout not found',
    'dialog.layout.loaded': 'Layout "{name}" has been loaded',
    'dialog.layout.resetConfirm': 'Are you sure you want to reset to default layout?',
    'dialog.layout.resetDone': 'Layout has been reset to default',
    'dialog.layout.deleteConfirm': 'Are you sure you want to delete layout "{name}"?',
    'dialog.location.track.recordCompleted': 'Track recording completed:\nName: {name}\nPoints: {points}\nDistance: {distance} m\nAverage speed: {speed} m/s',
    'dialog.location.permissionDenied': 'Location permission denied',
    'dialog.location.getCurrentFirst': 'Please get current location first',
    'dialog.location.getFailed': 'Failed to get location: {error}',
    'dialog.location.startTrackFailed': 'Failed to start track recording',
    'dialog.location.startTrackFailedWithReason': 'Failed to start track recording: {error}',
    'dialog.location.stopTrackFailed': 'Failed to stop track recording: {error}',
    'dialog.location.deleteGeofenceConfirm': 'Are you sure you want to delete this geofence?',
    'dialog.chart.exportFailed': 'Failed to export chart, please try again',
    'dialog.config.appliedPreset': 'Applied preset: {name}',
    'dialog.config.applied': 'Applied config: {name}',
    'dialog.config.name.prompt': 'Enter config name:',
    'dialog.config.description.prompt': 'Enter config description (optional):',
    'dialog.config.presetType.prompt': 'Choose preset type (environment/agriculture/geology/custom):',
    'dialog.config.createSuccess': 'Config created successfully',
    'dialog.config.createFailed': 'Failed to create config: {error}',
    'dialog.config.name.label': 'Config name:',
    'dialog.config.description.label': 'Config description:',
    'dialog.config.updateSuccess': 'Config updated successfully',
    'dialog.config.updateFailed': 'Failed to update config: {error}',
    'dialog.config.copySuccess': 'Config copied successfully',
    'dialog.config.copyFailed': 'Failed to copy config: {error}',
    'dialog.config.deleteConfirm': 'Are you sure you want to delete config "{name}"?',
    'dialog.config.deleteSuccess': 'Config deleted successfully',
    'dialog.config.deleteFailed': 'Failed to delete config: {error}',
    'dialog.config.exportSuccess': 'Config exported successfully',
    'dialog.config.exportFailed': 'Failed to export config: {error}',
    'dialog.config.importResult': 'Import finished:\nSuccess: {success}\nFailed: {failed}\nErrors:\n{errors}',
    'dialog.config.importFailed': 'Failed to import config: {error}',
    'dialog.config.resetConfirm': 'Are you sure you want to reset to default config? This will clear all custom configs.',
    'dialog.config.resetSuccess': 'Reset to default config completed',
    'dialog.config.resetFailed': 'Reset failed: {error}',
    'dialog.feedback.maxFiles': 'You can upload up to {maxFiles} files',
    'dialog.feedback.fileTooLarge': 'File {fileName} exceeds the 5MB limit',
    'dialog.feedback.contentRequired': 'Please fill in feedback content',
    'dialog.feedback.submitSuccess': 'Feedback submitted. Thank you for your suggestion!',
    'dialog.feedback.clearAllConfirm': 'Are you sure you want to clear all feedback? This action cannot be undone.',
    'dialog.geofence.radius.prompt': 'Please enter geofence radius (meters):',
    'dialog.geofence.invalidRadius': 'Please enter a valid radius',
    'dialog.geofence.name.prompt': 'Please enter geofence name:',
    'dialog.geofence.defaultName': 'geofence_{time}',
    'dialog.geofence.created': 'Geofence "{name}" created successfully',
    'dialog.geofence.createFailed': 'Failed to create geofence: {error}',
    'dialog.geofence.rename.prompt': 'Please enter a new geofence name:',
    'dialog.industry.getRecommendationFailed': 'Failed to get recommended parameters. Please try again later.',
    'dialog.realtime.subscriptionName.prompt': 'Please enter subscription name:',
    'dialog.realtime.updateInterval.prompt': 'Please enter update interval (ms):',
    'dialog.realtime.updateInterval.invalid': 'Update interval must be greater than or equal to 1000 ms',
    'dialog.realtime.clearCacheConfirm': 'Are you sure you want to clear all cache?',
    'dialog.realtime.resetPerfConfirm': 'Are you sure you want to reset all performance metrics?',
    'dialog.recommendation.exportFailed': 'Export failed: {error}',
    'dialog.task.result': 'Task result:\n{result}',
    'dialog.task.clearHistoryConfirm': 'Are you sure you want to clear all history records?',
    'dialog.parameterTab.name.prompt': 'Enter parameter combination name:',
    'dialog.parameterTab.saved': 'Parameters have been saved',
    'dialog.parameterTab.deleteConfirm': 'Are you sure you want to delete this record?',
    'dialog.parameterTab.applied': 'Applied parameter combination: {name}',
    'dialog.parameterTab.importResult': 'Import succeeded: {success}, failed: {failed}',
    'dialog.cache.clearAllConfirm': 'Are you sure you want to clear all cache? This action cannot be undone.',
    'dialog.kriging3d.exportSuccess': 'Export succeeded: {path}',
    'dialog.kriging3d.exportFailed': 'Export failed: {error}',

    // 项目信息
    'project.info': 'Project Information',
    'project.name': 'Project Name',
    'project.mode': 'Sampling Mode',
    'project.mode.free': 'Free Sampling',
    'project.mode.region': 'Region Sampling',
    'project.points': 'Sample Points',
    'project.created': 'Created',
    'project.status': 'Status',
    'project.status.active': 'Active',
    'project.status.completed': 'Completed',
};

// ========== 语言包注册表 ==========

const LOCALES: Record<string, LocaleMessages> = {
    'zh-CN': ZH_CN,
    'en-US': EN_US,
};

type IntlFormatter =
    | Intl.DateTimeFormat
    | Intl.NumberFormat
    | Intl.RelativeTimeFormat
    | Intl.Collator
    | Intl.PluralRules;

// ========== I18n 管理器 ==========

export class I18n {
    private static _locale: string = DEFAULT_LOCALE;
    private static _listeners: Set<(locale: string) => void> = new Set();
    private static _missingKeyUsage: Map<string, number> = new Map();
    private static _translationCache: Map<string, string> = new Map();
    private static _pendingLocaleLoads: Map<string, Promise<boolean>> = new Map();
    private static _intlFormatterCache: Map<string, IntlFormatter> = new Map();
    private static _timeZone: string | null = null;

    static init(locale?: string): void {
        const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('udake_locale') : null;
        this._locale = this.normalizeLocale(locale || saved || navigator.language || DEFAULT_LOCALE);
        this.applyLocaleSideEffects(this._locale);
        void this.ensureLocaleLoaded(this._locale).then((loaded) => {
            if (loaded && this._locale) {
                this.applyLocaleSideEffects(this._locale);
            }
        });
    }

    static get locale(): string { return this._locale; }

    static setLocale(locale: string): void {
        const normalized = this.normalizeLocale(locale);
        const isUnsupportedInput = normalized === FALLBACK_LOCALE
            && !LOCALES[locale]
            && !LAZY_LOCALE_LOADERS[locale]
            && !locale.toLowerCase().startsWith('en');
        if (isUnsupportedInput) {
            return;
        }
        if (!LOCALES[normalized] && LAZY_LOCALE_LOADERS[normalized]) {
            void this.setLocaleAsync(normalized);
            return;
        }
        if (!LOCALES[normalized]) {
            return;
        }
        this.applyLocale(normalized);
    }

    static async setLocaleAsync(locale: string): Promise<boolean> {
        const normalized = this.normalizeLocale(locale);
        const isUnsupportedInput = normalized === FALLBACK_LOCALE
            && !LOCALES[locale]
            && !LAZY_LOCALE_LOADERS[locale]
            && !locale.toLowerCase().startsWith('en');
        if (isUnsupportedInput) {
            return false;
        }
        const loaded = await this.ensureLocaleLoaded(normalized);
        if (!loaded) {
            return false;
        }
        this.applyLocale(normalized);
        return true;
    }

    /** 获取翻译文本，支持 {key} 插值 */
    static t(key: string, params?: Record<string, string | number>): string {
        if (key === '') {
            return '';
        }
        const cachedKey = params ? null : `${this._locale}:${key}`;
        if (cachedKey && this._translationCache.has(cachedKey)) {
            return this._translationCache.get(cachedKey)!;
        }

        let text = this.resolveMessage(key, this._locale);
        if (text === key) {
            const count = this._missingKeyUsage.get(key) || 0;
            this._missingKeyUsage.set(key, count + 1);
        }

        if (params) {
            text = text.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, paramName: string) => {
                const value = params[paramName];
                return value === undefined ? match : String(value);
            });
        }

        if (cachedKey && text !== key) {
            this._translationCache.set(cachedKey, text);
        }

        return text;
    }

    /** 复数翻译：优先使用 .one/.other（也支持 Intl.PluralRules 分类） */
    static tp(baseKey: string, count: number, params?: Record<string, string | number>): string {
        const pluralRules = this.getIntlFormatter(
            `plural:${this._locale}`,
            () => new Intl.PluralRules(this.toIntlLocale(this._locale))
        ) as Intl.PluralRules;
        const pluralCategory = pluralRules.select(count);
        const candidates = [
            `${baseKey}.${pluralCategory}`,
            `${baseKey}.${count === 1 ? 'one' : 'other'}`,
            baseKey
        ];
        const mergedParams = { count, ...(params || {}) };
        const resolved = candidates.find((candidate) => this.hasKey(candidate));
        return this.t(resolved || baseKey, mergedParams);
    }

    /** 变体翻译：如 greeting.male / greeting.female */
    static tv(baseKey: string, variant: string, params?: Record<string, string | number>): string {
        const variantKey = `${baseKey}.${variant}`;
        return this.hasKey(variantKey) ? this.t(variantKey, params) : this.t(baseKey, params);
    }

    static getMissingKeys(baseLocale: string = 'zh-CN'): Record<string, string[]> {
        const baseMessages = LOCALES[baseLocale] || {};
        const baseKeys = Object.keys(baseMessages);
        const result: Record<string, string[]> = {};

        Object.entries(LOCALES).forEach(([locale, messages]) => {
            if (locale === baseLocale) {
                return;
            }
            result[locale] = baseKeys.filter(key => !(key in messages));
        });

        return result;
    }

    static getLocaleCoverage(locale: string, baseLocale: string = 'zh-CN'): number {
        const baseMessages = LOCALES[baseLocale] || {};
        const targetMessages = LOCALES[locale] || {};
        const total = Object.keys(baseMessages).length;
        if (total === 0) {
            return 1;
        }
        const available = Object.keys(baseMessages).filter(key => key in targetMessages).length;
        return available / total;
    }

    static getMissingKeyUsage(): Array<{ key: string; count: number }> {
        return Array.from(this._missingKeyUsage.entries())
            .map(([key, count]) => ({ key, count }))
            .sort((a, b) => b.count - a.count);
    }

    static clearMissingKeyUsage(): void {
        this._missingKeyUsage.clear();
    }

    static async preloadAllLocales(): Promise<void> {
        const allLocaleCodes = Object.keys(LAZY_LOCALE_LOADERS);
        await Promise.all(allLocaleCodes.map((localeCode) => this.ensureLocaleLoaded(localeCode)));
    }

    static formatDate(
        value: Date | number | string,
        options: Intl.DateTimeFormatOptions = {},
        locale: string = this._locale
    ): string {
        const date = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(date.getTime())) {
            return '';
        }
        const effectiveLocale = this.normalizeLocale(locale);
        const timeZone = options.timeZone || this.getTimeZone();
        const cacheKey = `date:${effectiveLocale}:${timeZone}:${JSON.stringify(options)}`;
        const formatter = this.getIntlFormatter(
            cacheKey,
            () => new Intl.DateTimeFormat(this.toIntlLocale(effectiveLocale), { ...options, timeZone })
        ) as Intl.DateTimeFormat;
        return formatter.format(date);
    }

    static formatDateTime(
        value: Date | number | string,
        locale: string = this._locale
    ): string {
        return this.formatDate(
            value,
            {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            },
            locale
        );
    }

    static formatNumber(
        value: number,
        options: Intl.NumberFormatOptions = {},
        locale: string = this._locale
    ): string {
        const effectiveLocale = this.normalizeLocale(locale);
        const cacheKey = `number:${effectiveLocale}:${JSON.stringify(options)}`;
        const formatter = this.getIntlFormatter(
            cacheKey,
            () => new Intl.NumberFormat(this.toIntlLocale(effectiveLocale), options)
        ) as Intl.NumberFormat;
        return formatter.format(value);
    }

    static formatCurrency(
        value: number,
        currency: string = 'CNY',
        locale: string = this._locale
    ): string {
        return this.formatNumber(
            value,
            {
                style: 'currency',
                currency,
                currencyDisplay: 'symbol'
            },
            locale
        );
    }

    static formatRelativeTime(
        value: number,
        unit: Intl.RelativeTimeFormatUnit,
        locale: string = this._locale
    ): string {
        const effectiveLocale = this.normalizeLocale(locale);
        const cacheKey = `relative:${effectiveLocale}`;
        const formatter = this.getIntlFormatter(
            cacheKey,
            () => new Intl.RelativeTimeFormat(this.toIntlLocale(effectiveLocale), { numeric: 'auto' })
        ) as Intl.RelativeTimeFormat;
        return formatter.format(value, unit);
    }

    static sortByLocale(
        values: string[],
        locale: string = this._locale,
        options: Intl.CollatorOptions = {}
    ): string[] {
        const effectiveLocale = this.normalizeLocale(locale);
        const cacheKey = `collator:${effectiveLocale}:${JSON.stringify(options)}`;
        const collator = this.getIntlFormatter(
            cacheKey,
            () => new Intl.Collator(this.toIntlLocale(effectiveLocale), { numeric: true, sensitivity: 'base', ...options })
        ) as Intl.Collator;
        return [...values].sort((a, b) => collator.compare(a, b));
    }

    static setTimeZone(timeZone: string | null): void {
        this._timeZone = timeZone && timeZone.trim() ? timeZone.trim() : null;
        this._intlFormatterCache.clear();
    }

    static getTimeZone(): string {
        if (this._timeZone) {
            return this._timeZone;
        }
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        } catch {
            return 'UTC';
        }
    }

    static getDirection(locale: string = this._locale): 'ltr' | 'rtl' {
        const normalized = this.normalizeLocale(locale).toLowerCase();
        return RTL_LOCALE_PREFIXES.some((prefix) => normalized.startsWith(prefix)) ? 'rtl' : 'ltr';
    }

    static applyToDOM(root: ParentNode = document): void {
        if (typeof document === 'undefined') {
            return;
        }

        const hasElementCtor = typeof Element !== 'undefined';
        const isElementRoot = hasElementCtor && root instanceof Element;
        const canQuery = typeof (root as ParentNode & { querySelectorAll?: unknown }).querySelectorAll === 'function';

        if (!isElementRoot && !canQuery) {
            return;
        }

        const resolveNodes = (selector: string): Element[] => {
            const nodes: Element[] = [];
            if (isElementRoot && (root as Element).matches(selector)) {
                nodes.push(root);
            }
            if (canQuery) {
                nodes.push(...Array.from(root.querySelectorAll(selector)));
            }
            return nodes;
        };

        resolveNodes('[data-i18n]').forEach((node) => {
            const key = node.getAttribute('data-i18n');
            if (key) {
                node.textContent = this.t(key);
            }
        });

        const attrPairs: Array<[string, string]> = [
            ['data-i18n-title', 'title'],
            ['data-i18n-placeholder', 'placeholder'],
            ['data-i18n-aria-label', 'aria-label'],
            ['data-i18n-value', 'value']
        ];

        attrPairs.forEach(([dataAttr, targetAttr]) => {
            resolveNodes(`[${dataAttr}]`).forEach((node) => {
                const key = node.getAttribute(dataAttr);
                if (!key) {
                    return;
                }

                const value = this.t(key);
                if (targetAttr === 'value' && typeof HTMLInputElement !== 'undefined' && node instanceof HTMLInputElement) {
                    node.value = value;
                    return;
                }

                node.setAttribute(targetAttr, value);
            });
        });
    }

    /** 获取可用语言列表 */
    static getAvailableLocales(): Array<{ code: string; name: string }> {
        const localeCodes = I18N_AVAILABLE_LOCALE_CODES;
        return localeCodes.map((code) => ({
            code,
            name: this.resolveMessage(`settings.language.${code}`, this._locale)
        }));
    }

    static onChange(cb: (locale: string) => void): () => void {
        this._listeners.add(cb);
        return () => { this._listeners.delete(cb); };
    }

    /** 注册自定义语言包 */
    static registerLocale(code: string, messages: LocaleMessages): void {
        LOCALES[code] = { ...(LOCALES[code] || {}), ...messages };
        this._translationCache.clear();
    }

    /** 获取模版文件名（根据当前语言） */
    static getTemplateFilename(industry: string): string {
        const templateNames: Record<string, Record<string, string>> = {
            'mining': {
                'zh-CN': '矿业模版.geojson',
                'en-US': 'mining_template.geojson'
            },
            'geology': {
                'zh-CN': '地质模版.geojson',
                'en-US': 'geology_template.geojson'
            },
            'hydrology': {
                'zh-CN': '水文模版.geojson',
                'en-US': 'hydrology_template.geojson'
            },
            'meteorology': {
                'zh-CN': '气象模版.geojson',
                'en-US': 'meteorology_template.geojson'
            },
            'pollution': {
                'zh-CN': '污染模版.geojson',
                'en-US': 'pollution_template.geojson'
            },
            'soil': {
                'zh-CN': '土壤模版.geojson',
                'en-US': 'soil_template.geojson'
            },
            'environment': {
                'zh-CN': '环境模版.geojson',
                'en-US': 'environment_template.geojson'
            },
            'topography': {
                'zh-CN': '地形测绘模版.geojson',
                'en-US': 'topography_template.geojson'
            },
            'custom': {
                'zh-CN': '自定义模版.geojson',
                'en-US': 'custom_template.geojson'
            }
        };

        return templateNames[industry]?.[this._locale] || templateNames[industry]?.['en-US'] || `${industry}_template.geojson`;
    }

    /** 获取行业名称（根据当前语言） */
    static getIndustryName(industry: string): string {
        const industryNames: Record<string, Record<string, string>> = {
            'mining': {
                'zh-CN': '矿业',
                'en-US': 'Mining'
            },
            'geology': {
                'zh-CN': '地质',
                'en-US': 'Geology'
            },
            'hydrology': {
                'zh-CN': '水文',
                'en-US': 'Hydrology'
            },
            'meteorology': {
                'zh-CN': '气象',
                'en-US': 'Meteorology'
            },
            'pollution': {
                'zh-CN': '污染',
                'en-US': 'Pollution'
            },
            'soil': {
                'zh-CN': '土壤',
                'en-US': 'Soil'
            },
            'environment': {
                'zh-CN': '环境',
                'en-US': 'Environment'
            },
            'topography': {
                'zh-CN': '地形测绘',
                'en-US': 'Topographic Mapping'
            },
            'custom': {
                'zh-CN': '自定义',
                'en-US': 'Custom'
            }
        };

        return industryNames[industry]?.[this._locale] || industryNames[industry]?.['en-US'] || industry;
    }

    private static normalizeLocale(locale: string): string {
        const normalized = (locale || '').trim();
        if (!normalized) {
            return DEFAULT_LOCALE;
        }

        if (LOCALES[normalized] || LAZY_LOCALE_LOADERS[normalized]) {
            return normalized;
        }

        const lower = normalized.toLowerCase();
        if (lower.startsWith('zh-tw') || lower.includes('hant')) {
            return 'zh-TW';
        }
        if (lower.startsWith('zh')) {
            return 'zh-CN';
        }
        if (lower.startsWith('ja')) {
            return 'ja-JP';
        }
        if (lower.startsWith('ko')) {
            return 'ko-KR';
        }
        return FALLBACK_LOCALE;
    }

    private static async ensureLocaleLoaded(locale: string): Promise<boolean> {
        if (LOCALES[locale]) {
            return true;
        }
        const loader = LAZY_LOCALE_LOADERS[locale];
        if (!loader) {
            return false;
        }
        if (this._pendingLocaleLoads.has(locale)) {
            return this._pendingLocaleLoads.get(locale)!;
        }

        const loadPromise = loader()
            .then((messages) => {
                LOCALES[locale] = { ...(LOCALES[locale] || {}), ...messages };
                this._translationCache.clear();
                return true;
            })
            .catch((error) => {
                console.error(`[I18n] 语言包加载失败: ${locale}`, error);
                return false;
            })
            .finally(() => {
                this._pendingLocaleLoads.delete(locale);
            });
        this._pendingLocaleLoads.set(locale, loadPromise);
        return loadPromise;
    }

    private static applyLocale(locale: string): void {
        this._locale = locale;
        this._translationCache.clear();
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('udake_locale', locale);
        }
        this.applyLocaleSideEffects(locale);
        this._listeners.forEach((callback) => {
            try {
                callback(locale);
            } catch (error) {
                console.error(error);
            }
        });
    }

    private static applyLocaleSideEffects(locale: string): void {
        if (typeof document === 'undefined') {
            return;
        }
        document.documentElement.lang = locale.startsWith('zh') ? locale : locale.split('-')[0];
        document.documentElement.dir = this.getDirection(locale);
        this.applyToDOM(document);
    }

    private static resolveLocaleChain(locale: string): string[] {
        const normalized = this.normalizeLocale(locale);
        const chain = [normalized];
        if (normalized !== FALLBACK_LOCALE) {
            chain.push(FALLBACK_LOCALE);
        }
        if (normalized !== DEFAULT_LOCALE) {
            chain.push(DEFAULT_LOCALE);
        }
        return chain;
    }

    private static resolveMessage(key: string, locale: string): string {
        const chain = this.resolveLocaleChain(locale);
        for (const localeCode of chain) {
            const messages = LOCALES[localeCode];
            if (messages && Object.prototype.hasOwnProperty.call(messages, key)) {
                return messages[key];
            }
        }
        return key;
    }

    private static hasKey(key: string): boolean {
        return this.resolveLocaleChain(this._locale).some((localeCode) => {
            const messages = LOCALES[localeCode];
            return Boolean(messages && Object.prototype.hasOwnProperty.call(messages, key));
        });
    }

    private static toIntlLocale(locale: string): string {
        if (locale === 'zh-TW') {
            return 'zh-Hant-TW';
        }
        return locale;
    }

    private static getIntlFormatter<T extends IntlFormatter>(
        key: string,
        factory: () => T
    ): T {
        if (this._intlFormatterCache.has(key)) {
            return this._intlFormatterCache.get(key)! as T;
        }
        const formatter = factory();
        this._intlFormatterCache.set(key, formatter);
        return formatter;
    }
}
