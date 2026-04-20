# 前端国际化检查报告

- 生成时间: 2026-04-20T01:55:42.238Z
- 基准语言总键数: 436
- 检测到使用键数: 652
- 未使用键数: 48
- 基线保留键数: 131
- 可疑硬编码数: 2020
- 基线忽略硬编码数: 79

## 语言覆盖率

- zh-CN: 100.00% (缺失 0)
- en-US: 99.77% (缺失 1)
- zh-TW: 99.77% (缺失 1)
- ja-JP: 99.77% (缺失 1)
- ko-KR: 99.77% (缺失 1)

## 命名规范问题

- 无

## 未使用翻译键（最多 50 条）

- common.delete
- common.view
- error.common.detailsButton
- error.common.helpButton
- error.common.icon.error
- error.common.icon.success
- error.common.icon.warning
- error.common.refreshButton
- explain.action.refresh
- explain.action.submit
- explain.action.verify
- explain.method.hybrid
- explain.method.lime
- explain.method.shap
- explain.method.switchAria
- explain.monitor.active
- explain.monitor.avgDuration
- explain.monitor.cache
- explain.monitor.errorRate
- explain.monitor.queue
- explain.monitor.successRate
- explain.panel.subtitle
- explain.panel.title
- explain.result.tab.compare
- explain.result.tab.lime
- explain.result.tab.shap
- explain.result.tab.spatiotemporal
- explain.result.title
- explain.status.cancelled
- explain.status.completed
- explain.status.emptyResult
- explain.status.failed
- explain.status.noTask
- explain.status.queued
- explain.status.retrying
- explain.status.running
- explain.status.selectTask
- explain.status.taskUnavailable
- explain.submit.title
- explain.task.loadMore
- explain.task.partial
- explain.task.progress
- explain.task.retry
- explain.task.title
- intelligent.recommend
- kriging.help.parameter-relations.suggestion
- kriging.help.quick-start.suggestion
- nav.language

## 可疑硬编码（最多 50 条）

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
- apps/frontend/landing-page/docs-html/anomaly.html:74 -> 自编码器（Autoencoder）
- apps/frontend/landing-page/docs-html/anomaly.html:75 -> 变分自编码器（VAE）
