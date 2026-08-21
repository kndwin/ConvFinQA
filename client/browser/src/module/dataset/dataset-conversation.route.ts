import { createFileRoute } from "@tanstack/react-router";
import { DatasetConversationPage } from "./dataset-conversation.ui";
import { explorerSearchSchema } from "./dataset-conversation-search.schema";

export const Route = createFileRoute("/")({
  validateSearch: explorerSearchSchema,
  component: DatasetConversationPage,
});
