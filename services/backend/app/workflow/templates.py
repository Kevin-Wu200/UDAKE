"""内置工作流模板库。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List


def _simple_template(
    template_id: str,
    name: str,
    category: str,
    tags: List[str],
    records: List[float],
    step: int,
    target_count: int,
    export_format: str = "json",
) -> Dict[str, Any]:
    workflow = {
        "workflow_id": f"wf_template_{template_id}",
        "name": name,
        "description": f"模板: {name}",
        "version": 1,
        "variables": {},
        "nodes": [
            {
                "node_id": "input_data",
                "name": "输入数据",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": records},
            },
            {
                "node_id": "sampling",
                "name": "采样",
                "kind": "process",
                "node_type": "process.sample",
                "params": {"step": step},
            },
            {
                "node_id": "interpolate",
                "name": "插值",
                "kind": "process",
                "node_type": "process.interpolate",
                "params": {"target_count": target_count},
            },
            {
                "node_id": "export",
                "name": "导出",
                "kind": "process",
                "node_type": "process.export",
                "params": {"format": export_format},
            },
            {
                "node_id": "output",
                "name": "输出",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["interpolate", "export"]},
            },
        ],
        "edges": [
            {"source": "input_data", "target": "sampling"},
            {"source": "sampling", "target": "interpolate"},
            {"source": "interpolate", "target": "export"},
            {"source": "export", "target": "output"},
        ],
        "metadata": {
            "template": True,
            "category": category,
            "tags": tags,
        },
    }

    now = datetime.now(timezone.utc).isoformat()
    return {
        "template_id": template_id,
        "name": name,
        "category": category,
        "tags": tags,
        "description": f"{category}场景最佳实践模板",
        "workflow": workflow,
        "shared": True,
        "rating_average": 4.2,
        "rating_count": 1,
        "usage_count": 0,
        "created_at": now,
        "updated_at": now,
    }


def built_in_templates() -> List[Dict[str, Any]]:
    specs = [
        ("tpl_001", "基础采样插值流程", "sampling", ["基础", "采样", "插值"], [1, 3, 5, 7, 9], 1, 9),
        ("tpl_002", "污染监测快速流程", "environment", ["污染", "监测", "快速"], [12, 18, 13, 19, 22], 1, 10),
        ("tpl_003", "地质调查标准流程", "geology", ["地质", "标准", "输出"], [10, 9, 8, 7, 7], 1, 8),
        ("tpl_004", "水文时序分析流程", "hydrology", ["水文", "时序", "分析"], [2, 4, 8, 16, 32], 1, 12),
        ("tpl_005", "土壤采样最小闭环", "soil", ["土壤", "闭环"], [0.3, 0.4, 0.41, 0.42], 1, 10),
        ("tpl_006", "温度异常排查流程", "meteorology", ["温度", "异常", "排查"], [22, 23, 24, 29, 21], 1, 15),
        ("tpl_007", "企业质检自动流", "industry", ["企业", "质检", "自动化"], [91, 95, 94, 93], 1, 8),
        ("tpl_008", "高密度采样流程", "sampling", ["高密度", "精细化"], [1, 2, 3, 4, 5, 6], 1, 24),
        ("tpl_009", "低频采样流程", "sampling", ["低频", "节省成本"], [10, 20, 30, 40], 2, 6),
        ("tpl_010", "风险评估数据准备", "risk", ["风险", "评估", "准备"], [0.1, 0.25, 0.5, 0.8], 1, 12),
        ("tpl_011", "遥感预处理流程", "remote-sensing", ["遥感", "预处理"], [101, 103, 98, 105], 1, 9),
        ("tpl_012", "矿区巡检模板", "mining", ["矿区", "巡检", "模板"], [55, 56, 58, 57], 1, 8),
        ("tpl_013", "断点续跑示例", "ops", ["恢复", "重试", "运维"], [5, 5, 5, 5], 1, 4),
        ("tpl_014", "批处理导出示例", "ops", ["批处理", "导出"], [6, 9, 12, 15], 1, 10),
        ("tpl_015", "多区域汇总模板", "analysis", ["多区域", "汇总"], [13, 8, 21, 34], 1, 11),
        ("tpl_016", "变异趋势观察模板", "analysis", ["趋势", "变异"], [3, 5, 8, 13, 21], 1, 13),
        ("tpl_017", "数据接入最小模板", "ingest", ["接入", "最小"], [1, 1, 2, 3], 1, 7),
        ("tpl_018", "异常阈值对比模板", "analysis", ["异常", "阈值", "对比"], [70, 72, 69, 90], 1, 16),
        ("tpl_019", "巡检日报生成模板", "report", ["巡检", "日报", "报告"], [12, 14, 13, 15], 1, 10),
        ("tpl_020", "周报批量模板", "report", ["周报", "批量"], [66, 68, 64, 70], 1, 10),
        ("tpl_021", "并行分析模板", "analysis", ["并行", "加速"], [4, 8, 16, 32], 1, 12),
        ("tpl_022", "长链路流程模板", "advanced", ["长链路", "高级"], [1, 4, 9, 16, 25], 1, 14),
    ]

    templates = [_simple_template(*spec) for spec in specs]
    return deepcopy(templates)
