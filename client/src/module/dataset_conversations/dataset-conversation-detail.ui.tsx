import { ArrowLeft, ChevronDown, FileText, MessageSquare, RefreshCw } from "lucide-react";
import type React from "react";
import { Badge } from "@/platform/ui/badge";
import { Button } from "@/platform/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";
import { Skeleton } from "@/platform/ui/skeleton";
import { ScrollArea } from "@/platform/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/platform/ui/tabs";
import type { DatasetConversation } from "./dataset-conversation.model";

export type DatasetConversationDetailState =
  | { status: "invalid" }
  | { status: "loading" }
  | { status: "error"; onRetry: () => void }
  | { status: "not-found" }
  | {
      status: "ready";
      item: DatasetConversation;
      chat: React.ReactNode;
      activeTab: "record" | "chat-sessions";
      onTabChange: (tab: "record" | "chat-sessions") => void;
      rawPayloadOpen: boolean;
      onRawPayloadToggle: () => void;
    };

export type DatasetConversationDetailProps = {
  state: DatasetConversationDetailState;
  onBack: () => void;
};

export function DatasetConversationDetail({ state, onBack }: DatasetConversationDetailProps) {
  let content: React.ReactNode;

  switch (state.status) {
    case "invalid":
      content = (
        <DetailState
          title="Invalid dataset record"
          message="Dataset record IDs must be positive integers."
        />
      );
      break;
    case "loading":
      content = <DetailLoadingSkeleton />;
      break;
    case "error":
      content = (
        <DetailState
          title="Unable to load dataset record"
          message="Check that the API is running, then try again."
          action={
            <Button onClick={state.onRetry}>
              <RefreshCw size={15} /> Try again
            </Button>
          }
        />
      );
      break;
    case "not-found":
      content = (
        <DetailState
          title="Dataset record not found"
          message="No dataset record exists with this ID."
        />
      );
      break;
    case "ready":
      content = <ReadyDetail {...state} />;
      break;
  }

  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-6xl px-5 pb-16 pt-10">
        <Button
          type="button"
          variant="ghost"
          className="h-auto px-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
          onClick={onBack}
        >
          <ArrowLeft size={15} /> Back to dataset library
        </Button>
        <div className="mt-8">{content}</div>
      </section>
    </main>
  );
}

