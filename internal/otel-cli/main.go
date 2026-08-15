package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"sort"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/alecthomas/kong"
	_ "github.com/zzir/quackdriver"
)

type Options struct {
	Service    string        `name:"service" env:"OTEL_CLI_QUACK_SERVICE" default:"openai-deploy-api" help:"Only include data from this service (empty disables the filter)."`
	Since      time.Duration `name:"since" help:"Only include data newer than this duration, for example 15m, 1h, or 24h."`
	Limit      int           `name:"limit" default:"50" help:"Maximum rows to return (1-10000); trace get always returns the complete tree."`
	Output     string        `name:"output" default:"table" enum:"table,json" help:"Output format: table is human-readable; json is machine-readable."`
	NoFlush    bool          `name:"no-flush" help:"Do not flush pending OTLP data before querying (flush happens by default)."`
	URL        string        `name:"url" env:"OTEL_CLI_QUACK_URL" default:"quack://127.0.0.1:9494" help:"Quack connection URL."`
	Token      string        `name:"token" env:"OTEL_CLI_QUACK_TOKEN" default:"dev-quack-token-123456" help:"Quack authentication token."`
	Query      string        `short:"q" help:"Case-insensitive text search across the signal's useful fields (not only the body)."`
	Attributes []string      `name:"attribute" short:"a" help:"Filter by an attribute key=value; repeat -a for multiple AND filters."`
}
type CLI struct {
	Options
	Trace  TraceCmd  `cmd:"" help:"Inspect distributed traces."`
	Log    LogCmd    `cmd:"" help:"Inspect application logs."`
	Metric MetricCmd `cmd:"" help:"Inspect OpenTelemetry metrics."`
}
type TraceCmd struct {
	List TraceList `cmd:"" help:"List root spans and their trace summaries."`
	Get  TraceGet  `cmd:"" help:"Show all spans in one trace as a tree."`
}
type TraceList struct{}
type TraceGet struct {
	ID               string `arg:"" help:"Trace ID or unique prefix (prefixes are convenient for copied IDs)."`
	RenderAttributes bool   `name:"attributes" help:"Include resource and span attributes in the trace tree."`
}
type LogCmd struct {
	List LogList `cmd:"" help:"List recent log records."`
	Get  LogGet  `cmd:"" help:"Get logs for a trace, optionally narrowed to one span."`
}
type LogList struct{}
type LogGet struct {
	Trace string `name:"trace" required:"" help:"Trace ID selector; required because logs are commonly correlated through traces."`
	Span  string `name:"span" help:"Optional span ID selector within the trace."`
}
type MetricCmd struct {
	List MetricList `cmd:"" help:"List recent metric samples."`
	Get  MetricGet  `cmd:"" help:"Get samples for one metric name."`
}
type MetricList struct{}
type MetricGet struct {
	Name string `arg:"" help:"Metric name (as emitted by the instrument)."`
}

func (CLI) Help() string {
	return `Examples:
  otel-cli trace list --since 1h --limit 20
  otel-cli trace get 4bf92f36 --attributes
  otel-cli log list -q timeout -a http.method=GET --output json
  otel-cli metric get http.server.request.duration

Filters apply to list results and select get results. -q searches signal
text/name fields; repeat -a key=value to require multiple attributes. Trace
get still displays the complete matching tree. Data is flushed before each
query unless --no-flush is set.`
}
func (TraceList) Help() string {
	return "Examples:\n  otel-cli trace list --since 15m\n  otel-cli trace list -q checkout -a deployment.environment=prod"
}
func (TraceGet) Help() string {
	return "Examples:\n  otel-cli trace get 4bf92f36\n  otel-cli trace get 4bf92f36 --attributes\n\nA trace ID prefix is accepted when it identifies exactly one trace. Global filters select the trace without removing spans from the displayed tree."
}
func (LogList) Help() string {
	return "Examples:\n  otel-cli log list --since 30m\n  otel-cli log list -q error --output json"
}
func (LogGet) Help() string {
	return "Examples:\n  otel-cli log get --trace 4bf92f36\n  otel-cli log get --trace 4bf92f36 --span 00f067aa\n\nTrace is required to make log correlation explicit; use --span to narrow it further."
}
func (MetricList) Help() string {
	return "Examples:\n  otel-cli metric list --since 1h\n  otel-cli metric list -q request --output json"
}
func (MetricGet) Help() string {
	return "Examples:\n  otel-cli metric get http.server.request.duration\n  otel-cli metric get queue.depth --since 24h"
}

