import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from evals.config_schema import EvaluationConfig
from evals.convfinqa import load_cases_async
from evals.targets import resolve_target


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an evaluation plan without model calls")
    parser.add_argument("benchmark", choices=("convfinqa",))
    parser.add_argument("--dataset-ids")
    parser.add_argument("--dataset-path")
    parser.add_argument("--split")
    parser.add_argument(
        "--targets",
        default="baseline:v1,baseline-tool:v1,program-of-thought:v1",
    )
    parser.add_argument("--application-model", default="gpt-5.6-luna")
    try:
        args = parser.parse_args(argv)
        config = EvaluationConfig(
            dataset_ids=_csv(args.dataset_ids or ""),
            targets=_csv(args.targets),
            application_model=args.application_model,
            dataset_path=args.dataset_path,
            split=args.split,
        )
        targets = tuple(resolve_target(item) for item in config.targets)
        cases = asyncio.run(load_cases_async(config))
        payload = {
            "benchmark": args.benchmark,
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
    except (ValidationError, ValueError, OSError) as exc:
        print(f"Invalid evaluation plan: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
