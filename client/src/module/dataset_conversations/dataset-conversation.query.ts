import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { openapiClient } from "@/platform/api/openapi-client";
import { datasetConversationSchema } from "./dataset-conversation.model";

const idSchema = z.number().int().positive();
const paginationSchema = z.object({
  offset: z.number().int().nonnegative().default(0),
  limit: z
    .number()
    .int()
    .positive()
    .default(100)
    .transform((value) => Math.min(value, 100)),
});

export const datasetConversationQueries = {
  all: ["dataset-conversations"] as const,
  list: (pagination: { offset?: number; limit?: number } = {}) => {
    const parsed = paginationSchema.parse(pagination);
    return [...datasetConversationQueries.all, "list", parsed] as const;
  },
  detail: (id: number) => [...datasetConversationQueries.all, "detail", id] as const,
};

function paginationFor(options: { offset?: number; limit?: number }) {
  return paginationSchema.parse(options);
}

export function datasetConversationListOptions(options: { offset?: number; limit?: number } = {}) {
  const pagination = paginationFor(options);
  return queryOptions({
    queryKey: datasetConversationQueries.list(pagination),
    queryFn: async () => {
      const response = await openapiClient.GET("/dataset-conversations", {
        params: { query: pagination },
      });
      if (response.error) {
        throw new Error(
          "The dataset conversation service could not be reached. Check the API URL and server status.",
        );
      }
      return datasetConversationSchema.array().parse(response.data ?? []);
    },
  });
}

export function datasetConversationDetailOptions(id: number) {
  const valid = idSchema.safeParse(id).success;
  return queryOptions({
    queryKey: datasetConversationQueries.detail(id),
    enabled: valid,
    queryFn: async () => {
      if (!valid) return null;
      const response = await openapiClient.GET("/dataset-conversations/{dataset_conversation_id}", {
        params: { path: { dataset_conversation_id: id } },
      });
      if (response.response.status === 404) return null;
      if (response.error || !response.data) {
        throw new Error("The requested dataset conversation could not be loaded.");
      }
      return datasetConversationSchema.parse(response.data);
    },
  });
}
