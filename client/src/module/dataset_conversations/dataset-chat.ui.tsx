import { useMachine } from "@xstate/react";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { useChat } from "@tanstack/ai-react";
import { fetchServerSentEvents } from "@tanstack/ai-client";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
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
const agentApproaches = ["baseline", "baseline-tool"] as const satisfies readonly AgentApproach[];
const agentApproachLabels: Record<AgentApproach, string> = {
  baseline: "Baseline",
  "baseline-tool": "Baseline + tool",
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
  const bottomRef = useRef<HTMLDivElement>(null);
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
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chat.messages, chat.isLoading]);
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
});
ChatTranscript.displayName = "ChatTranscript";
