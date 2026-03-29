"""智能工作流执行引擎。"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Tuple
from uuid import uuid4

from .expression import evaluate_condition, resolve_value, safe_eval_bool
from .schema import WorkflowValidationError, get_node_param_rules, validate_and_normalize_definition

NodeHandler = Callable[[Mapping[str, Any], MutableMapping[str, Any], List[Any], int], Any]


class WorkflowEngine:
    """支持 DAG、分支、循环、并行、重试的执行引擎。"""

    def __init__(self) -> None:
        self._custom_handlers: Dict[str, NodeHandler] = {}
        self._builtin_handlers: Dict[str, NodeHandler] = {
            "input.constant": self._handle_input_constant,
            "input.variable": self._handle_input_variable,
            "input.dataset": self._handle_input_dataset,
            "process.transform": self._handle_process_transform,
            "process.sample": self._handle_process_sample,
            "process.interpolate": self._handle_process_interpolate,
            "process.export": self._handle_process_export,
            "process.fail_then_pass": self._handle_process_fail_then_pass,
            "control.condition": self._handle_control_condition,
            "control.loop": self._handle_control_loop,
            "control.parallel": self._handle_control_parallel,
            "output.collect": self._handle_output_collect,
            "output.variable_write": self._handle_output_variable_write,
        }

    def validate_definition(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return validate_and_normalize_definition(payload)

    def list_node_types(self) -> Dict[str, Any]:
        return {
            "built_in": sorted(self._builtin_handlers.keys()),
            "custom": sorted(self._custom_handlers.keys()),
            "param_rules": get_node_param_rules(),
        }

    def register_custom_handler(self, node_type: str, handler: NodeHandler) -> None:
        if not node_type.startswith("custom."):
            raise ValueError("自定义节点类型必须以 custom. 开头")
        self._custom_handlers[node_type] = handler

    def execute(
        self,
        definition: Mapping[str, Any],
        input_variables: Optional[Mapping[str, Any]] = None,
        trigger: str = "manual",
        debug: bool = False,
    ) -> Dict[str, Any]:
        normalized = self.validate_definition(definition)

        run_id = f"run_{uuid4().hex[:12]}"
        start_time = time.perf_counter()

        run_context: Dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": normalized["workflow_id"],
            "workflow_version": normalized["version"],
            "trigger": trigger,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "duration_ms": None,
            "progress": 0.0,
            "error": None,
            "debug": debug,
            "logs": [],
            "node_statuses": {},
            "node_attempts": {},
            "node_outputs": {},
            "node_timings_ms": {},
            "variables": deepcopy(normalized.get("variables") or {}),
            "dag_levels": deepcopy(normalized.get("dag_levels") or []),
        }

        if input_variables:
            run_context["variables"].update(deepcopy(dict(input_variables)))

        nodes: List[Dict[str, Any]] = deepcopy(normalized["nodes"])
        edges: List[Dict[str, Any]] = deepcopy(normalized["edges"])

        node_map: Dict[str, Dict[str, Any]] = {node["node_id"]: node for node in nodes}
        incoming: Dict[str, List[Dict[str, Any]]] = {node["node_id"]: [] for node in nodes}
        outgoing: Dict[str, List[Dict[str, Any]]] = {node["node_id"]: [] for node in nodes}
        for edge in edges:
            incoming[edge["target"]].append(edge)
            outgoing[edge["source"]].append(edge)

        pending = set(node_map.keys())
        edge_active: Dict[Tuple[str, str], bool] = {}
        fail_fast = bool((normalized.get("metadata") or {}).get("fail_fast", True))

        while pending:
            progressed = False

            for node_id in list(pending):
                predecessors = incoming.get(node_id, [])
                predecessor_ids = [edge["source"] for edge in predecessors]

                # 前驱尚未处理完成
                if any(pred_id in pending for pred_id in predecessor_ids):
                    continue

                active_predecessors: List[str] = []
                for edge in predecessors:
                    source_id = edge["source"]
                    target_id = edge["target"]
                    is_active = edge_active.get((source_id, target_id), True)
                    if is_active:
                        active_predecessors.append(source_id)

                # 被分支剪枝
                if predecessor_ids and not active_predecessors:
                    self._mark_node_skipped(
                        run_context,
                        node_id,
                        "branch_not_selected",
                    )
                    pending.remove(node_id)
                    progressed = True
                    continue

                # 上游失败导致跳过
                if any(run_context["node_statuses"].get(pred_id) == "failed" for pred_id in active_predecessors):
                    self._mark_node_skipped(
                        run_context,
                        node_id,
                        "upstream_failed",
                    )
                    pending.remove(node_id)
                    progressed = True
                    continue

                node = node_map[node_id]
                if not node.get("enabled", True):
                    self._mark_node_skipped(run_context, node_id, "node_disabled")
                    pending.remove(node_id)
                    progressed = True
                    continue

                upstream_values = [run_context["node_outputs"].get(pred_id) for pred_id in active_predecessors]
                upstream_map = {pred_id: run_context["node_outputs"].get(pred_id) for pred_id in active_predecessors}

                try:
                    result = self._execute_single_node(
                        node=node,
                        run_context=run_context,
                        upstream_values=upstream_values,
                        upstream_map=upstream_map,
                    )
                    run_context["node_outputs"][node_id] = result
                    run_context["node_statuses"][node_id] = "completed"

                    # 执行后更新分支边激活状态
                    for edge in outgoing.get(node_id, []):
                        key = (edge["source"], edge["target"])
                        edge_active[key] = self._evaluate_edge_condition(
                            edge_condition=edge.get("condition", "always"),
                            node_output=result,
                            run_context=run_context,
                        )

                except Exception as exc:  # pylint: disable=broad-except
                    run_context["node_statuses"][node_id] = "failed"
                    run_context["error"] = f"节点 {node_id} 执行失败: {exc}"
                    run_context["logs"].append(
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "node_id": node_id,
                            "event": "node_failed",
                            "message": str(exc),
                        }
                    )

                    if fail_fast:
                        for remaining in list(pending):
                            if remaining == node_id:
                                continue
                            self._mark_node_skipped(run_context, remaining, "cancelled_due_to_failure")
                            pending.remove(remaining)
                        pending.remove(node_id)
                        progressed = True
                        break

                pending.remove(node_id)
                progressed = True
                self._refresh_progress(run_context, total_nodes=len(nodes))

            if not progressed:
                unresolved = ", ".join(sorted(pending))
                raise RuntimeError(f"调度器无法推进，剩余节点: {unresolved}")

        if any(status == "failed" for status in run_context["node_statuses"].values()):
            run_context["status"] = "failed"
        else:
            run_context["status"] = "completed"
            run_context["progress"] = 100.0

        end_time = time.perf_counter()
        run_context["ended_at"] = datetime.now(timezone.utc).isoformat()
        run_context["duration_ms"] = round((end_time - start_time) * 1000, 3)
        run_context["summary"] = {
            "completed_nodes": sum(1 for status in run_context["node_statuses"].values() if status == "completed"),
            "failed_nodes": sum(1 for status in run_context["node_statuses"].values() if status == "failed"),
            "skipped_nodes": sum(1 for status in run_context["node_statuses"].values() if status == "skipped"),
        }

        return run_context

    def _execute_single_node(
        self,
        node: Mapping[str, Any],
        run_context: MutableMapping[str, Any],
        upstream_values: List[Any],
        upstream_map: Mapping[str, Any],
    ) -> Any:
        node_id = node["node_id"]
        node_type = node.get("node_type") or ""
        retry_policy = node.get("retry_policy") or {}
        max_retries = int(retry_policy.get("max_retries", 0))
        delay_ms = int(retry_policy.get("delay_ms", 0))

        handler = self._resolve_handler(str(node_type), str(node.get("kind") or ""))

        attempt = 0
        while True:
            attempt += 1
            node_start = time.perf_counter()
            run_context["node_attempts"][node_id] = attempt

            scope = {
                "variables": run_context["variables"],
                "nodes": run_context["node_outputs"],
                "upstream": upstream_map,
                "node": node,
                "run": {
                    "run_id": run_context["run_id"],
                    "workflow_id": run_context["workflow_id"],
                    "trigger": run_context["trigger"],
                },
            }

            try:
                result = handler(node, scope, upstream_values, attempt)
                duration_ms = round((time.perf_counter() - node_start) * 1000, 3)
                run_context["node_timings_ms"][node_id] = duration_ms
                run_context["logs"].append(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "node_id": node_id,
                        "event": "node_completed",
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                    }
                )
                return result

            except Exception as exc:  # pylint: disable=broad-except
                duration_ms = round((time.perf_counter() - node_start) * 1000, 3)
                run_context["node_timings_ms"][node_id] = duration_ms
                run_context["logs"].append(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "node_id": node_id,
                        "event": "node_retry" if attempt <= max_retries else "node_failed",
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "message": str(exc),
                    }
                )

                if attempt > max_retries:
                    raise
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)

    def _resolve_handler(self, node_type: str, node_kind: str) -> NodeHandler:
        if node_type in self._builtin_handlers:
            return self._builtin_handlers[node_type]
        if node_type in self._custom_handlers:
            return self._custom_handlers[node_type]

        # 兜底：按 kind 使用基础行为
        if node_kind == "input":
            return self._handle_input_constant
        if node_kind == "output":
            return self._handle_output_collect

        raise ValueError(f"未找到节点处理器: {node_type}")

    @staticmethod
    def _refresh_progress(run_context: MutableMapping[str, Any], total_nodes: int) -> None:
        finished = sum(
            1
            for status in run_context["node_statuses"].values()
            if status in {"completed", "failed", "skipped"}
        )
        run_context["progress"] = round((finished / total_nodes) * 100.0, 2) if total_nodes > 0 else 100.0

    @staticmethod
    def _mark_node_skipped(run_context: MutableMapping[str, Any], node_id: str, reason: str) -> None:
        run_context["node_statuses"][node_id] = "skipped"
        run_context["logs"].append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "node_id": node_id,
                "event": "node_skipped",
                "reason": reason,
            }
        )

    def _evaluate_edge_condition(self, edge_condition: str, node_output: Any, run_context: Mapping[str, Any]) -> bool:
        condition = (edge_condition or "always").strip().lower()
        if condition in {"always", "*"}:
            return True
        if condition == "true":
            return bool(node_output) is True
        if condition == "false":
            return bool(node_output) is False
        if condition.startswith("equals:"):
            expected = edge_condition.split(":", 1)[1]
            return str(node_output) == expected
        if condition.startswith("not_equals:"):
            expected = edge_condition.split(":", 1)[1]
            return str(node_output) != expected
        if condition.startswith("expr:"):
            expr = edge_condition.split(":", 1)[1].strip()
            scope = {
                "output": node_output,
                "variables": run_context.get("variables", {}),
                "nodes": run_context.get("node_outputs", {}),
            }
            return safe_eval_bool(expr, scope)
        return True

    # ---- 内置节点处理器 ----
    def _handle_input_constant(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (scope, upstream_values, attempt)
        return deepcopy((node.get("params") or {}).get("value"))

    def _handle_input_variable(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (upstream_values, attempt)
        params = node.get("params") or {}
        name = str(params.get("name") or "").strip()
        if not name:
            raise ValueError("input.variable 缺少 name")
        return resolve_value(f"{{{{variables.{name}}}}}", scope)

    def _handle_input_dataset(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (scope, upstream_values, attempt)
        return deepcopy((node.get("params") or {}).get("records") or [])

    def _handle_process_transform(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = attempt
        params = node.get("params") or {}
        operation = str(params.get("operation") or "").lower()

        source = resolve_value(params.get("source"), scope)
        if source is None and upstream_values:
            source = upstream_values[-1]
        if source is None:
            source = params.get("value")

        operand = resolve_value(params.get("operand"), scope)
        if operand is None:
            operand = params.get("factor", 1)

        if operation in {"identity", "passthrough", "copy"}:
            return deepcopy(source)
        if operation == "add":
            return source + operand
        if operation == "subtract":
            return source - operand
        if operation == "multiply":
            return source * operand
        if operation == "divide":
            return source / operand
        if operation == "sum":
            if not isinstance(source, list):
                raise ValueError("sum 操作要求 source 为数组")
            return sum(source)
        if operation == "mean":
            if not isinstance(source, list) or not source:
                raise ValueError("mean 操作要求 source 为非空数组")
            return sum(source) / len(source)
        if operation == "max":
            if not isinstance(source, list) or not source:
                raise ValueError("max 操作要求 source 为非空数组")
            return max(source)
        if operation == "min":
            if not isinstance(source, list) or not source:
                raise ValueError("min 操作要求 source 为非空数组")
            return min(source)
        if operation == "concat":
            if not isinstance(source, list):
                raise ValueError("concat 操作要求 source 为数组")
            return source + [operand]

        raise ValueError(f"不支持的 transform.operation: {operation}")

    def _handle_process_sample(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = attempt
        params = node.get("params") or {}
        source = resolve_value(params.get("source"), scope)
        if source is None and upstream_values:
            source = upstream_values[-1]
        if source is None:
            source = params.get("data")

        if not isinstance(source, list):
            raise ValueError("process.sample 需要数组输入")

        step = max(1, int(params.get("step", 1)))
        offset = max(0, int(params.get("offset", 0)))
        sampled = source[offset::step]

        limit = params.get("limit")
        if limit is not None:
            sampled = sampled[: max(0, int(limit))]

        return sampled

    def _handle_process_interpolate(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = attempt
        params = node.get("params") or {}

        source = resolve_value(params.get("source"), scope)
        if source is None and upstream_values:
            source = upstream_values[-1]
        if source is None:
            source = params.get("data")

        if not isinstance(source, list) or not source:
            raise ValueError("process.interpolate 需要非空数组输入")

        target_count = max(1, int(params.get("target_count", len(source))))
        numeric_source = [float(item) for item in source]
        if target_count == len(numeric_source):
            return numeric_source
        if len(numeric_source) == 1:
            return [numeric_source[0] for _ in range(target_count)]

        result: List[float] = []
        for index in range(target_count):
            ratio = (index / (target_count - 1)) if target_count > 1 else 0.0
            source_pos = ratio * (len(numeric_source) - 1)
            left_index = int(source_pos)
            right_index = min(left_index + 1, len(numeric_source) - 1)
            weight = source_pos - left_index
            value = numeric_source[left_index] * (1 - weight) + numeric_source[right_index] * weight
            result.append(round(value, 6))

        return result

    def _handle_process_export(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = attempt
        params = node.get("params") or {}
        fmt = str(params.get("format") or "json").lower()

        source = resolve_value(params.get("source"), scope)
        if source is None and upstream_values:
            source = upstream_values[-1]

        if fmt == "json":
            content = json.dumps(source, ensure_ascii=False)
        elif fmt == "csv":
            if isinstance(source, list):
                content = "\n".join(str(item) for item in source)
            elif isinstance(source, Mapping):
                header = ",".join(source.keys())
                row = ",".join(str(value) for value in source.values())
                content = f"{header}\n{row}"
            else:
                content = str(source)
        elif fmt == "text":
            content = str(source)
        else:
            raise ValueError(f"不支持导出格式: {fmt}")

        return {
            "format": fmt,
            "content": content,
        }

    def _handle_process_fail_then_pass(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = scope
        params = node.get("params") or {}
        fail_until_attempt = int(params.get("fail_until_attempt", 0))
        if attempt <= fail_until_attempt:
            raise RuntimeError(f"模拟失败 attempt={attempt}")
        return {
            "attempt": attempt,
            "upstream": upstream_values[-1] if upstream_values else None,
            "status": "passed",
        }

    def _handle_control_condition(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (upstream_values, attempt)
        params = node.get("params") or {}
        return evaluate_condition(params, scope)

    def _handle_control_loop(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (upstream_values, attempt)
        params = node.get("params") or {}

        iterable = resolve_value(params.get("iterable"), scope)
        if iterable is None:
            iterable = params.get("iterable")
        if not isinstance(iterable, list):
            raise ValueError("control.loop 需要 iterable 为数组")

        operation = str(params.get("operation") or "identity").lower()
        operand = resolve_value(params.get("operand"), scope)
        if operand is None:
            operand = params.get("factor", 1)

        output: List[Any] = []
        for item in iterable:
            if operation == "identity":
                output.append(item)
            elif operation == "square":
                output.append(item * item)
            elif operation == "multiply":
                output.append(item * operand)
            elif operation == "add":
                output.append(item + operand)
            elif operation == "subtract":
                output.append(item - operand)
            else:
                raise ValueError(f"control.loop 不支持 operation: {operation}")

        aggregate = str(params.get("aggregate") or "").lower()
        if aggregate == "sum":
            return sum(output)
        if aggregate == "max":
            return max(output) if output else None
        if aggregate == "min":
            return min(output) if output else None

        return output

    def _handle_control_parallel(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = attempt
        params = node.get("params") or {}
        tasks = params.get("tasks") or []
        if not isinstance(tasks, list) or not tasks:
            raise ValueError("control.parallel 需要非空 tasks")

        default_source = upstream_values[-1] if upstream_values else None
        lock = threading.Lock()
        result: Dict[str, Any] = {}

        def _run_task(task: Mapping[str, Any]) -> Tuple[str, Any]:
            name = str(task.get("name") or f"task_{uuid4().hex[:6]}")
            operation = str(task.get("operation") or "identity")
            operand = task.get("operand")
            source = resolve_value(task.get("source"), scope)
            if source is None:
                source = task.get("value", default_source)

            temp_node = {
                "node_id": f"parallel::{name}",
                "params": {
                    "operation": operation,
                    "source": source,
                    "operand": operand,
                },
            }
            value = self._handle_process_transform(temp_node, scope, [], 1)
            return name, value

        max_workers = max(1, min(8, len(tasks)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_task, task) for task in tasks]
            for future in as_completed(futures):
                name, value = future.result()
                with lock:
                    result[name] = value

        return result

    def _handle_output_collect(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (upstream_values, attempt)
        params = node.get("params") or {}
        fields = params.get("fields") or []

        if fields:
            output = {field: scope["nodes"].get(field) for field in fields}
        else:
            output = {
                "variables": deepcopy(scope["variables"]),
                "nodes": deepcopy(scope["nodes"]),
            }
        return output

    def _handle_output_variable_write(
        self,
        node: Mapping[str, Any],
        scope: MutableMapping[str, Any],
        upstream_values: List[Any],
        attempt: int,
    ) -> Any:
        _ = (upstream_values, attempt)
        params = node.get("params") or {}
        name = str(params.get("name") or "").strip()
        if not name:
            raise ValueError("output.variable_write 缺少 name")
        value = resolve_value(params.get("from"), scope)
        scope["variables"][name] = value
        return value
