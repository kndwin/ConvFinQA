import { getRouteApi } from "@tanstack/react-router";
import { ChatSessionGroupDetailPage } from "./chat-session-group-detail.page";

const routeApi = getRouteApi("/chat-session-groups/$chatSessionGroupId");

export function ChatSessionGroupDetailRoute() {
  const { chatSessionGroupId } = routeApi.useParams();
  return <ChatSessionGroupDetailPage chatSessionGroupId={chatSessionGroupId} />;
}
