import { useMachine } from "@xstate/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useChat } from "@tanstack/ai-react";
import { fetchServerSentEvents } from "@tanstack/ai-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/platform/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";
import { ScrollArea } from "@/platform/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
import {
  chatRunUrl,
  datasetChatCreateSessionOptions,
  datasetChatMessagesOptions,
  datasetChatQueries,
  datasetChatSessionsOptions,
  type AgentVariant,
  type PersistedMessage,
} from "./dataset-chat.query";
import {
  datasetChatSessionSelectionMachine,
  datasetChatTranscriptMachine,
} from "./dataset-chat.machine";
import type { DatasetConversation } from "./dataset-conversation.model";

type TextPart = { type: "text"; content: string };
type ToolCallPart = {
  type: "tool-call";
  id: string;
  name: string;
  arguments: unknown;
  state: string;
};
type ToolResultPart = {
  type: "tool-result";
  toolCallId: string;
  content: unknown;
  state: string;
  error?: unknown;
};
type InitialMessage = { id: string; role: "user" | "assistant"; parts: TextPart[] };
const agentVariants = ["direct-mini", "calculator-mini"] as const satisfies readonly AgentVariant[];
const agentVariantLabels: Record<AgentVariant, string> = {
  "direct-mini": "Direct mini",
  "calculator-mini": "Calculator mini",
};
const agentVariantDescriptions: Record<AgentVariant, string> = {
  "direct-mini": "Answers directly from the dataset context.",
  "calculator-mini": "Can use arithmetic for calculation questions.",
};
function isAgentVariant(value: string): value is AgentVariant {
  return agentVariants.some((variant) => variant === value);
}

const initial = (messages: PersistedMessage[]): InitialMessage[] =>
  messages
    .filter(
      (m): m is PersistedMessage & { role: "user" | "assistant" } =>
        m.role === "user" || m.role === "assistant",
    )
    .map((m) => ({
      id: String(m.id),
      role: m.role,
      parts: [{ type: "text", content: m.content }],
    }));

export type CandidateQa = DatasetConversation["candidate_qa"];

