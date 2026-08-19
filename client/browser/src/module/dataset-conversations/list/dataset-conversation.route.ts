import { createFileRoute } from "@tanstack/react-router";
import { DatasetConversationPage } from "./dataset-conversation.ui";
import { explorerSearchSchema } from "./dataset-conversation-search.model";

export const Route = createFileRoute("/")({
  validateSearch: explorerSearchSchema,
  component: DatasetConversationPage,
});
