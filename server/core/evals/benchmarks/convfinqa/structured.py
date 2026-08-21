"""Strict, deterministic result handling for the opt-in ConvFinQA targets.

This module deliberately has no reference-answer dependency.  It is also used by
the no-model tests, so keeping the document index and arithmetic here (rather than
in a prompt) makes the benchmark's integrity boundary explicit.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal, DecimalException, InvalidOperation
from typing import Any

from src.module.agent_execution.agent_approach.baseline.structured_output import StructuredAnswer
from src.module.agent_execution.agent_approach.evidence.index import (
    index_document as production_index_document,
)

from evals.benchmarks.convfinqa.structured_schema import EvidenceItem

_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
CANONICALIZER_VERSION = "convfinqa-structured:v1"


def _validate_number(answer: StructuredAnswer) -> Decimal:
    if answer.kind != "number" or not _DECIMAL.fullmatch(answer.value):
        raise ValueError("number value must be a decimal string")
    if answer.representation is None or answer.scale is None:
        raise ValueError("numbers require representation and scale")
    try:
        return Decimal(answer.value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc


def canonicalize(
    answer: StructuredAnswer | dict[str, Any],
    question: str = "",
    *,
    source_metadata: dict[str, Any] | None = None,
) -> StructuredAnswer:
    """Validate and canonicalize model output; no gold or distance is consulted."""
    result = (
        answer if isinstance(answer, StructuredAnswer) else StructuredAnswer.model_validate(answer)
    )
    if result.kind != "number":
        return result
    value = _validate_number(result)
    # Model/source metadata can establish that a source value was a percentage;
    # copied values and arbitrary prose cannot.
    if result.representation == "percent":
        value /= Decimal(100)
        representation = "raw"
    else:
        representation = "raw"
    requested = _requested_scale(question)
    source = source_metadata or {}
    # Without an explicit requested unit, preserve the model's declared unit.
    # This avoids inventing a conversion from an unlabeled source.
    scale = requested or source.get("scale") or result.scale
    factors = {
        "ones": Decimal(1),
        "thousand": Decimal(1000),
        "million": Decimal(10**6),
        "billion": Decimal(10**9),
    }
    # The canonical execution space is ones. Display conversion only occurs when
    # the question explicitly requests a unit (or validated source metadata does).
    value *= factors[result.scale] / factors[scale]
    value = value.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
    return StructuredAnswer(
        kind="number", value=format(value, "f"), representation=representation, scale=scale
    )


def canonicalize_gold_execution(value: str) -> StructuredAnswer:
    """Authoritative executed_answers are already in execution space."""
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise ValueError("authoritative executed answer is not decimal")
    decimal = Decimal(value).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
    return StructuredAnswer(
        kind="number", value=format(decimal, "f"), representation="raw", scale="ones"
    )


def _requested_scale(question: str) -> str | None:
    q = question.lower()
    for word in ("billion", "million", "thousand"):
        if word in q:
            return word
    return "ones" if re.search(r"\bin (?:dollars|units|ones)\b", q) else None


def index_document(document: str | dict[str, Any]) -> tuple[EvidenceItem, ...]:
    """Compatibility facade over the production indexer."""
    return tuple(
        EvidenceItem.model_validate(item.model_dump())
        for item in production_index_document(document)
    )


def resolve_evidence(
    ids: list[str] | tuple[str, ...], index: tuple[EvidenceItem, ...]
) -> tuple[EvidenceItem, ...]:
    by_id = {item.id: item for item in index}
    if len(ids) != len(set(ids)) or any(item_id not in by_id for item_id in ids):
        raise ValueError("invalid or duplicate evidence ID")
    return tuple(by_id[item_id] for item_id in ids)


def stage1_request(
    question: str, history: list[dict[str, Any]], index: tuple[EvidenceItem, ...]
) -> str:
    """Build the full-document selection request (the only stage that sees it)."""
    return json.dumps(
        {
            "task": "select evidence IDs only",
            "question": question,
            "history": history,
            "evidence": [item.model_dump(mode="json") for item in index],
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def validate_stage1(
    raw: str | dict[str, Any], index: tuple[EvidenceItem, ...]
) -> tuple[EvidenceItem, ...]:
    payload = json.loads(raw) if isinstance(raw, str) else raw
    if (
        not isinstance(payload, dict)
        or set(payload) != {"evidence_ids"}
        or not isinstance(payload["evidence_ids"], list)
    ):
        raise ValueError("stage one must contain only evidence_ids")
    if any(not isinstance(item, str) for item in payload["evidence_ids"]):
        raise ValueError("evidence IDs must be strings")
    return resolve_evidence(payload["evidence_ids"], index)


def stage2_request(
    question: str, history: list[dict[str, Any]], selected: tuple[EvidenceItem, ...]
) -> str:
    """Build stage two input; importantly it contains no original document."""
    return json.dumps(
        {
            "question": question,
            "history": history,
            "validated_evidence": [item.model_dump(mode="json") for item in selected],
            "output": "strict structured answer JSON only",
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def process_output(
    target: str,
    raw: str,
    question: str,
    *,
    selected: tuple[EvidenceItem, ...] = (),
    prior: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Single target-aware boundary used by execution and scoring."""
    artifact: dict[str, Any] = {
        "target": target,
        "raw_action_stage": raw,
        "canonicalizer_version": CANONICALIZER_VERSION,
    }
    try:
        if target == "program-of-thought:v3":
            from evals.benchmarks.convfinqa.dsl import execute_ast_diagnostics

            factors = {
                "ones": Decimal(1),
                "thousand": Decimal(1000),
                "million": Decimal(10**6),
                "billion": Decimal(10**9),
            }
            evidence = {}
            for item in selected:
                if item.numeric is not None:
                    value = Decimal(item.numeric) * factors.get(item.scale or "ones", Decimal(1))
                    if item.representation == "percent":
                        value /= Decimal(100)
                    evidence[item.id] = value
            diagnostics = execute_ast_diagnostics(json.loads(raw), evidence, prior)
            value = Decimal(diagnostics["value"]).quantize(
                Decimal("0.00001"), rounding=ROUND_HALF_UP
            )
            artifact.update(
                diagnostics=diagnostics,
                canonical=StructuredAnswer(
                    kind="number", value=format(value, "f"), representation="raw", scale="ones"
                ).model_dump(mode="json"),
                valid=True,
            )
        else:
            canonical = canonicalize(StructuredAnswer.model_validate_json(raw), question)
            artifact.update(canonical=canonical.model_dump(mode="json"), valid=True)
    except (ValueError, TypeError, json.JSONDecodeError, DecimalException, KeyError) as exc:
        artifact.update(valid=False, validation_error=str(exc))
    return artifact


