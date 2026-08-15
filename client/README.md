# DatasetConversation explorer

## Prerequisites

- Node.js 20 or newer
- pnpm 10 (`corepack enable` can activate the version in `package.json`)
- The backend running locally (see [`../server/README.md`](../server/README.md))

## Environment

Copy `.env.example` to `.env` and adjust values as needed:

```bash
cp .env.example .env
```

`VITE_API_BASE_URL` defaults to `/api`. `VITE_OPENAPI_URL` defaults to
`http://127.0.0.1:8000/openapi.json` for schema generation.

The dataset detail screen uses TanStack AI to stream agent responses from the
configured API base URL. Chat sessions and transcripts are persisted by the
backend; browser storage is not used for history.

The client is organized into feature modules under `src/module` and platform
services under `src/platform`. Routing is configured virtually in
`src/platform/router/routes.ts`;
the generated OpenAPI schema lives at `src/platform/api/openapi-schema.ts`.

## Development and verification

Run these commands from `client/`:

```bash
pnpm install
pnpm dev
pnpm typecheck
pnpm build
pnpm check
```

`pnpm check` runs typechecking, Oxlint, Oxfmt verification, and the production
build. Custom module-boundary lint diagnostics point to `lint/module.ui.md` or
`lint/module.route.md`; read the referenced guide before changing a boundary.

## API schema generation

With the API running, regenerate the checked-in TypeScript schema:

```bash
pnpm generate:api
```

The script uses POSIX shell parameter expansion for its URL fallback. Set
`VITE_OPENAPI_URL` explicitly when using a non-POSIX shell or remote API.
