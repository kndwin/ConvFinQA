import { index, rootRoute, route } from "@tanstack/virtual-file-routes";

export default rootRoute("platform/router/root.route.ts", [
  index("module/dataset/dataset-conversation.route.ts"),
  route(
    "dataset-conversations/$datasetConversationId",
    "module/dataset/dataset-conversation-detail.route.ts",
  ),
  route(
    "chat-session-groups/$chatSessionGroupId",
    "module/chat-group/chat-session-group-detail.route.ts",
  ),
]);
