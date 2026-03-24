import type { PanelConfig } from './ConfigurableApiPanel.js';

const sampleMatrixPayload = {
    task_id: 'task-20260324-001',
    prediction: [
        [10.5, 11.2, 10.8],
        [11.0, 10.9, 11.3],
        [10.7, 11.1, 10.6]
    ],
    variance: [
        [0.5, 0.8, 0.6],
        [0.7, 0.9, 0.4],
        [0.3, 0.6, 0.5]
    ],
    x_coords: [120.1, 120.2, 120.3],
    y_coords: [30.1, 30.2, 30.3]
};

const sampleModelEvalPayload = {
    task_id: 'task-20260324-001',
    actual_values: [10.3, 11.0, 10.9, 10.8, 10.6],
    predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7],
    variance: [0.5, 0.8, 0.6, 0.7, 0.3],
    model_params: {
        method: 'kriging',
        variogram_model: 'spherical',
        range: 100,
        sill: 1,
        nugget: 0.1
    },
    x_coords: [120.1, 120.2, 120.3, 120.4, 120.5],
    y_coords: [30.1, 30.2, 30.3, 30.4, 30.5]
};

export const panelConfigs: Record<string, PanelConfig> = {
    dataQuality: {
        key: 'data-quality',
        title: '数据质量评估面板',
        description: '覆盖规则管理、质量评估、报告查询、异常与建议、历史与导出。',
        fields: [
            { key: 'dataset_id', label: '数据集 ID', type: 'text', defaultValue: 'dataset-001' },
            { key: 'rule_id', label: '规则 ID', type: 'text', defaultValue: 'rule-001' },
            { key: 'report_id', label: '报告 ID', type: 'text', defaultValue: 'report-001' },
            {
                key: 'format',
                label: '导出格式',
                type: 'select',
                defaultValue: 'json',
                options: [
                    { label: 'JSON', value: 'json' },
                    { label: 'Markdown', value: 'markdown' },
                    { label: 'HTML', value: 'html' }
                ]
            },
            { key: 'enabled', label: '启用规则', type: 'checkbox', defaultValue: true },
            {
                key: 'payload',
                label: '请求体(JSON)',
                type: 'json',
                defaultValue: {
                    dataset_id: 'dataset-001',
                    rules: [
                        { name: 'required_name', rule_type: 'required', field: 'name', priority: 1, enabled: true },
                        { name: 'range_value', rule_type: 'range', field: 'value', params: { min: 0, max: 100 }, priority: 2, enabled: true }
                    ]
                }
            }
        ],
        operations: [
            { id: 'dq-health', label: '健康检查', method: 'GET', path: '/data-quality/health' },
            { id: 'dq-rules-list', label: '列出规则', method: 'GET', path: '/data-quality/rules' },
            { id: 'dq-rules-create', label: '创建规则', method: 'POST', path: '/data-quality/rules', bodyFieldAsRoot: 'payload' },
            { id: 'dq-rules-update', label: '更新规则', method: 'PUT', path: '/data-quality/rules/:rule_id', bodyFieldAsRoot: 'payload' },
            { id: 'dq-rules-toggle', label: '启用/禁用规则', method: 'PATCH', path: '/data-quality/rules/:rule_id/enabled', bodyFromFields: ['enabled'] },
            { id: 'dq-rules-delete', label: '删除规则', method: 'DELETE', path: '/data-quality/rules/:rule_id' },
            { id: 'dq-evaluate', label: '执行质量评估', method: 'POST', path: '/data-quality/evaluate', bodyFieldAsRoot: 'payload' },
            { id: 'dq-report', label: '获取评估报告', method: 'GET', path: '/data-quality/reports/:report_id' },
            { id: 'dq-anomalies', label: '获取异常数据', method: 'GET', path: '/data-quality/reports/:report_id/anomalies' },
            { id: 'dq-suggestions', label: '获取改进建议', method: 'GET', path: '/data-quality/reports/:report_id/suggestions' },
            { id: 'dq-export', label: '导出质量报告', method: 'GET', path: '/data-quality/reports/:report_id/export?fmt=:format' },
            { id: 'dq-history', label: '获取质量历史', method: 'GET', path: '/data-quality/history/:dataset_id' }
        ]
    },

    modelEvaluation: {
        key: 'model-evaluation',
        title: '模型评估报告面板',
        description: '提交实际值/预测值/方差并生成模型评估报告与建议。',
        fields: [
            { key: 'payload', label: '评估参数(JSON)', type: 'json', defaultValue: sampleModelEvalPayload }
        ],
        operations: [
            { id: 'model-eval', label: '执行模型评估', method: 'POST', path: '/model/evaluation', bodyFieldAsRoot: 'payload' }
        ]
    },

    userValidation: {
        key: 'user-validation',
        title: '用户验证与自评估面板',
        description: '实时评估、模型选择、优化控制、报告生成与查询。',
        fields: [
            { key: 'window_minutes', label: '统计窗口(分钟)', type: 'number', defaultValue: 120 },
            { key: 'sample_size', label: '样本数量', type: 'number', defaultValue: 200 },
            {
                key: 'payload',
                label: '请求体(JSON)',
                type: 'json',
                defaultValue: {
                    task_id: 'task-20260324-001',
                    actual_values: [10.3, 11.0, 10.9, 10.8, 10.6],
                    predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7],
                    variance: [0.5, 0.8, 0.6, 0.7, 0.3],
                    trigger_reason: 'manual'
                }
            }
        ],
        operations: [
            { id: 'uv-realtime', label: '实时评估', method: 'POST', path: '/evaluation/realtime', bodyFieldAsRoot: 'payload' },
            { id: 'uv-perf', label: '性能指标', method: 'GET', path: '/evaluation/performance' },
            { id: 'uv-errors', label: '错误分析', method: 'GET', path: '/evaluation/errors' },
            { id: 'uv-uncertainty', label: '不确定性分析', method: 'GET', path: '/evaluation/uncertainty' },
            { id: 'uv-model-select', label: '选择最佳模型', method: 'POST', path: '/model-selection/select', bodyFieldAsRoot: 'payload' },
            { id: 'uv-model-status', label: '模型选择状态', method: 'GET', path: '/model-selection/status' },
            { id: 'uv-model-switch', label: '切换模型', method: 'POST', path: '/model-selection/switch', bodyFieldAsRoot: 'payload' },
            { id: 'uv-model-rollback', label: '回滚模型', method: 'POST', path: '/model-selection/rollback', bodyFieldAsRoot: 'payload' },
            { id: 'uv-opt-trigger', label: '触发优化', method: 'POST', path: '/optimization/trigger', bodyFieldAsRoot: 'payload' },
            { id: 'uv-opt-status', label: '优化状态', method: 'GET', path: '/optimization/status' },
            { id: 'uv-opt-cancel', label: '取消优化', method: 'POST', path: '/optimization/cancel', bodyFieldAsRoot: 'payload' },
            { id: 'uv-report-perf', label: '性能报告', method: 'GET', path: '/reports/performance?window_minutes=:window_minutes&sample_size=:sample_size' },
            { id: 'uv-report-eval', label: '评估报告', method: 'GET', path: '/reports/evaluation?window_minutes=:window_minutes&sample_size=:sample_size' },
            { id: 'uv-report-opt', label: '优化报告', method: 'GET', path: '/reports/optimization' },
            { id: 'uv-report-generate', label: '生成报告', method: 'POST', path: '/reports/generate', bodyFieldAsRoot: 'payload' }
        ]
    },

    modelFusion: {
        key: 'model-fusion',
        title: '模型融合面板',
        description: '融合任务创建、状态追踪、结果获取、策略对比与权重优化。',
        fields: [
            { key: 'task_id', label: '融合任务 ID', type: 'text', defaultValue: 'fusion-task-001' },
            {
                key: 'payload',
                label: '融合参数(JSON)',
                type: 'json',
                defaultValue: {
                    models: ['kriging', 'deep_learning'],
                    strategy: 'weighted_average',
                    predictions: [[10.2, 10.5], [10.6, 10.8]],
                    uncertainty: [[0.3, 0.4], [0.5, 0.6]],
                    weights: [0.6, 0.4]
                }
            }
        ],
        operations: [
            { id: 'fusion-create', label: '创建融合任务', method: 'POST', path: '/fusion/create-task', bodyFieldAsRoot: 'payload' },
            { id: 'fusion-status', label: '任务状态', method: 'GET', path: '/fusion/task/:task_id/status' },
            { id: 'fusion-result', label: '任务结果', method: 'GET', path: '/fusion/task/:task_id/result' },
            { id: 'fusion-compare', label: '策略对比', method: 'POST', path: '/fusion/compare-strategies', bodyFieldAsRoot: 'payload' },
            { id: 'fusion-optimize', label: '优化权重', method: 'POST', path: '/fusion/optimize-weights', bodyFieldAsRoot: 'payload' },
            { id: 'fusion-list', label: '任务列表', method: 'GET', path: '/fusion/tasks' },
            { id: 'fusion-strategies', label: '融合策略', method: 'GET', path: '/fusion/strategies' },
            { id: 'fusion-weight-methods', label: '权重方法', method: 'GET', path: '/fusion/weight-methods' },
            { id: 'fusion-global-status', label: '融合状态', method: 'GET', path: '/fusion/status' }
        ]
    },

    modelRecommendation: {
        key: 'model-recommendation',
        title: '模型推荐面板',
        description: '基于场景与数据特征推荐插值参数和模型。',
        fields: [
            {
                key: 'payload',
                label: '推荐参数(JSON)',
                type: 'json',
                defaultValue: {
                    industry: 'environment',
                    data_scale: 'medium',
                    target: 'accuracy_first',
                    constraints: {
                        latency_ms: 800,
                        max_memory_mb: 512
                    }
                }
            }
        ],
        operations: [
            { id: 'model-recommend', label: '获取推荐', method: 'POST', path: '/recommend-parameters', bodyFieldAsRoot: 'payload' }
        ]
    },

    batchKriging: {
        key: 'batch-kriging',
        title: '批量插值任务面板',
        description: '启动、监控、控制批量任务并获取结果。',
        fields: [
            { key: 'batch_id', label: '批量任务 ID', type: 'text', defaultValue: 'batch-001' },
            {
                key: 'action',
                label: '控制动作',
                type: 'select',
                defaultValue: 'pause',
                options: [
                    { label: '暂停', value: 'pause' },
                    { label: '恢复', value: 'resume' },
                    { label: '取消', value: 'cancel' }
                ]
            },
            {
                key: 'payload',
                label: '批量参数(JSON)',
                type: 'json',
                defaultValue: {
                    task_name: 'batch-kriging-demo',
                    dataset_ids: ['dataset-001', 'dataset-002'],
                    parameters: {
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 100
                    }
                }
            }
        ],
        operations: [
            { id: 'batch-start', label: '启动批量任务', method: 'POST', path: '/batch-kriging', bodyFieldAsRoot: 'payload' },
            { id: 'batch-status', label: '任务状态', method: 'GET', path: '/batch-kriging/:batch_id/status' },
            { id: 'batch-control', label: '控制任务', method: 'POST', path: '/batch-kriging/:batch_id/control', bodyFromFields: ['action'] },
            { id: 'batch-results', label: '获取结果', method: 'GET', path: '/batch-kriging/:batch_id/results' },
            { id: 'batch-list', label: '任务列表', method: 'GET', path: '/batch-kriging' }
        ]
    },

    batchReport: {
        key: 'batch-report',
        title: '批量报告生成面板',
        description: '报告模板、章节、格式、预览与批量生成。',
        fields: [
            { key: 'batch_id', label: '批量任务 ID', type: 'text', defaultValue: 'batch-001' },
            {
                key: 'payload',
                label: '报告配置(JSON)',
                type: 'json',
                defaultValue: {
                    batch_id: 'batch-001',
                    template: 'default',
                    sections: ['summary', 'metrics', 'recommendations'],
                    formats: ['pdf', 'html']
                }
            }
        ],
        operations: [
            { id: 'batch-report-generate', label: '生成批量报告', method: 'POST', path: '/batch-reports/generate', bodyFieldAsRoot: 'payload' },
            { id: 'batch-report-templates', label: '模板列表', method: 'GET', path: '/batch-reports/templates' },
            { id: 'batch-report-sections', label: '章节列表', method: 'GET', path: '/batch-reports/sections' },
            { id: 'batch-report-formats', label: '格式列表', method: 'GET', path: '/batch-reports/formats' },
            { id: 'batch-report-preview', label: '预览报告', method: 'GET', path: '/batch-reports/preview/:batch_id' }
        ]
    },

    parameterTemplate: {
        key: 'parameter-template',
        title: '参数批量应用面板',
        description: '模板管理、参数验证、批量应用、自动调整。',
        fields: [
            { key: 'template_id', label: '模板 ID', type: 'text', defaultValue: 'template-001' },
            {
                key: 'payload',
                label: '参数配置(JSON)',
                type: 'json',
                defaultValue: {
                    name: '环境监测模板',
                    description: '适用于环境监测场景',
                    parameters: {
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 120
                    },
                    dataset_ids: ['dataset-001', 'dataset-002']
                }
            }
        ],
        operations: [
            { id: 'param-template-create', label: '创建模板', method: 'POST', path: '/parameter-templates', bodyFieldAsRoot: 'payload' },
            { id: 'param-template-list', label: '模板列表', method: 'GET', path: '/parameter-templates' },
            { id: 'param-template-defaults', label: '默认模板', method: 'GET', path: '/parameter-templates/defaults' },
            { id: 'param-template-detail', label: '模板详情', method: 'GET', path: '/parameter-templates/:template_id' },
            { id: 'param-template-delete', label: '删除模板', method: 'DELETE', path: '/parameter-templates/:template_id' },
            { id: 'param-template-apply', label: '应用模板', method: 'POST', path: '/parameter-templates/:template_id/apply', bodyFieldAsRoot: 'payload' },
            { id: 'param-validate', label: '参数验证', method: 'POST', path: '/parameters/validate', bodyFieldAsRoot: 'payload' },
            { id: 'param-apply', label: '参数应用', method: 'POST', path: '/parameters/apply', bodyFieldAsRoot: 'payload' },
            { id: 'param-auto-adjust', label: '自动调整', method: 'POST', path: '/parameters/auto-adjust', bodyFieldAsRoot: 'payload' }
        ]
    },

    reportGeneration: {
        key: 'report-generation',
        title: '报告生成面板',
        description: '支持通用分析报告与自评估报告生成。',
        fields: [
            { key: 'analysis_id', label: '分析 ID', type: 'text', defaultValue: 'analysis-001' },
            {
                key: 'payload',
                label: '报告参数(JSON)',
                type: 'json',
                defaultValue: {
                    report_type: 'all',
                    format: 'markdown',
                    window_minutes: 120,
                    sample_size: 200
                }
            }
        ],
        operations: [
            { id: 'report-generate-unified', label: '生成综合报告', method: 'POST', path: '/reports/generate', bodyFieldAsRoot: 'payload' },
            { id: 'report-generate-analysis', label: '分析报告下载', method: 'GET', path: '/analysis/:analysis_id/report' }
        ]
    },

    riskReport: {
        key: 'risk-report',
        title: '风险报告面板',
        description: '基于预测、方差、风险指数生成风险报告。',
        fields: [
            {
                key: 'payload',
                label: '风险报告参数(JSON)',
                type: 'json',
                defaultValue: {
                    ...sampleMatrixPayload,
                    risk_index: [
                        [0.5, 0.8, 0.6],
                        [0.7, 0.9, 0.4],
                        [0.3, 0.6, 0.5]
                    ],
                    metadata: {
                        project_name: '环境监测项目',
                        location: '杭州市',
                        date: '2026-03-24'
                    },
                    save_to_file: true
                }
            }
        ],
        operations: [
            { id: 'risk-report-generate', label: '生成风险报告', method: 'POST', path: '/risk/report', bodyFieldAsRoot: 'payload' }
        ]
    },

    performanceReport: {
        key: 'performance-report',
        title: '性能报告面板',
        description: '性能报告生成、趋势分析与历史统计。',
        fields: [
            { key: 'task_id', label: '任务 ID', type: 'text', defaultValue: 'task-20260324-001' },
            { key: 'task_type', label: '任务类型', type: 'text', defaultValue: 'kriging' },
            {
                key: 'payload',
                label: '性能报告参数(JSON)',
                type: 'json',
                defaultValue: {
                    task_id: 'task-20260324-001',
                    include_trend: true,
                    include_statistics: true
                }
            }
        ],
        operations: [
            { id: 'performance-report-create', label: '生成性能报告', method: 'POST', path: '/performance/report', bodyFieldAsRoot: 'payload' },
            { id: 'performance-report-trend', label: '获取性能趋势', method: 'GET', path: '/performance/trend/:task_id' },
            { id: 'performance-report-history', label: '历史统计', method: 'GET', path: '/performance/historical-stats/:task_type' }
        ]
    },

    uncertaintyClassification: {
        key: 'uncertainty-classification',
        title: '不确定性分级面板',
        description: '预测结果按不确定性等级分级并返回关键区域。',
        fields: [
            {
                key: 'payload',
                label: '分级参数(JSON)',
                type: 'json',
                defaultValue: sampleMatrixPayload
            }
        ],
        operations: [
            { id: 'uncertainty-classify', label: '执行不确定性分级', method: 'POST', path: '/uncertainty/classify', bodyFieldAsRoot: 'payload' }
        ]
    },

    decisionThreshold: {
        key: 'decision-threshold',
        title: '决策阈值面板',
        description: '分析不同阈值下覆盖率和风险，给出推荐阈值。',
        fields: [
            {
                key: 'payload',
                label: '阈值参数(JSON)',
                type: 'json',
                defaultValue: {
                    ...sampleMatrixPayload,
                    decision_goal: '确定污染物预警阈值',
                    risk_tolerance: 0.1,
                    custom_thresholds: [10.0, 10.5, 11.0, 11.5]
                }
            }
        ],
        operations: [
            { id: 'decision-threshold-analyze', label: '执行阈值分析', method: 'POST', path: '/decision/thresholds', bodyFieldAsRoot: 'payload' }
        ]
    },

    riskIndex: {
        key: 'risk-index',
        title: '风险指数面板',
        description: '计算风险指数、风险分级与高风险区域统计。',
        fields: [
            {
                key: 'payload',
                label: '风险参数(JSON)',
                type: 'json',
                defaultValue: {
                    ...sampleMatrixPayload,
                    confidence_level: 0.95,
                    threshold_values: {
                        low: 0.3,
                        medium: 0.6,
                        high: 0.9,
                        critical: 1.2
                    }
                }
            }
        ],
        operations: [
            { id: 'risk-calculate', label: '计算风险指数', method: 'POST', path: '/risk/calculate', bodyFieldAsRoot: 'payload' }
        ]
    },

    resultComparison: {
        key: 'result-comparison',
        title: '结果对比分析面板',
        description: '批量任务结果对比、排名、差异、统计与导出。',
        fields: [
            { key: 'batch_id', label: '批量任务 ID', type: 'text', defaultValue: 'batch-001' }
        ],
        operations: [
            { id: 'comparison-full', label: '完整对比', method: 'GET', path: '/batch-kriging/:batch_id/comparison' },
            { id: 'comparison-ranking', label: '结果排名', method: 'GET', path: '/batch-kriging/:batch_id/ranking' },
            { id: 'comparison-difference', label: '差异分析', method: 'GET', path: '/batch-kriging/:batch_id/difference' },
            { id: 'comparison-stats', label: '对比统计', method: 'GET', path: '/batch-kriging/:batch_id/comparison/statistics' },
            { id: 'comparison-summary', label: '对比摘要', method: 'GET', path: '/batch-kriging/:batch_id/comparison/summary' },
            { id: 'comparison-export', label: '导出对比', method: 'GET', path: '/batch-kriging/:batch_id/comparison/export' }
        ]
    },

    resultQuery: {
        key: 'result-query',
        title: '结果查询面板',
        description: '预测结果、方差结果、报告和下载入口。',
        fields: [
            { key: 'task_id', label: '任务 ID', type: 'text', defaultValue: 'task-20260324-001' },
            { key: 'filename', label: '文件名', type: 'text', defaultValue: 'task-20260324-001_prediction.geojson' }
        ],
        operations: [
            { id: 'result-prediction', label: '查询预测结果', method: 'GET', path: '/result/prediction/:task_id' },
            { id: 'result-variance', label: '查询方差结果', method: 'GET', path: '/result/variance/:task_id' },
            { id: 'result-report', label: '查询任务报告', method: 'GET', path: '/result/report/:task_id' },
            { id: 'result-download', label: '下载结果文件', method: 'GET', path: '/result/download/:task_id/:filename' }
        ]
    },

    errorPrediction: {
        key: 'error-prediction',
        title: '误差预测面板',
        description: '预测误差分布并可选训练误差模型。',
        fields: [
            {
                key: 'payload',
                label: '误差预测参数(JSON)',
                type: 'json',
                defaultValue: {
                    task_id: 'task-20260324-001',
                    x_coords: [120.1, 120.2, 120.3, 120.4, 120.5, 120.6, 120.7, 120.8, 120.9, 121.0],
                    y_coords: [30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7, 30.8, 30.9, 31.0],
                    predicted_values: [10.5, 11.2, 10.8, 11.0, 10.7, 10.9, 11.1, 10.6, 11.3, 10.8],
                    actual_values: [10.3, 11.0, 10.9, 10.8, 10.6, 10.75, 10.85, 10.55, 11.0, 10.68],
                    train_model: true
                }
            }
        ],
        operations: [
            { id: 'error-predict', label: '执行误差预测', method: 'POST', path: '/error/predict', bodyFieldAsRoot: 'payload' }
        ]
    },

    dataFeedback: {
        key: 'data-feedback',
        title: '数据反馈面板',
        description: '反馈录入、修改、校验、查询、质量与冲突处理。',
        fields: [
            { key: 'entity_id', label: '实体 ID', type: 'text', defaultValue: 'feedback-entity-001' },
            { key: 'conflict_id', label: '冲突 ID', type: 'text', defaultValue: 'conflict-001' },
            {
                key: 'payload',
                label: '反馈参数(JSON)',
                type: 'json',
                defaultValue: {
                    dataset_id: 'dataset-001',
                    record_id: 'record-001',
                    content: { field: 'pm25', value: 32.5 },
                    reason: '现场复核修正'
                }
            }
        ],
        operations: [
            { id: 'feedback-health', label: '反馈服务健康', method: 'GET', path: '/feedback/health' },
            { id: 'feedback-input', label: '提交输入反馈', method: 'POST', path: '/feedback/input', bodyFieldAsRoot: 'payload' },
            { id: 'feedback-mod', label: '提交修改反馈', method: 'POST', path: '/feedback/modification', bodyFieldAsRoot: 'payload' },
            { id: 'feedback-validation', label: '提交校验反馈', method: 'POST', path: '/feedback/validation', bodyFieldAsRoot: 'payload' },
            { id: 'feedback-annotation', label: '提交标注反馈', method: 'POST', path: '/feedback/annotation', bodyFieldAsRoot: 'payload' },
            { id: 'feedback-query', label: '查询反馈数据', method: 'GET', path: '/feedback/data?dataset_id=dataset-001' },
            { id: 'feedback-history', label: '查询反馈历史', method: 'GET', path: '/feedback/history?entity_id=:entity_id' },
            { id: 'feedback-quality', label: '查询反馈质量', method: 'GET', path: '/feedback/quality?record_id=record-001' },
            { id: 'feedback-conflicts', label: '查询冲突', method: 'GET', path: '/feedback/conflicts?unresolved_only=true' },
            { id: 'feedback-resolve', label: '解决冲突', method: 'POST', path: '/feedback/conflicts/:conflict_id/resolve', bodyFieldAsRoot: 'payload' },
            { id: 'feedback-stats', label: '反馈统计', method: 'GET', path: '/feedback/stats?dataset_id=dataset-001' }
        ]
    },

    generalDataProcessing: {
        key: 'general-data-processing',
        title: '通用数据处理面板',
        description: '插值、采样、分析、报告、导入与导出流程。',
        fields: [
            { key: 'analysis_id', label: '分析 ID', type: 'text', defaultValue: 'analysis-001' },
            {
                key: 'payload',
                label: '处理参数(JSON)',
                type: 'json',
                defaultValue: {
                    points: [
                        { x: 120.1, y: 30.1, value: 10.3 },
                        { x: 120.2, y: 30.2, value: 11.0 },
                        { x: 120.3, y: 30.3, value: 10.9 }
                    ],
                    parameters: {
                        method: 'ordinary',
                        variogram_model: 'spherical',
                        grid_resolution: 100
                    }
                }
            }
        ],
        operations: [
            { id: 'gdp-interpolation', label: '提交插值', method: 'POST', path: '/interpolation', bodyFieldAsRoot: 'payload' },
            { id: 'gdp-sampling', label: '生成采样点', method: 'POST', path: '/sampling', bodyFieldAsRoot: 'payload' },
            { id: 'gdp-analysis', label: '执行分析', method: 'POST', path: '/analysis', bodyFieldAsRoot: 'payload' },
            { id: 'gdp-report', label: '分析报告', method: 'GET', path: '/analysis/:analysis_id/report' },
            { id: 'gdp-export', label: '导出数据', method: 'POST', path: '/export', bodyFieldAsRoot: 'payload' },
            { id: 'gdp-import', label: '导入数据', method: 'POST', path: '/import', bodyFieldAsRoot: 'payload' }
        ]
    },

    taskQueue: {
        key: 'task-queue',
        title: '任务队列管理面板',
        description: '任务入队、控制、优先级、配置与运行状态。',
        fields: [
            { key: 'task_id', label: '任务 ID', type: 'text', defaultValue: 'queue-task-001' },
            {
                key: 'payload',
                label: '队列参数(JSON)',
                type: 'json',
                defaultValue: {
                    task_type: 'kriging',
                    priority: 'normal',
                    payload: {
                        dataset_id: 'dataset-001'
                    }
                }
            }
        ],
        operations: [
            { id: 'queue-create', label: '创建队列任务', method: 'POST', path: '/queue/tasks', bodyFieldAsRoot: 'payload' },
            { id: 'queue-detail', label: '任务详情', method: 'GET', path: '/queue/tasks/:task_id' },
            { id: 'queue-list', label: '任务列表', method: 'GET', path: '/queue/tasks' },
            { id: 'queue-control', label: '任务控制', method: 'POST', path: '/queue/tasks/control', bodyFieldAsRoot: 'payload' },
            { id: 'queue-priority', label: '更新优先级', method: 'PUT', path: '/queue/tasks/:task_id/priority', bodyFieldAsRoot: 'payload' },
            { id: 'queue-stats', label: '队列统计', method: 'GET', path: '/queue/statistics' },
            { id: 'queue-config-get', label: '读取队列配置', method: 'GET', path: '/queue/config' },
            { id: 'queue-config-put', label: '更新队列配置', method: 'PUT', path: '/queue/config', bodyFieldAsRoot: 'payload' },
            { id: 'queue-start', label: '启动队列', method: 'POST', path: '/queue/start' },
            { id: 'queue-stop', label: '停止队列', method: 'POST', path: '/queue/stop' }
        ]
    },

    gpuAcceleration: {
        key: 'gpu-acceleration',
        title: 'GPU 加速面板',
        description: 'GPU 健康、状态、配置、指标、任务与加速计算。',
        fields: [
            { key: 'task_id', label: 'GPU任务 ID', type: 'text', defaultValue: 'gpu-task-001' },
            {
                key: 'payload',
                label: 'GPU参数(JSON)',
                type: 'json',
                defaultValue: {
                    enable_gpu: true,
                    auto_switch: true,
                    min_size_for_gpu: 8,
                    matrix_a: [[1, 2], [3, 4]],
                    matrix_b: [[5, 6], [7, 8]],
                    prefer_gpu: true
                }
            }
        ],
        operations: [
            { id: 'gpu-health', label: 'GPU健康检查', method: 'GET', path: '/gpu/health' },
            { id: 'gpu-status', label: 'GPU状态', method: 'GET', path: '/gpu/status' },
            { id: 'gpu-devices', label: 'GPU设备列表', method: 'GET', path: '/gpu/devices' },
            { id: 'gpu-config-put', label: '更新GPU配置', method: 'PUT', path: '/gpu/config', bodyFieldAsRoot: 'payload' },
            { id: 'gpu-metrics', label: 'GPU指标', method: 'GET', path: '/gpu/metrics' },
            { id: 'gpu-task-list', label: 'GPU任务列表', method: 'GET', path: '/gpu/tasks' },
            { id: 'gpu-task-detail', label: 'GPU任务详情', method: 'GET', path: '/gpu/tasks/:task_id' },
            { id: 'gpu-matrix-mul', label: '矩阵乘法', method: 'POST', path: '/gpu/compute/matrix/multiply', bodyFieldAsRoot: 'payload' }
        ]
    }
};
