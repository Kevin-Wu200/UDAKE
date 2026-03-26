(function () {
  const STORAGE_KEY = 'udake_locale';
  const DEFAULT_LOCALE = 'zh-CN';
  const SUPPORTED_LOCALES = ['zh-CN', 'en-US'];

  const dictionaries = {
    'zh-CN': {
      'test.switch': 'English',
      'test.coordinateParser.title': '坐标解析器测试',
      'test.mapEngine.title': '地图引擎测试工具 - UDAKE',
      'test.modal.title': '弹窗测试',
      'test.modelFusion.title': '模型融合系统测试',
      'test.multiObjective.title': '多目标优化采样系统',
      'test.newProject.title': '新建项目功能测试',
      'test.routePlanning.title': '路径规划测试',
      'test.taskManager.title': '任务管理器测试'
    },
    'en-US': {
      'test.switch': '中文',
      'test.coordinateParser.title': 'Coordinate Parser Test',
      'test.mapEngine.title': 'Map Engine Test Tool - UDAKE',
      'test.modal.title': 'Modal Test',
      'test.modelFusion.title': 'Model Fusion System Test',
      'test.multiObjective.title': 'Multi-objective Optimization Sampling System',
      'test.newProject.title': 'New Project Feature Test',
      'test.routePlanning.title': 'Route Planning Test',
      'test.taskManager.title': 'Task Manager Test'
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
