(function () {
  const STORAGE_KEY = 'udake_locale';
  const DEFAULT_LOCALE = 'zh-CN';
  const SUPPORTED_LOCALES = ['zh-CN', 'en-US'];

  const dictionaries = {
    'zh-CN': {
      'test.switch': 'English',
      'test.coordinateParser.title': '坐标解析器测试',
      'test.coordinateParser.heading': '坐标解析器测试',
      'test.coordinateParser.autoCases': '自动化测试用例',
      'test.coordinateParser.interactive': '交互式测试',
      'test.coordinateParser.longitudeLabel': '经度测试：',
      'test.coordinateParser.longitudePlaceholder': '输入经度',
      'test.coordinateParser.latitudeLabel': '纬度测试：',
      'test.coordinateParser.latitudePlaceholder': '输入纬度',
      'test.coordinateParser.sampleValueLabel': '采样值测试：',
      'test.coordinateParser.sampleValuePlaceholder': '输入采样值',
      'test.mapEngine.title': '地图引擎测试工具 - UDAKE',
      'test.mapEngine.heading': '🧪 地图引擎测试工具',
      'test.mapEngine.subtitle': 'UDAKE 地图引擎切换功能测试套件',
      'test.mapEngine.systemInfo': '系统信息',
      'test.mapEngine.currentEngine': '当前地图引擎',
      'test.mapEngine.loading': '加载中...',
      'test.mapEngine.browser': '浏览器',
      'test.mapEngine.testStatus': '测试状态',
      'test.mapEngine.notStarted': '未开始',
      'test.mapEngine.control': '测试控制',
      'test.mapEngine.runAllTests': '运行所有测试',
      'test.mapEngine.clearConsole': '清空控制台',
      'test.mapEngine.exportReport': '导出报告',
      'test.mapEngine.mapPreview': '地图预览',
      'test.mapEngine.results': '测试结果',
      'test.mapEngine.consoleOutput': '控制台输出',
      'test.modal.title': '弹窗测试',
      'test.modal.heading': '弹窗功能测试',
      'test.modal.testButton': '测试弹窗',
      'test.modelFusion.title': '模型融合系统测试',
      'test.modelFusion.heading': '🔮 模型融合系统',
      'test.modelFusion.subtitle': '集成多个克里金模型的预测结果，通过加权平均、堆叠等方法提高预测稳定性和准确性',
      'test.modelFusion.tab.simple': '简单融合',
      'test.modelFusion.tab.compare': '策略对比',
      'test.modelFusion.tab.optimize': '权重优化',
      'test.modelFusion.modelInput': '模型输入',
      'test.modelFusion.config': '融合配置',
      'test.modelFusion.createTask': '创建融合任务',
      'test.modelFusion.checkStatus': '检查状态',
      'test.modelFusion.taskResult': '任务结果',
      'test.modelFusion.compareTitle': '策略对比',
      'test.modelFusion.compareDesc': '对比不同融合策略的性能',
      'test.modelFusion.compareAction': '执行策略对比',
      'test.modelFusion.compareResult': '对比结果',
      'test.modelFusion.optimizeTitle': '权重优化',
      'test.modelFusion.optimizeDesc': '自动选择最佳权重计算方法',
      'test.modelFusion.optimizeAction': '执行权重优化',
      'test.modelFusion.optimizeResult': '优化结果',
      'test.multiObjective.title': '多目标优化采样系统',
      'test.multiObjective.heading': '🎯 多目标优化采样系统',
      'test.multiObjective.subtitle': '综合考虑方差、成本、可达性等多个目标，智能推荐最优采样点组合',
      'test.multiObjective.configTitle': '⚙️ 参数配置',
      'test.multiObjective.varianceWeight': '📊 方差权重',
      'test.multiObjective.varianceHint': '最小化插值预测方差',
      'test.multiObjective.costWeight': '💰 成本权重',
      'test.multiObjective.costHint': '最小化采样总成本',
      'test.multiObjective.accessibilityWeight': '🚀 可达性权重',
      'test.multiObjective.accessibilityHint': '最大化采样点可达性',
      'test.multiObjective.samplingParams': '🎯 采样参数',
      'test.multiObjective.sampleCount': '采样点数量',
      'test.multiObjective.generations': '进化代数',
      'test.multiObjective.constraints': '🔒 约束条件',
      'test.multiObjective.minDistance': '最小间距（米）',
      'test.multiObjective.budget': '预算限制（元）',
      'test.multiObjective.start': '🚀 开始优化',
      'test.multiObjective.reset': '🔄 重置参数',
      'test.multiObjective.progress': '📈 优化进度',
      'test.multiObjective.running': '运行中',
      'test.multiObjective.elapsed': '已耗时: 0s',
      'test.multiObjective.results': '✅ 优化结果',
      'test.multiObjective.tab.pareto': '帕累托前沿',
      'test.multiObjective.tab.recommended': '推荐方案',
      'test.multiObjective.tab.metrics': '性能指标',
      'test.multiObjective.paretoChart': '📊 帕累托前沿可视化',
      'test.multiObjective.recommendedDetail': '🌟 推荐方案详情',
      'test.multiObjective.loading': '正在优化中，请稍候...',
      'test.newProject.title': '新建项目功能测试',
      'test.newProject.heading': '新建项目功能测试',
      'test.newProject.scenarios': '测试场景',
      'test.newProject.openModal': '测试新建项目弹窗',
      'test.newProject.freeManual': '自由采样 + 手动输入',
      'test.newProject.freeDevice': '自由采样 + 自动定位',
      'test.newProject.regionManual': '区域采样 + 手动输入',
      'test.newProject.regionDevice': '区域采样 + 自动定位',
      'test.newProject.errorHandler': '测试错误处理',
      'test.newProject.clearResult': '清空结果',
      'test.newProject.mapView': '地图视图',
      'test.newProject.currentProjectInfo': '当前项目信息',
      'test.routePlanning.title': '路径规划测试',
      'test.routePlanning.heading': '路径规划系统',
      'test.routePlanning.subtitle': '智能采样路径规划，提高野外采样效率',
      'test.taskManager.title': '任务管理器测试',
      'test.taskManager.heading': '任务管理器测试',
      'test.taskManager.subtitle': '测试后台任务管理、通知功能和任务持久化',
      'test.taskManager.createTask': '创建测试任务',
      'test.taskManager.createBatchTasks': '创建批量任务',
      'test.taskManager.viewStats': '查看统计',
      'test.taskManager.clearHistory': '清空历史',
      'test.taskManager.testNotification': '测试通知',
      'test.taskManager.totalTasks': '总任务数',
      'test.taskManager.pending': '待处理',
      'test.taskManager.running': '运行中',
      'test.taskManager.completed': '已完成',
      'test.taskManager.failed': '失败',
      'test.taskManager.panelTitle': '任务管理面板',
      'test.taskManager.logTitle': '测试日志'
    },
    'en-US': {
      'test.switch': '中文',
      'test.coordinateParser.title': 'Coordinate Parser Test',
      'test.coordinateParser.heading': 'Coordinate Parser Test',
      'test.coordinateParser.autoCases': 'Automated Test Cases',
      'test.coordinateParser.interactive': 'Interactive Tests',
      'test.coordinateParser.longitudeLabel': 'Longitude:',
      'test.coordinateParser.longitudePlaceholder': 'Enter longitude',
      'test.coordinateParser.latitudeLabel': 'Latitude:',
      'test.coordinateParser.latitudePlaceholder': 'Enter latitude',
      'test.coordinateParser.sampleValueLabel': 'Sample value:',
      'test.coordinateParser.sampleValuePlaceholder': 'Enter sample value',
      'test.mapEngine.title': 'Map Engine Test Tool - UDAKE',
      'test.mapEngine.heading': '🧪 Map Engine Test Tool',
      'test.mapEngine.subtitle': 'UDAKE map engine switching test suite',
      'test.mapEngine.systemInfo': 'System Information',
      'test.mapEngine.currentEngine': 'Current Map Engine',
      'test.mapEngine.loading': 'Loading...',
      'test.mapEngine.browser': 'Browser',
      'test.mapEngine.testStatus': 'Test Status',
      'test.mapEngine.notStarted': 'Not started',
      'test.mapEngine.control': 'Test Control',
      'test.mapEngine.runAllTests': 'Run All Tests',
      'test.mapEngine.clearConsole': 'Clear Console',
      'test.mapEngine.exportReport': 'Export Report',
      'test.mapEngine.mapPreview': 'Map Preview',
      'test.mapEngine.results': 'Test Results',
      'test.mapEngine.consoleOutput': 'Console Output',
      'test.modal.title': 'Modal Test',
      'test.modal.heading': 'Modal Feature Test',
      'test.modal.testButton': 'Test Modal',
      'test.modelFusion.title': 'Model Fusion System Test',
      'test.modelFusion.heading': '🔮 Model Fusion System',
      'test.modelFusion.subtitle': 'Integrate predictions from multiple kriging models to improve stability and accuracy via weighted average or stacking.',
      'test.modelFusion.tab.simple': 'Simple Fusion',
      'test.modelFusion.tab.compare': 'Strategy Comparison',
      'test.modelFusion.tab.optimize': 'Weight Optimization',
      'test.modelFusion.modelInput': 'Model Inputs',
      'test.modelFusion.config': 'Fusion Configuration',
      'test.modelFusion.createTask': 'Create Fusion Task',
      'test.modelFusion.checkStatus': 'Check Status',
      'test.modelFusion.taskResult': 'Task Result',
      'test.modelFusion.compareTitle': 'Strategy Comparison',
      'test.modelFusion.compareDesc': 'Compare performance of different fusion strategies',
      'test.modelFusion.compareAction': 'Run Strategy Comparison',
      'test.modelFusion.compareResult': 'Comparison Result',
      'test.modelFusion.optimizeTitle': 'Weight Optimization',
      'test.modelFusion.optimizeDesc': 'Automatically choose the best weighting method',
      'test.modelFusion.optimizeAction': 'Run Weight Optimization',
      'test.modelFusion.optimizeResult': 'Optimization Result',
      'test.multiObjective.title': 'Multi-objective Optimization Sampling System',
      'test.multiObjective.heading': '🎯 Multi-objective Optimization Sampling System',
      'test.multiObjective.subtitle': 'Optimize sampling combinations by considering variance, cost and accessibility together.',
      'test.multiObjective.configTitle': '⚙️ Parameter Configuration',
      'test.multiObjective.varianceWeight': '📊 Variance Weight',
      'test.multiObjective.varianceHint': 'Minimize interpolation prediction variance',
      'test.multiObjective.costWeight': '💰 Cost Weight',
      'test.multiObjective.costHint': 'Minimize total sampling cost',
      'test.multiObjective.accessibilityWeight': '🚀 Accessibility Weight',
      'test.multiObjective.accessibilityHint': 'Maximize accessibility of sampling points',
      'test.multiObjective.samplingParams': '🎯 Sampling Parameters',
      'test.multiObjective.sampleCount': 'Number of samples',
      'test.multiObjective.generations': 'Evolution generations',
      'test.multiObjective.constraints': '🔒 Constraints',
      'test.multiObjective.minDistance': 'Minimum spacing (m)',
      'test.multiObjective.budget': 'Budget limit',
      'test.multiObjective.start': '🚀 Start Optimization',
      'test.multiObjective.reset': '🔄 Reset Parameters',
      'test.multiObjective.progress': '📈 Optimization Progress',
      'test.multiObjective.running': 'Running',
      'test.multiObjective.elapsed': 'Elapsed: 0s',
      'test.multiObjective.results': '✅ Optimization Results',
      'test.multiObjective.tab.pareto': 'Pareto Front',
      'test.multiObjective.tab.recommended': 'Recommended Plan',
      'test.multiObjective.tab.metrics': 'Performance Metrics',
      'test.multiObjective.paretoChart': '📊 Pareto Front Visualization',
      'test.multiObjective.recommendedDetail': '🌟 Recommended Plan Details',
      'test.multiObjective.loading': 'Optimizing, please wait...',
      'test.newProject.title': 'New Project Feature Test',
      'test.newProject.heading': 'New Project Feature Test',
      'test.newProject.scenarios': 'Test Scenarios',
      'test.newProject.openModal': 'Test New Project Modal',
      'test.newProject.freeManual': 'Free Sampling + Manual Input',
      'test.newProject.freeDevice': 'Free Sampling + Auto Location',
      'test.newProject.regionManual': 'Region Sampling + Manual Input',
      'test.newProject.regionDevice': 'Region Sampling + Auto Location',
      'test.newProject.errorHandler': 'Test Error Handler',
      'test.newProject.clearResult': 'Clear Result',
      'test.newProject.mapView': 'Map View',
      'test.newProject.currentProjectInfo': 'Current Project Info',
      'test.routePlanning.title': 'Route Planning Test',
      'test.routePlanning.heading': 'Route Planning System',
      'test.routePlanning.subtitle': 'Intelligent sampling route planning to improve field efficiency',
      'test.taskManager.title': 'Task Manager Test',
      'test.taskManager.heading': 'Task Manager Test',
      'test.taskManager.subtitle': 'Test background task management, notifications, and task persistence',
      'test.taskManager.createTask': 'Create Test Task',
      'test.taskManager.createBatchTasks': 'Create Batch Tasks',
      'test.taskManager.viewStats': 'View Stats',
      'test.taskManager.clearHistory': 'Clear History',
      'test.taskManager.testNotification': 'Test Notification',
      'test.taskManager.totalTasks': 'Total Tasks',
      'test.taskManager.pending': 'Pending',
      'test.taskManager.running': 'Running',
      'test.taskManager.completed': 'Completed',
      'test.taskManager.failed': 'Failed',
      'test.taskManager.panelTitle': 'Task Manager Panel',
      'test.taskManager.logTitle': 'Test Logs'
    }
  };

  const literalMap = {
    '没有可导出的测试报告': {
      'zh-CN': '没有可导出的测试报告',
      'en-US': 'No test report available for export'
    },
    '这是一个路径规划测试页面。在实际应用中，需要：\n1. 集成地图引擎（如高德、百度地图）\n2. 加载路径规划面板组件\n3. 连接后端API服务': {
      'zh-CN': '这是一个路径规划测试页面。在实际应用中，需要：\n1. 集成地图引擎（如高德、百度地图）\n2. 加载路径规划面板组件\n3. 连接后端API服务',
      'en-US': 'This is a route planning test page. In production, you need:\n1. Integrate a map engine (Amap/Baidu, etc.)\n2. Load the route planning panel component\n3. Connect backend API services'
    }
  };

  function normalizeLocale(locale) {
    if (locale === 'en') {
      return 'en-US';
    }

    if (!locale) {
      return DEFAULT_LOCALE;
    }

    if (SUPPORTED_LOCALES.includes(locale)) {
      return locale;
    }

    return locale.startsWith('zh') ? 'zh-CN' : 'en-US';
  }

  function getLocale() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return normalizeLocale(stored || document.documentElement.lang || navigator.language);
    } catch (error) {
      return DEFAULT_LOCALE;
    }
  }

  function setLocale(locale) {
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch (error) {
      // ignore storage errors
    }
  }

  function t(key, locale) {
    const dictionary = dictionaries[locale] || dictionaries[DEFAULT_LOCALE];
    const defaultDictionary = dictionaries[DEFAULT_LOCALE];
    return dictionary[key] || defaultDictionary[key] || key;
  }

  function translateLiteral(message, locale) {
    const entry = literalMap[message];
    if (!entry) {
      return message;
    }
    return entry[locale] || entry[DEFAULT_LOCALE] || message;
  }

  function applyLocale(locale) {
    const normalized = normalizeLocale(locale);
    document.documentElement.lang = normalized;

    document.querySelectorAll('[data-i18n]').forEach(function (element) {
      const key = element.getAttribute('data-i18n');
      if (!key) {
        return;
      }
      element.textContent = t(key, normalized);
    });

    document.querySelectorAll('[data-i18n-title]').forEach(function (element) {
      const key = element.getAttribute('data-i18n-title');
      if (!key) {
        return;
      }
      element.setAttribute('title', t(key, normalized));
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (element) {
      const key = element.getAttribute('data-i18n-placeholder');
      if (!key) {
        return;
      }
      element.setAttribute('placeholder', t(key, normalized));
    });

    const switcher = document.getElementById('test-i18n-switcher');
    if (switcher) {
      switcher.textContent = t('test.switch', normalized);
    }

    const titleNode = document.querySelector('title[data-i18n]');
    if (titleNode) {
      const key = titleNode.getAttribute('data-i18n');
      if (key) {
        document.title = t(key, normalized);
      }
    }

    setLocale(normalized);
  }

  function toggleLocale() {
    const current = getLocale();
    const next = current === 'zh-CN' ? 'en-US' : 'zh-CN';
    applyLocale(next);
  }

  function ensureToggleButton() {
    if (document.getElementById('test-i18n-switcher')) {
      return;
    }

    const button = document.createElement('button');
    button.id = 'test-i18n-switcher';
    button.type = 'button';
    button.style.position = 'fixed';
    button.style.top = '12px';
    button.style.right = '12px';
    button.style.zIndex = '99999';
    button.style.padding = '6px 10px';
    button.style.border = '1px solid #ccc';
    button.style.borderRadius = '6px';
    button.style.background = '#fff';
    button.style.cursor = 'pointer';
    button.style.fontSize = '12px';
    button.addEventListener('click', toggleLocale);
    document.body.appendChild(button);
  }

  function patchDialogMethods() {
    if (window.__TEST_I18N_DIALOG_PATCHED__) {
      return;
    }

    window.__TEST_I18N_DIALOG_PATCHED__ = true;

    const originalAlert = window.alert.bind(window);
    const originalConfirm = window.confirm.bind(window);
    const originalPrompt = window.prompt.bind(window);

    window.alert = function (message) {
      originalAlert(translateLiteral(String(message), getLocale()));
    };

    window.confirm = function (message) {
      return originalConfirm(translateLiteral(String(message), getLocale()));
    };

    window.prompt = function (message, defaultValue) {
      return originalPrompt(translateLiteral(String(message), getLocale()), defaultValue);
    };
  }

  function bootstrap() {
    ensureToggleButton();
    patchDialogMethods();
    applyLocale(getLocale());
  }

  window.TestPageI18n = {
    applyLocale: applyLocale,
    toggleLocale: toggleLocale,
    getLocale: getLocale,
    t: t
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
})();
