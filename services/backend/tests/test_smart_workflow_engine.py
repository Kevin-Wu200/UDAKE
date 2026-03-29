"""智能工作流引擎单元测试。"""

from __future__ import annotations

import pytest

from app.workflow.engine import WorkflowEngine
from app.workflow.schema import WorkflowValidationError


def test_validate_dag_cycle_should_fail() -> None:
    engine = WorkflowEngine()
    definition = {
        "name": "cycle-test",
        "nodes": [
            {"node_id": "a", "kind": "input", "node_type": "input.constant", "params": {"value": 1}},
            {"node_id": "b", "kind": "process", "node_type": "process.transform", "params": {"operation": "add", "operand": 1}},
        ],
        "edges": [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ],
    }

    with pytest.raises(WorkflowValidationError):
        engine.validate_definition(definition)


def test_execute_with_retry_and_branch() -> None:
    engine = WorkflowEngine()
    definition = {
        "name": "retry-branch",
        "variables": {},
        "nodes": [
            {
                "node_id": "input_numbers",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": [1, 2, 3, 4, 5]},
            },
            {
                "node_id": "sample",
                "kind": "process",
                "node_type": "process.sample",
                "params": {"step": 2},
            },
            {
                "node_id": "unstable",
                "kind": "process",
                "node_type": "process.fail_then_pass",
                "params": {"fail_until_attempt": 1},
                "retry_policy": {"max_retries": 2, "delay_ms": 0},
            },
            {
                "node_id": "condition",
                "kind": "control",
                "node_type": "control.condition",
                "params": {
                    "left": "{{nodes.unstable.status}}",
                    "operator": "==",
                    "right": "passed",
                },
            },
            {
                "node_id": "true_branch",
                "kind": "process",
                "node_type": "process.transform",
                "params": {
                    "operation": "sum",
                    "source": "{{nodes.sample}}",
                },
            },
            {
                "node_id": "false_branch",
                "kind": "process",
                "node_type": "process.transform",
                "params": {
                    "operation": "sum",
                    "source": "{{nodes.sample}}",
                },
            },
            {
                "node_id": "output",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["true_branch", "false_branch", "condition"]},
            },
        ],
        "edges": [
            {"source": "input_numbers", "target": "sample"},
            {"source": "sample", "target": "unstable"},
            {"source": "unstable", "target": "condition"},
            {"source": "condition", "target": "true_branch", "condition": "true"},
            {"source": "condition", "target": "false_branch", "condition": "false"},
            {"source": "true_branch", "target": "output"},
            {"source": "false_branch", "target": "output"},
        ],
    }

    result = engine.execute(definition)
    assert result["status"] == "completed"
    assert result["node_attempts"]["unstable"] == 2
    assert result["node_statuses"]["true_branch"] == "completed"
    assert result["node_statuses"]["false_branch"] == "skipped"

    output = result["node_outputs"]["output"]
    assert output["condition"] is True
    assert output["true_branch"] == 9
    assert output["false_branch"] is None


def test_execute_loop_and_parallel_nodes() -> None:
    engine = WorkflowEngine()
    definition = {
        "name": "loop-parallel",
        "nodes": [
            {
                "node_id": "input",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": [1, 2, 3]},
            },
            {
                "node_id": "loop",
                "kind": "control",
                "node_type": "control.loop",
                "params": {
                    "iterable": "{{nodes.input}}",
                    "operation": "square",
                },
            },
            {
                "node_id": "parallel",
                "kind": "control",
                "node_type": "control.parallel",
                "params": {
                    "tasks": [
                        {"name": "sum_value", "operation": "sum", "source": "{{nodes.loop}}"},
                        {"name": "max_value", "operation": "max", "source": "{{nodes.loop}}"},
                        {"name": "min_value", "operation": "min", "source": "{{nodes.loop}}"},
                    ]
                },
            },
            {
                "node_id": "output",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["loop", "parallel"]},
            },
        ],
        "edges": [
            {"source": "input", "target": "loop"},
            {"source": "loop", "target": "parallel"},
            {"source": "parallel", "target": "output"},
        ],
    }

    result = engine.execute(definition)
    assert result["status"] == "completed"
    assert result["node_outputs"]["loop"] == [1, 4, 9]

    parallel_output = result["node_outputs"]["parallel"]
    assert parallel_output["sum_value"] == 14
    assert parallel_output["max_value"] == 9
    assert parallel_output["min_value"] == 1
