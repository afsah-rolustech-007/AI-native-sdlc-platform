"""Declarative `applies_if` evaluation. YAML cannot store Python callables.

Unknown (`None`) is not False. Security predicates use `any_true_or_unknown`
so Qsec* stay eligible until every related flag is explicitly False.
"""

from __future__ import annotations

from typing import Any

from requirements_engine.context import WorkflowContext
from requirements_engine.exceptions import PredicateError

_BOOL_FLAGS = frozenset(
    {"touches_auth", "touches_pii", "touches_payments", "has_database_changes"}
)
_SCALAR_FIELDS = frozenset(
    {
        "work_type",
        "risk_tier",
        "repo_architecture",
        "affected_modules",
        *_BOOL_FLAGS,
    }
)

_LEAF_KEYS = frozenset(
    {
        "always",
        "all",
        "any",
        "work_type_in",
        "risk_tier_in",
        "any_true_or_unknown",
        "affected_modules_gt",
        "field",
        "eq",
        "neq",
    }
)


def validate_predicate(node: Any, *, path: str = "applies_if") -> None:
    if not isinstance(node, dict) or not node:
        raise PredicateError(f"{path} must be a non-empty mapping")
    unknown = set(node) - _LEAF_KEYS
    if unknown:
        raise PredicateError(f"{path} has unknown keys: {sorted(unknown)}")

    if "always" in node:
        _exactly(node, {"always"}, path)
        if not isinstance(node["always"], bool):
            raise PredicateError(f"{path}.always must be a bool")
        return
    if "all" in node:
        _exactly(node, {"all"}, path)
        _list_of_preds(node["all"], f"{path}.all")
        return
    if "any" in node:
        _exactly(node, {"any"}, path)
        _list_of_preds(node["any"], f"{path}.any")
        return
    if "work_type_in" in node:
        _exactly(node, {"work_type_in"}, path)
        _list_of_str(node["work_type_in"], f"{path}.work_type_in")
        return
    if "risk_tier_in" in node:
        _exactly(node, {"risk_tier_in"}, path)
        _list_of_str(node["risk_tier_in"], f"{path}.risk_tier_in")
        return
    if "any_true_or_unknown" in node:
        _exactly(node, {"any_true_or_unknown"}, path)
        fields = node["any_true_or_unknown"]
        _list_of_str(fields, f"{path}.any_true_or_unknown")
        bad = [name for name in fields if name not in _BOOL_FLAGS]
        if bad:
            raise PredicateError(f"{path}.any_true_or_unknown unknown flags: {bad}")
        return
    if "affected_modules_gt" in node:
        _exactly(node, {"affected_modules_gt"}, path)
        if not isinstance(node["affected_modules_gt"], int):
            raise PredicateError(f"{path}.affected_modules_gt must be an int")
        return
    if "field" in node and ("eq" in node or "neq" in node):
        if "eq" in node and "neq" in node:
            raise PredicateError(f"{path} cannot combine eq and neq")
        extra = set(node) - {"field", "eq", "neq"}
        if extra:
            raise PredicateError(f"{path} has extra keys: {sorted(extra)}")
        if node["field"] not in _SCALAR_FIELDS:
            raise PredicateError(f"{path}.field is not a WorkflowContext field: {node['field']}")
        return
    raise PredicateError(f"{path} is not a recognized predicate: {sorted(node)}")


def evaluate_predicate(node: dict[str, Any], context: WorkflowContext) -> bool:
    validate_predicate(node)
    if "always" in node:
        return bool(node["always"])
    if "all" in node:
        return all(evaluate_predicate(child, context) for child in node["all"])
    if "any" in node:
        return any(evaluate_predicate(child, context) for child in node["any"])
    if "work_type_in" in node:
        if context.work_type is None:
            return False
        return context.work_type.value in node["work_type_in"]
    if "risk_tier_in" in node:
        if context.risk_tier is None:
            return False
        return context.risk_tier.value in node["risk_tier_in"]
    if "any_true_or_unknown" in node:
        values = [getattr(context, name) for name in node["any_true_or_unknown"]]
        return any(value is True or value is None for value in values)
    if "affected_modules_gt" in node:
        if context.affected_modules is None:
            return False
        return context.affected_modules > node["affected_modules_gt"]
    actual = _field_value(context, node["field"])
    if actual is None:
        return False
    if "eq" in node:
        return actual == node["eq"]
    return actual != node["neq"]


def _field_value(context: WorkflowContext, field: str) -> Any:
    raw = getattr(context, field)
    if field in {"work_type", "risk_tier"} and raw is not None:
        return raw.value
    return raw


def _exactly(node: dict[str, Any], allowed: set[str], path: str) -> None:
    if set(node) != allowed:
        raise PredicateError(f"{path} must contain only {sorted(allowed)}")


def _list_of_preds(value: Any, path: str) -> None:
    if not isinstance(value, list) or not value:
        raise PredicateError(f"{path} must be a non-empty list")
    for index, child in enumerate(value):
        validate_predicate(child, path=f"{path}[{index}]")


def _list_of_str(value: Any, path: str) -> None:
    if not isinstance(value, list) or not value:
        raise PredicateError(f"{path} must be a non-empty list of strings")
    if not all(isinstance(item, str) for item in value):
        raise PredicateError(f"{path} must be a non-empty list of strings")
