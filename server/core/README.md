
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

Direct chat runs stream over the existing AG-UI SSE endpoint.

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

Settings load from environment variables and `.env` when commands run from
this directory. Override the local default PostgreSQL URL with `DATABASE_URL` (it
must use the `postgresql+asyncpg://` scheme). Run tests with:

```bash
uv run pytest src
```

## Code quality

Run these commands from `server/core/`; tools are development dependencies managed by
uv:

```bash
uv run ruff format .       # format Python files
uv run ruff format --check .
uv run ruff check .        # lint and import sorting
uv run ty check            # static type checking
uv run lint-imports        # enforce the contracts in pyproject.toml
```

## ConvFinQA evaluation

See [`evals/README.md`](evals/README.md) for the evaluation workflow. The canonical
30-sample run from `server/core/` is:

```bash
uv run --group eval inspect eval evals/benchmarks/convfinqa/task.py --limit 30 --log-dir evals/.report
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
# Server core

Core application package. Benchmark prompts, scoring, and rerun instructions
are documented in [evals/README.md](evals/README.md).