export function DatasetChat({
  datasetId,
  candidateQa,
}: {
  datasetId: number;
  candidateQa: CandidateQa;
}) {
  const queryClient = useQueryClient();
  const [selection, sendSelection] = useMachine(datasetChatSessionSelectionMachine);
  const [selectedVariant, setSelectedVariant] = useState<AgentVariant>("direct-mini");
  const selected = selection.context.selected;
  const sessionsQuery = useQuery(datasetChatSessionsOptions(datasetId));
  const messagesQuery = useQuery(datasetChatMessagesOptions(datasetId, selected));
  const createMutation = useMutation({
    ...datasetChatCreateSessionOptions(datasetId),
    onSuccess: async (session) => {
      await queryClient.invalidateQueries({ queryKey: datasetChatQueries.sessions(datasetId) });
      sendSelection({ type: "session.created", sessionId: session.id });
    },
  });
  useEffect(() => {
    sendSelection({ type: "dataset.reset" });
  }, [datasetId]);
  useEffect(() => {
    const values = sessionsQuery.data;
    if (!values) return;
    sendSelection({
      type: "sessions.synchronized",
      sessionIds: values.map((session) => session.id),
    });
  }, [sessionsQuery.data, sendSelection]);
  const sessions = sessionsQuery.data ?? [];
  const error =
    createMutation.error?.message ?? sessionsQuery.error?.message ?? messagesQuery.error?.message;
  return (
    <Card className="flex h-[clamp(32rem,calc(100vh-14rem),44rem)] min-h-0 flex-col overflow-hidden">
      <CardHeader className="shrink-0">
        <CardTitle>Dataset chat</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1">
        <div className="grid h-full min-h-0 gap-4 md:grid-cols-[220px_minmax(0,1fr)_minmax(220px,300px)]">
          <aside className="flex min-h-0 flex-col gap-2 border-b pb-4 md:border-b-0 md:border-r md:pb-0 md:pr-4">
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="dataset-chat-agent">
                Agent
              </label>
              <Select
                value={selectedVariant}
                onValueChange={(value) => {
                  if (isAgentVariant(value)) setSelectedVariant(value);
                }}
              >
                <SelectTrigger
                  aria-describedby="dataset-chat-agent-help"
                  id="dataset-chat-agent"
                  disabled={createMutation.isPending}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {agentVariants.map((variant) => (
                    <SelectItem key={variant} value={variant}>
                      {agentVariantLabels[variant]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground" id="dataset-chat-agent-help">
                {agentVariantDescriptions[selectedVariant]}
              </p>
            </div>
            <Button
              className="w-full shrink-0"
              disabled={createMutation.isPending}
              onClick={() => createMutation.mutate(selectedVariant)}
            >
              {createMutation.isPending ? "Creating…" : "New chat"}
            </Button>
            {sessionsQuery.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {sessionsQuery.isError && (
              <Button onClick={() => void sessionsQuery.refetch()}>Retry chats</Button>
            )}
            {!sessionsQuery.isLoading && !sessionsQuery.isError && sessions.length === 0 && (
              <p className="text-sm text-muted-foreground">No chats yet.</p>
            )}
            <ScrollArea className="min-h-0 flex-1">
              <div className="space-y-2 pr-3">
                {sessions.map((s) => (
                  <button
                    aria-pressed={selected === s.id}
                    className={`block w-full rounded p-2 text-left text-sm ${selected === s.id ? "bg-muted font-medium" : "hover:bg-muted"}`}
                    key={s.id}
                    onClick={() => {
                      sendSelection({ type: "session.selected", sessionId: s.id });
                    }}
                  >
                    {s.title || `Chat #${s.id}`}
                    <span className="block text-xs text-muted-foreground">
                      {agentVariantLabels[s.agent_variant]} ·{" "}
                      {new Date(s.updated_at).toLocaleString()}
                    </span>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </aside>
          {selected && !messagesQuery.isError && messagesQuery.data ? (
            <ChatTranscript
              key={selected}
              datasetId={datasetId}
              sessionId={selected}
              initialMessages={initial(messagesQuery.data)}
              onDone={() => {
                void queryClient.invalidateQueries({
                  queryKey: datasetChatQueries.sessions(datasetId),
                });
                void queryClient.invalidateQueries({
                  queryKey: datasetChatQueries.messages(datasetId, selected),
                });
              }}
            />
          ) : (
            <div className="flex h-full min-h-0 items-center justify-center p-8 text-sm text-muted-foreground">
              {messagesQuery.isLoading
                ? "Loading transcript…"
                : messagesQuery.isError
                  ? "Transcript failed to load. Select this chat to retry."
                  : selected
                    ? "No messages yet."
                    : "Choose New chat to begin."}
              {messagesQuery.isError && (
                <Button className="mt-2" onClick={() => void messagesQuery.refetch()}>
                  Retry
                </Button>
              )}
            </div>
          )}
          <CandidateQaPanel candidateQa={candidateQa} />
        </div>
        {error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function CandidateQaPanel({ candidateQa }: { candidateQa: CandidateQa }) {
  return (
    <Card className="flex min-h-0 flex-col overflow-hidden">
      <CardHeader className="shrink-0 pb-3">
        <CardTitle className="text-base">Candidate Q&amp;A</CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1">
        {candidateQa.length === 0 ? (
          <p className="text-sm text-muted-foreground">No candidate questions available.</p>
        ) : (
          <ScrollArea className="h-full">
            <div className="space-y-4 pr-3">
              {candidateQa.map((candidate) => (
                <article
                  className="space-y-1 text-sm"
                  key={`${candidate.question}-${candidate.answer ?? ""}`}
                >
                  <h3 className="font-medium">Question</h3>
                  <p className="break-words whitespace-pre-wrap [overflow-wrap:anywhere]">
                    {candidate.question}
                  </p>
                  <h3 className="pt-2 font-medium">Expected answer</h3>
                  <p className="break-words whitespace-pre-wrap text-muted-foreground [overflow-wrap:anywhere]">
                    {candidate.answer ?? "Unavailable"}
                  </p>
                </article>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

/* oxlint-disable jsx-a11y/prefer-tag-over-role -- Keep the explicit live-region role for clarity. */
export function AgentReplyingIndicator() {
  return (
    <div className="mr-8 rounded-lg border p-3" role="status" aria-live="polite">
      <div className="typeset typeset-docs max-w-[37em]">
        Agent is replying
        <span aria-hidden="true" className="ml-1 inline-flex items-center gap-1 align-middle">
          <span className="size-1.5 animate-bounce rounded-full bg-current motion-reduce:animate-none" />
          <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.2s] motion-reduce:animate-none" />
          <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.4s] motion-reduce:animate-none" />
        </span>
      </div>
    </div>
  );
}
/* oxlint-enable jsx-a11y/prefer-tag-over-role */

function hasVisibleTextPart(message: { parts: readonly { type: string; content?: unknown }[] }) {
  return message.parts.some(
    (part) =>
      (part.type === "text" &&
        typeof part.content === "string" &&
        part.content.trim().length > 0) ||
      part.type === "tool-call" ||
      part.type === "tool-result",
  );
}

export function ToolActivity({ part }: { part: ToolCallPart | ToolResultPart }) {
  if (part.type === "tool-call") {
    return (
      <div className="my-1 rounded border bg-muted/40 p-2 text-xs">
        <strong>Tool: {part.name}</strong> · {part.state}
        <pre className="mt-1 whitespace-pre-wrap">
          {typeof part.arguments === "string" ? part.arguments : JSON.stringify(part.arguments)}
        </pre>
      </div>
    );
  }
  return (
    <div className="my-1 rounded border p-2 text-xs">
      <strong>Tool result</strong> · {part.state}
      <div>{typeof part.content === "string" ? part.content : JSON.stringify(part.content)}</div>
      {part.error ? <div className="text-destructive">{String(part.error)}</div> : null}
    </div>
  );
}

function ChatTranscript({
  datasetId,
  sessionId,
  initialMessages,
  onDone,
}: {
  datasetId: number;
  sessionId: number;
  initialMessages: InitialMessage[];
  onDone: () => void;
}) {
  const [transcript, sendTranscript] = useMachine(datasetChatTranscriptMachine);
  const { input, sendError } = transcript.context;
  const bottomRef = useRef<HTMLDivElement>(null);
  const connection = useMemo(
    () => fetchServerSentEvents(chatRunUrl(datasetId, sessionId)),
    [datasetId, sessionId],
  );
  const chat = useChat({
    threadId: `dataset-${datasetId}-session-${sessionId}`,
    connection,
    initialMessages,
    onFinish: onDone,
  });
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chat.messages, chat.isLoading]);
  const visibleMessages = chat.messages.filter(hasVisibleTextPart);
  const send = async () => {
    const draft = input.trim();
    if (!draft || chat.isLoading) return;
    sendTranscript({ type: "send.started" });
    try {
      await chat.sendMessage(draft);
    } catch (e) {
      sendTranscript({
        type: "send.failed",
        draft,
        error: e instanceof Error ? e.message : "Message failed",
      });
    }
  };
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 whitespace-pre-wrap break-words pr-4 [overflow-wrap:anywhere]">
          {visibleMessages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Ask a question about this financial dataset.
            </p>
          )}
          {visibleMessages.map((m) => (
            <div
              className={`rounded-lg p-3 ${m.role === "user" ? "ml-8 bg-muted" : "mr-8 border"}`}
              key={m.id}
            >
              <div className="typeset typeset-docs max-w-[37em]">
                {m.parts.map((part) =>
                  part.type === "text" ? (
                    <span key={`${m.id}-${part.type}`}>{part.content}</span>
                  ) : part.type === "tool-call" || part.type === "tool-result" ? (
                    <ToolActivity
                      key={part.type === "tool-call" ? part.id : part.toolCallId}
                      part={part as ToolCallPart | ToolResultPart}
                    />
                  ) : null,
                )}
              </div>
            </div>
          ))}
          {chat.isLoading && <AgentReplyingIndicator />}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>
      <form
        className="mt-4 flex shrink-0 gap-2 border-t pt-4"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          aria-label="Message"
          value={input}
          onChange={(e) => sendTranscript({ type: "input.changed", value: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              if (!chat.isLoading) void send();
            }
          }}
          className="min-h-12 flex-1 resize-none rounded border bg-background p-2 text-sm"
          placeholder="Ask about the record…"
          disabled={chat.isLoading}
        />
        {chat.isLoading ? (
          <Button type="button" onClick={chat.stop}>
            Stop
          </Button>
        ) : (
          <Button type="submit" disabled={!input.trim()}>
            Send
          </Button>
        )}
      </form>
      {(sendError || chat.error) && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {sendError || chat.error?.message}
        </p>
      )}
    </div>
  );
}
