# 前端国际化检查报告

- 生成时间: 2026-04-19T05:13:11.015Z
- 基准语言总键数: 409
- 检测到使用键数: 622
- 未使用键数: 44
- 基线保留键数: 131
- 可疑硬编码数: 2044
- 基线忽略硬编码数: 79

## 语言覆盖率

- zh-CN: 100.00% (缺失 0)
- en-US: 100.00% (缺失 0)
- zh-TW: 100.00% (缺失 0)
- ja-JP: 100.00% (缺失 0)
- ko-KR: 100.00% (缺失 0)

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

## 可疑硬编码（最多 50 条）

- apps/frontend/index.html:50 -> 跳转到主内容
- apps/frontend/index.html:51 -> 跳转到地图
- apps/frontend/index.html:52 -> 跳转到项目面板
- apps/frontend/index.html:111 -> 参数模板
- apps/frontend/index.html:113 -> 平衡模式（默认）
- apps/frontend/index.html:114 -> 快速估算模式
- apps/frontend/index.html:115 -> 高精度模式
- apps/frontend/index.html:116 -> 大数据集模式
- apps/frontend/index.html:117 -> 地形分析模式
- apps/frontend/index.html:118 -> 自定义模板
- apps/frontend/index.html:120 -> 为常见场景提供参数起点，可继续手动微调
- apps/frontend/index.html:123 -> 应用模板
- apps/frontend/index.html:124 -> 智能推荐
- apps/frontend/index.html:153 -> 网格分辨率必须是 1~10000 的正整数
- apps/frontend/index.html:164 -> 高级参数（新手可保持默认）
- apps/frontend/index.html:193 -> 参数帮助文档
- apps/frontend/index.html:195 -> 快速上手：
- apps/frontend/index.html:196 -> 参数关系：
- apps/frontend/index.html:197 -> 经验范围：
- apps/frontend/index.html:202 -> 保存为模板
- apps/frontend/index.html:203 -> 导出模板
- apps/frontend/index.html:204 -> 导入模板
- apps/frontend/index.html:332 -> 地图支持键盘操作。聚焦地图后，可使用方向键平移，+ 或 - 调整缩放。
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
