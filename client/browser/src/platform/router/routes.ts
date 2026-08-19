import { index, rootRoute, route } from "@tanstack/virtual-file-routes";

export default rootRoute("platform/router/root.route.ts", [
  index("module/dataset-conversations/list/dataset-conversation.route.ts"),
  route(
    "dataset-conversations/$datasetConversationId",
    "module/dataset-conversations/detail/dataset-conversation-detail.route.ts",
  ),
  route(
    "chat-session-groups/$chatSessionGroupId",
    "module/dataset-conversations/chat-session-groups/chat-session-group-detail.route.ts",
  ),
]);
