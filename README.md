# ConvFinQA Explorer

ConvFinQA Explorer is a local web application for browsing ConvFinQA conversations and running document-grounded chat.

## Project layout

- [`client/`](client/) — browser application; see [`client/browser/README.md`](client/browser/README.md).
- [`server/`](server/) — backend packages; see [`server/core/README.md`](server/core/README.md).
- [`infra/`](infra/) — local services and production deployment definitions.
- [`internal/`](internal/) — internal tools, including the [OTEL CLI](internal/otel-cli/README.md).

## Quick start

Prerequisites include Docker, `uv`, Node.js with pnpm, and (for the OTEL CLI)
Go 1.26 or newer.

Start the local database and telemetry services from the repository root:

```sh
docker compose -f infra/local/compose.yaml up -d --wait
```

In one terminal, configure and run the backend:

```sh
cd server/core
cp .env.example .env
# Set OPENAI_API_KEY in .env before using chat.
uv run alembic upgrade head
uv run fastapi dev src/main.py
```

In another terminal, install and run the frontend:

```sh
cd client/browser
pnpm install
pnpm dev
```

Open the URL printed by Vite. The API is available at
<http://127.0.0.1:8000>; interactive API docs are at
<http://127.0.0.1:8000/docs>.

Stop or reset local services with:

```sh
docker compose -f infra/local/compose.yaml stop
docker compose -f infra/local/compose.yaml down -v  # removes local data
```

For focused development and deployment instructions, start with the linked
README files above. The [local infrastructure guide](infra/local/README.md)
also documents service ports and lifecycle commands.
