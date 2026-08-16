import { useMachine } from "@xstate/react";
import { useQuery } from "@tanstack/react-query";
import { getRouteApi } from "@tanstack/react-router";
import { DatasetConversationDetail } from "./dataset-conversation-detail.ui";
import { datasetConversationDetailMachine } from "./dataset-conversation-detail.machine";
import { datasetConversationDetailOptions } from "./dataset-conversation.query";
import { DatasetChat } from "./dataset-chat.ui";

const routeApi = getRouteApi("/dataset-conversations/$datasetConversationId");

export function DatasetConversationDetailPage() {
  const { datasetConversationId } = routeApi.useParams();
  const navigate = routeApi.useNavigate();
  const [snapshot, send] = useMachine(datasetConversationDetailMachine);
  const id = Number(datasetConversationId);
  const valid = Number.isInteger(id) && id > 0;
  const detailQuery = useQuery(datasetConversationDetailOptions(id));

  const onBack = () => void navigate({ to: "/", search: { q: "", split: "all", page: 1 } });

  if (!valid) {
    return <DatasetConversationDetail state={{ status: "invalid" }} onBack={onBack} />;
  }
  if (detailQuery.isLoading) {
    return <DatasetConversationDetail state={{ status: "loading" }} onBack={onBack} />;
  }
  if (detailQuery.isError) {
    return (
      <DatasetConversationDetail
        state={{
          status: "error",
          onRetry: () => void detailQuery.refetch(),
        }}
        onBack={onBack}
      />
    );
  }

  const item = detailQuery.data;
  if (!item) {
    return <DatasetConversationDetail state={{ status: "not-found" }} onBack={onBack} />;
  }

  return (
    <DatasetConversationDetail
      state={{
        status: "ready",
        item,
        chat: <DatasetChat datasetId={item.id!} />,
        activeTab: snapshot.matches({ tab: "record" }) ? "record" : "chat-sessions",
        onTabChange: (tab) =>
          send({
            type: tab === "record" ? "tab.recordSelected" : "tab.chatSessionsSelected",
          }),
        rawPayloadOpen: snapshot.matches({ rawPayload: "open" }),
        onRawPayloadToggle: () => send({ type: "rawPayload.toggled" }),
      }}
      onBack={onBack}
    />
  );
}
