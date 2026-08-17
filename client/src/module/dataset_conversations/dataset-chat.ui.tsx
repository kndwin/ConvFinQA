import { useMachine } from "@xstate/react";
import { forwardRef, useImperativeHandle, useMemo, useRef, useState } from "react";
import { useChat } from "@tanstack/ai-react";
import { fetchServerSentEvents } from "@tanstack/ai-client";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Button } from "@/platform/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";
import { ScrollArea } from "@/platform/ui/scroll-area";
import { Message, MessageContent, MessageHeader } from "@/platform/ui/message";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/platform/ui/message-scroller";
import { Marker, MarkerContent, MarkerIcon } from "@/platform/ui/marker";
import { AlertCircle, Check, LoaderCircle, Wrench } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
import { chatRunUrl, type AgentApproach, type OpenAIModel } from "./dataset-chat.query";
import { datasetChatTranscriptMachine } from "./dataset-chat.machine";
import type { DatasetConversation } from "./dataset-conversation.model";
import {
  chatSessionGroupListOptions,
  useCreateChatSessionGroup,
} from "./chat-session-groups.query";

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
const agentApproaches = [
  "baseline",
  "baseline-tool",
  "program-of-thought",
] as const satisfies readonly AgentApproach[];
const agentApproachLabels: Record<AgentApproach, string> = {
  baseline: "Baseline",
  "baseline-tool": "Baseline + tool",
  "program-of-thought": "Program of thought",
};
function isAgentApproach(value: string): value is AgentApproach {
  return agentApproaches.some((approach) => approach === value);
}
const models = [
  "gpt-5.6-luna",
  "gpt-5.6-terra",
  "gpt-5.6-sol",
  "gpt-5-mini",
] as const satisfies readonly OpenAIModel[];
const modelLabels: Record<OpenAIModel, string> = {
  "gpt-5.6-luna": "GPT-5.6 Luna",
  "gpt-5.6-terra": "GPT-5.6 Terra",
  "gpt-5.6-sol": "GPT-5.6 Sol",
  "gpt-5-mini": "GPT-5 Mini",
};
function isOpenAIModel(value: string): value is OpenAIModel {
  return models.some((model) => model === value);
}

export type CandidateQa = DatasetConversation["candidate_qa"];