def process_evidence_output(target: str, raw: str, question: str, collector) -> dict[str, Any]:
    """Validate native evidence output and retain the complete tool audit."""
    artifact = {
        "target": target,
        "raw_output": raw,
        "tool_version": "evidence-tools:v1",
        "index_version": "evidence-index:v1",
        "tool_calls": [
            x.model_dump() if hasattr(x, "model_dump") else vars(x) for x in collector.tools
        ],
    }
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("final output must be a JSON object")
        result_ref = payload.get("result_ref")
        audit = audit_evidence_tools(collector.tools)
        artifact.update(audit)
        results, fetches = audit["calculator_results"], audit["fetched_evidence"]
        if audit["errors"]:
            raise ValueError("; ".join(audit["errors"]))
        if not fetches:
            raise ValueError("no successful evidence fetch")
        if payload.get("kind") == "number":
            if result_ref not in results:
                raise ValueError("final result_ref does not match calculator result")
            declared = Decimal(payload["value"])
            if payload.get("representation") == "percent":
                declared /= Decimal(100)
            if declared.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP) != Decimal(
                results[result_ref]
            ).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP):
                raise ValueError("final result_ref does not match calculator result")
            authoritative = Decimal(results[result_ref]).quantize(
                Decimal("0.00001"), rounding=ROUND_HALF_UP
            )
            canonical = StructuredAnswer(
                kind="number", value=format(authoritative, "f"), representation="raw", scale="ones"
            )
        else:
            answer = {k: v for k, v in payload.items() if k != "result_ref"}
            canonical = StructuredAnswer.model_validate(answer)
        artifact.update(canonical=canonical.model_dump(mode="json"), valid=True)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, DecimalException) as exc:
        artifact.update(valid=False, validation_error=str(exc))
    return artifact


