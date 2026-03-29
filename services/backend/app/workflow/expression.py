"""工作流表达式与条件计算。"""

from __future__ import annotations

import ast
import operator
from typing import Any, Dict, Mapping


_COMPARE_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "contains": lambda left, right: right in left,
    "not_contains": lambda left, right: right not in left,
    "in": lambda left, right: left in right,
    "not_in": lambda left, right: left not in right,
}


def _resolve_path(scope: Mapping[str, Any], path: str) -> Any:
    current: Any = scope
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
            continue

        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue

        return None

    return current


def resolve_value(value: Any, scope: Mapping[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
        path = value[2:-2].strip()
        return _resolve_path(scope, path)
    return value


class _SafeExpressionEvaluator(ast.NodeVisitor):
    """仅支持极小子集表达式，避免执行任意代码。"""

    def __init__(self, scope: Mapping[str, Any]):
        self.scope = scope

    def visit_Expression(self, node: ast.Expression) -> Any:  # noqa: N802
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: N802
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:  # noqa: N802
        return self.scope.get(node.id)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:  # noqa: N802
        values = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("unsupported boolean operator")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:  # noqa: N802
        value = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> Any:  # noqa: N802
        left = self.visit(node.left)
        right = self.visit(node.right)

        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right

        raise ValueError("unsupported binary operator")

    def visit_Compare(self, node: ast.Compare) -> Any:  # noqa: N802
        left = self.visit(node.left)
        for comparator, op in zip(node.comparators, node.ops):
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.In):
                ok = left in right
            elif isinstance(op, ast.NotIn):
                ok = left not in right
            else:
                raise ValueError("unsupported compare operator")

            if not ok:
                return False
            left = right

        return True

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"unsupported expression node: {node.__class__.__name__}")


def safe_eval_bool(expression: str, scope: Mapping[str, Any]) -> bool:
    parsed = ast.parse(expression, mode="eval")
    evaluator = _SafeExpressionEvaluator(scope)
    return bool(evaluator.visit(parsed))


def evaluate_condition(params: Mapping[str, Any], scope: Mapping[str, Any]) -> bool:
    expression = params.get("expression")
    if isinstance(expression, str) and expression.strip():
        return safe_eval_bool(expression.strip(), scope)

    left = resolve_value(params.get("left"), scope)
    operator_key = str(params.get("operator") or "==")
    right = resolve_value(params.get("right"), scope)

    if operator_key not in _COMPARE_OPERATORS:
        raise ValueError(f"unsupported operator: {operator_key}")

    return bool(_COMPARE_OPERATORS[operator_key](left, right))