function DetailLoadingSkeleton() {
  return (
    <output aria-busy="true" aria-label="Loading dataset record" className="block">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-9 w-80 max-w-[75vw]" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16 rounded-full" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      </div>

      <div className="mt-8 inline-flex h-10 items-center gap-1 rounded-md bg-muted p-1">
        <Skeleton className="h-8 w-36" />
        <Skeleton className="h-8 w-36" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-36" />
            </CardHeader>
            <CardContent className="space-y-8">
              <LoadingTextBlock />
              <LoadingTextBlock />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
          </Card>
        </div>

        <aside className="space-y-5">
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-32" />
            </CardHeader>
            <CardContent className="space-y-4">
              {["source", "split", "id", "turns"].map((key) => (
                <div key={key} className="flex justify-between gap-4 border-b pb-3 last:border-0">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-24" />
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-28" />
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-4/5" />
            </CardContent>
          </Card>
        </aside>
      </div>
      <span className="sr-only">Loading dataset record…</span>
    </output>
  );
}

function LoadingTextBlock() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-5 w-44" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    </div>
  );
}

function ReadyDetail({
  item,
  chat,
  activeTab,
  onTabChange,
  rawPayloadOpen,
  onRawPayloadToggle,
}: Extract<DatasetConversationDetailState, { status: "ready" }>) {
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-muted-foreground">
            {item.split} · Record #{item.id}
          </p>
          <h1 className="mt-2 break-all text-3xl font-semibold tracking-tight">{item.source_id}</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge>{item.num_dialogue_turns ?? 0} turns</Badge>
          {item.has_type2_question && <Badge variant="outline">Type 2</Badge>}
          {item.has_duplicate_columns && <Badge variant="outline">Duplicates</Badge>}
          {item.has_non_numeric_values && <Badge variant="outline">Non-numeric</Badge>}
        </div>
      </div>
      <Tabs
        value={activeTab}
        className="mt-8"
        onValueChange={(value) => {
          if (value === "record" || value === "chat-sessions") onTabChange(value);
        }}
      >
        <TabsList aria-label="Dataset record sections">
          <TabsTrigger value="record" className="gap-2">
            <FileText size={16} /> Dataset record
          </TabsTrigger>
          <TabsTrigger value="chat-sessions" className="gap-2">
            <MessageSquare size={16} /> Chat sessions
          </TabsTrigger>
        </TabsList>
        <TabsContent
          value="record"
          className="mt-6 min-w-0 grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]"
        >
          <div className="min-w-0 space-y-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Source context</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[28rem] max-h-[70vh] pr-3 sm:h-[32rem] lg:h-[34rem]">
                  <div className="space-y-8 pr-3">
                    <TextSection title="Before the question" value={item.pre_text} />
                    <TextSection title="After the question" value={item.post_text} />
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
            <section className="min-w-0 overflow-hidden rounded-lg border bg-card shadow-sm">
              <button
                type="button"
                aria-expanded={rawPayloadOpen}
                aria-controls="raw-dataset-payload"
                className="flex w-full items-center justify-between px-6 py-4 text-left text-sm font-semibold"
                onClick={onRawPayloadToggle}
              >
                Raw dataset payload
                <ChevronDown
                  size={16}
                  className={
                    rawPayloadOpen ? "rotate-180 transition-transform" : "transition-transform"
                  }
                />
              </button>
              {rawPayloadOpen && (
                <div id="raw-dataset-payload" className="min-w-0 grid gap-5 p-6 pt-1">
                  <JsonCard title="Dialogue" value={item.dialogue_json} />
                  <JsonCard title="Features" value={item.features_json} />
                  <JsonCard title="Document" value={item.doc_json} />
                </div>
              )}
            </section>
          </div>
          <aside className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Record details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <Meta label="Source ID" value={item.source_id} />
                <Meta label="Split" value={item.split} />
                <Meta label="Database ID" value={String(item.id)} />
                <Meta label="Dialogue turns" value={String(item.num_dialogue_turns ?? 0)} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Data quality</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-6 text-muted-foreground">
                  {qualityNotes(item).join(" ") ||
                    "No quality flags were reported for this record."}
                </p>
              </CardContent>
            </Card>
          </aside>
        </TabsContent>
        <TabsContent value="chat-sessions" className="mt-6">
          {chat}
        </TabsContent>
      </Tabs>
    </>
  );
}

function DetailState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{message}</p>
      </CardHeader>
      {action && <CardContent>{action}</CardContent>}
    </Card>
  );
}

function TextSection({ title, value }: { title: string; value: string }) {
  return (
    <section className="min-w-0 space-y-3 border-b pb-8 last:border-b-0 last:pb-0">
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      <p className="break-words whitespace-pre-wrap text-sm leading-7 text-muted-foreground [overflow-wrap:anywhere]">
        {value || "No text available."}
      </p>
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b pb-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all text-right font-medium">{value}</span>
    </div>
  );
}

function qualityNotes(item: DatasetConversation) {
  return [
    item.has_type2_question && "Contains a type 2 question.",
    item.has_duplicate_columns && "Contains duplicate columns.",
    item.has_non_numeric_values && "Contains non-numeric values.",
  ].filter(Boolean) as string[];
}

function JsonCard({ title, value }: { title: string; value: string | null }) {
  let formatted = value ?? "No data available.";
  if (value) {
    try {
      formatted = JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      /* Keep malformed API data readable. */
    }
  }
  return (
    <Card className="min-w-0 overflow-hidden">
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="max-h-96 max-w-full overflow-y-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-4 text-xs leading-6 [overflow-wrap:anywhere]">
          {formatted}
        </pre>
      </CardContent>
    </Card>
  );
}
