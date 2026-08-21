# Local infrastructure

This directory contains the Docker Compose stack for local PostgreSQL and
`duckdb-otel` services.

Ports exposed on localhost:

- PostgreSQL: `5433`
- OTLP/HTTP: `4318`
- Quack: `9494`

Run these commands from `infra/local`:

```sh
docker compose up -d --wait
docker compose stop
docker compose down -v
```

The first command starts the services, the second stops them, and the last
resets the stack. **Reset removes Docker volumes and all local database and
telemetry data.**
