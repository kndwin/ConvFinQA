import { useMachine } from "@xstate/react";
import { forwardRef, useImperativeHandle, useMemo, useRef } from "react";
import { useChat } from "@tanstack/ai-react";
import { fetchServerSentEvents } from "@tanstack/ai-client";
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
import { MarkdownContent } from "@/platform/ui/markdown";
import { AlertCircle, Check, LoaderCircle, Wrench } from "lucide-react";
import { chatSessionRunUrl } from "./chat-session.query";
import { chatSessionTranscriptMachine } from "./chat-session.machine";

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

export type CandidateQa = { question: string; answer: string | null }[];

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
  const [transcript, sendTranscript] = useMachine(chatSessionTranscriptMachine);
  const { input, sendError } = transcript.context;
  const sendErrorRef = useRef<Error | null>(null);
  const connection = useMemo(
    () => fetchServerSentEvents(chatSessionRunUrl(datasetId, sessionId)),
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
  const cancel = () => chat.stop();
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
                        <div className="space-y-2">
                          {m.parts.map((part) =>
                            part.type === "text" ? (
                              <MarkdownContent key={`${m.id}-${part.type}`}>
                                {part.content}
                              </MarkdownContent>
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
          <Button type="button" onClick={() => void cancel()}>
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
