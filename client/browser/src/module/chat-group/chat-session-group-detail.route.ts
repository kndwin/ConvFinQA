import { createFileRoute } from "@tanstack/react-router";
import { ChatSessionGroupDetailRoute } from "./chat-session-group-detail.route-adapter";

export const Route = createFileRoute("/chat-session-groups/$chatSessionGroupId")({
  component: ChatSessionGroupDetailRoute,
});
