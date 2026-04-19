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
            subtitle: "高精度空间面构建",
            desc: "融合地统计学与机器学习方法，支持从稀疏样本快速生成连续空间分布并可视化输出。",
            highlights: ["支持克里金、IDW、样条等方法", "预测结果支持热力图与等值面展示"],
          },
          uncertainty: {
            title: "不确定性分析模块",
            subtitle: "可量化置信度评估",
            desc: "围绕方差与置信区间构建不确定性地图，帮助团队快速识别高风险区域与决策边界。",
            highlights: ["方差场与置信区间联动展示", "不确定性等级自动分区"],
          },
          sampling: {
            title: "采样优化模块",
            subtitle: "采样预算更高效",
            desc: "根据不确定性热点与信息增益自动推荐新增采样点，在有限资源下提升采样覆盖效率。",
            highlights: ["自动推荐新增点位", "支持约束下的采样路径规划"],
          },
          optimization: {
            title: "多目标优化模块",
            subtitle: "冲突目标平衡决策",
            desc: "在成本、时效、风险等多目标约束下进行 Pareto 优化，提供可解释的候选决策方案。",
            highlights: ["可视化 Pareto 解集", "支持鲁棒性与敏感性评估"],
          },
          realtime: {
            title: "实时插值模块",
            subtitle: "动态更新空间态势",
            desc: "基于实时数据流进行增量插值计算，让空间预测与告警结果随现场状态持续更新。",
            highlights: ["支持 WebSocket 数据接入", "秒级刷新预测与热点预警"],
          },
          deepLearning: {
            title: "深度学习模块",
            subtitle: "复杂模式自动学习",
            desc: "引入神经网络建模复杂非线性空间关系，配合 GPU 加速提升训练与推理效率。",
            highlights: ["支持 CNN/RNN/GNN 扩展", "模型版本可追踪对比"],
          },
          anomaly: {
            title: "异常检测模块",
            subtitle: "数据质量智能守门",
            desc: "自动识别异常点、突变段与可疑模式，减少脏数据传播，保障后续分析链路稳定。",
            highlights: ["时空异常联合识别", "支持人工复核闭环"],
          },
          risk: {
            title: "风险评估模块",
            subtitle: "风险指数与预警闭环",
            desc: "融合预测结果与业务阈值生成多维风险指数，支撑风险分级、预警与应对策略制定。",
            highlights: ["多维指标综合评分", "阈值模板灵活配置"],
          },
        },
      },
      pages: {
        common: {
          overviewTitle: "模块概述",
          coreTitle: "核心功能",
          useCasesTitle: "适用场景",
          ctaDocs: "查看文档",
          ctaDocsPending: "文档待完善",
          ctaStart: "开始使用",
          backHome: "返回首页",
        },
        interpolation: {
          metaTitle: "UDAKE - 空间插值模块",
          heroTitle: "空间插值模块",
          heroSubtitle: "融合地统计学与机器学习，实现高精度空间预测与可视化输出。",
          overview:
            "空间插值模块面向稀疏采样和监测点不足的业务场景，可快速构建连续空间分布，支持环境治理、资源评估与城市管理等任务。",
          coreFeatures: [
            "支持克里金、反距离加权、样条等多种插值算法切换",
            "支持栅格热力图、等值面与分级专题图输出",
            "可与实时数据流联动，动态更新预测结果",
          ],
          useCases: ["污染物浓度空间估算", "地下水位连续面重建", "城市热岛分布分析", "土壤属性快速制图"],
        },
        uncertainty: {
          metaTitle: "UDAKE - 不确定性分析模块",
          heroTitle: "不确定性分析模块",
          heroSubtitle: "把模型置信度可视化，让风险边界更清晰、决策更稳健。",
          overview:
            "不确定性分析模块针对“只看均值”带来的判断偏差，提供方差、置信区间与分级评估能力，帮助团队理解结果可靠性。",
          coreFeatures: [
            "方差场与置信区间结果联动展示",
            "支持不确定性等级分区与阈值高亮",
            "支持不同模型结果的不确定性对比分析",
          ],
          useCases: ["高风险区域优先排查", "监测方案可靠性评审", "应急决策边界设定"],
        },
        sampling: {
          metaTitle: "UDAKE - 采样优化模块",
          heroTitle: "采样优化模块",
          heroSubtitle: "基于信息增益推荐采样点位，持续提升数据价值密度。",
          overview:
            "采样优化模块结合数据分布与模型不确定性，自动识别高价值补样位置，帮助团队在预算和时效约束下提升采样效率。",
          coreFeatures: [
            "支持自适应采样与批量点位推荐",
            "内置信息增益与覆盖度联合评分机制",
            "支持约束条件下的可执行路径规划",
          ],
          useCases: ["环境监测网络加密", "野外调查路线优化", "长期监测站点迭代布局"],
        },
        optimization: {
          metaTitle: "UDAKE - 多目标优化模块",
          heroTitle: "多目标优化模块",
          heroSubtitle: "在成本、时效与风险之间找到平衡解，支撑复杂场景决策。",
          overview:
            "多目标优化模块通过 Pareto 前沿分析生成候选方案集，让业务团队在冲突目标间快速筛选可执行决策。",
          coreFeatures: [
            "支持多目标函数与多约束条件配置",
            "支持 Pareto 解集可视化与方案对比",
            "支持敏感性与鲁棒性评估",
          ],
          useCases: ["项目资源配置优化", "多约束调度策略制定", "政策方案组合评估"],
        },
        realtime: {
          metaTitle: "UDAKE - 实时插值模块",
          heroTitle: "实时插值模块",
          heroSubtitle: "流式数据驱动动态插值，快速响应现场变化。",
          overview:
            "实时插值模块适用于在线监测和应急响应场景，数据到达后即可触发局部更新，让预测结果和预警状态保持实时同步。",
          coreFeatures: [
            "支持 WebSocket 数据流接入与订阅",
            "支持增量更新与局部重计算机制",
            "支持热点识别与阈值告警联动",
          ],
          useCases: ["在线空气质量监控", "突发污染事件追踪", "生产现场动态风险看板"],
        },
        deepLearning: {
          metaTitle: "UDAKE - 深度学习模块",
          heroTitle: "深度学习模块",
          heroSubtitle: "利用神经网络学习复杂空间模式，提升非线性场景预测性能。",
          overview:
            "深度学习模块支持多种网络结构和训练策略，可处理高维、多源、异构数据，为复杂场景提供更强的表达能力。",
          coreFeatures: [
            "支持 CNN、RNN、GNN 等模型扩展",
            "支持 GPU 加速训练与推理",
            "支持模型版本管理与效果对比",
          ],
          useCases: ["高维环境变量联合建模", "多源遥感数据融合预测", "复杂地质体性质反演"],
        },
        anomaly: {
          metaTitle: "UDAKE - 异常检测模块",
          heroTitle: "异常检测模块",
          heroSubtitle: "自动识别异常点与异常模式，提升数据质量与告警准确率。",
          overview:
            "异常检测模块可在数据接入和分析阶段识别离群值、突变点与可疑模式，减少异常传播对业务判断的影响。",
          coreFeatures: [
            "支持统计规则与机器学习联合检测",
            "支持时空异常模式关联识别",
            "支持异常标签回写与人工复核闭环",
          ],
          useCases: ["传感器故障点筛查", "异常排放事件定位", "生产数据质量巡检"],
        },
        risk: {
          metaTitle: "UDAKE - 风险评估模块",
          heroTitle: "风险评估模块",
          heroSubtitle: "构建多维风险指数与预警机制，推动风险治理前置化。",
          overview:
            "风险评估模块将预测结果、不确定性指标与业务阈值融合，输出风险等级与应对建议，支撑部门协同决策。",
          coreFeatures: [
            "支持多维指标归一化与综合评分",
            "支持风险阈值模板化配置",
            "支持时序风险趋势分析与预警通知",
          ],
          useCases: ["区域风险分级管控", "应急资源精准投放", "日常风险态势监测"],
        },
      },
      download: {
        title: "客户端下载",
        subtitle: "从统一下载入口获取 UDAKE 最新版本。",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "立即下载",
        comingSoon: "即将推出",
        chooseArchitecture: "选择芯片架构下载",
        appleSilicon: "Apple Silicon",
        intel: "Intel",
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
      ticket: {
        getKey: "获取密钥",
        title: "申请密钥",
        submit: "提交申请",
        cancel: "取消",
        queryLink: "已有工单？点击查询状态",
        fields: {
          type: "工单类型",
          keyType: "密钥类型",
          existingKey: "需延期的密钥",
          email: "邮箱",
          phone: "电话号码",
          industry: "所处行业",
          purpose: "用途说明"
        },
        options: {
          apply: "申请密钥",
          renew: "延长密钥期限",
          personal_trial: "个人试用 (10次)",
          personal_standard: "个人标准 (100次)",
          enterprise_trial: "企业试用 (500次)",
          enterprise_standard: "企业标准 (1000次)"
        },
        placeholders: {
          existingKey: "请输入需要延期的密钥",
          email: "请输入邮箱",
          phone: "请输入手机号",
          industry: "请输入企业/个人所处行业",
          purpose: "请简要说明用途"
        },
        errors: {
          required: "该字段为必填项",
          email: "邮箱格式不正确",
          phoneInvalid: "手机号格式不正确",
          phoneTooShort: "手机号长度不足"
        },
        success: {
          title: "提交成功",
          message: "您的申请已提交，请记录您的工单 ID：",
          hint: "审批结果将发送至您的邮箱。"
        },
        query: {
          title: "查询工单状态",
          id: "工单 ID",
          idPlaceholder: "请输入工单 ID",
          emailPlaceholder: "请输入申请时填写的邮箱",
          btn: "查询"
        }
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
            subtitle: "High-Precision Surface Modeling",
            desc: "Blend geostatistics and ML methods to generate continuous spatial surfaces from sparse samples with visual outputs.",
            highlights: ["Switch across Kriging, IDW, and spline methods", "Render heatmaps and contours in seconds"],
          },
          uncertainty: {
            title: "Uncertainty Analysis",
            subtitle: "Quantified Confidence Insights",
            desc: "Build variance and confidence maps to reveal high-risk regions and make decision boundaries explicit.",
            highlights: ["Linked variance and confidence-interval views", "Automatic uncertainty zoning"],
          },
          sampling: {
            title: "Sampling Optimization",
            subtitle: "Higher ROI per Sample",
            desc: "Recommend new sampling points from uncertainty hotspots and information gain scores under practical constraints.",
            highlights: ["Automatic next-point recommendation", "Constraint-aware route planning"],
          },
          optimization: {
            title: "Multi-Objective Optimization",
            subtitle: "Balance Competing Targets",
            desc: "Optimize trade-offs among cost, timeliness, and risk with interpretable Pareto-optimal plan candidates.",
            highlights: ["Visualized Pareto solution sets", "Sensitivity and robustness evaluation"],
          },
          realtime: {
            title: "Real-Time Interpolation",
            subtitle: "Live Spatial Situation Updates",
            desc: "Run incremental interpolation on streaming data so predictions and alerts keep pace with changing field conditions.",
            highlights: ["WebSocket stream integration", "Second-level refresh for forecasts and alerts"],
          },
          deepLearning: {
            title: "Deep Learning",
            subtitle: "Learn Complex Patterns",
            desc: "Use neural networks to model nonlinear spatial relationships and accelerate training/inference with GPU support.",
            highlights: ["Extensible CNN/RNN/GNN architectures", "Versioned model comparison"],
          },
          anomaly: {
            title: "Anomaly Detection",
            subtitle: "Smart Data Quality Guard",
            desc: "Automatically detect outliers, abrupt shifts, and suspicious patterns to keep downstream analytics reliable.",
            highlights: ["Spatiotemporal anomaly linkage", "Human-in-the-loop review workflow"],
          },
          risk: {
            title: "Risk Assessment",
            subtitle: "Closed-Loop Risk Alerts",
            desc: "Fuse predictions and business thresholds into multidimensional risk indices for grading and response planning.",
            highlights: ["Composite scoring across multiple metrics", "Flexible threshold templates"],
          },
        },
      },
      pages: {
        common: {
          overviewTitle: "Module Overview",
          coreTitle: "Core Capabilities",
          useCasesTitle: "Use Cases",
          ctaDocs: "View Docs",
          ctaDocsPending: "Docs Pending",
          ctaStart: "Start Using",
          backHome: "Back to Home",
        },
        interpolation: {
          metaTitle: "UDAKE - Spatial Interpolation",
          heroTitle: "Spatial Interpolation Module",
          heroSubtitle:
            "Combine geostatistics and ML for high-accuracy spatial prediction and visual outputs.",
          overview:
            "Designed for sparse monitoring scenarios, this module reconstructs continuous spatial surfaces for environmental governance, resource assessment, and urban operations.",
          coreFeatures: [
            "Switch among Kriging, IDW, and spline interpolation methods",
            "Output heatmaps, contours, and classified thematic maps",
            "Update predictions dynamically with streaming inputs",
          ],
          useCases: [
            "Pollutant concentration estimation",
            "Groundwater surface reconstruction",
            "Urban heat-island mapping",
            "Rapid soil-property mapping",
          ],
        },
        uncertainty: {
          metaTitle: "UDAKE - Uncertainty Analysis",
          heroTitle: "Uncertainty Analysis Module",
          heroSubtitle:
            "Visualize model confidence to clarify risk boundaries and improve decision robustness.",
          overview:
            "This module addresses mean-only bias by offering variance, confidence-interval, and uncertainty-grade analytics.",
          coreFeatures: [
            "Linked display of variance maps and confidence intervals",
            "Automatic uncertainty zoning with threshold highlights",
            "Cross-model uncertainty comparison",
          ],
          useCases: [
            "Priority screening of high-risk regions",
            "Reliability review of monitoring plans",
            "Emergency decision boundary setup",
          ],
        },
        sampling: {
          metaTitle: "UDAKE - Sampling Optimization",
          heroTitle: "Sampling Optimization Module",
          heroSubtitle:
            "Recommend sampling points by information gain to continuously improve data value density.",
          overview:
            "By combining current distribution and uncertainty hotspots, this module suggests high-value new samples under budget and schedule constraints.",
          coreFeatures: [
            "Adaptive sampling and batch point recommendation",
            "Joint scoring of information gain and spatial coverage",
            "Constraint-aware executable route planning",
          ],
          useCases: [
            "Monitoring-network densification",
            "Field-survey route optimization",
            "Long-term station layout iteration",
          ],
        },
        optimization: {
          metaTitle: "UDAKE - Multi-Objective Optimization",
          heroTitle: "Multi-Objective Optimization Module",
          heroSubtitle:
            "Find balanced solutions across cost, timeliness, and risk in complex planning scenarios.",
          overview:
            "Using Pareto-front analysis, this module produces candidate solution sets for fast selection under competing objectives.",
          coreFeatures: [
            "Configure multiple objectives and constraints",
            "Visualize Pareto sets and compare alternatives",
            "Run sensitivity and robustness assessments",
          ],
          useCases: [
            "Resource allocation optimization",
            "Constraint-heavy scheduling strategy",
            "Policy portfolio evaluation",
          ],
        },
        realtime: {
          metaTitle: "UDAKE - Real-Time Interpolation",
          heroTitle: "Real-Time Interpolation Module",
          heroSubtitle:
            "Streaming data drives dynamic interpolation for rapid response to field changes.",
          overview:
            "Built for online monitoring and emergency response, this module triggers local updates as soon as new data arrives.",
          coreFeatures: [
            "WebSocket stream ingestion and subscription",
            "Incremental update with local recomputation",
            "Hotspot detection with threshold-based alerts",
          ],
          useCases: [
            "Online air-quality surveillance",
            "Incident pollution tracking",
            "Live operational risk dashboard",
          ],
        },
        deepLearning: {
          metaTitle: "UDAKE - Deep Learning",
          heroTitle: "Deep Learning Module",
          heroSubtitle:
            "Leverage neural networks to model complex nonlinear spatial patterns.",
          overview:
            "This module supports multiple architectures and training strategies for high-dimensional, multi-source, and heterogeneous datasets.",
          coreFeatures: [
            "Extend with CNN, RNN, and GNN models",
            "Accelerate training and inference with GPU",
            "Track model versions and benchmark results",
          ],
          useCases: [
            "Multivariate environmental modeling",
            "Remote-sensing data fusion prediction",
            "Complex geological inversion tasks",
          ],
        },
        anomaly: {
          metaTitle: "UDAKE - Anomaly Detection",
          heroTitle: "Anomaly Detection Module",
          heroSubtitle:
            "Automatically detect abnormal points and patterns to improve data quality and alert precision.",
          overview:
            "This module catches outliers, abrupt changes, and suspicious patterns during ingestion and analysis to prevent quality drift.",
          coreFeatures: [
            "Hybrid statistical-rule and ML detection",
            "Spatiotemporal anomaly pattern linkage",
            "Label feedback and human review loop",
          ],
          useCases: [
            "Sensor fault screening",
            "Abnormal discharge localization",
            "Production data quality inspection",
          ],
        },
        risk: {
          metaTitle: "UDAKE - Risk Assessment",
          heroTitle: "Risk Assessment Module",
          heroSubtitle:
            "Build multidimensional risk indices and warning mechanisms for proactive governance.",
          overview:
            "The module fuses prediction outputs, uncertainty metrics, and business thresholds into risk grades and response suggestions.",
          coreFeatures: [
            "Normalize multi-metric inputs for composite scoring",
            "Configure threshold templates by scenario",
            "Analyze temporal risk trends with warning notifications",
          ],
          useCases: [
            "Regional risk zoning and control",
            "Targeted emergency resource allocation",
            "Routine risk situation monitoring",
          ],
        },
      },
      download: {
        title: "Downloads",
        subtitle: "Get the latest UDAKE release from one unified entry point.",
        android: "Android",
        windows: "Windows",
        macos: "macOS",
        direct: "Download Now",
        comingSoon: "Coming Soon",
        chooseArchitecture:
          "Choose your chip architecture",
        appleSilicon: "Apple Silicon",
        intel: "Intel",
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
      ticket: {
        getKey: "Get Key",
        title: "Apply for API Key",
        submit: "Submit Application",
        cancel: "Cancel",
        queryLink: "Already have a ticket? Click to check status",
        fields: {
          type: "Ticket Type",
          keyType: "Key Type",
          existingKey: "Key to Renew",
          email: "Email",
          phone: "Phone Number",
          industry: "Industry",
          purpose: "Purpose"
        },
        options: {
          apply: "Apply for New Key",
          renew: "Renew Existing Key",
          personal_trial: "Personal Trial (10 requests)",
          personal_standard: "Personal Standard (100 requests)",
          enterprise_trial: "Enterprise Trial (500 requests)",
          enterprise_standard: "Enterprise Standard (1000 requests)"
        },
        placeholders: {
          existingKey: "Enter the key you want to renew",
          email: "Enter your email",
          phone: "Enter your phone number",
          industry: "Enter your industry (Enterprise/Individual)",
          purpose: "Briefly explain the purpose"
        },
        errors: {
          required: "This field is required",
          email: "Invalid email format",
          phoneInvalid: "Invalid phone number",
          phoneTooShort: "Phone number too short"
        },
        success: {
          title: "Submitted Successfully",
          message: "Your application has been submitted. Please note your Ticket ID:",
          hint: "The result will be sent to your email."
        },
        query: {
          title: "Check Ticket Status",
          id: "Ticket ID",
          idPlaceholder: "Enter your Ticket ID",
          emailPlaceholder: "Enter the email used for application",
          btn: "Query"
        }
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
        if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
          element.placeholder = text;
        } else {
          element.textContent = text;
        }
      }
    });

    document
      .querySelectorAll("[data-i18n-placeholder]")
      .forEach(function (element) {
        const key = element.getAttribute("data-i18n-placeholder");
        const text = getByPath(dictionary, key);
        if (typeof text === "string") {
          element.placeholder = text;
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
