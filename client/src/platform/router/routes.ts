import { index, rootRoute, route } from "@tanstack/virtual-file-routes";

export default rootRoute("platform/router/root.route.ts", [
  index("module/dataset_conversations/dataset-conversation.route.ts"),
  route(
    "dataset-conversations/$datasetConversationId",
    "module/dataset_conversations/dataset-conversation-detail.route.ts",
  ),
  route(
    "chat-session-groups/$chatSessionGroupId",
    "chat-session-groups.$chatSessionGroupId.route.ts",
  ),
]);
