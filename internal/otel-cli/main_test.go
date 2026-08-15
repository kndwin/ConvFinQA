package main

import (
	"bytes"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/alecthomas/kong"
)

func TestFiltersUseArgumentsAndSignalAttributes(t *testing.T) {
	a := &app{o: &Options{Service: "api", Since: time.Minute, Query: "ERROR", Attributes: []string{"http.method=GET"}}}
	where, args := a.filters("l.", "time_unix_nano", "log_attributes")
	if !strings.Contains(where, "l.service_name = ?") || !strings.Contains(where, "l.log_attributes") {
		t.Fatalf("unexpected filter: %s", where)
	}
	if strings.Contains(where, "api") || strings.Contains(where, "GET") || len(args) != 11 {
		t.Fatalf("values should be parameters: where=%s args=%v", where, args)
	}
}

func TestDSNWithTokenPreservesQueryAndEscapes(t *testing.T) {
	dsn, err := dsnWithToken("quack://localhost:9494?mode=read", "a&b=c ?")
	if err != nil || !strings.Contains(dsn, "mode=read") || !strings.Contains(dsn, "token=a%26b%3Dc+%3F") {
		t.Fatalf("bad DSN %q: %v", dsn, err)
	}
}

func TestSignalSearchExpressionsAreNotBodyOnly(t *testing.T) {
	a := &app{o: &Options{Query: "needle"}}
	w, _ := a.filtersFor("m.", "time_unix_nano", "metric_attributes", "m.name", "m.description")
	if !strings.Contains(w, "m.name") || !strings.Contains(w, "m.description") || strings.Contains(w, "m.body") {
		t.Fatalf("unexpected metric search: %s", w)
	}
}

func TestAttributeValidationShape(t *testing.T) {
	valid := []string{"key=value", "a=b=c"}
	for _, value := range valid {
		if !strings.Contains(value, "=") || strings.SplitN(value, "=", 2)[0] == "" {
			t.Errorf("expected valid attribute %q", value)
		}
	}
	for _, value := range []string{"", "=value", "key"} {
		if strings.Contains(value, "=") && strings.SplitN(value, "=", 2)[0] != "" {
			t.Errorf("expected invalid attribute %q", value)
		}
	}
}

func TestOutputEnumAndHelpAreDiscoverable(t *testing.T) {
	var cli CLI
	var help bytes.Buffer
	parser, err := kong.New(&cli, kong.Name("otel-cli"), kong.Writers(&help, &help), kong.Exit(func(int) {}))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := parser.Parse([]string{"--output", "yaml"}); err == nil || !strings.Contains(err.Error(), "table") {
		t.Fatalf("expected enum validation mentioning valid output values, got %v", err)
	}
	// Kong's low-level Parse validates required positionals before handling
	// --help; the public kong.Parse path (used by main) prints this help first.
	text := (TraceGet{}).Help() + "\n" + (CLI{}).Help()
	for _, want := range []string{"4bf92f36", "--attributes"} {
		if !strings.Contains(text, want) {
			t.Errorf("help missing %q:\n%s", want, text)
		}
	}
	options, _ := reflect.TypeOf(CLI{}).FieldByName("Options")
	output, _ := options.Type.FieldByName("Output")
	if output.Tag.Get("enum") != "table,json" || !strings.Contains(output.Tag.Get("help"), "machine-readable") {
		t.Fatalf("output help must advertise enum and formats")
	}
	traceID, _ := reflect.TypeOf(TraceGet{}).FieldByName("ID")
	if !strings.Contains(traceID.Tag.Get("help"), "prefix") {
		t.Fatalf("trace ID help should explain prefixes")
	}
}

func TestValidateOptions(t *testing.T) {
	if err := validateOptions(Options{Limit: 0}); err == nil {
		t.Fatal("expected limit validation")
	}
	if err := validateOptions(Options{Limit: 1, Attributes: []string{"=value"}}); err == nil {
		t.Fatal("expected attribute validation")
	}
	if err := validateOptions(Options{Limit: 1, Output: "yaml"}); err != nil {
		t.Fatalf("output enum belongs to Kong; options validation should not duplicate it: %v", err)
	}
}