type app struct {
	db queryer
	o  *Options
}

// queryer is deliberately small so command and SQL builder tests need no live server.
type queryer interface {
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
}

func main() {
	var cli CLI
	ctx := kong.Parse(&cli, kong.Name("otel-cli"), kong.Description("Inspect OpenTelemetry data in Quack."), kong.ShortUsageOnError())
	if err := validateOptions(cli.Options); err != nil {
		ctx.Fatalf("%v", err)
	}
	dsn, err := dsnWithToken(cli.URL, cli.Token)
	if err != nil {
		ctx.Fatalf("connect: %v", err)
	}
	db, err := sql.Open("quack", dsn)
	if err != nil {
		ctx.Fatalf("connect: %v", err)
	}
	defer db.Close()
	x := &app{db: db, o: &cli.Options}
	var err2 error
	switch ctx.Command() {
	case "trace list":
		err2 = x.traceList()
	case "trace get", "trace get <id>":
		err2 = x.traceGet(cli.Trace.Get)
	case "log list":
		err2 = x.logList()
	case "log get", "log get --trace=STRING":
		err2 = x.logGet(cli.Log.Get)
	case "metric list":
		err2 = x.metricList()
	case "metric get", "metric get <name>":
		err2 = x.metricGet(cli.Metric.Get)
	default:
		// Kong may include positional/required flag notation in Command().
		switch {
		case strings.HasPrefix(ctx.Command(), "trace get"):
			err2 = x.traceGet(cli.Trace.Get)
		case strings.HasPrefix(ctx.Command(), "log get"):
			err2 = x.logGet(cli.Log.Get)
		case strings.HasPrefix(ctx.Command(), "metric get"):
			err2 = x.metricGet(cli.Metric.Get)
		default:
			err2 = x.dispatchFallback(&cli)
		}
	}
	if err2 != nil {
		ctx.Fatalf("%v", err2)
	}
}

func validateOptions(o Options) error {
	if o.Limit < 1 || o.Limit > 10000 {
		return errors.New("--limit must be between 1 and 10000")
	}
	if o.Since < 0 {
		return errors.New("--since must not be negative")
	}
	for _, a := range o.Attributes {
		if !strings.Contains(a, "=") || strings.SplitN(a, "=", 2)[0] == "" {
			return fmt.Errorf("invalid attribute %q (want key=value)", a)
		}
	}
	return nil
}

// Kong's zero-valued command structs need explicit dispatch for list commands.
func (a *app) dispatchFallback(c *CLI) error {
	return errors.New("choose trace, log, or metric and a subcommand")
}

func (a *app) query(sqltext string, args ...any) ([]map[string]any, error) {
	return a.queryNamed("query", sqltext, args...)
}
func (a *app) queryNamed(command, sqltext string, args ...any) ([]map[string]any, error) {
	ctx := context.Background()
	if !a.o.NoFlush {
		flush, err := a.db.QueryContext(ctx, "SELECT * FROM otlp_flush('otlp:0.0.0.0:4318')")
		if err != nil {
			return nil, fmt.Errorf("flush: %w", err)
		}
		if err := flush.Close(); err != nil {
			return nil, fmt.Errorf("flush: %w", err)
		}
		if err := flush.Err(); err != nil {
			return nil, fmt.Errorf("flush: %w", err)
		}
	}
	rows, err := a.db.QueryContext(ctx, sqltext, args...)
	if err != nil {
		return nil, fmt.Errorf("%s query failed: %w", command, err)
	}
	defer rows.Close()
	names, _ := rows.Columns()
	out := []map[string]any{}
	for rows.Next() {
		vals := make([]any, len(names))
		ptr := make([]any, len(names))
		for i := range vals {
			ptr[i] = &vals[i]
		}
		if err := rows.Scan(ptr...); err != nil {
			return nil, fmt.Errorf("%s scan failed: %w", command, err)
		}
		m := map[string]any{}
		for i, n := range names {
			v := vals[i]
			if b, ok := v.([]byte); ok {
				v = string(b)
			}
			m[n] = v
		}
		out = append(out, m)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("%s query rows: %w", command, err)
	}
	return out, nil
}
func dsnWithToken(raw, token string) (string, error) {
	u, err := url.Parse(raw)
	if err != nil {
		return "", err
	}
	q := u.Query()
	q.Set("token", token)
	u.RawQuery = q.Encode()
	return u.String(), nil
}

