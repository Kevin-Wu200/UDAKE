(function () {
  const STORAGE_KEY = "udake_locale";
  const DEFAULT_LANGUAGE = "zh-CN";
  const SUPPORTED_LANGUAGES = ["zh-CN", "en-US"];

  const translations = {
    "zh-CN": {
      title: "UDAKE - 智能不确定性驱动空间决策平台",
      brand: {
        title: "智能不确定性驱动空间决策平台",
        ariaHome: "UDAKE 首页"
      },
      language: {
        toggleAria: "切换语言"
      },
      hero: {
        kicker: "UDAKE 平台",
        title: "智能空间决策，驱动未来",
        subtitle: "专业的空间插值与不确定性分析平台",
        cta: "立即体验"
      },
      features: {
        title: "核心功能模块",
        items: {
          interpolation: {
            title: "空间插值模块",
            desc: "支持克里金、反距离加权等多种插值方法，实时预测结果可视化。"
          },
          uncertainty: {
            title: "不确定性分析模块",
            desc: "方差估计与置信区间计算，不确定性分级可视化。"
          },
          sampling: {
            title: "采样优化模块",
            desc: "自适应采样策略，高不确定性区域自动识别。"
          },
          optimization: {
            title: "多目标优化模块",
            desc: "帕累托前沿分析，多约束条件下的最优决策。"
          },
          realtime: {
            title: "实时插值模块",
            desc: "WebSocket 实时数据更新，动态采样点推荐。"
          },
          deepLearning: {
            title: "深度学习模块",
            desc: "神经网络辅助插值，GPU 加速计算。"
          },
          anomaly: {
            title: "异常检测模块",
            desc: "自动识别数据异常，智能数据清洗。"
          },
          risk: {
            title: "风险评估模块",
            desc: "多维度风险指数计算，决策阈值建议。"
          }
        }
      },
      download: {
        title: "客户端下载",
        subtitle: "从统一下载入口获取 UDAKE 最新版本。",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "立即下载 APK",
        comingSoon: "即将推出"
      },
      contact: {
        title: "联系我们",
        email: "邮箱",
        github: "GitHub"
      },
      footer: {
        copy: "© 2026 UDAKE. All rights reserved."
      },
      modal: {
        title: "提示",
        message: "该平台版本开发中，敬请期待。",
        close: "我知道了"
      }
    },
    "en-US": {
      title: "UDAKE - Intelligent Uncertainty-Driven Spatial Decision Platform",
      brand: {
        title: "Intelligent Uncertainty-Driven Spatial Decision Platform",
        ariaHome: "UDAKE Home"
      },
      language: {
        toggleAria: "Switch language"
      },
      hero: {
        kicker: "UDAKE Platform",
        title: "Intelligent Spatial Decisions for the Future",
        subtitle: "A professional platform for spatial interpolation and uncertainty analysis",
        cta: "Get Started"
      },
      features: {
        title: "Core Modules",
        items: {
          interpolation: {
            title: "Spatial Interpolation",
            desc: "Support for Kriging, IDW, and other interpolation methods with real-time visualization."
          },
          uncertainty: {
            title: "Uncertainty Analysis",
            desc: "Variance estimation, confidence interval calculation, and uncertainty-level visualization."
          },
          sampling: {
            title: "Sampling Optimization",
            desc: "Adaptive sampling strategies and automatic high-uncertainty region detection."
          },
          optimization: {
            title: "Multi-Objective Optimization",
            desc: "Pareto-front analysis and optimal decisions under multiple constraints."
          },
          realtime: {
            title: "Real-Time Interpolation",
            desc: "WebSocket-driven real-time updates and dynamic sampling-point recommendation."
          },
          deepLearning: {
            title: "Deep Learning",
            desc: "Neural-network-assisted interpolation with GPU acceleration."
          },
          anomaly: {
            title: "Anomaly Detection",
            desc: "Automatic anomaly identification and intelligent data cleaning."
          },
          risk: {
            title: "Risk Assessment",
            desc: "Multi-dimensional risk index calculation and decision-threshold suggestions."
          }
        }
      },
      download: {
        title: "Downloads",
        subtitle: "Get the latest UDAKE release from one unified entry point.",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "Download APK Now",
        comingSoon: "Coming Soon"
      },
      contact: {
        title: "Contact",
        email: "Email",
        github: "GitHub"
      },
      footer: {
        copy: "© 2026 UDAKE. All rights reserved."
      },
      modal: {
        title: "Notice",
        message: "This platform version is under development. Stay tuned.",
        close: "OK"
      }
    }
  };

  function getByPath(source, path) {
    return path.split(".").reduce(function (value, key) {
      return value && value[key] !== undefined ? value[key] : null;
    }, source);
  }

  function normalizeLanguage(input) {
    if (SUPPORTED_LANGUAGES.indexOf(input) !== -1) {
      return input;
    }
    return DEFAULT_LANGUAGE;
  }

  function getStoredLanguage() {
    try {
      return normalizeLanguage(localStorage.getItem(STORAGE_KEY));
    } catch (error) {
      return DEFAULT_LANGUAGE;
    }
  }

  function setStoredLanguage(language) {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch (error) {
      return;
    }
  }

  function applyLanguage(language) {
    const normalized = normalizeLanguage(language);
    const dictionary = translations[normalized];

    document.documentElement.lang = normalized;
    document.title = dictionary.title;

    document.querySelectorAll("[data-i18n]").forEach(function (element) {
      const key = element.getAttribute("data-i18n");
      const text = getByPath(dictionary, key);
      if (typeof text === "string") {
        element.textContent = text;
      }
    });

    document.querySelectorAll("[data-i18n-aria-label]").forEach(function (element) {
      const key = element.getAttribute("data-i18n-aria-label");
      const text = getByPath(dictionary, key);
      if (typeof text === "string") {
        element.setAttribute("aria-label", text);
      }
    });

    const toggleButton = document.getElementById("languageToggle");
    if (toggleButton) {
      toggleButton.textContent = normalized === "zh-CN" ? "English" : "中文";
    }

    setStoredLanguage(normalized);
    window.dispatchEvent(new CustomEvent("udake-language-change", { detail: { language: normalized } }));
    return normalized;
  }

  function toggleLanguage() {
    const current = getCurrentLanguage();
    const next = current === "zh-CN" ? "en-US" : "zh-CN";
    return applyLanguage(next);
  }

  function getCurrentLanguage() {
    const lang = document.documentElement.lang || getStoredLanguage();
    return normalizeLanguage(lang);
  }

  function init() {
    applyLanguage(getStoredLanguage());
  }

  window.UDAKEI18N = {
    applyLanguage: applyLanguage,
    toggleLanguage: toggleLanguage,
    getCurrentLanguage: getCurrentLanguage,
    init: init
  };
})();