export function DatasetChat({ datasetId }: { datasetId: number }) {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [groupTitle, setGroupTitle] = useState("");
  const [groupConfigs, setGroupConfigs] = useState(() => [
    {
      id: crypto.randomUUID(),
      agent_approach: "baseline" as AgentApproach,
      model: "gpt-5.6-luna" as OpenAIModel,
    },
    {
      id: crypto.randomUUID(),
      agent_approach: "baseline" as AgentApproach,
      model: "gpt-5.6-luna" as OpenAIModel,
    },
  ]);
  const groupsQuery = useQuery(chatSessionGroupListOptions(datasetId));
  const createGroup = useCreateChatSessionGroup(datasetId);
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Playground groups</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Compare durable chats with different approaches and models for this dataset.
          </p>
        </div>
        <Button onClick={() => setCreating((value) => !value)}>
          {creating ? "Cancel" : "New group"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {creating && (
          <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
            <div className="space-y-1">
              <label className="text-sm font-medium" htmlFor="group-title">
                Title (optional)
              </label>
              <input
                id="group-title"
                className="h-9 w-full rounded border bg-background px-2 text-sm"
                placeholder="Optional group title"
                value={groupTitle}
                onChange={(e) => setGroupTitle(e.target.value)}
              />
              <div className="space-y-2">
                {groupConfigs.map((config, index) => (
                  <div className="space-y-1 rounded border p-2" key={config.id}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium">Chat {index + 1}</span>
                      {groupConfigs.length > 2 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setGroupConfigs((items) => items.filter((_, i) => i !== index))
                          }
                        >
                          Remove
                        </Button>
                      )}
                    </div>
                    <Select
                      value={config.agent_approach}
                      onValueChange={(value) => {
                        if (isAgentApproach(value))
                          setGroupConfigs((items) =>
                            items.map((item, i) =>
                              i === index ? { ...item, agent_approach: value } : item,
                            ),
                          );
                      }}
                    >
                      <SelectTrigger aria-label={`Chat ${index + 1} approach`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {agentApproaches.map((approach) => (
                          <SelectItem key={approach} value={approach}>
                            {agentApproachLabels[approach]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={config.model}
                      onValueChange={(value) => {
                        if (isOpenAIModel(value))
                          setGroupConfigs((items) =>
                            items.map((item, i) =>
                              i === index ? { ...item, model: value } : item,
                            ),
                          );
                      }}
                    >
                      <SelectTrigger aria-label={`Chat ${index + 1} model`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {models.map((model) => (
                          <SelectItem key={model} value={model}>
                            {modelLabels[model]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
                {groupConfigs.length < 4 && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() =>
                      setGroupConfigs((items) => [
                        ...items,
                        { ...items[items.length - 1], id: crypto.randomUUID() },
                      ])
                    }
                  >
                    Add chat
                  </Button>
                )}
                <Button
                  className="w-full"
                  disabled={createGroup.isPending}
                  onClick={() =>
                    createGroup
                      .mutateAsync({
                        title: groupTitle.trim() || null,
                        sessions: groupConfigs.map(({ agent_approach, model }) => ({
                          agent_approach,
                          model,
                          tags: [],
                        })),
                      })
                      .then((group) =>
                        navigate({
                          to: "/chat-session-groups/$chatSessionGroupId",
                          params: { chatSessionGroupId: String(group.id) },
                        }),
                      )
                  }
                >
                  {createGroup.isPending ? "Creating…" : "Create group"}
                </Button>
              </div>
              {createGroup.isError && (
                <p className="text-xs text-destructive">{createGroup.error.message}</p>
              )}
            </div>
          </div>
        )}
        {groupsQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Loading playground groups…</p>
        )}
        {groupsQuery.isError && (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-destructive">
              Could not load playground groups.
            </p>
            <Button variant="outline" onClick={() => void groupsQuery.refetch()}>
              Retry
            </Button>
          </div>
        )}
        {!groupsQuery.isLoading &&
          !groupsQuery.isError &&
          (groupsQuery.data?.length ?? 0) === 0 && (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              No playground groups yet. Create one to compare chats.
            </p>
          )}
        <div className="grid gap-3 sm:grid-cols-2">
          {groupsQuery.data?.map((group) => (
            <button
              key={group.id}
              className="group rounded-lg border p-4 text-left transition-colors hover:border-primary hover:bg-muted/40"
              onClick={() =>
                void navigate({
                  to: "/chat-session-groups/$chatSessionGroupId",
                  params: { chatSessionGroupId: String(group.id) },
                })
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div className="font-medium">{group.title || `Playground group #${group.id}`}</div>
                <span
                  aria-hidden="true"
                  className="text-muted-foreground group-hover:text-foreground"
                >
                  →
                </span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {group.sessions?.length ?? 0} chats ·{" "}
                {[
                  ...new Set(
                    (group.sessions ?? []).map(
                      (s) => `${agentApproachLabels[s.agent_approach]} / ${modelLabels[s.model]}`,
                    ),
                  ),
                ].join(", ") || "No approaches"}
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                Updated {new Date(group.updated_at).toLocaleString()} · Created{" "}
                {new Date(group.created_at).toLocaleDateString()}
              </p>
            </button>
          ))}
        </div>
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

function displayToolName(name: string) {
  return name
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[._-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\w/, (character) => character.toUpperCase());
}

function displayToolValue(value: unknown) {
  if (typeof value === "string") return value;
  const json = JSON.stringify(value, null, 2);
  return json ?? String(value);
}

export function ToolActivity({ part }: { part: ToolCallPart | ToolResultPart }) {
  if (part.type === "tool-call") {
    return (
      <details className="my-1 min-w-0 text-xs">
        <summary
          aria-label={`Show arguments for ${displayToolName(part.name)}`}
          className="cursor-pointer list-none rounded-md outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden"
        >
          <Marker className="rounded-md border border-border/70 bg-muted/30 px-2 py-1.5 text-xs hover:bg-muted/50">
            <MarkerIcon>
              <Wrench />
            </MarkerIcon>
            <MarkerContent>
              <span className="font-medium text-foreground">{displayToolName(part.name)}</span>
              <span className="ml-2">{displayToolName(part.state)}</span>
            </MarkerContent>
          </Marker>
        </summary>
        <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-border/60 bg-muted/20 p-2 font-mono text-[0.7rem] leading-relaxed [overflow-wrap:anywhere]">
          {displayToolValue(part.arguments)}
        </pre>
      </details>
    );
  }
  const hasError = part.error !== undefined && part.error !== null;
  return (
    <details className="my-1 min-w-0 text-xs" open={hasError || undefined}>
      <summary
        aria-label={`Show tool result (${displayToolName(part.state)})`}
        className="cursor-pointer list-none rounded-md outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden"
      >
        <Marker
          className={
            hasError
              ? "rounded-md border border-destructive/40 bg-destructive/5 px-2 py-1.5 text-xs"
              : "rounded-md border border-border/70 bg-muted/30 px-2 py-1.5 text-xs hover:bg-muted/50"
          }
        >
          <MarkerIcon>{hasError ? <AlertCircle /> : <Check />}</MarkerIcon>
          <MarkerContent>
            <span className="font-medium text-foreground">Tool result</span>
            <span className="ml-2">{displayToolName(part.state)}</span>
          </MarkerContent>
        </Marker>
      </summary>
      <div className="mt-1 space-y-1 rounded-md border border-border/60 bg-muted/20 p-2 font-mono text-[0.7rem] leading-relaxed [overflow-wrap:anywhere]">
        <pre className="whitespace-pre-wrap">{displayToolValue(part.content)}</pre>
        {hasError ? (
          <pre className="whitespace-pre-wrap text-destructive">{displayToolValue(part.error)}</pre>
        ) : null}
      </div>
    </details>
  );
}

export type ChatTranscriptHandle = { send: (message: string) => Promise<boolean> };

export const ChatTranscript = forwardRef<
  ChatTranscriptHandle,
  {
    datasetId: number;
    sessionId: number;
    initialMessages: InitialMessage[];
    onDone: () => void;
    onError?: (error: Error) => void;
  }
>(({ datasetId, sessionId, initialMessages, onDone, onError }, ref) => {
  const [transcript, sendTranscript] = useMachine(datasetChatTranscriptMachine);
  const { input, sendError } = transcript.context;
  const sendErrorRef = useRef<Error | null>(null);
  const connection = useMemo(
    () => fetchServerSentEvents(chatRunUrl(datasetId, sessionId)),
    [datasetId, sessionId],
  );
  const chat = useChat({
    threadId: `dataset-${datasetId}-session-${sessionId}`,
    connection,
    initialMessages,
    onFinish: onDone,
    onError: (error) => {
      sendErrorRef.current = error;
      onError?.(error);
    },
  });
  const visibleMessages = chat.messages.filter(hasVisibleTextPart);
  const send = async (question = input) => {
    const draft = question.trim();
    if (!draft || chat.isLoading) return false;
    sendErrorRef.current = null;
    sendTranscript({ type: "send.started" });
    try {
      await chat.sendMessage(draft);
      if (sendErrorRef.current) throw sendErrorRef.current;
      sendTranscript({ type: "input.changed", value: "" });
      return true;
    } catch (e) {
      sendTranscript({
        type: "send.failed",
        draft,
        error: e instanceof Error ? e.message : "Message failed",
      });
      return false;
    }
  };
  useImperativeHandle(ref, () => ({ send: (message) => send(message) }), [send]);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <MessageScrollerProvider autoScroll defaultScrollPosition="last-anchor">
        <MessageScroller className="min-h-0 flex-1">
          <MessageScrollerViewport>
            <MessageScrollerContent className="pr-2" aria-busy={chat.isLoading}>
              {visibleMessages.length === 0 && (
                <MessageScrollerItem messageId="empty-transcript">
                  <p className="text-sm text-muted-foreground">
                    Ask a question about this financial dataset.
                  </p>
                </MessageScrollerItem>
              )}
              {visibleMessages.map((m) => (
                <MessageScrollerItem key={m.id} messageId={m.id} scrollAnchor={m.role === "user"}>
                  <Message align={m.role === "user" ? "end" : "start"}>
                    <MessageContent>
                      <MessageHeader className={m.role === "user" ? "justify-end" : undefined}>
                        {m.role === "user" ? "You" : "Assistant"}
                      </MessageHeader>
                      <div
                        className={
                          m.role === "user"
                            ? "ml-auto max-w-[37em] rounded-lg bg-muted px-3 py-2"
                            : "max-w-[44em] px-3 py-1"
                        }
                      >
                        <div className="space-y-2 whitespace-pre-wrap">
                          {m.parts.map((part) =>
                            part.type === "text" ? (
                              <span className="typeset typeset-docs" key={`${m.id}-${part.type}`}>
                                {part.content}
                              </span>
                            ) : part.type === "tool-call" || part.type === "tool-result" ? (
                              <ToolActivity
                                key={part.type === "tool-call" ? part.id : part.toolCallId}
                                part={part as ToolCallPart | ToolResultPart}
                              />
                            ) : null,
                          )}
                        </div>
                      </div>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ))}
              {chat.isLoading && (
                <MessageScrollerItem messageId="streaming-status">
                  {/* oxlint-disable-next-line jsx-a11y/prefer-tag-over-role -- status is the primitive's documented live-region contract. */}
                  <Marker role="status" className="px-3" aria-live="polite">
                    <MarkerIcon>
                      <LoaderCircle className="animate-spin" />
                    </MarkerIcon>
                    <MarkerContent>Agent is replying…</MarkerContent>
                  </Marker>
                </MessageScrollerItem>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>
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
});
ChatTranscript.displayName = "ChatTranscript";
