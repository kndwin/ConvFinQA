
# Server

From this directory, start PostgreSQL and the local OTLP receiver and wait for
their healthchecks:

```bash
docker compose up -d --wait db duckdb-otel
uv run alembic upgrade head
```

Set `OPENAI_API_KEY` in `.env` before starting an agent run.
The `baseline`, `baseline-tool`, and `program-of-thought` approaches support all four selectable
OpenAI models.
The API can start without a key, but chat runs return a configuration error
until one is provided.

## Durable Temporal agent proof

Temporal is opt-in and does not change the existing chat or evaluation paths.
Start the local server and its UI with:

```bash
docker compose up -d --wait temporal
uv run python -m src.temporal_worker
```

The production-provider Worker requires the normal `OPENAI_API_KEY` setting,
but starting it does not itself invoke a model. The UI is available at
http://127.0.0.1:8233. The no-paid-call proof uses a
fake model and requires neither `OPENAI_API_KEY` nor OpenAI network access
(Temporal may download its test-server binary the first time it runs):

```bash
uv run python -m unittest tests.test_temporal_durable_agent
```

The Temporal SQLite history is stored in the `temporal-data` volume. `docker
compose down -v` removes local Temporal history (as well as other compose
volumes).

### Ensemble demo

Create a chat session with `agent_approach: "ensemble"` to run the selected
two or three direct approaches concurrently as Temporal child Workflows and
then ask a no-tool reviewer for the canonical answer. Enable the API path and
start the separate Worker before running the demo:

```bash
TEMPORAL_ENABLED=true uv run fastapi dev src/main.py
uv run alembic upgrade head
uv run python -m src.temporal_worker
```

The chat API multiplexes candidate and reviewer model events over one AG-UI
SSE response. Candidate output is diagnostic; only the reviewer answer is
persisted as an assistant message. Run status, result, event reattachment, and
cancellation are available below the chat session's `/runs/{run_id}` path.

Chat sessions persist their agent approach, pinned prompt, context, and model. The
supported approaches are `baseline`, which answers directly from document context,
and `baseline-tool`, which must use a local arithmetic calculator, or
`program-of-thought`, which must use OpenAI hosted Code Interpreter, for
document-grounded calculations.

All approaches run through one shared agent-execution service and select one of three
vertical slices. Calculator tool-call UI events are streamed live but are not
persisted or replayed after reload.

Each vertical slice owns its execution, Markdown prompts, and context selection:

```text
agent_execution/
├── agent_execution_service.py
├── agent_execution_runner.py
├── agent_execution_repository.py
├── repositories/{callbacks.py,in_memory.py}
└── agent_approach/
    ├── baseline/{run.py,prompts/,context/}
    ├── baseline_tool/{run.py,prompts/,context/,tools/}
    ├── program_of_thought/{run.py,prompts/,context/}
    └── shared/
        ├── agents.py
        ├── context/{document_conversation.py,registry.py}
        └── tools/code_execution/{provider.py,openai_provider.py}
```

The current prompt IDs are `baseline:v1`, `baseline-tool:v1`, and
`program-of-thought:v1`. All slices
currently select the shared `document-conversation:v1` context renderer. A session
pins these immutable IDs when it is created, so later default changes do not alter
an existing conversation.

Copy `.env.example` to `.env`; its local OTLP settings enable OTLP/HTTP export:

```bash
uv run fastapi dev src/main.py
```

Settings in `.env` are bridged to the standard OpenTelemetry variables before
Logfire starts; process environment values still take precedence. If
`LOGFIRE_TOKEN` is also set, it continues exporting to remote Logfire as well.

Exercise the API (and generate a span) from another terminal:

```bash
curl -sS 'http://127.0.0.1:8000/dataset-conversations?limit=1'
```

After making a request, flush accepted rows and query the running DuckDB
process from a host DuckDB CLI using its Quack extension:

```bash
duckdb <<'SQL'
INSTALL quack;
LOAD quack;
FROM quack_query(
    'quack:localhost:9494',
    'SELECT * FROM otlp_flush(''otlp:0.0.0.0:4318'')',
    token := 'dev-quack-token-123456'
);
FROM quack_query(
    'quack:localhost:9494',
    $$
    SELECT service_name, name
    FROM lake.main.otlp_traces
    WHERE service_name = 'openai-deploy-api'
    ORDER BY start_time_unix_nano DESC
    LIMIT 20
    $$,
    token := 'dev-quack-token-123456'
);
SQL
```

