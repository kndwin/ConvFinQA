import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { openapiClient } from "@/platform/api/openapi-client";
import type { components } from "@/platform/api/openapi-schema";

export const chatSessionGroupQueries = {
  all: ["chat-session-groups"] as const,
  list: (datasetConversationId: number) =>
    [...chatSessionGroupQueries.all, "list", datasetConversationId] as const,
  detail: (id: number) => [...chatSessionGroupQueries.all, "detail", id] as const,
};

export function chatSessionGroupListOptions(datasetConversationId: number) {
  return queryOptions({
    queryKey: chatSessionGroupQueries.list(datasetConversationId),
    queryFn: async () => {
      const result = await openapiClient.GET(
        "/dataset-conversations/{dataset_conversation_id}/chat-session-groups",
        { params: { path: { dataset_conversation_id: datasetConversationId } } },
      );
      if (result.error) throw new Error("Could not load playground groups");
      return result.data ?? [];
    },
  });
}

export function chatSessionGroupDetailOptions(id: number) {
  return queryOptions({
    queryKey: chatSessionGroupQueries.detail(id),
    enabled: id > 0,
    queryFn: async () => {
      const result = await openapiClient.GET("/chat-session-groups/{chat_session_group_id}", {
        params: { path: { chat_session_group_id: id } },
      });
      if (result.error || !result.data) throw new Error("Could not load playground group");
      return result.data;
    },
  });
}

export function useCreateChatSessionGroup(datasetConversationId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: components["schemas"]["ChatSessionGroupCreateRequest"]) => {
      const result = await openapiClient.POST("/dataset-conversations/{dataset_conversation_id}/chat-session-groups", {
        params: { path: { dataset_conversation_id: datasetConversationId } },
        body,
      });
      if (result.error || !result.data) throw new Error("Could not create playground group");
      return result.data;
    },
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: chatSessionGroupQueries.list(datasetConversationId),
      }),
  });
}

export function useRenameChatSessionGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: number; title: string | null }) =>
      openapiClient.PATCH("/chat-session-groups/{chat_session_group_id}", {
        params: { path: { chat_session_group_id: id } },
        body: { title },
      }),
    onSuccess: (result) => {
      if (result.data)
        queryClient.setQueryData(chatSessionGroupQueries.detail(result.data.id), result.data);
    },
  });
}

export function useDeleteChatSessionGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      deleteChatSessions = false,
    }: {
      id: number;
      deleteChatSessions?: boolean;
    }) =>
      openapiClient.DELETE("/chat-session-groups/{chat_session_group_id}", {
        params: {
          path: { chat_session_group_id: id },
          query: { delete_chat_sessions: deleteChatSessions },
        },
      }),
    onSuccess: (_result, variables) =>
      queryClient.removeQueries({ queryKey: chatSessionGroupQueries.detail(variables.id) }),
  });
}
