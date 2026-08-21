import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Button } from "@/platform/ui/button";
import { Badge, badgeVariants } from "@/platform/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/platform/ui/select";
import type { AgentApproach, OpenAIModel } from "../chat-session/chat-session.query";
import { chatSessionGroupListOptions, useCreateChatSessionGroup } from "./chat-group.query";
import { ChatSessionTags } from "../chat-session/chat-session-tags.ui";
import { ChatTranscript } from "../chat-session/chat-session.ui";
import {
  chatSessionCreateOptions,
  chatSessionMessagesOptions,
} from "../chat-session/chat-session.query";
import { transformPersistedMessages } from "./chat-session-group-detail.util";

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
type GroupConfig = {
  id: string;
  agent_approach: AgentApproach;
  model: OpenAIModel;
  tags: string[];
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

export function ChatGroupPanel({ datasetId }: { datasetId: number }) {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const [creatingChat, setCreatingChat] = useState(false);
  const [chatTags, setChatTags] = useState<string[]>([]);
  const [session, setSession] = useState<{ id: number; tags: string[] }>();
  const [groupTitle, setGroupTitle] = useState("");
  const [groupConfigs, setGroupConfigs] = useState<GroupConfig[]>(() => [
    {
      id: crypto.randomUUID(),
      agent_approach: "baseline" as AgentApproach,
      model: "gpt-5.6-luna" as OpenAIModel,
      tags: [],
    },
    {
      id: crypto.randomUUID(),
      agent_approach: "baseline" as AgentApproach,
      model: "gpt-5.6-luna" as OpenAIModel,
      tags: [],
    },
  ]);
  const groupsQuery = useQuery(chatSessionGroupListOptions(datasetId));
  const createGroup = useCreateChatSessionGroup(datasetId);
  const createChat = useMutation(chatSessionCreateOptions(datasetId));
  const messagesQuery = useQuery(chatSessionMessagesOptions(datasetId, session?.id));
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Playground groups</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Compare chats with different approaches and models for this dataset.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setCreatingChat((value) => !value)}>
            {creatingChat ? "Cancel" : "New chat"}
          </Button>
          <Button onClick={() => setCreating((value) => !value)}>
            {creating ? "Cancel" : "New group"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {creatingChat && !session && (
          <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
            <p className="text-sm font-medium">Start a chat</p>
            <ChatSessionTags id="normal-chat-tags" value={chatTags} onChange={setChatTags} />
            <Button
              disabled={createChat.isPending}
              onClick={() =>
                void createChat
                  .mutateAsync({ approach: "baseline", model: "gpt-5.6-luna", tags: chatTags })
                  .then((created) =>
                    setSession({
                      id: created.id,
                      tags: (created.tags ?? []).map((tag) => tag.value),
                    }),
                  )
              }
            >
              {createChat.isPending ? "Starting…" : "Start chat"}
            </Button>
            {createChat.isError && (
              <p role="alert" className="text-xs text-destructive">
                {createChat.error.message}
              </p>
            )}
          </div>
        )}
        {session && messagesQuery.data && (
          <div className="h-[32rem] rounded-lg border p-4">
            <div className="mb-3 flex flex-wrap gap-1">
              <span className="mr-1 text-sm font-medium">Session #{session.id}</span>
              {session.tags.map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
            <ChatTranscript
              datasetId={datasetId}
              sessionId={session.id}
              initialMessages={transformPersistedMessages({ messages: messagesQuery.data })}
              onDone={() => undefined}
            />
          </div>
        )}
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
                              i === index
                                ? {
                                    ...item,
                                    agent_approach: value,
                                  }
                                : item,
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
                    <ChatSessionTags
                      id={`group-chat-${config.id}`}
                      value={config.tags}
                      onChange={(tags) =>
                        setGroupConfigs((items) =>
                          items.map((item, i) => (i === index ? { ...item, tags } : item)),
                        )
                      }
                    />
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
                        {
                          ...items[items.length - 1],
                          id: crypto.randomUUID(),
                        },
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
                        sessions: groupConfigs.map(({ agent_approach, model, tags }) => ({
                          agent_approach,
                          model,
                          tags: tags.map((value) => ({ value })),
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
              <div className="mt-2 flex flex-wrap gap-1">
                {[
                  ...new Set(
                    (group.sessions ?? []).flatMap((groupSession) =>
                      (groupSession.tags ?? []).map((tag) => tag.value),
                    ),
                  ),
                ].map((tag) => (
                  <span key={tag} className={badgeVariants({ variant: "secondary" })}>
                    {tag}
                  </span>
                ))}
              </div>
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