// filters builds signal-specific predicates. Attribute keys and values are always parameters.
func (a *app) filters(alias, col, attrs string) (string, []any) {
	return a.filtersFor(alias, col, attrs, alias+"body", alias+"event_name", alias+"severity_text")
}
func (a *app) filtersFor(alias, col, attrs string, search ...string) (string, []any) {
	var w []string
	var args []any
	if a.o.Service != "" {
		w = append(w, alias+"service_name = ?")
		args = append(args, a.o.Service)
	}
	if a.o.Since > 0 {
		w = append(w, alias+col+" >= ?")
		args = append(args, time.Now().Add(-a.o.Since))
	}
	if a.o.Query != "" {
		parts := make([]string, len(search))
		for i, s := range search {
			parts[i] = "lower(CAST(" + s + " AS VARCHAR)) LIKE ?"
		}
		w = append(w, "("+strings.Join(parts, " OR ")+")")
		for range search {
			args = append(args, "%"+strings.ToLower(a.o.Query)+"%")
		}
	}
	for _, x := range a.o.Attributes {
		p := strings.SplitN(x, "=", 2)
		pred := "(EXISTS (SELECT 1 FROM json_each(CAST(" + alias + "resource_attributes AS JSON)) j WHERE j.key = ? AND (json_extract_string(j.value, '$') = ? OR CAST(j.value AS VARCHAR) = ?)) OR EXISTS (SELECT 1 FROM json_each(CAST(" + alias + attrs + " AS JSON)) j2 WHERE j2.key = ? AND (json_extract_string(j2.value, '$') = ? OR CAST(j2.value AS VARCHAR) = ?)))"
		w = append(w, pred)
		args = append(args, p[0], p[1], p[1], p[0], p[1], p[1])
	}
	if len(w) == 0 {
		return "", args
	}
	return " WHERE " + strings.Join(w, " AND "), args
}
func attrPredicate(alias, attrs string, list []string) (string, []any) {
	var p []string
	var args []any
	for _, x := range list {
		k := strings.SplitN(x, "=", 2)
		p = append(p, "(EXISTS (SELECT 1 FROM json_each(CAST("+alias+"resource_attributes AS JSON)) r WHERE r.key=? AND (json_extract_string(r.value,'$')=? OR CAST(r.value AS VARCHAR)=?)) OR EXISTS (SELECT 1 FROM json_each(CAST("+alias+attrs+" AS JSON)) s WHERE s.key=? AND (json_extract_string(s.value,'$')=? OR CAST(s.value AS VARCHAR)=?)))")
		args = append(args, k[0], k[1], k[1], k[0], k[1], k[1])
	}
	return strings.Join(p, " AND "), args
}
func (a *app) traceList() error {
	var root []string
	var args []any
	root = append(root, "t.parent_span_id IS NULL")
	if a.o.Service != "" {
		root = append(root, "t.service_name = ?")
		args = append(args, a.o.Service)
	}
	if a.o.Since > 0 {
		root = append(root, "t.start_time_unix_nano >= ?")
		args = append(args, time.Now().Add(-a.o.Since))
	}
	// Search and attributes apply to any span in the trace, not merely its root.
	if a.o.Query != "" {
		root = append(root, "EXISTS (SELECT 1 FROM lake.main.otlp_traces WHERE trace_id=t.trace_id AND (lower(CAST(name AS VARCHAR)) LIKE ? OR lower(CAST(status_status_message AS VARCHAR)) LIKE ?))")
		v := "%" + strings.ToLower(a.o.Query) + "%"
		args = append(args, v, v)
	}
	for _, x := range a.o.Attributes {
		p := strings.SplitN(x, "=", 2)
		root = append(root, "(EXISTS (SELECT 1 FROM lake.main.otlp_traces m, json_each(CAST(m.resource_attributes AS JSON)) j WHERE m.trace_id=t.trace_id AND j.key=? AND (json_extract_string(j.value,'$')=? OR CAST(j.value AS VARCHAR)=?)) OR EXISTS (SELECT 1 FROM lake.main.otlp_traces m, json_each(CAST(m.span_attributes AS JSON)) j2 WHERE m.trace_id=t.trace_id AND j2.key=? AND (json_extract_string(j2.value,'$')=? OR CAST(j2.value AS VARCHAR)=?)))")
		args = append(args, p[0], p[1], p[1], p[0], p[1], p[1])
	}
	q := "SELECT t.trace_id, t.start_time_unix_nano AS time, t.duration_time_unix_nano AS duration_ns, t.status_code, t.service_name, t.name AS root_name, (SELECT count(*) FROM lake.main.otlp_traces s WHERE s.trace_id=t.trace_id) AS span_count FROM lake.main.otlp_traces t WHERE " + strings.Join(root, " AND ") + " ORDER BY t.start_time_unix_nano DESC LIMIT ?"
	args = append(args, a.o.Limit)
	return a.render(a.queryNamed("trace list", q, args...))
}
func (a *app) traceGet(g TraceGet) error {
	id := g.ID
	q := "SELECT * FROM lake.main.otlp_traces WHERE starts_with(trace_id, ?)"
	args := []any{id}
	// Service selects the trace, but is intentionally not added to the row query:
	// child spans may belong to other services and remain visible in the tree.
	if a.o.Service != "" {
		q += " AND EXISTS (SELECT 1 FROM lake.main.otlp_traces f WHERE f.trace_id=otlp_traces.trace_id AND f.service_name = ?)"
		args = append(args, a.o.Service)
	}
	if a.o.Since > 0 {
		q += " AND EXISTS (SELECT 1 FROM lake.main.otlp_traces f WHERE f.trace_id=otlp_traces.trace_id AND f.start_time_unix_nano >= ?)"
		args = append(args, time.Now().Add(-a.o.Since))
	}
	if a.o.Query != "" {
		q += " AND EXISTS (SELECT 1 FROM lake.main.otlp_traces f WHERE f.trace_id=otlp_traces.trace_id AND (lower(CAST(f.name AS VARCHAR)) LIKE ? OR lower(CAST(f.status_status_message AS VARCHAR)) LIKE ?))"
		value := "%" + strings.ToLower(a.o.Query) + "%"
		args = append(args, value, value)
	}
	for _, attribute := range a.o.Attributes {
		parts := strings.SplitN(attribute, "=", 2)
		q += " AND (EXISTS (SELECT 1 FROM lake.main.otlp_traces f, json_each(CAST(f.resource_attributes AS JSON)) j WHERE f.trace_id=otlp_traces.trace_id AND j.key=? AND (json_extract_string(j.value,'$')=? OR CAST(j.value AS VARCHAR)=?)) OR EXISTS (SELECT 1 FROM lake.main.otlp_traces f, json_each(CAST(f.span_attributes AS JSON)) j WHERE f.trace_id=otlp_traces.trace_id AND j.key=? AND (json_extract_string(j.value,'$')=? OR CAST(j.value AS VARCHAR)=?)))"
		args = append(args, parts[0], parts[1], parts[1], parts[0], parts[1], parts[1])
	}
	q += " ORDER BY start_time_unix_nano"
	rows, err := a.queryNamed("trace get", q, args...)
	if err != nil {
		return err
	}
	if len(rows) == 0 {
		return fmt.Errorf("trace %q not found", id)
	}
	traceIDs := make(map[string]struct{})
	for _, row := range rows {
		traceIDs[fmt.Sprint(row["trace_id"])] = struct{}{}
	}
	if len(traceIDs) > 1 {
		return fmt.Errorf("trace prefix %q is ambiguous", id)
	}
	if !g.RenderAttributes {
		for _, r := range rows {
			delete(r, "resource_attributes")
			delete(r, "span_attributes")
		}
	}
	return a.renderTree(rows)
}
func (a *app) logList() error {
	w, args := a.filters("l.", "time_unix_nano", "log_attributes")
	q := "SELECT time_unix_nano AS timestamp, severity_text, service_name, body, trace_id, span_id FROM lake.main.otlp_logs l " + w + " ORDER BY time_unix_nano DESC LIMIT ?"
	args = append(args, a.o.Limit)
	return a.render(a.query(q, args...))
}
func (a *app) logGet(g LogGet) error {
	q := "SELECT * FROM lake.main.otlp_logs WHERE trace_id = ?"
	args := []any{g.Trace}
	if g.Span != "" {
		q += " AND span_id = ?"
		args = append(args, g.Span)
	}
	// get has the same global filters as list; trace/span selectors remain mandatory.
	if a.o.Service != "" {
		q += " AND service_name = ?"
		args = append(args, a.o.Service)
	}
	if a.o.Since > 0 {
		q += " AND time_unix_nano >= ?"
		args = append(args, time.Now().Add(-a.o.Since))
	}
	if a.o.Query != "" {
		q += " AND (lower(CAST(body AS VARCHAR)) LIKE ? OR lower(CAST(event_name AS VARCHAR)) LIKE ? OR lower(CAST(severity_text AS VARCHAR)) LIKE ?)"
		v := "%" + strings.ToLower(a.o.Query) + "%"
		args = append(args, v, v, v)
	}
	// Reuse the robust JSON predicate without its WHERE prefix.
	if len(a.o.Attributes) > 0 {
		p, aa := attrPredicate("", "log_attributes", a.o.Attributes)
		q += " AND " + p
		args = append(args, aa...)
	}
	q += " ORDER BY time_unix_nano DESC LIMIT ?"
	args = append(args, a.o.Limit)
	return a.render(a.queryNamed("log get", q, args...))
}
func (a *app) metricList() error           { return a.metricQuery("", a.o.Limit) }
func (a *app) metricGet(g MetricGet) error { return a.metricQuery(g.Name, a.o.Limit) }
func (a *app) metricQuery(name string, limit int) error {
	q := `SELECT time_unix_nano AS timestamp, name, description, service_name, resource_attributes, metric_attributes, 'gauge' AS type, int_value, double_value, NULL AS count, NULL AS sum, NULL AS min, NULL AS max FROM lake.main.otlp_metrics_gauge UNION ALL SELECT time_unix_nano,name,description,service_name,resource_attributes,metric_attributes,'sum',int_value,double_value,NULL,NULL,NULL,NULL FROM lake.main.otlp_metrics_sum UNION ALL SELECT time_unix_nano,name,description,service_name,resource_attributes,metric_attributes,'histogram',NULL,NULL,count,sum,min,max FROM lake.main.otlp_metrics_histogram UNION ALL SELECT time_unix_nano,name,description,service_name,resource_attributes,metric_attributes,'exp_histogram',NULL,NULL,count,sum,min,max FROM lake.main.otlp_metrics_exp_histogram`
	var args []any
	clauses := []string{}
	if a.o.Service != "" {
		clauses = append(clauses, "service_name = ?")
		args = append(args, a.o.Service)
	}
	if name != "" {
		clauses = append(clauses, "name = ?")
		args = append(args, name)
	}
	if a.o.Query != "" {
		clauses = append(clauses, "(lower(name) LIKE ? OR lower(CAST(description AS VARCHAR)) LIKE ?)")
		v := "%" + strings.ToLower(a.o.Query) + "%"
		args = append(args, v, v)
	}
	if a.o.Since > 0 {
		clauses = append(clauses, "timestamp >= ?")
		args = append(args, time.Now().Add(-a.o.Since))
	}
	if p, aa := attrPredicate("metrics.", "metric_attributes", a.o.Attributes); p != "" {
		clauses = append(clauses, p)
		args = append(args, aa...)
	}
	if len(clauses) > 0 {
		q = "SELECT * FROM (" + q + ") metrics WHERE " + strings.Join(clauses, " AND ")
	}
	q += " ORDER BY timestamp DESC LIMIT ?"
	args = append(args, limit)
	return a.render(a.queryNamed("metric", q, args...))
}

