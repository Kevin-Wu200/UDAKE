# 前端国际化检查报告

- 生成时间: 2026-05-12T02:59:39.714Z
- 基准语言总键数: 970
- 检测到使用键数: 809
- 未使用键数: 437
- 基线保留键数: 130
- 可疑硬编码数: 1852
- 基线忽略硬编码数: 72

## 语言覆盖率

- zh-CN: 100.00% (缺失 0)
- en-US: 100.00% (缺失 0)
- zh-TW: 100.00% (缺失 0)
- ja-JP: 100.00% (缺失 0)
- ko-KR: 100.00% (缺失 0)

## 命名规范问题

- 无

## 未使用翻译键（最多 50 条）

- accessibility.calculate.start.title
- accessibility.color-blind
- accessibility.color-blind.deuteranopia
- accessibility.color-blind.grayscale
- accessibility.color-blind.none
- accessibility.color-blind.protanopia
- accessibility.color-blind.tritanopia
- accessibility.dark-optimize
- accessibility.font-scale
- accessibility.fontScale.change.success
- accessibility.fontScale.larger.title
- accessibility.fontScale.smaller.title
- accessibility.high-constract
- accessibility.high-contrast.closed
- accessibility.high-contrast.open
- accessibility.high-contrast.title
- accessibility.inputControl
- accessibility.interpolation.start.failed
- accessibility.interpolation.start.success
- accessibility.interpolation.start.title
- accessibility.jump.main.success
- accessibility.jump.map.success
- accessibility.jump.right-panel.switch-btn.success
- accessibility.mobile-close.sidebar.success
- accessibility.mobile-open.sidebar.success
- accessibility.name
- accessibility.newProject.success
- accessibility.newProject.title
- accessibility.open-settings
- accessibility.panel.main
- accessibility.panel.mapShow
- accessibility.panel.mapSpatial
- accessibility.panel.name
- accessibility.panel.recommend
- accessibility.prompt.newProject
- accessibility.prompt.upload-data
- accessibility.prompt.upload-failed
- accessibility.reduce-motion
- accessibility.setAttribute
- accessibility.settings
- accessibility.settings-panel.title
- accessibility.settings.open.success
- accessibility.settings.open.title
- accessibility.settings.title
- accessibility.shortcut.panel.open.success
- accessibility.shortcut.panel.title
- accessibility.shortcuts-help
- accessibility.shortcuts-jump.template
- accessibility.smart-assist
- accessibility.submit.data.success

## 可疑硬编码（最多 50 条）

- apps/frontend/index.html:62 -> 新建项目
- apps/frontend/index.html:230 -> ，且
- apps/frontend/landing-page/detail-interpolation.html:9 -> 跳转到空间插值模块详情页
- apps/frontend/landing-page/detail-realtime.html:9 -> 跳转到实时插值模块详情页
- apps/frontend/landing-page/detail-template.html:6 -> UDAKE - 详情页模板
- apps/frontend/landing-page/detail-template.html:18 -> 智能不确定性驱动空间决策平台
- apps/frontend/landing-page/detail-template.html:25 -> 模块标题
- apps/frontend/landing-page/detail-template.html:26 -> 模块详情标题
- apps/frontend/landing-page/detail-template.html:27 -> 模块一句话价值说明（2-3 句内）
- apps/frontend/landing-page/detail-template.html:32 -> 模块概述
- apps/frontend/landing-page/detail-template.html:33 -> 模块概述：该模块解决什么问题、适用什么场景。
- apps/frontend/landing-page/detail-template.html:37 -> 核心功能
- apps/frontend/landing-page/detail-template.html:39 -> 核心功能 1 + 简要说明
- apps/frontend/landing-page/detail-template.html:40 -> 核心功能 2 + 简要说明
- apps/frontend/landing-page/detail-template.html:41 -> 核心功能 3 + 简要说明
- apps/frontend/landing-page/detail-template.html:46 -> 适用场景
- apps/frontend/landing-page/detail-template.html:48 -> 场景 1
- apps/frontend/landing-page/detail-template.html:49 -> 场景 2
- apps/frontend/landing-page/detail-template.html:50 -> 场景 3
- apps/frontend/landing-page/detail-template.html:56 -> 查看文档
- apps/frontend/landing-page/detail-template.html:57 -> 开始使用
- apps/frontend/landing-page/detail-template.html:61 -> 返回首页
- apps/frontend/landing-page/docs-html/anomaly.html:6 -> UDAKE - 异常检测模块
- apps/frontend/landing-page/docs-html/anomaly.html:18 -> 智能不确定性驱动空间决策平台
- apps/frontend/landing-page/docs-html/anomaly.html:21 -> 返回首页
- apps/frontend/landing-page/docs-html/anomaly.html:26 -> 官网功能文档
- apps/frontend/landing-page/docs-html/anomaly.html:27 -> 异常检测模块
- apps/frontend/landing-page/docs-html/anomaly.html:28 -> 来源路径：anomaly.md
- apps/frontend/landing-page/docs-html/anomaly.html:34 -> 文档导航
- apps/frontend/landing-page/docs-html/anomaly.html:36 -> 模块简介
- apps/frontend/landing-page/docs-html/anomaly.html:41 -> 快速操作
- apps/frontend/landing-page/docs-html/anomaly.html:43 -> 返回功能页
- apps/frontend/landing-page/docs-html/anomaly.html:44 -> 开始使用
- apps/frontend/landing-page/docs-html/anomaly.html:50 -> 异常检测模块
- apps/frontend/landing-page/docs-html/anomaly.html:51 -> 模块简介
- apps/frontend/landing-page/docs-html/anomaly.html:52 -> 异常检测模块是UDAKE平台的数据质量保障功能，通过多种智能算法自动识别数据中的异常模式和离群点。该模块支持时空异常联合检测，提供异常标注、清洗和分析功能，确保输入数据的质量和可靠性，为后续的空间分析提供坚实的数据基础。
- apps/frontend/landing-page/docs-html/anomaly.html:53 -> 核心功能
- apps/frontend/landing-page/docs-html/anomaly.html:54 -> 1. 异常检测算法
- apps/frontend/landing-page/docs-html/anomaly.html:56 -> 统计方法
- apps/frontend/landing-page/docs-html/anomaly.html:58 -> Z-score方法
- apps/frontend/landing-page/docs-html/anomaly.html:59 -> IQR（四分位数范围）方法
- apps/frontend/landing-page/docs-html/anomaly.html:60 -> Grubbs检验
- apps/frontend/landing-page/docs-html/anomaly.html:61 -> 箱线图分析
- apps/frontend/landing-page/docs-html/anomaly.html:64 -> 机器学习方法
- apps/frontend/landing-page/docs-html/anomaly.html:66 -> 孤立森林（Isolation Forest）
- apps/frontend/landing-page/docs-html/anomaly.html:66 -> 孤立森林（Isolation Forest）
- apps/frontend/landing-page/docs-html/anomaly.html:67 -> 局部异常因子（LOF）
- apps/frontend/landing-page/docs-html/anomaly.html:68 -> 单类SVM
- apps/frontend/landing-page/docs-html/anomaly.html:69 -> DBSCAN聚类
- apps/frontend/landing-page/docs-html/anomaly.html:72 -> 深度学习方法
