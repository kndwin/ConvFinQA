import { mutationOptions, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { openapiClient } from "@/platform/api/openapi-client";
import type { components } from "@/platform/api/openapi-schema";

const idSchema = z.number().int().positive();
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api";

export const chatRunUrl = (datasetId: number, sessionId: number) =>
  `${apiBaseUrl.replace(/\/$/, "")}/dataset-conversations/${datasetId}/chat-sessions/${sessionId}/runs`;

export type Session = components["schemas"]["ChatSessionResponse"];
export type PersistedMessage = components["schemas"]["ChatMessageResponse"];
export type AgentApproach = components["schemas"]["AgentApproach"];
export type OpenAIModel = components["schemas"]["OpenAIModel"];

export const datasetChatQueries = {
  all: ["dataset-chat"] as const,
  sessions: (datasetId: number) => [...datasetChatQueries.all, "sessions", datasetId] as const,
  messages: (datasetId: number, sessionId: number) =>
    [...datasetChatQueries.all, "messages", datasetId, sessionId] as const,
};

export function datasetChatSessionsOptions(datasetId: number) {
  const valid = idSchema.safeParse(datasetId).success;
  return queryOptions({
    queryKey: datasetChatQueries.sessions(datasetId),
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

export function datasetChatMessagesOptions(datasetId: number, sessionId: number | undefined) {
  const valid = idSchema.safeParse(datasetId).success && idSchema.safeParse(sessionId).success;
  return queryOptions({
    queryKey: datasetChatQueries.messages(datasetId, sessionId ?? 0),
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

export function datasetChatCreateSessionOptions(datasetId: number) {
  const valid = idSchema.safeParse(datasetId).success;
  return mutationOptions({
    mutationFn: async (selection: { approach: AgentApproach; model: OpenAIModel }) => {
      if (!valid) throw new Error("A valid dataset is required to start a chat.");
      const { data, error } = await openapiClient.POST(
        "/dataset-conversations/{dataset_conversation_id}/chat-sessions",
        {
          params: { path: { dataset_conversation_id: datasetId } },
          body: { agent_approach: selection.approach, model: selection.model },
        },
      );
      if (error || !data) throw new Error("Unable to create chat. Please try again.");
      return data;
    },
  });
}
