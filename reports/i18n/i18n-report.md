# 前端国际化检查报告

- 生成时间: 2026-04-06T09:20:13.380Z
- 基准语言总键数: 409
- 检测到使用键数: 477
- 未使用键数: 44
- 基线保留键数: 131
- 可疑硬编码数: 140
- 基线忽略硬编码数: 84

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

- apps/frontend/index.html:48 -> 跳转到主内容
- apps/frontend/index.html:49 -> 跳转到地图
- apps/frontend/index.html:50 -> 跳转到项目面板
- apps/frontend/index.html:109 -> 参数模板
- apps/frontend/index.html:111 -> 平衡模式（默认）
- apps/frontend/index.html:112 -> 快速估算模式
- apps/frontend/index.html:113 -> 高精度模式
- apps/frontend/index.html:114 -> 大数据集模式
- apps/frontend/index.html:115 -> 地形分析模式
- apps/frontend/index.html:116 -> 自定义模板
- apps/frontend/index.html:118 -> 为常见场景提供参数起点，可继续手动微调
- apps/frontend/index.html:121 -> 应用模板
- apps/frontend/index.html:122 -> 智能推荐
- apps/frontend/index.html:151 -> 网格分辨率必须是 1~10000 的正整数
- apps/frontend/index.html:162 -> 高级参数（新手可保持默认）
- apps/frontend/index.html:191 -> 参数帮助文档
- apps/frontend/index.html:193 -> 快速上手：
- apps/frontend/index.html:194 -> 参数关系：
- apps/frontend/index.html:195 -> 经验范围：
- apps/frontend/index.html:200 -> 保存为模板
- apps/frontend/index.html:201 -> 导出模板
- apps/frontend/index.html:202 -> 导入模板
- apps/frontend/index.html:330 -> 地图支持键盘操作。聚焦地图后，可使用方向键平移，+ 或 - 调整缩放。
- apps/frontend/js/components/DeepLearningPanel.ts:113 -> '深度学习 ▾'
- apps/frontend/js/components/DeepLearningPanel.ts:123 -> '深度学习服务状态：检测中...'
- apps/frontend/js/components/DeepLearningPanel.ts:132 -> '深度学习服务状态：${health.status}（device: ${health.device}）'
- apps/frontend/js/components/DeepLearningPanel.ts:138 -> '模型注册数：${health.registered_models?.length ?? 0}，异常模型：${health.trained_anomaly_models?.length ?? 0}，RL模型：${health.trained_sampling_rl_models?.length ?? 0}'
- apps/frontend/js/components/DeepLearningPanel.ts:142 -> '深度学习服务状态：不可用 (${error instanceof Error ? error.message : String(error)})'
- apps/frontend/js/components/DeepLearningPanel.ts:148 -> '请确认后端已启动且 /api/dl 路由可访问。'
- apps/frontend/js/components/FrontendIntegrationHub.ts:126 -> '前端功能集成补齐 ▸'
- apps/frontend/js/components/FrontendIntegrationHub.ts:131 -> '前端功能集成补齐 ▾'
- apps/frontend/js/components/LocationServicePanel.ts:467 -> '>暂无地理围栏</div>'
- apps/frontend/js/components/LocationServicePanel.ts:594 -> '>暂无采样点</div>'
- apps/frontend/js/components/Map25DHeatmapController.ts:256 -> '切换 2.5D'
- apps/frontend/js/components/Map25DHeatmapController.ts:294 -> '暂停时间轴'
- apps/frontend/js/components/Map25DHeatmapController.ts:690 -> '值: ${(nearest.point.value * 100).toFixed(1)}%<br/>点位: ${nearest.point.sourceId}'
- apps/frontend/js/components/Map25DHeatmapController.ts:713 -> '选中 ${nearest.point.sourceId} 值 ${(nearest.point.value * 100).toFixed(1)}%'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:88 -> '下拉刷新'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:100 -> '上拉加载更多'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:153 -> '松开立即刷新'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:202 -> '正在刷新...'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:209 -> '刷新完成'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:213 -> '刷新失败'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:221 -> '下拉刷新'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:236 -> '正在加载更多...'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:242 -> '继续上拉加载'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:246 -> '加载失败，请重试'
- apps/frontend/js/components/MobileInteractionEnhancer.ts:252 -> '上拉加载更多'
- apps/frontend/js/components/MobileNavigation.ts:105 -> '打开菜单'
- apps/frontend/js/components/MobileParameterDrawer.ts:168 -> '参数设置'
