import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { DatasetConversationPage } from "./dataset-conversation.ui";

export const explorerSearchSchema = z.object({
  q: z.string().catch(""),
  split: z.string().min(1).catch("all"),
  page: z.coerce.number().int().positive().catch(1),
});

export type ExplorerSearch = z.infer<typeof explorerSearchSchema>;

export const Route = createFileRoute("/")({
  validateSearch: explorerSearchSchema,
  component: DatasetConversationPage,
});
