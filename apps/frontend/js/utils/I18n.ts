/**
 * 国际化 (i18n) 管理器
 * 支持中文、英文语言切换
 */

type LocaleKey = string;
type LocaleMessages = Record<LocaleKey, string>;

interface I18nConfig {
    defaultLocale: string;
    fallbackLocale: string;
}

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

    // 通用
    'common.confirm': '确认',
    'common.cancel': '取消',
    'common.close': '关闭',
    'common.loading': '加载中...',
    'common.error': '错误',
    'common.success': '成功',

    // 设置
    'settings.title': '设置',
    'settings.button': '设置',
    'settings.language': '语言',
    'settings.language.zh-CN': '简体中文',
    'settings.language.en-US': 'English',
    'settings.save': '保存',
    'settings.reset': '重置',

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

    // Errors (i18n)
    'error.common.unknown': 'Unknown error',
    'error.common.retryButton': 'Retry',
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

    // 通用
    'common.confirm': 'Confirm',
    'common.cancel': 'Cancel',
    'common.close': 'Close',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    'common.success': 'Success',

    // 设置
    'settings.title': 'Settings',
    'settings.button': 'Settings',
    'settings.language': 'Language',
    'settings.language.zh-CN': '简体中文',
    'settings.language.en-US': 'English',
    'settings.save': 'Save',
    'settings.reset': 'Reset',

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

// ========== I18n 管理器 ==========

export class I18n {
    private static _locale: string = 'zh-CN';
    private static _listeners: Set<(locale: string) => void> = new Set();
    private static _missingKeyUsage: Map<string, number> = new Map();

    static init(locale?: string): void {
        const saved = localStorage.getItem('udake_locale');
        this._locale = locale || saved || navigator.language || 'zh-CN';
        // 规范化
        if (!LOCALES[this._locale]) {
            this._locale = this._locale.startsWith('zh') ? 'zh-CN' : 'en-US';
        }
        if (typeof document !== 'undefined') {
            document.documentElement.lang = this._locale.startsWith('zh') ? 'zh-CN' : 'en';
            this.applyToDOM(document);
        }
    }

    static get locale(): string { return this._locale; }

    static setLocale(locale: string): void {
        if (!LOCALES[locale]) return;
        this._locale = locale;
        localStorage.setItem('udake_locale', locale);
        if (typeof document !== 'undefined') {
            document.documentElement.lang = locale.startsWith('zh') ? 'zh-CN' : 'en';
            this.applyToDOM(document);
        }
        this._listeners.forEach(cb => { try { cb(locale); } catch (e) { console.error(e); } });
    }

    /** 获取翻译文本，支持 {key} 插值 */
    static t(key: string, params?: Record<string, string | number>): string {
        const messages = LOCALES[this._locale] || LOCALES['zh-CN'];
        let text = messages[key] || LOCALES['zh-CN'][key] || key;
        if (text === key) {
            const count = this._missingKeyUsage.get(key) || 0;
            this._missingKeyUsage.set(key, count + 1);
        }
        if (params) {
            Object.entries(params).forEach(([k, v]) => {
                text = text.replace(`{${k}}`, String(v));
            });
        }
        return text;
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
        return [
            { code: 'zh-CN', name: '简体中文' },
            { code: 'en-US', name: 'English' },
        ];
    }

    static onChange(cb: (locale: string) => void): () => void {
        this._listeners.add(cb);
        return () => { this._listeners.delete(cb); };
    }

    /** 注册自定义语言包 */
    static registerLocale(code: string, messages: LocaleMessages): void {
        LOCALES[code] = { ...(LOCALES[code] || {}), ...messages };
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
}
