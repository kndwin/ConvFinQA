# Simple chat bot

This repository contains:

- [`server/`](server/) — the FastAPI backend, database migrations, and tests.
- [`client/`](client/) — the React conversation explorer.
- [`internal/otel-cli/`](internal/otel-cli/) — a standalone Go CLI for querying
  traces, logs, and metrics in the local Quack OTLP store.

## OTEL CLI

With the local Quack server running, install or build the CLI:

```sh
(cd internal/otel-cli && go install .)
(cd internal/otel-cli && go build -o /tmp/otel-cli .)
```

At a glance: `trace list`, `trace get TRACE_ID`, `log list`,
`log get --trace TRACE_ID [--span SPAN_ID]`, `metric list`, and
`metric get METRIC_NAME`. Start with `otel-cli --help` or add `--help` to any
command for examples and all applicable flags.

```sh
otel-cli trace list --since 1h --limit 20
otel-cli log list -q timeout -a http.method=GET --output json
otel-cli trace get TRACE_ID --attributes
```

`--since` accepts durations such as `15m`, `1h`, and `24h`; repeat `-a
key=value` for AND filters. Output is `table` by default or `json`. OTLP data
is flushed before every query by default; use `--no-flush` to skip it.
Filters select a trace for `trace get` without pruning spans from its tree;
`--limit` applies to row-oriented commands rather than trace trees.
Connection defaults are `quack://127.0.0.1:9494`, token
`dev-quack-token-123456`, and service `openai-deploy-api`. Override them with
`OTEL_CLI_QUACK_URL`, `OTEL_CLI_QUACK_TOKEN`, `OTEL_CLI_QUACK_SERVICE`, or the
matching flags. Trace IDs may be unique prefixes; trace `get` still displays
child spans from other services.

## Database and API

The application uses PostgreSQL. From the repository root, start the database
and apply the Alembic migrations:

```sh
docker compose up -d --wait db
(cd server && uv run alembic upgrade head)
```

Set `DATABASE_URL` to override the local default. Run the API with:

```sh
(cd server && uv run fastapi dev src/main.py)
```

For agentic chat, copy `server/.env.example` to `server/.env` and set
`OPENAI_API_KEY`. The backend uses the OpenAI Agents SDK and streams AG-UI
events to the TanStack AI client; PostgreSQL stores sessions and messages.

Run backend tests with:

```sh
(cd server && uv run python -m unittest discover -s tests)
```

Interactive Scalar API docs are available at <http://127.0.0.1:8000/docs>, and
the OpenAPI schema is at <http://127.0.0.1:8000/openapi.json>.

Stop the database with `docker compose stop db`, or remove it and its volume
with `docker compose down -v`.

## Client

With the API running, start the web app in another terminal:

```sh
cd client
pnpm install
pnpm dev
```

The Vite development server proxies `/api` to the local backend. See
[`client/README.md`](client/README.md) for environment configuration,
OpenAPI type generation, type checking, and production builds.

## ConvFinQA data

Each conversation preserves `doc_json`, `features_json`, and the complete raw
`dialogue_json`. Normalized dialogue turns are indexed by source questions;
nullable companion fields avoid truncating malformed arrays. The source has two
known extra-answer cases (4/5 for `Single_ETR/2016/page_144.pdf-4`, and 2/3 for
`Double_ADBE/2014/page_70.pdf`), which remain in `dialogue_json` rather than
being turned into fabricated turns.