DuckDB receives and stores application spans; it does not emit spans about its
own SQL execution.

Settings load from environment variables and `server/.env` when commands run from
this directory. Override the local default PostgreSQL URL with `DATABASE_URL` (it
must use the `postgresql+asyncpg://` scheme). Run tests with:

```bash
uv run python -m unittest discover -s tests -p 'test*.py'
```

## Code quality

Run these commands from `server/`; tools are development dependencies managed by
uv:

```bash
uv run ruff format .       # format Python files
uv run ruff format --check .
uv run ruff check .        # lint and import sorting
uv run ty check            # static type checking
uv run lint-imports        # enforce the contracts in pyproject.toml
```

## ConvFinQA evaluation

Inspect AI is the runner and viewer. The default task uses dataset `3139`, all three
registered targets, and application model `gpt-5.6-luna`; live runs incur model usage.
Validate the matrix without any model call first:

```bash
uv run --group eval python -m evals.plan convfinqa
```

Run one evaluation from `server/` (Inspect task arguments use `-T name=value`):

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py \
  --log-dir evals/.report --max-samples 1 -T dataset_ids=3139 \
  -T targets=baseline:v1,baseline-tool:v1,program-of-thought:v1 \
  -T executor=direct -T application_model=gpt-5.6-luna
```

Use `-T executor=remote -T base_url=http://127.0.0.1:8000` to exercise the
running HTTP application instead; `-T keep_sessions=true` retains its temporary
sessions. `--max-samples 1` keeps application-backed samples sequential and avoids
an accidental burst of paid calls; increase it deliberately when desired.
The planner accepts the same dataset, target, executor, model, base URL, and
session options and performs no model calls. Live evaluations are paid model
calls; the planner and unit tests are not.

Inspect logs are canonical and are written under `evals/.report/`. View a completed
log locally with `uv run --group eval inspect view --log-dir evals/.report`.
The deterministic evaluation records separate `numeric_accuracy` and
 `contains_accuracy` scores. Numeric is a candidate-based scorer with a 1%
 relative tolerance (relative to the golden magnitude), normalizing percentages
 before comparison; `contains_accuracy` is literal, case-sensitive substring
 matching. Both can pass intermediate mentions, although an explicit `Final
 answer`/`Answer is` candidate takes priority for numeric scoring. Both scores
 record turn accuracy, fully-correct conversations,
latency, target metadata, and tool-call payloads. Execution errors
are recorded by Inspect as failed samples. Tool payloads may contain benchmark or
application data, so review logs before sharing them.
Application-owned model calls are bridged into each Inspect sample's native model
usage bookkeeping, using the model and token usage reported by the Agents SDK (no
Inspect provider call is made). Remote runs receive the same data through the
AG-UI custom usage event; an older server that does not emit that event leaves
remote usage unavailable rather than reporting zeros.

To rescore an existing log offline (without a model call), use source-qualified
scorer references. The first command writes fresh scores to a new file; the second
adds the other scorer:

```bash
uv run --group eval inspect score evals/.report/<log>.eval \
  --scorer evals/benchmarks/convfinqa/task.py@numeric_accuracy \
  --action overwrite --output-file /tmp/convfinqa-rescored.eval --overwrite --display none
uv run --group eval inspect score /tmp/convfinqa-rescored.eval \
  --scorer evals/benchmarks/convfinqa/task.py@contains_accuracy \
  --action append --output-file /tmp/convfinqa-rescored.eval --overwrite --display none
```

The architectural contracts are also documented in `lint/`. Controllers call
services, services call repositories, and schemas remain transport/data types.
Modules can depend on platform adapters, while platform infrastructure must not
depend on modules (the `dependency_injection` composition root is the documented
exception). Database migration scripts are reviewed separately and are excluded
from Ruff's application lint baseline.

Observability is provided by Logfire. Each request produces a SERVER/root span;
application service and repository methods produce INTERNAL spans, and SQLAlchemy
operations produce nested CLIENT/database spans. Set `LOGFIRE_TOKEN` to send
telemetry remotely, and optionally set `LOGFIRE_ENVIRONMENT` (default:
`development`). Without a token, telemetry remains local and no data is sent to
Logfire.

Stop the local services with:

```bash
docker compose stop db duckdb-otel
```

Remove the database and its volume with:

```bash
docker compose down -v
```

Interactive Scalar API docs are available at http://127.0.0.1:8000/docs, and
the OpenAPI schema is at http://127.0.0.1:8000/openapi.json.
