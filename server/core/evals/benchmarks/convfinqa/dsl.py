"""Audited Decimal AST for program-of-thought:v3."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

OPS = frozenset({"add", "subtract", "multiply", "divide", "greater", "exp"})
CONSTANTS = {
    "const_1": Decimal(1),
    "const_2": Decimal(2),
    "const_3": Decimal(3),
    "const_4": Decimal(4),
    "const_5": Decimal(5),
    "const_7": Decimal(7),
    "const_8": Decimal(8),
    "const_10": Decimal(10),
    "const_6": Decimal(6),
    "const_9": Decimal(9),
    "const_100": Decimal(100),
    "const_1000": Decimal(1000),
    "const_100000": Decimal(100000),
    "const_1000000": Decimal(1000000),
    "const_1000000000": Decimal(1000000000),
}
MAX_DEPTH, MAX_NODES = 12, 64


def execute_ast(
    ast: Any, evidence: dict[str, Decimal], prior: dict[str, Decimal] | None = None
) -> Decimal:
    prior = prior or {}
    count = [0]

    def visit(node: Any, depth: int) -> Decimal:
        count[0] += 1
        if count[0] > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError("AST limit exceeded")
        if not isinstance(node, dict) or set(node) - {"op", "args", "id", "turn"}:
            raise ValueError("invalid AST node")
        op = node.get("op")
        if op == "evidence":
            if set(node) != {"op", "id"} or node["id"] not in evidence:
                raise ValueError("bad evidence reference")
            return Decimal(evidence[node["id"]])
        if op == "prior":
            key = str(node.get("turn"))
            if set(node) != {"op", "turn"} or key not in prior:
                raise ValueError("bad prior reference")
            return Decimal(prior[key])
        if op == "constant":
            if set(node) != {"op", "id"} or node["id"] not in CONSTANTS:
                raise ValueError("constant not allowlisted")
            return CONSTANTS[node["id"]]
        if op not in OPS or not isinstance(node.get("args"), list):
            raise ValueError("invalid operation")
        args = [visit(x, depth + 1) for x in node["args"]]
        if op in {"add", "subtract", "multiply", "divide", "greater"} and len(args) != 2:
            raise ValueError("binary operation requires two args")
        if op == "add":
            return args[0] + args[1]
        if op == "subtract":
            return args[0] - args[1]
        if op == "multiply":
            return args[0] * args[1]
        if op == "divide":
            if args[1] == 0:
                raise ValueError("division by zero")
            return args[0] / args[1]
        if op == "greater":
            return Decimal(1 if args[0] > args[1] else 0)
        if op == "exp":
            if len(args) != 2 or args[1] != int(args[1]) or abs(args[1]) > 100:
                raise ValueError("invalid exponent")
            return args[0] ** int(args[1])
        raise ValueError("unsupported operation")

    try:
        return visit(ast, 0)
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("invalid decimal operation") from exc


def execute_ast_diagnostics(
    ast: Any, evidence: dict[str, Decimal], prior: dict[str, Decimal] | None = None
) -> dict[str, Any]:
    """Execute while retaining auditable operation/reference counters."""
    import json

    operations: list[str] = []
    evidence_ids: list[str] = []
    prior_ids: list[str] = []
    nodes = 0
    depth = 0

    def walk(node: Any, level: int) -> None:
        nonlocal nodes, depth
        nodes += 1
        depth = max(depth, level)
        if isinstance(node, dict):
            op = node.get("op")
            if op in OPS:
                operations.append(str(op))
            if op == "evidence":
                evidence_ids.append(str(node.get("id")))
            if op == "prior":
                prior_ids.append(str(node.get("turn")))
            for child in node.get("args", []):
                walk(child, level + 1)

    walk(ast, 0)
    value = execute_ast(ast, evidence, prior)
    return {
        "ast": json.loads(json.dumps(ast)),
        "operations": operations,
        "depth": depth,
        "nodes": nodes,
        "evidence_ids": evidence_ids,
        "prior_ids": prior_ids,
        "value": format(value, "f"),
    }


__all__ = ["OPS", "CONSTANTS", "MAX_DEPTH", "MAX_NODES", "execute_ast"]