func (a *app) render(rows []map[string]any, err error) error {
	if err != nil {
		return err
	}
	if a.o.Output == "json" {
		b, e := json.MarshalIndent(rows, "", "  ")
		if e == nil {
			fmt.Println(string(b))
		}
		return e
	}
	if len(rows) == 0 {
		fmt.Println("No results.")
		return nil
	}
	preferred := []string{"timestamp", "time", "trace_id", "span_id", "service_name", "root_name", "name", "duration_ns", "span_count", "status_code", "severity_text", "body", "type", "description", "int_value", "double_value", "count", "sum", "min", "max"}
	keys := orderedKeys(rows[0], preferred)
	w := tabwriter.NewWriter(os.Stdout, 0, 2, 2, ' ', 0)
	fmt.Fprintln(w, strings.Join(keys, "\t"))
	for _, r := range rows {
		v := make([]string, len(keys))
		for i, k := range keys {
			v[i] = fmt.Sprint(r[k])
		}
		fmt.Fprintln(w, strings.Join(v, "\t"))
	}
	return w.Flush()
}
func orderedKeys(row map[string]any, preferred []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, k := range preferred {
		if _, ok := row[k]; ok {
			out = append(out, k)
			seen[k] = true
		}
	}
	var rest []string
	for k := range row {
		if !seen[k] {
			rest = append(rest, k)
		}
	}
	sort.Strings(rest)
	return append(out, rest...)
}
func (a *app) renderTree(rows []map[string]any) error {
	if a.o.Output == "json" {
		return a.render(rows, nil)
	}
	type node struct {
		r    map[string]any
		kids []*node
	}
	by := map[string]*node{}
	var roots []*node
	for _, r := range rows {
		id := fmt.Sprint(r["span_id"])
		by[id] = &node{r: r}
	}
	for _, n := range by {
		p := fmt.Sprint(n.r["parent_span_id"])
		if p == "<nil>" || p == "" || by[p] == nil {
			roots = append(roots, n)
		} else {
			by[p].kids = append(by[p].kids, n)
		}
	}
	sort.Slice(roots, func(i, j int) bool {
		return fmt.Sprint(roots[i].r["start_time_unix_nano"]) < fmt.Sprint(roots[j].r["start_time_unix_nano"])
	})
	var walk func(*node, string, bool)
	w := tabwriter.NewWriter(os.Stdout, 0, 2, 2, ' ', 0)
	fmt.Fprintln(w, "SPAN ID\tTIME\tDURATION\tSTATUS\tSERVICE\tNAME")
	walk = func(n *node, prefix string, last bool) {
		r := n.r
		connector := ""
		if prefix != "" {
			connector = "├─ "
			if last {
				connector = "└─ "
			}
		}
		dur := durationMillis(r["duration_time_unix_nano"])
		fmt.Fprintf(w, "%s%s%v\t%v\t%s\t%v\t%v\t%v\n", prefix, connector, r["span_id"], r["start_time_unix_nano"], dur, r["status_code"], r["service_name"], r["name"])
		if a.o != nil && a.o.Output == "table" && (r["resource_attributes"] != nil || r["span_attributes"] != nil) {
			fmt.Fprintf(w, "%s    attrs: resource=%s span=%s\n", prefix, compactJSON(r["resource_attributes"]), compactJSON(r["span_attributes"]))
		}
		sort.Slice(n.kids, func(i, j int) bool {
			return fmt.Sprint(n.kids[i].r["start_time_unix_nano"]) < fmt.Sprint(n.kids[j].r["start_time_unix_nano"])
		})
		for i, k := range n.kids {
			walk(k, prefix+map[bool]string{true: "│   ", false: "    "}[prefix != ""], i == len(n.kids)-1)
		}
	}
	for _, r := range roots {
		walk(r, "", true)
	}
	return w.Flush()
}
func durationMillis(v any) string {
	var n int64
	switch x := v.(type) {
	case int64:
		n = x
	case int:
		n = int64(x)
	case float64:
		n = int64(x)
	default:
		fmt.Sscan(fmt.Sprint(v), &n)
	}
	return fmt.Sprintf("%.3fms", float64(n)/1e6)
}
func compactJSON(v any) string {
	if v == nil || fmt.Sprint(v) == "<nil>" {
		return "{}"
	}
	var raw json.RawMessage
	switch x := v.(type) {
	case []byte:
		raw = x
	case string:
		raw = []byte(x)
	default:
		b, _ := json.Marshal(x)
		raw = b
	}
	var out any
	if json.Unmarshal(raw, &out) == nil {
		b, _ := json.Marshal(out)
		return string(b)
	}
	return fmt.Sprint(v)
}
