import { mutationOptions, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { openapiClient } from "@/platform/api/openapi-client";
import type { components } from "@/platform/api/openapi-schema";

const idSchema = z.number().int().positive();
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";

export const chatSessionRunUrl = (datasetId: number, sessionId: number) =>
  `${apiBaseUrl.replace(/\/$/, "")}/dataset-conversations/${datasetId}/chat-sessions/${sessionId}/runs`;

export type Session = components["schemas"]["ChatSessionResponse"];
export type PersistedMessage = components["schemas"]["ChatMessageResponse"];
export type AgentApproach = components["schemas"]["AgentApproach"];
export type OpenAIModel = components["schemas"]["OpenAIModel"];

export function chatSessionTagsOptions() {
  return {
    queryKey: ["chat-session-tags", "suggestions"] as const,
    queryFn: async () => {
      const result = await openapiClient.GET("/chat-session-tags", {
        params: { query: { limit: 100 } },
      });
      if (result.error) throw new Error("Could not load tag suggestions.");
      return result.data ?? [];
    },
    staleTime: 60_000,
  };
}

export const chatSessionQueries = {
  all: ["chat-sessions"] as const,
  sessions: (datasetId: number) => [...chatSessionQueries.all, "sessions", datasetId] as const,
  messages: (datasetId: number, sessionId: number) =>
    [...chatSessionQueries.all, "messages", datasetId, sessionId] as const,
};

export function chatSessionListOptions(datasetId: number) {
  const valid = idSchema.safeParse(datasetId).success;
  return queryOptions({
    queryKey: chatSessionQueries.sessions(datasetId),
    enabled: valid,
    queryFn: async () => {
      if (!valid) return [] as Session[];
      const { data, error } = await openapiClient.GET(
        "/dataset-conversations/{dataset_conversation_id}/chat-sessions",
        { params: { path: { dataset_conversation_id: datasetId } } },
      );
      if (error || !data) throw new Error("Unable to load chat history. Please try again.");
      return data;
    },
  });
}

export function chatSessionMessagesOptions(datasetId: number, sessionId: number | undefined) {
  const valid = idSchema.safeParse(datasetId).success && idSchema.safeParse(sessionId).success;
  return queryOptions({
    queryKey: chatSessionQueries.messages(datasetId, sessionId ?? 0),
    enabled: valid,
    queryFn: async () => {
      if (!valid || sessionId === undefined) return [] as PersistedMessage[];
      const { data, error } = await openapiClient.GET(
        "/dataset-conversations/{dataset_conversation_id}/chat-sessions/{chat_session_id}/messages",
        {
          params: {
            path: { dataset_conversation_id: datasetId, chat_session_id: sessionId },
          },
        },
      );
      if (error || !data) throw new Error("Unable to load the transcript. Please try again.");
      return data;
    },
  });
}

export function chatSessionCreateOptions(datasetId: number) {
  const valid = idSchema.safeParse(datasetId).success;
  return mutationOptions({
    mutationFn: async (selection: {
      approach: AgentApproach;
      model: OpenAIModel;
      tags?: string[];
    }) => {
      if (!valid) throw new Error("A valid dataset is required to start a chat.");
      const { data, error } = await openapiClient.POST(
        "/dataset-conversations/{dataset_conversation_id}/chat-sessions",
        {
          params: { path: { dataset_conversation_id: datasetId } },
          body: {
            agent_approach: selection.approach,
            model: selection.model,
            tags: selection.tags?.map((value) => ({ value })),
          },
        },
      );
      if (error || !data) throw new Error("Unable to create chat. Please try again.");
      return data;
    },
  });
}
