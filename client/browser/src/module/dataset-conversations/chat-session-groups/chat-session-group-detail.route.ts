import { createFileRoute } from "@tanstack/react-router";
import { ChatSessionGroupDetailPage } from "./chat-session-group-detail.page";

export const Route = createFileRoute("/chat-session-groups/$chatSessionGroupId")({
  component: ChatSessionGroupDetailPage,
});
