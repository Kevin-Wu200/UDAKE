"""工作流定义校验与 DAG 解析。"""

from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Tuple
from uuid import uuid4


ALLOWED_NODE_KINDS = {"input", "process", "output", "control", "custom"}

# 节点参数规则（最小可行版本，支持扩展）
NODE_TYPE_PARAM_RULES: Dict[str, Dict[str, Any]] = {
    "input.constant": {"required": ["value"]},
    "input.variable": {"required": ["name"]},
    "input.dataset": {"required": ["records"]},
    "process.transform": {"required": ["operation"]},
    "process.sample": {"required": ["step"]},
    "process.interpolate": {"required": ["target_count"]},
    "process.export": {"required": ["format"]},
    "process.fail_then_pass": {"required": ["fail_until_attempt"]},
    "control.condition": {"required": ["left", "operator", "right"]},
    "control.loop": {"required": ["iterable", "operation"]},
    "control.parallel": {"required": ["tasks"]},
    "output.collect": {"required": []},
    "output.variable_write": {"required": ["name", "from"]},
}


WORKFLOW_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "UDAKE Workflow Definition",
    "type": "object",
    "required": ["name", "nodes", "edges"],
    "properties": {
        "workflow_id": {"type": "string"},
        "name": {"type": "string", "minLength": 1, "maxLength": 200},
        "description": {"type": "string"},
        "version": {"type": "integer", "minimum": 1},
        "variables": {"type": "object"},
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["node_id", "kind"],
                "properties": {
                    "node_id": {"type": "string"},
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": sorted(ALLOWED_NODE_KINDS)},
                    "node_type": {"type": "string"},
                    "params": {"type": "object"},
                    "enabled": {"type": "boolean"},
                    "retry_policy": {
                        "type": "object",
                        "properties": {
                            "max_retries": {"type": "integer", "minimum": 0, "maximum": 20},
                            "delay_ms": {"type": "integer", "minimum": 0, "maximum": 60000},
                        },
                    },
                },
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "target"],
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "condition": {"type": "string"},
                },
            },
        },
        "metadata": {"type": "object"},
    },
}


class WorkflowValidationError(ValueError):
    """工作流定义非法。"""


def _ensure_mapping(value: Any, field_name: str) -> MutableMapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, MutableMapping):
        raise WorkflowValidationError(f"{field_name} 必须是对象")
    return dict(value)


def _validate_node_params(node: Mapping[str, Any]) -> None:
    node_type = str(node.get("node_type") or "")
    params = node.get("params") or {}
    if not isinstance(params, Mapping):
        raise WorkflowValidationError(f"节点 {node.get('node_id')} 的 params 必须是对象")

    rules = NODE_TYPE_PARAM_RULES.get(node_type)
    if rules is None and node.get("kind") == "custom":
        return

    if rules is None:
        # 未定义的类型允许通过，避免阻塞未来扩展
        return

    required_fields = rules.get("required", [])
    missing = [name for name in required_fields if name not in params]
    if missing:
        raise WorkflowValidationError(
            f"节点 {node.get('node_id')}({node_type}) 缺少参数: {', '.join(missing)}"
        )



def _build_graph(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, int], Dict[str, List[Dict[str, Any]]]]:
    adjacency: Dict[str, List[str]] = defaultdict(list)
    indegree: Dict[str, int] = {node["node_id"]: 0 for node in nodes}
    edge_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        adjacency[source].append(target)
        indegree[target] += 1
        edge_map[source].append(edge)

    return dict(adjacency), indegree, dict(edge_map)


