import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Button } from "@/platform/ui/button";
import { Badge } from "@/platform/ui/badge";
import { Card, CardContent } from "@/platform/ui/card";
import { chatSessionGroupDetailOptions } from "./chat-session-groups.query";
import { CandidateQaPanel, ChatTranscript, type ChatTranscriptHandle } from "./dataset-chat.ui";
import { datasetChatMessagesOptions, type PersistedMessage } from "./dataset-chat.query";
import { datasetConversationDetailOptions } from "./dataset-conversation.query";
import { DocumentContextPopover } from "./document-context-popover";

const initial = (messages: PersistedMessage[]) =>
  messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      id: String(m.id),
      role: m.role as "user" | "assistant",
      parts: [{ type: "text" as const, content: m.content }],
    }));

function GroupSessionCard({
  datasetId,
  session,
  onRef,
}: {
  datasetId: number;
  session: { id: number; agent_approach: string; model: string };
  onRef: (handle: ChatTranscriptHandle | null) => void;
}) {
  const messages = useQuery(datasetChatMessagesOptions(datasetId, session.id));
  return (
    <article className="flex min-h-[28rem] min-w-0 flex-col rounded-lg border p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm font-medium">
        <span>Session #{session.id}</span>
        <Badge variant="secondary">{session.agent_approach}</Badge>
        <Badge variant="outline">{session.model}</Badge>
      </div>
      {messages.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Transcript failed to load.
        </p>
      ) : messages.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading transcript…</p>
      ) : (
        <ChatTranscript
          ref={onRef}
          datasetId={datasetId}
          sessionId={session.id}
          initialMessages={initial(messages.data ?? [])}
          onDone={() => undefined}
        />
      )}
    </article>
  );
}

export function ChatSessionGroupDetailPage() {
  const params = useParams({ strict: false }) as {
    chatSessionGroupId: string;
  };
  const group = useQuery(chatSessionGroupDetailOptions(Number(params.chatSessionGroupId)));
  const datasetId = group.data?.dataset_conversation_id ?? 0;
  const dataset = useQuery(datasetConversationDetailOptions(datasetId));
  const handles = useRef(new Map<number, ChatTranscriptHandle>());
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const sendAll = async () => {
    const text = message.trim();
    if (!text || sending || !group.data) return;
    setSending(true);
    setSendError(null);
    const targets = (group.data.sessions ?? [])
      .map((session) => handles.current.get(session.id))
      .filter(Boolean) as ChatTranscriptHandle[];
    const results = await Promise.allSettled(targets.map((handle) => handle.send(text)));
    setSending(false);
    const failed = results.filter((result) => result.status === "rejected" || !result.value).length;
    if (failed)
      setSendError(
        `${failed} chat${failed === 1 ? "" : "s"} failed to send. See the affected card for details.`,
      );
    if (failed < results.length) setMessage("");
  };
  if (group.isLoading) return <main className="p-6">Loading playground group…</main>;
  if (group.isError || !group.data)
    return (
      <main className="p-6" role="alert">
        Playground group not found.
      </main>
    );
  return (
    <main className="mx-auto max-w-7xl space-y-6 p-6">
      <Link
        to="/dataset-conversations/$datasetConversationId"
        params={{ datasetConversationId: String(datasetId) }}
        className="text-sm text-muted-foreground"
      >
        Back to conversation
      </Link>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">
            {group.data.title ?? `Playground group #${group.data.id}`}
          </h1>
          <DocumentContextPopover docJson={dataset.data?.doc_json ?? null} />
        </div>
        <p className="text-sm text-muted-foreground">
          Durable chats for this dataset. Send explicitly to all.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {(group.data.sessions ?? []).map((session) => (
          <GroupSessionCard
            key={session.id}
            datasetId={datasetId}
            session={session}
            onRef={(handle) => {
              if (handle) handles.current.set(session.id, handle);
              else handles.current.delete(session.id);
            }}
          />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,24rem)]">
        <form
          className="flex min-w-0 gap-2 rounded-lg border p-4"
          onSubmit={(event) => {
            event.preventDefault();
            void sendAll();
          }}
        >
          <textarea
            className="min-h-12 min-w-0 flex-1 rounded-md border px-3 py-2"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Send a message to all chats"
            disabled={sending}
          />
          <Button
            type="submit"
            disabled={
              !message.trim() ||
              sending ||
              handles.current.size !== (group.data.sessions ?? []).length
            }
          >
            {sending ? "Sending…" : "Send to all"}
          </Button>
        </form>
        {dataset.isLoading ? (
          <Card>
            <CardContent className="p-4 text-sm text-muted-foreground">
              Loading Candidate Q&amp;A…
            </CardContent>
          </Card>
        ) : dataset.isError ? (
          <Card>
            <CardContent className="p-4 text-sm text-destructive">
              Dataset context could not be loaded.
            </CardContent>
          </Card>
        ) : (
          <CandidateQaPanel candidateQa={dataset.data?.candidate_qa ?? []} />
        )}
      </div>
      {sendError && (
        <p role="alert" className="text-sm text-destructive">
          {sendError}
        </p>
      )}
    </main>
  );
}
