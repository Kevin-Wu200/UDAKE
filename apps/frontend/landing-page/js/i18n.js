(function () {
  const STORAGE_KEY = "udake_locale";
  const DEFAULT_LANGUAGE = "zh-CN";
  const SUPPORTED_LANGUAGES = ["zh-CN", "en-US"];

  const translations = {
    "zh-CN": {
      title: "UDAKE - 智能不确定性驱动空间决策平台",
      brand: {
        title: "智能不确定性驱动空间决策平台",
        ariaHome: "UDAKE 首页",
      },
      language: {
        toggleAria: "切换语言",
      },
      hero: {
        kicker: "UDAKE 平台",
        title: "智能空间决策，驱动未来",
        subtitle: "专业的空间插值与不确定性分析平台",
        cta: "立即体验",
      },
      features: {
        title: "核心功能模块",
        items: {
          interpolation: {
            title: "空间插值模块",
            desc: "支持克里金、反距离加权等多种插值方法，实时预测结果可视化。",
          },
          uncertainty: {
            title: "不确定性分析模块",
            desc: "方差估计与置信区间计算，不确定性分级可视化。",
          },
          sampling: {
            title: "采样优化模块",
            desc: "自适应采样策略，高不确定性区域自动识别。",
          },
          optimization: {
            title: "多目标优化模块",
            desc: "帕累托前沿分析，多约束条件下的最优决策。",
          },
          realtime: {
            title: "实时插值模块",
            desc: "WebSocket 实时数据更新，动态采样点推荐。",
          },
          deepLearning: {
            title: "深度学习模块",
            desc: "神经网络辅助插值，GPU 加速计算。",
          },
          anomaly: {
            title: "异常检测模块",
            desc: "自动识别数据异常，智能数据清洗。",
          },
          risk: {
            title: "风险评估模块",
            desc: "多维度风险指数计算，决策阈值建议。",
          },
        },
      },
      pages: {
        common: {
          introTitle: "功能介绍",
          techTitle: "技术特点",
          valueTitle: "业务价值",
          backHome: "返回首页",
        },
        interpolation: {
          metaTitle: "UDAKE - 空间插值模块",
          heroTitle: "空间插值模块",
          heroSubtitle:
            "融合地统计学与机器学习算法，实现高精度空间预测与结果可视化。",
          intro:
            "空间插值模块面向稀疏采样场景，支持快速构建连续空间分布，适用于环境监测、资源评估与城市治理。",
          tech: [
            "支持克里金、IDW 与样条等算法灵活切换",
            "支持栅格化输出与等值面可视化",
            "与实时数据流联动，动态更新预测结果",
          ],
          value: [
            "减少高成本外业采样工作量",
            "提升空间决策结果的可解释性",
            "为后续风险评估提供连续输入数据",
          ],
        },
        uncertainty: {
          metaTitle: "UDAKE - 不确定性分析模块",
          heroTitle: "不确定性分析模块",
          heroSubtitle:
            "对预测结果进行置信度量化，帮助团队明确高风险区域与决策边界。",
          intro:
            "不确定性分析模块可对模型结果进行方差、置信区间与分级评估，降低“只看均值”导致的判断偏差。",
          tech: [
            "提供方差场与置信区间联合展示",
            "支持不确定性分级地图输出",
            "支持模型对比下的不确定性敏感度分析",
          ],
          value: [
            "提升方案评估的稳健性",
            "提前识别高风险决策区域",
            "为采样优化与风险评估提供依据",
          ],
        },
        sampling: {
          metaTitle: "UDAKE - 采样优化模块",
          heroTitle: "采样优化模块",
          heroSubtitle:
            "基于不确定性热点自动推荐采样点位，持续优化数据采集策略。",
          intro:
            "采样优化模块结合当前数据分布与模型不确定性，输出最具信息增益的新采样建议。",
          tech: [
            "支持自适应采样与批量点位推荐",
            "内置覆盖度与信息增益联合指标",
            "支持约束条件下的可执行采样路径规划",
          ],
          value: [
            "在有限预算下提升采样效率",
            "缩短模型收敛周期",
            "形成可迭代的闭环采样机制",
          ],
        },
        optimization: {
          metaTitle: "UDAKE - 多目标优化模块",
          heroTitle: "多目标优化模块",
          heroSubtitle:
            "在成本、时效、风险等多目标之间寻找平衡解，支撑复杂场景决策。",
          intro:
            "多目标优化模块通过帕累托前沿分析，帮助团队在冲突目标之间快速筛选可行方案。",
          tech: [
            "支持多目标函数与多约束条件配置",
            "提供帕累托解集可视化分析",
            "支持方案敏感性与鲁棒性评估",
          ],
          value: [
            "降低拍脑袋决策带来的风险",
            "提升资源分配与调度效率",
            "为管理层提供可量化决策依据",
          ],
        },
        realtime: {
          metaTitle: "UDAKE - 实时插值模块",
          heroTitle: "实时插值模块",
          heroSubtitle:
            "通过实时数据流驱动动态插值，快速响应现场变化并持续更新空间结果。",
          intro:
            "实时插值模块适用于在线监测场景，可在数据到达后秒级刷新预测与预警结果。",
          tech: [
            "支持 WebSocket 数据流接入",
            "支持增量更新与局部重计算机制",
            "支持在线告警阈值与动态热区识别",
          ],
          value: [
            "提升异常事件响应速度",
            "降低数据延迟带来的决策偏差",
            "让业务监控从静态报表走向实时态势",
          ],
        },
        deepLearning: {
          metaTitle: "UDAKE - 深度学习模块",
          heroTitle: "深度学习模块",
          heroSubtitle:
            "利用神经网络学习复杂空间模式，提升非线性场景下的预测性能。",
          intro:
            "深度学习模块支持多种神经网络模型与训练策略，适用于高维特征、多源异构数据场景。",
          tech: [
            "支持 CNN、RNN 与图网络等模型扩展",
            "支持 GPU 加速训练与推理",
            "支持模型版本管理与效果对比",
          ],
          value: [
            "提升复杂场景预测精度",
            "增强模型泛化能力",
            "缩短从实验到部署的交付周期",
          ],
        },
        anomaly: {
          metaTitle: "UDAKE - 异常检测模块",
          heroTitle: "异常检测模块",
          heroSubtitle:
            "自动识别异常点与异常模式，提升数据质量并降低误判风险。",
          intro:
            "异常检测模块可在数据入库和分析阶段及时发现离群值、突变点和可疑模式。",
          tech: [
            "支持统计规则与机器学习联合检测",
            "支持时空异常联动识别",
            "支持异常标签回写与人工复核闭环",
          ],
          value: [
            "减少脏数据对模型的干扰",
            "提高业务告警的准确率",
            "支撑高质量数据治理体系",
          ],
        },
        risk: {
          metaTitle: "UDAKE - 风险评估模块",
          heroTitle: "风险评估模块",
          heroSubtitle:
            "构建多维风险指数与预警机制，帮助团队提前制定应对策略。",
          intro:
            "风险评估模块将预测结果、不确定性与业务阈值融合，输出可执行的风险分级建议。",
          tech: [
            "支持多维指标归一化与综合评分",
            "支持风险阈值与场景模板配置",
            "支持时序风险趋势分析与预警通知",
          ],
          value: [
            "提升风险识别的前瞻性",
            "推动应急资源精准投放",
            "将复杂分析结果转化为可执行策略",
          ],
        },
      },
      download: {
        title: "客户端下载",
        subtitle: "从统一下载入口获取 UDAKE 最新版本。",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "立即下载 APK",
        comingSoon: "即将推出",
      },
      contact: {
        title: "联系我们",
        email: "邮箱",
        github: "GitHub",
      },
      footer: {
        copy: "© 2026 UDAKE. All rights reserved.",
      },
      modal: {
        title: "提示",
        message: "该平台版本开发中，敬请期待。",
        close: "我知道了",
      },
    },
    "en-US": {
      title: "UDAKE - Intelligent Uncertainty-Driven Spatial Decision Platform",
      brand: {
        title: "Intelligent Uncertainty-Driven Spatial Decision Platform",
        ariaHome: "UDAKE Home",
      },
      language: {
        toggleAria: "Switch language",
      },
      hero: {
        kicker: "UDAKE Platform",
        title: "Intelligent Spatial Decisions for the Future",
        subtitle:
          "A professional platform for spatial interpolation and uncertainty analysis",
        cta: "Get Started",
      },
      features: {
        title: "Core Modules",
        items: {
          interpolation: {
            title: "Spatial Interpolation",
            desc: "Support for Kriging, IDW, and other interpolation methods with real-time visualization.",
          },
          uncertainty: {
            title: "Uncertainty Analysis",
            desc: "Variance estimation, confidence interval calculation, and uncertainty-level visualization.",
          },
          sampling: {
            title: "Sampling Optimization",
            desc: "Adaptive sampling strategies and automatic high-uncertainty region detection.",
          },
          optimization: {
            title: "Multi-Objective Optimization",
            desc: "Pareto-front analysis and optimal decisions under multiple constraints.",
          },
          realtime: {
            title: "Real-Time Interpolation",
            desc: "WebSocket-driven real-time updates and dynamic sampling-point recommendation.",
          },
          deepLearning: {
            title: "Deep Learning",
            desc: "Neural-network-assisted interpolation with GPU acceleration.",
          },
          anomaly: {
            title: "Anomaly Detection",
            desc: "Automatic anomaly identification and intelligent data cleaning.",
          },
          risk: {
            title: "Risk Assessment",
            desc: "Multi-dimensional risk index calculation and decision-threshold suggestions.",
          },
        },
      },
      pages: {
        common: {
          introTitle: "Overview",
          techTitle: "Technical Highlights",
          valueTitle: "Business Value",
          backHome: "Back to Home",
        },
        interpolation: {
          metaTitle: "UDAKE - Spatial Interpolation",
          heroTitle: "Spatial Interpolation Module",
          heroSubtitle:
            "Combine geostatistics and ML to deliver high-accuracy spatial prediction and visualization.",
          intro:
            "The spatial interpolation module is designed for sparse sampling scenarios, enabling continuous surface estimation for environmental monitoring and planning.",
          tech: [
            "Switch between Kriging, IDW, and spline methods",
            "Generate raster outputs and contour visualizations",
            "Update interpolation results with streaming inputs",
          ],
          value: [
            "Reduce expensive field sampling efforts",
            "Improve interpretability of spatial decisions",
            "Provide continuous inputs for risk modeling",
          ],
        },
        uncertainty: {
          metaTitle: "UDAKE - Uncertainty Analysis",
          heroTitle: "Uncertainty Analysis Module",
          heroSubtitle:
            "Quantify confidence and identify high-risk decision areas with transparent uncertainty metrics.",
          intro:
            "This module evaluates variance, confidence intervals, and uncertainty grading to avoid decision bias from mean-only outputs.",
          tech: [
            "Joint display of variance maps and confidence intervals",
            "Export uncertainty-level zoning maps",
            "Sensitivity comparison across model candidates",
          ],
          value: [
            "Strengthen decision robustness",
            "Identify high-risk regions early",
            "Support sampling and risk strategies",
          ],
        },
        sampling: {
          metaTitle: "UDAKE - Sampling Optimization",
          heroTitle: "Sampling Optimization Module",
          heroSubtitle:
            "Recommend next sampling points from uncertainty hotspots to improve data acquisition efficiency.",
          intro:
            "The module combines current data distribution and model uncertainty to suggest new points with the highest information gain.",
          tech: [
            "Adaptive sampling and batch recommendation",
            "Coverage and information-gain co-optimization",
            "Constraint-aware executable route planning",
          ],
          value: [
            "Increase sampling efficiency under budget limits",
            "Shorten model convergence cycles",
            "Enable closed-loop iterative sampling",
          ],
        },
        optimization: {
          metaTitle: "UDAKE - Multi-Objective Optimization",
          heroTitle: "Multi-Objective Optimization Module",
          heroSubtitle:
            "Balance cost, timeliness, and risk across competing objectives for complex decision scenarios.",
          intro:
            "Using Pareto frontier analysis, this module helps teams select feasible plans quickly under conflicting objectives.",
          tech: [
            "Configure multiple objectives and constraints",
            "Visualize Pareto solution sets",
            "Run sensitivity and robustness assessments",
          ],
          value: [
            "Reduce subjective decision risk",
            "Improve resource allocation efficiency",
            "Deliver quantifiable options for leadership",
          ],
        },
        realtime: {
          metaTitle: "UDAKE - Real-Time Interpolation",
          heroTitle: "Real-Time Interpolation Module",
          heroSubtitle:
            "Drive dynamic interpolation with streaming data for fast response to field changes.",
          intro:
            "This module targets online monitoring scenarios and refreshes predictions and alerts within seconds of data arrival.",
          tech: [
            "Integrate WebSocket data streams",
            "Use incremental updates and local recomputation",
            "Support dynamic hotspot and threshold alerts",
          ],
          value: [
            "Improve incident response speed",
            "Reduce latency-induced decision bias",
            "Upgrade monitoring from static reporting to live awareness",
          ],
        },
        deepLearning: {
          metaTitle: "UDAKE - Deep Learning",
          heroTitle: "Deep Learning Module",
          heroSubtitle:
            "Leverage neural networks to capture complex spatial patterns in nonlinear environments.",
          intro:
            "The deep learning module supports multiple architectures and training strategies for high-dimensional and multi-source data.",
          tech: [
            "Extend with CNN, RNN, and graph neural networks",
            "Accelerate training and inference on GPU",
            "Compare model versions with reproducible tracking",
          ],
          value: [
            "Improve prediction accuracy in complex scenarios",
            "Enhance model generalization",
            "Shorten the path from experiment to deployment",
          ],
        },
        anomaly: {
          metaTitle: "UDAKE - Anomaly Detection",
          heroTitle: "Anomaly Detection Module",
          heroSubtitle:
            "Detect abnormal points and patterns automatically to improve data quality and alert precision.",
          intro:
            "This module identifies outliers, abrupt changes, and suspicious patterns during both ingestion and analysis stages.",
          tech: [
            "Combine statistical rules with ML-based detection",
            "Recognize spatiotemporal anomaly patterns",
            "Enable label feedback and human review loop",
          ],
          value: [
            "Reduce model interference from noisy data",
            "Improve business alert precision",
            "Support scalable data quality governance",
          ],
        },
        risk: {
          metaTitle: "UDAKE - Risk Assessment",
          heroTitle: "Risk Assessment Module",
          heroSubtitle:
            "Build multidimensional risk indices and early warning rules for proactive response planning.",
          intro:
            "The module fuses prediction outputs, uncertainty metrics, and business thresholds into actionable risk grades.",
          tech: [
            "Normalize multi-metric inputs for composite scoring",
            "Configure risk thresholds and scenario templates",
            "Analyze risk trends over time with warning notifications",
          ],
          value: [
            "Improve forward-looking risk visibility",
            "Enable precise emergency resource allocation",
            "Translate complex analytics into executable actions",
          ],
        },
      },
      download: {
        title: "Downloads",
        subtitle: "Get the latest UDAKE release from one unified entry point.",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "Download APK Now",
        comingSoon: "Coming Soon",
      },
      contact: {
        title: "Contact",
        email: "Email",
        github: "GitHub",
      },
      footer: {
        copy: "© 2026 UDAKE. All rights reserved.",
      },
      modal: {
        title: "Notice",
        message: "This platform version is under development. Stay tuned.",
        close: "OK",
      },
    },
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

  function getPageTitle(dictionary) {
    const pageFeature = document.body
      ? document.body.getAttribute("data-feature")
      : "";
    const pageTitle = pageFeature
      ? getByPath(dictionary, "pages." + pageFeature + ".metaTitle")
      : null;
    return typeof pageTitle === "string" ? pageTitle : dictionary.title;
  }

  function applyLanguage(language) {
    const normalized = normalizeLanguage(language);
    const dictionary = translations[normalized];

    document.documentElement.lang = normalized;
    document.title = getPageTitle(dictionary);

    document.querySelectorAll("[data-i18n]").forEach(function (element) {
      const key = element.getAttribute("data-i18n");
      const text = getByPath(dictionary, key);
      if (typeof text === "string") {
        element.textContent = text;
      }
    });

    document
      .querySelectorAll("[data-i18n-aria-label]")
      .forEach(function (element) {
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
    window.dispatchEvent(
      new CustomEvent("udake-language-change", {
        detail: { language: normalized },
      }),
    );
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
    init: init,
  };
})();