def topological_sort(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    adjacency, indegree, _ = _build_graph(nodes, edges)
    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])

    order: List[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for nxt in adjacency.get(current, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(nodes):
        raise WorkflowValidationError("DAG 校验失败：存在循环依赖")

    return order


def dag_levels(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[List[str]]:
    adjacency, indegree, _ = _build_graph(nodes, edges)
    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
    levels: List[List[str]] = []

    while queue:
        level_size = len(queue)
        level_nodes: List[str] = []
        for _ in range(level_size):
            current = queue.popleft()
            level_nodes.append(current)
            for nxt in adjacency.get(current, []):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        levels.append(level_nodes)

    if sum(len(level) for level in levels) != len(nodes):
        raise WorkflowValidationError("DAG 层级构建失败：存在循环依赖")

    return levels


def validate_and_normalize_definition(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise WorkflowValidationError("工作流定义必须是对象")

    normalized = deepcopy(dict(payload))
    normalized["workflow_id"] = str(normalized.get("workflow_id") or f"wf_{uuid4().hex[:12]}")
    normalized["name"] = str(normalized.get("name") or "").strip()
    if not normalized["name"]:
        raise WorkflowValidationError("name 不能为空")

    normalized["description"] = str(normalized.get("description") or "")
    normalized["version"] = int(normalized.get("version") or 1)
    if normalized["version"] < 1:
        raise WorkflowValidationError("version 必须 >= 1")

    normalized["variables"] = _ensure_mapping(normalized.get("variables"), "variables")
    normalized["metadata"] = _ensure_mapping(normalized.get("metadata"), "metadata")

    nodes = normalized.get("nodes")
    edges = normalized.get("edges")

    if not isinstance(nodes, list) or not nodes:
        raise WorkflowValidationError("nodes 必须是非空数组")
    if not isinstance(edges, list):
        raise WorkflowValidationError("edges 必须是数组")

    normalized_nodes: List[Dict[str, Any]] = []
    node_ids = set()
    for raw_node in nodes:
        if not isinstance(raw_node, Mapping):
            raise WorkflowValidationError("node 必须是对象")

        node = deepcopy(dict(raw_node))
        node_id = str(node.get("node_id") or "").strip()
        if not node_id:
            raise WorkflowValidationError("node_id 不能为空")
        if node_id in node_ids:
            raise WorkflowValidationError(f"重复 node_id: {node_id}")
        node_ids.add(node_id)

        kind = str(node.get("kind") or "").strip()
        if kind not in ALLOWED_NODE_KINDS:
            raise WorkflowValidationError(f"节点 {node_id} kind 非法: {kind}")

        node_type = str(node.get("node_type") or f"{kind}.generic").strip()
        node["node_id"] = node_id
        node["kind"] = kind
        node["node_type"] = node_type
        node["name"] = str(node.get("name") or node_id)
        node["enabled"] = bool(node.get("enabled", True))
        node["params"] = _ensure_mapping(node.get("params"), f"node[{node_id}].params")

        retry = _ensure_mapping(node.get("retry_policy"), f"node[{node_id}].retry_policy")
        node["retry_policy"] = {
            "max_retries": max(0, int(retry.get("max_retries", 0))),
            "delay_ms": max(0, int(retry.get("delay_ms", 0))),
        }

        _validate_node_params(node)
        normalized_nodes.append(node)

    normalized_edges: List[Dict[str, Any]] = []
    for raw_edge in edges:
        if not isinstance(raw_edge, Mapping):
            raise WorkflowValidationError("edge 必须是对象")

        edge = deepcopy(dict(raw_edge))
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not source or not target:
            raise WorkflowValidationError("edge.source 与 edge.target 不能为空")
        if source not in node_ids or target not in node_ids:
            raise WorkflowValidationError(f"edge 引用了不存在节点: {source} -> {target}")

        normalized_edges.append(
            {
                "source": source,
                "target": target,
                "condition": str(edge.get("condition") or "always").strip() or "always",
            }
        )

    # DAG 校验
    topological_sort(normalized_nodes, normalized_edges)

    if not any(edge["source"] != edge["target"] for edge in normalized_edges):
        # 允许单节点无边图；若有边且都是自环，在上方 DAG 检查会失败，这里只是补充说明
        pass

    normalized["nodes"] = normalized_nodes
    normalized["edges"] = normalized_edges
    normalized["dag_levels"] = dag_levels(normalized_nodes, normalized_edges)

    return normalized


def get_workflow_schema() -> Dict[str, Any]:
    return deepcopy(WORKFLOW_JSON_SCHEMA)


def get_node_param_rules() -> Dict[str, Dict[str, Any]]:
    return deepcopy(NODE_TYPE_PARAM_RULES)
