import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from evals.convfinqa import load_cases_async
from evals.models_schema import EvaluationConfig
from evals.targets import resolve_target


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an evaluation plan without model calls")
    parser.add_argument("benchmark", choices=("convfinqa",))
    parser.add_argument("--dataset-ids", default="3139")
    parser.add_argument(
        "--targets",
        default="baseline:v1,baseline-tool:v1,program-of-thought:v1",
    )
    parser.add_argument("--executor", choices=("direct", "remote"), default="direct")
    parser.add_argument("--application-model", default="gpt-5.6-luna")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--keep-sessions", action="store_true")
    try:
        args = parser.parse_args(argv)
        config = EvaluationConfig(
            dataset_ids=tuple(int(item) for item in _csv(args.dataset_ids)),
            targets=_csv(args.targets),
            executor=args.executor,
            application_model=args.application_model,
            base_url=args.base_url,
            keep_sessions=args.keep_sessions,
        )
        targets = tuple(resolve_target(item) for item in config.targets)
        cases = asyncio.run(load_cases_async(config))
        payload = {
            "benchmark": args.benchmark,
            "executor": config.executor,
            "application_model": config.application_model,
            "cases": len(cases),
            "turns": sum(len(case.turns) for case in cases),
            "samples": len(cases) * len(targets),
            "datasets": [
                {"dataset_id": case.dataset_id, "turns": len(case.turns)} for case in cases
            ],
            "targets": [target.metadata(config.application_model) for target in targets],
        }
        print(json.dumps(payload, indent=2))
        return 0
    except (ValidationError, ValueError, OSError, httpx.HTTPError) as exc:
        print(f"Invalid evaluation plan: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
