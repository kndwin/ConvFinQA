# ConvFinQA evaluations

Run commands from `server/core/`; Inspect loads this source task directly.
V2 adds benchmark-faithful executable-answer prompts without changing v1
defaults. The v2 target IDs are `baseline:v2`, `baseline-tool:v2`, and
`program-of-thought:v2`.

The opt-in structured cohort adds `baseline:v3` (one strict JSON call),
`evidence:v1` (a first-class agent with evidence-fetch and grounded-calculator
tools), and `program-of-thought:v3` (a hard evidence-selection stage followed by
an audited Decimal JSON AST; no hosted Code Interpreter). The evidence agent's
model context excludes the raw document: values enter only through validated
tool results, and numeric answers must reference a calculator result. Invalid
JSON, tool ordering/provenance, IDs, or ASTs score incorrect and do not fall back
to prose. Program-of-thought v3 uses two model stages per turn; evidence v1 may
use multiple model requests while completing its required tool loop.

Canonical structured run (paid; use `--max-samples` conservatively):
```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py \
  --task-config evals/configs/convfinqa-2026-08-20-30-structured.yaml \
  --max-samples 4 --no-fail-on-error --continue-on-fail --log-dir evals/.report
```

## Exact v2 cohort

This is the exact 30-record, three-target cohort (90 paid samples). Known
upstream annotation defects, including AMAT, remain intentionally unchanged:

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py \
  --task-config evals/configs/convfinqa-2026-08-20-30-v2.yaml \
  --max-samples 4 --no-fail-on-error --continue-on-fail \
  --log-dir evals/.report
```

The task config is an Inspect task-argument file; the task remains positional.
`--max-samples 4` limits concurrent conversations (not the number evaluated),
and the error flags let the other records finish if one provider run fails.
For one record, quote the long target override safely:

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py \
  -T 'dataset_ids=Double_AMAT/2013/page_18.pdf' \
  -T 'targets=baseline:v2,baseline-tool:v2,program-of-thought:v2' \
  --log-dir evals/.report
```

For a fair v1/v2 comparison on selected records (six targets; paid):

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py \
  -T 'dataset_ids=Double_AMAT/2013/page_18.pdf' \
  -T 'targets=baseline:v1,baseline-tool:v1,program-of-thought:v1,baseline:v2,baseline-tool:v2,program-of-thought:v2' \
  --log-dir evals/.report
```

## Other runs and checks

Normal runs and fair record-limited comparisons:

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py --limit 30 --log-dir evals/.report
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py -T record_limit=30 --log-dir evals/.report
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py -T 'targets=baseline:v1' --limit 30 --log-dir evals/.report
```

`record_limit` applies before records are expanded across targets; do not use
`--limit 90` as the fair-comparison mechanism. View logs and run no-model
checks with:

```bash
uv run --group eval inspect view --log-dir evals/.report
uv run --group eval python -m evals.plan convfinqa --dataset-path "$(pwd)/evals/data/convfinqa_dataset.json" --split dev
PYTHONPATH=. uv run --group eval python -m unittest discover -s evals -p 'test*.py'
```

The primary `turn_execution_accuracy` scorer uses authoritative ConvFinQA
`executed_answers` when present, with `conv_answers` as fallback. It compares
numeric answers in execution space with `abs_error <= max(1e-5, abs(gold)*1e-4)`
(0.01%), handles percentages/ requested units, and normalizes boolean and text
answers deterministically. `conversation_exact_accuracy` is 1 only when every
turn is correct, while `parse_failure_rate` counts turns with no usable answer.
Per-conversation turn scores are macro means (Inspect does not robustly aggregate
the metadata counters into a micro metric). `numeric_accuracy` retains the old
1% tolerance for comparability, and `contains_accuracy` remains only a weak,
legacy literal-formatting diagnostic. An explicit `Final answer:` candidate has
exclusive priority; otherwise the final suitable result is selected without
comparing candidates to gold.

Live evaluations are paid model runs and require `OPENAI_API_KEY`. Planner,
configuration construction, tests, and static checks make no model calls.

References: [ConvFinQA paper](https://aclanthology.org/2022.emnlp-main.421/), [official
repository](https://github.com/czyssrs/ConvFinQA), and [Inspect task
configuration docs](https://inspect.aisi.org.uk/configuration.html).