def audit_evidence_tools(calls) -> dict[str, Any]:
    """Validate ordered calls and reconstruct only server-returned handles."""
    fetched, results, errors, failed_tool_calls, order = [], {}, [], [], []
    fetched_ids: set[str] = set()
    for call in calls:
        args = None
        try:
            args = json.loads(call.arguments if call.arguments is not None else "{}")
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid tool payload: arguments must decode to a JSON object ({exc})")
            continue
        if not isinstance(args, dict):
            errors.append("invalid tool payload: arguments must decode to a JSON object")
            continue
        try:
            value = json.loads(call.result if call.result is not None else "{}")
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid tool payload: {exc}")
            continue
        # The runner serializes exceptions returned by the SDK as JSON strings.
        # They are failed attempts, not successful tool payloads: retain them for
        # auditability, but let a later grounded retry satisfy the policy.
        if isinstance(value, str):
            failed_tool_calls.append({"tool": call.name, "arguments": args, "error": value})
            continue
        if not isinstance(value, dict):
            errors.append("invalid tool payload: result must decode to a JSON object")
            continue
        if call.name == "evidence_fetch":
            items = value.get("results")
            if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
                errors.append("evidence_fetch result.results must be a JSON array of objects")
                continue
            if items:
                fetched.extend(items)
                fetched_ids.update(item["id"] for item in items if isinstance(item.get("id"), str))
            order.append({"tool": call.name, "ids": [x.get("id") for x in items]})
        elif call.name == "grounded_calculator":
            operands = args.get("operands", [])
            if not isinstance(operands, list) or any(not isinstance(x, str) for x in operands):
                errors.append(
                    "grounded_calculator arguments.operands must be a JSON array of strings"
                )
                continue
            handle = value.get("handle")
            if not isinstance(handle, str) or not handle:
                errors.append("grounded_calculator result.handle must be a nonempty string")
                continue
            if "value" not in value or not isinstance(value["value"], (str, int, float)):
                errors.append("grounded_calculator result.value must be a number or string")
                continue
            if not fetched_ids:
                errors.append("calculator before successful fetch")
            from src.module.agent_execution.agent_approach.evidence.tools import CONSTANTS

            if any(
                ref not in fetched_ids and ref not in results and ref not in CONSTANTS
                for ref in operands
            ):
                errors.append("calculator reference was not previously fetched")
            if not handle or handle in results or handle != f"calc:{len(results)}":
                errors.append("invalid or non-sequential calculator handle")
            results[handle] = value.get("value")
            order.append(
                {
                    "tool": call.name,
                    "operands": operands,
                    "handle": handle,
                    "value": value.get("value"),
                }
            )
    provenance_valid = all(
        isinstance(x.get("provenance"), str) and x["provenance"] for x in fetched
    )
    if not provenance_valid:
        errors.append("fetched evidence lacked provenance")
    return {
        "fetched_evidence": fetched,
        "calculator_results": results,
        "failed_tool_calls": failed_tool_calls,
        "ordering_valid": not errors,
        "provenance_valid": provenance_valid,
        "errors": errors,
        "ordered_audit": order,
    }


def staged_inputs(
    document: str | dict[str, Any], question: str, history: list[dict[str, Any]] | None = None
) -> tuple[str, tuple[EvidenceItem, ...]]:
    """No-model injectable seam: returns isolated stage-1 input and index."""
    index = index_document(document)
    return stage1_request(question, history or [], index), index


def run_staged_fake(
    document: str | dict[str, Any],
    question: str,
    selector_output: str,
    action_output: str,
    target: str = "evidence:v1",
) -> dict[str, Any]:
    """Deterministic injectable seam used to test both valid and invalid stages."""
    _, index = staged_inputs(document, question)
    artifact: dict[str, Any] = {
        "raw_evidence_stage": selector_output,
        "raw_action_stage": action_output,
    }
    try:
        selected = validate_stage1(selector_output, index)
        artifact["selected_evidence"] = [item.model_dump(mode="json") for item in selected]
        artifact.update(process_output(target, action_output, question, selected=selected))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        artifact.update(valid=False, validation_error=str(exc))
    return artifact


def run_staged_fake_sequence(
    document: str | dict[str, Any],
    turns: list[tuple[str, str, str]],
    target: str = "program-of-thought:v3",
) -> list[dict[str, Any]]:
    """Run a complete multi-turn staged conversation without a provider."""
    index = index_document(document)
    prior: dict[str, str] = {}
    history: list[dict[str, Any]] = []
    results = []
    for turn, (question, selector_output, action_output) in enumerate(turns, 1):
        artifact: dict[str, Any] = {
            "turn": turn,
            "question": question,
            "history": list(history),
            "raw_evidence_stage": selector_output,
        }
        try:
            selected = validate_stage1(selector_output, index)
            artifact.update(
                process_output(target, action_output, question, selected=selected, prior=prior)
            )
            artifact["selected_evidence"] = [item.model_dump(mode="json") for item in selected]
        except (ValueError, TypeError, json.JSONDecodeError, DecimalException, KeyError) as exc:
            artifact.update(valid=False, validation_error=str(exc))
        results.append(artifact)
        history.append(
            {
                "turn": turn,
                "question": question,
                "result": artifact.get("canonical"),
                "status": "valid" if artifact.get("valid") else "invalid",
            }
        )
        if artifact.get("valid") and artifact.get("canonical", {}).get("kind") == "number":
            prior[str(turn)] = artifact["canonical"]["value"]
    return results


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


__all__ = [
    "StructuredAnswer",
    "EvidenceItem",
    "index_document",
    "resolve_evidence",
    "canonicalize",
    "prompt_hash",
    "process_output",
    "canonicalize_gold_execution",
    "CANONICALIZER_VERSION",
    "run_staged_fake",
    "run_staged_fake_sequence",
]
