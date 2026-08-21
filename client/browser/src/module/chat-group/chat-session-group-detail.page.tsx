import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { match } from "ts-pattern";
import { Link } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Button } from "@/platform/ui/button";
import { Badge } from "@/platform/ui/badge";
import { Card, CardContent } from "@/platform/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/platform/ui/popover";
import { ChatSessionTags } from "../chat-session/chat-session-tags.ui";
import { openapiClient } from "@/platform/api/openapi-client";
import type { components } from "@/platform/api/openapi-schema";
import { chatSessionGroupDetailOptions } from "./chat-group.query";
import {
  CandidateQaPanel,
  ChatTranscript,
  type ChatTranscriptHandle,
} from "../chat-session/chat-session.ui";
import type { AgentApproach } from "../chat-session/chat-session.query";
import { chatSessionMessagesOptions } from "../chat-session/chat-session.query";
import { datasetConversationDetailOptions } from "../dataset/dataset-conversation.query";
import { DocumentContextPopover } from "../dataset/document-context-popover.ui";
import { transformPersistedMessages } from "./chat-session-group-detail.util";
import { chatSessionGroupQueries } from "./chat-group.query";

function GroupSessionCard({
  datasetId,
  groupId,
  session,
  onRef,
}: {
  datasetId: number;
  groupId: number;
  session: {
    id: number;
    agent_approach: AgentApproach;
    model: string;
    tags?: { value: string }[];
  };
  onRef: (handle: ChatTranscriptHandle | null) => void;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [tags, setTags] = useState(
    (session.tags ?? []).map((tag) => tag.value),
  );
  const serverTags = useRef(tags);
  const [tagError, setTagError] = useState<string | null>(null);
  const updateTags = useMutation({
    mutationFn: async (nextTags: string[]) => {
      const result = await openapiClient.PATCH(
        "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}",
        {
          params: {
            path: {
              dataset_conversation_id: datasetId,
              chat_session_id: session.id,
            },
          },
          body: { tags: nextTags.map((value) => ({ value })) },
        },
      );
      if (result.error || !result.data)
        throw new Error("Could not update tags");
      return result.data;
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<
        components["schemas"]["ChatSessionGroupResponse"]
      >(chatSessionGroupQueries.detail(groupId), (group) =>
        group
          ? {
              ...group,
              sessions: (group.sessions ?? []).map((item) =>
                item.id === updated.id ? updated : item,
              ),
            }
          : group,
      );
      setTags((updated.tags ?? []).map((tag) => tag.value));
      serverTags.current = (updated.tags ?? []).map((tag) => tag.value);
      setEditing(false);
      setTagError(null);
    },
    onError: (error) =>
      setTagError(
        error instanceof Error ? error.message : "Could not update tags",
      ),
  });
  const messagesQuery = useQuery(
    chatSessionMessagesOptions(datasetId, session.id),
  );
  const handleEditingChange = (open: boolean) => {
    if (!open && !updateTags.isPending) {
      setTags(serverTags.current);
      setTagError(null);
    }
    setEditing(open);
  };
  return (
    <article className="flex h-[32rem] min-h-0 min-w-0 flex-col rounded-lg border p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm font-medium">
        <span>Session #{session.id}</span>
        <Popover open={editing} onOpenChange={handleEditingChange}>
          <PopoverTrigger asChild>
            <Button type="button" variant="outline" size="sm">
              Edit tags
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start">
            <ChatSessionTags
              id={`edit-tags-${session.id}`}
              value={tags}
              onChange={setTags}
            />
            <Button
              type="button"
              className="mt-3 w-full"
              disabled={updateTags.isPending}
              onClick={() => updateTags.mutate(tags)}
            >
              {updateTags.isPending ? "Saving…" : "Save tags"}
            </Button>
            {tagError && (
              <p role="alert" className="mt-2 text-xs text-destructive">
                {tagError}
              </p>
            )}
          </PopoverContent>
        </Popover>
        <Badge variant="secondary">{session.agent_approach}</Badge>
        <Badge variant="outline">{session.model}</Badge>
        {(session.tags ?? []).map((tag) => (
          <Badge key={tag.value} variant="outline">
            {tag.value}
          </Badge>
        ))}
      </div>
      {match(messagesQuery)
        .with({ status: "pending" }, () => (
          <p className="text-sm text-muted-foreground">Loading transcript…</p>
        ))
        .with({ status: "error" }, () => (
          <p role="alert" className="text-sm text-destructive">
            Transcript failed to load.
          </p>
        ))
        .with({ status: "success" }, ({ data }) => (
          <ChatTranscript
            ref={onRef}
            datasetId={datasetId}
            sessionId={session.id}
            initialMessages={transformPersistedMessages({ messages: data })}
            onDone={() => undefined}
          />
        ))
        .exhaustive()}
    </article>
  );
}

export function ChatSessionGroupDetailPage({
  chatSessionGroupId,
}: {
  chatSessionGroupId: string;
}) {
  const groupQuery = useQuery(
    chatSessionGroupDetailOptions(Number(chatSessionGroupId)),
  );
  const datasetId = groupQuery.data?.dataset_conversation_id ?? 0;
  const datasetQuery = useQuery(datasetConversationDetailOptions(datasetId));
  const handles = useRef(new Map<number, ChatTranscriptHandle>());
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const sendAll = async () => {
    const text = message.trim();
    if (!text || sending || !groupQuery.data) return;
    setSending(true);
    setSendError(null);
    const targets = (groupQuery.data.sessions ?? [])
      .map((session) => handles.current.get(session.id))
      .filter(Boolean) as ChatTranscriptHandle[];
    const results = await Promise.allSettled(
      targets.map((handle) => handle.send(text)),
    );
    setSending(false);
    const failed = results.filter(
      (result) => result.status === "rejected" || !result.value,
    ).length;
    if (failed)
      setSendError(
        `${failed} chat${failed === 1 ? "" : "s"} failed to send. See the affected card for details.`,
      );
    if (failed < results.length) setMessage("");
  };
  if (groupQuery.isLoading)
    return <main className="p-6">Loading playground group…</main>;
  if (groupQuery.isError || !groupQuery.data)
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
            {groupQuery.data.title ?? `Playground group #${groupQuery.data.id}`}
          </h1>
          <DocumentContextPopover
            docJson={datasetQuery.data?.doc_json ?? null}
          />
        </div>
        <p className="text-sm text-muted-foreground">
          Direct chats for this dataset. Send explicitly to all.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {(groupQuery.data.sessions ?? []).map((session) => (
          <GroupSessionCard
            key={session.id}
            datasetId={datasetId}
            groupId={groupQuery.data.id}
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
              handles.current.size !== (groupQuery.data.sessions ?? []).length
            }
          >
            {sending ? "Sending…" : "Send to all"}
          </Button>
        </form>
        {match(datasetQuery)
          .with({ status: "pending" }, () => (
            <Card>
              <CardContent className="p-4 text-sm text-muted-foreground">
                Loading Candidate Q&amp;A…
              </CardContent>
            </Card>
          ))
          .with({ status: "error" }, () => (
            <Card>
              <CardContent className="p-4 text-sm text-destructive">
                Dataset context could not be loaded.
              </CardContent>
            </Card>
          ))
          .with({ status: "success" }, ({ data }) => (
            <CandidateQaPanel candidateQa={data?.candidate_qa ?? []} />
          ))
          .exhaustive()}
      </div>
      {sendError && (
        <p role="alert" className="text-sm text-destructive">
          {sendError}
        </p>
      )}
    </main>
  );
}
