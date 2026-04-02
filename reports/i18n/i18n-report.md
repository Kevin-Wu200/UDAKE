# 前端国际化检查报告

- 生成时间: 2026-04-02T04:36:49.203Z
- 基准语言总键数: 371
- 检测到使用键数: 477
- 未使用键数: 6
- 基线保留键数: 131
- 可疑硬编码数: 98
- 基线忽略硬编码数: 86

## 语言覆盖率

- zh-CN: 100.00% (缺失 0)
- en-US: 100.00% (缺失 0)
- zh-TW: 100.00% (缺失 0)
- ja-JP: 100.00% (缺失 0)
- ko-KR: 100.00% (缺失 0)

## 命名规范问题

- 无

## 未使用翻译键（最多 50 条）

- error.common.detailsButton
- error.common.helpButton
- error.common.icon.error
- error.common.icon.success
- error.common.icon.warning
- error.common.refreshButton

## 可疑硬编码（最多 50 条）

- apps/frontend/index.html:74 -> 跳转到主内容
- apps/frontend/index.html:75 -> 跳转到地图
- apps/frontend/index.html:76 -> 跳转到项目面板
- apps/frontend/index.html:308 -> 地图支持键盘操作。聚焦地图后，可使用方向键平移，+ 或 - 调整缩放。
- apps/frontend/js/components/DeepLearningPanel.ts:108 -> '深度学习 ▾'
- apps/frontend/js/components/DeepLearningPanel.ts:118 -> '深度学习服务状态：检测中...'
- apps/frontend/js/components/DeepLearningPanel.ts:127 -> '深度学习服务状态：${health.status}（device: ${health.device}）'
- apps/frontend/js/components/DeepLearningPanel.ts:133 -> '模型注册数：${health.registered_models?.length ?? 0}，异常模型：${health.trained_anomaly_models?.length ?? 0}，RL模型：${health.trained_sampling_rl_models?.length ?? 0}'
- apps/frontend/js/components/DeepLearningPanel.ts:137 -> '深度学习服务状态：不可用 (${error instanceof Error ? error.message : String(error)})'
- apps/frontend/js/components/DeepLearningPanel.ts:143 -> '请确认后端已启动且 /api/dl 路由可访问。'
- apps/frontend/js/components/FrontendIntegrationHub.ts:124 -> '前端功能集成补齐 ▸'
- apps/frontend/js/components/FrontendIntegrationHub.ts:129 -> '前端功能集成补齐 ▾'
- apps/frontend/js/components/LocationServicePanel.ts:467 -> '>暂无地理围栏</div>'
- apps/frontend/js/components/LocationServicePanel.ts:594 -> '>暂无采样点</div>'
- apps/frontend/js/components/Map25DHeatmapController.ts:256 -> '切换 2.5D'
- apps/frontend/js/components/Map25DHeatmapController.ts:294 -> '暂停时间轴'
- apps/frontend/js/components/Map25DHeatmapController.ts:690 -> '值: ${(nearest.point.value * 100).toFixed(1)}%<br/>点位: ${nearest.point.sourceId}'
- apps/frontend/js/components/Map25DHeatmapController.ts:713 -> '选中 ${nearest.point.sourceId} 值 ${(nearest.point.value * 100).toFixed(1)}%'
- apps/frontend/js/components/QuickActionBar.ts:205 -> '快捷操作栏'
- apps/frontend/js/components/SmartRecommendationEngine.ts:177 -> '检测为新手模式：建议先完成“导入向导”与“插值向导”。'
- apps/frontend/js/components/SmartRecommendationEngine.ts:179 -> '当前结果可导出，推荐优先执行结果导出。'
- apps/frontend/js/components/SmartRecommendationEngine.ts:181 -> '根据最近操作习惯和当前上下文生成推荐。'
- apps/frontend/js/components/SmartRecommendationEngine.ts:185 -> '>暂无推荐，请先进行几次操作。</p>'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:729 -> '编辑版本 v${version} 标签'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:927 -> '>请输入并加载数据集后查看快照列表。</div>'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:932 -> '>当前筛选条件下没有快照。</div>'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:1005 -> '>暂无快照详情。</div>'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:1278 -> '自动刷新已关闭。'
- apps/frontend/js/components/integration/HistorySnapshotPanel.ts:1315 -> '自动刷新中，${this.refreshRemainSec} 秒后刷新。'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:859 -> '>最新版本</option>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1089 -> '>未检测到异常点。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1095 -> '>当前筛选条件下暂无异常点。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1149 -> '>暂无可聚合的坐标异常点。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1157 -> '>当前无密集区域聚合。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1327 -> '>暂无预警历史记录。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1344 -> '>未检测到异常点，暂无原因分析。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1448 -> '>未检测到显著周期分量。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1878 -> '>执行趋势分析后展示模型切换。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:1879 -> '>执行趋势分析后展示模型性能对比。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2383 -> '>未加载 ECharts，无法展示交互式预览图表。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2635 -> '>暂无报告生成历史。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2674 -> '>暂无下载历史。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2686 -> '>暂无报告生成历史。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2691 -> '<h5>最近报告</h5><ul>${rows}</ul>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2696 -> '>暂无下载历史。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2701 -> '<h5>最近下载</h5><ul>${rows}</ul>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2932 -> '>执行趋势分析后展示统计指标。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2936 -> '>执行趋势分析后展示 Mann-Kendall 检验结果。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2940 -> '>执行趋势分析后展示周期识别结果。</div>'
- apps/frontend/js/components/integration/HistoryTrendAnalysisPanel.ts:2944 -> '>执行趋势分析后展示异常点列表。</div>'
