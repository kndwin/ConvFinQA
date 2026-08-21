# otel-cli

`otel-cli` queries traces, logs, and metrics from the local `duckdb-otel`
service. Use Go 1.26 or newer. From the repository root, start the local
service before querying:

```sh
cd ../../infra/local
docker compose up -d --wait duckdb-otel
```

Then, from the repository root, install and test the CLI:

```sh
cd internal/otel-cli
go install .
go test ./...
```

Representative queries:

```sh
otel-cli trace list --since 1h --limit 20
otel-cli trace get TRACE_ID
otel-cli log list --output json
```

Run `otel-cli --help` or append `--help` to a command for advanced flags and
additional examples.
