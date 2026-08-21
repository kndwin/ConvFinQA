import { createFileRoute } from "@tanstack/react-router";
import { DatasetConversationDetailPage } from "./dataset-conversation-detail.page";

export const Route = createFileRoute("/dataset-conversations/$datasetConversationId")({
  component: DatasetConversationDetailPage,
});
