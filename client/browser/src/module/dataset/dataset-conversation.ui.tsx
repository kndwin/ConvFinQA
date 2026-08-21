import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Database, RefreshCw, Search, Tag, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { match, P } from "ts-pattern";
import { Button } from "@/platform/ui/button";
import { Badge } from "@/platform/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/platform/ui/card";
import { Input } from "@/platform/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
import { Skeleton } from "@/platform/ui/skeleton";
import { Popover, PopoverContent, PopoverTrigger } from "@/platform/ui/popover";
import { chatSessionTagsOptions } from "../chat-session/chat-session.query";
import { datasetConversationKey } from "./dataset-conversation.schema";
import { datasetConversationListOptions } from "./dataset-conversation.query";
import { DatasetConversationCard } from "./dataset-conversation-card.ui";
import type { ExplorerSearch } from "./dataset-conversation-search.schema";
const routeApi = getRouteApi("/");
export function DatasetConversationPage() {
  const search = routeApi.useSearch();
  const navigate = routeApi.useNavigate();
  const pageSize = 12;
  const listQuery = useQuery(
    datasetConversationListOptions({
      offset: (search.page - 1) * pageSize,
      limit: pageSize + 1,
      tags: search.tags,
    }),
  );
  const rows = listQuery.data ?? [];
  const pageRows = rows.slice(0, pageSize);
  const filtered = useMemo(
    () =>
      pageRows.filter((item) => {
        const needle = search.q.toLowerCase().trim();
        return (
          (!needle ||
            [item.source_id, item.pre_text, item.post_text]
              .join(" ")
              .toLowerCase()
              .includes(needle)) &&
          (search.split === "all" || item.split === search.split)
        );
      }),
    [pageRows, search.q, search.split],
  );
  const hasNext = rows.length > pageSize;
  const splits = Array.from(new Set(pageRows.map((row) => row.split))).sort();
  const updateFilters = (values: Partial<typeof search>) =>
    void navigate({
      search: (previous: ExplorerSearch) => ({
        ...previous,
        ...values,
        page: 1,
      }),
      replace: true,
    });
  const loading = listQuery.isLoading;
  const refreshing = listQuery.isFetching;
  return (
    <main className="min-h-screen bg-background">
      <header className="border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-primary p-2 text-primary-foreground">
              <Database size={18} />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight">ConvFinQA Dataset Explorer</p>
              <p className="text-xs text-muted-foreground">Dataset library</p>
            </div>
          </div>
          <Button disabled={refreshing} variant="outline" onClick={() => void listQuery.refetch()}>
            <RefreshCw className={refreshing ? "animate-spin" : ""} size={15} />{" "}
            {refreshing ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
      </header>
      <section className="mx-auto max-w-6xl px-5 pb-16 pt-12">
        <div className="max-w-2xl">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">
            Dataset library
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Explore the ConvFinQA records
          </h1>
          <p className="mt-3 text-base leading-7 text-muted-foreground">
            Browse normalized dataset records, source context, and data quality signals from the
            ConvFinQA collection.
          </p>
        </div>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <label className="relative block flex-1">
            <Search className="absolute left-3 top-3 text-muted-foreground" size={18} />
            <Input
              value={search.q}
              onChange={(event) => updateFilters({ q: event.target.value })}
              placeholder="Search source, question, or follow-up…"
              className="pl-10"
              aria-label="Search dataset records"
            />
          </label>
          <div className="flex items-center gap-2">
            <label htmlFor="dataset-split" className="text-sm text-muted-foreground">
              Split
            </label>
            <Select value={search.split} onValueChange={(split) => updateFilters({ split })}>
              <SelectTrigger
                id="dataset-split"
                className="w-full sm:w-40"
                aria-label="Filter by split"
              >
                <SelectValue placeholder="All splits" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All splits</SelectItem>
                {splits.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <TagFilter tags={search.tags} onChange={(tags) => updateFilters({ tags })} />
        </div>
        <div className="mt-8 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {match(listQuery)
              .with({ status: "pending" }, () => "Loading dataset records…")
              .with({ status: "error" }, () => "Unable to load dataset records")
              .with(
                { status: "success" },
                () =>
                  `${filtered.length} ${filtered.length === 1 ? "record" : "records"} on this page`,
              )
              .exhaustive()}
          </span>
          {!loading && !listQuery.isError && (
            <span>
              Page {search.page} · Tags filter on the server; search and split apply to this page
            </span>
          )}
        </div>
        {match({ listQuery, filtered })
          .with({ listQuery: { status: "error" } }, () => (
            <Card className="mt-5">
              <CardHeader className="items-center text-center">
                <CardTitle className="text-lg">We couldn’t load the dataset snapshot.</CardTitle>
                <CardDescription>Check that the API is running, then try again.</CardDescription>
              </CardHeader>
              <CardContent className="text-center">
                <Button onClick={() => void listQuery.refetch()}>Try again</Button>
              </CardContent>
            </Card>
          ))
          .with({ listQuery: { status: "pending" } }, () => (
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {[1, 2, 3, 4].map((key) => (
                <Skeleton key={key} className="h-52" />
              ))}
            </div>
          ))
          .with(
            {
              listQuery: { status: "success" },
              filtered: P.when((items) => items.length === 0),
            },
            () => (
              <Card className="mt-5">
                <CardContent className="pt-10 text-center text-muted-foreground">
                  No dataset records match these filters.
                </CardContent>
              </Card>
            ),
          )
          .with({ listQuery: { status: "success" } }, ({ filtered: items }) => (
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {items.map((item) => (
                <DatasetConversationCard key={datasetConversationKey(item)} item={item} />
              ))}
            </div>
          ))
          .exhaustive()}
        {!loading && !listQuery.isError && (search.page > 1 || hasNext) && (
          <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-3">
            <Button
              variant="outline"
              size="icon"
              aria-label="Previous page"
              disabled={search.page <= 1}
              onClick={() =>
                void navigate({
                  search: (p: ExplorerSearch) => ({
                    ...p,
                    page: search.page - 1,
                  }),
                  replace: true,
                })
              }
            >
              <ChevronLeft size={18} />
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Next page"
              disabled={!hasNext}
              onClick={() =>
                void navigate({
                  search: (p: ExplorerSearch) => ({
                    ...p,
                    page: search.page + 1,
                  }),
                  replace: true,
                })
              }
            >
              <ChevronRight size={18} />
            </Button>
          </nav>
        )}
      </section>
    </main>
  );
}

function TagFilter({ tags, onChange }: { tags: string[]; onChange: (tags: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const suggestions = useQuery(chatSessionTagsOptions());
  const add = (value: string) => {
    const tag = value.trim();
    if (!tag || tags.includes(tag) || tags.length >= 50) return;
    onChange([...tags, tag]);
    setDraft("");
  };
  const available = (suggestions.data ?? [])
    .map((item) => item.value)
    .filter(
      (value) =>
        !tags.includes(value) &&
        (!draft.trim() || value.toLowerCase().includes(draft.trim().toLowerCase())),
    )
    .slice(0, 8);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant={tags.length ? "default" : "outline"} className="gap-2">
          <Tag size={15} /> Tags
          {tags.length > 0 && <Badge variant="outline">{tags.length}</Badge>}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Filter by tags</p>
            {tags.length > 0 && (
              <Button type="button" variant="ghost" size="sm" onClick={() => onChange([])}>
                Clear all
              </Button>
            )}
          </div>
          <Input
            value={draft}
            placeholder="Search tags…"
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Search tag suggestions"
          />
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                  <button
                    type="button"
                    className="ml-1 rounded-full"
                    aria-label={`Remove tag ${tag}`}
                    onClick={() => onChange(tags.filter((value) => value !== tag))}
                  >
                    <X size={12} />
                  </button>
                </Badge>
              ))}
            </div>
          )}
          {suggestions.isLoading && <p className="text-xs text-muted-foreground">Loading tags…</p>}
          {suggestions.isError && (
            <p className="text-xs text-muted-foreground">Tag suggestions unavailable.</p>
          )}
          {!suggestions.isLoading && !suggestions.isError && available.length === 0 && (
            <p className="text-xs text-muted-foreground">No matching tags.</p>
          )}
          <div className="flex flex-wrap gap-1">
            {available.map((tag) => (
              <Button key={tag} type="button" size="sm" variant="ghost" onClick={() => add(tag)}>
                {tag}
              </Button>
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
