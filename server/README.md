
# Server

From this directory, start PostgreSQL and the local OTLP receiver and wait for
their healthchecks:

```bash
docker compose up -d --wait db duckdb-otel
uv run alembic upgrade head
```

Set `OPENAI_API_KEY` in `.env` before starting an agent run.
The `direct-mini` and `calculator-mini` variants always use `gpt-5-mini`; their models are not configurable.
The API can start without a key, but chat runs return a configuration error
until one is provided.

Chat sessions persist their agent variant. The supported variants are `direct-mini`,
which answers directly from document context, and `calculator-mini`, which can use
a local arithmetic calculator for document-grounded calculations. Both use `gpt-5-mini`.

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
