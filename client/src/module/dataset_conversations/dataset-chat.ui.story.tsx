import type { Meta, StoryObj } from "@storybook/react-vite";
import type { OpenAIModel } from "./dataset-chat.query";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Button } from "@/platform/ui/button";
import { ScrollArea } from "@/platform/ui/scroll-area";
import { AgentReplyingIndicator, CandidateQaPanel, DatasetChat } from "./dataset-chat.ui";
import { datasetChatMessagesOptions, datasetChatSessionsOptions } from "./dataset-chat.query";
import type { Session, PersistedMessage } from "./dataset-chat.query";
import { chatSessionGroupListOptions } from "./chat-session-groups.query";

const datasetId = 42;
const session = {
  id: 7,
  dataset_conversation_id: datasetId,
  agent_approach: "baseline",
  prompt_version: "baseline:v1",
  context_version: "document-conversation:v1",
  model: "gpt-5.6-luna" satisfies OpenAIModel,
  title: "Revenue question",
  created_at: "2024-01-01T12:00:00Z",
  updated_at: "2024-01-02T12:00:00Z",
} satisfies Session;
const messages = [
  {
    id: 1,
    chat_session_id: 7,
    role: "user",
    content: "What changed?",
    created_at: "2024-01-02T12:00:00Z",
  },
  {
    id: 2,
    chat_session_id: 7,
    role: "assistant",
    content: "Revenue increased by 8%.",
    created_at: "2024-01-02T12:00:01Z",
  },
] satisfies PersistedMessage[];
const candidateQa = [
  { question: "What changed?", answer: "Revenue increased by 8%." },
  { question: "What explains the change?", answer: null },
];

function FixtureProvider({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  client.setQueryData(datasetChatSessionsOptions(datasetId).queryKey, [session]);
  client.setQueryData(datasetChatMessagesOptions(datasetId, session.id).queryKey, messages);
  client.setQueryData(chatSessionGroupListOptions(datasetId).queryKey, []);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const meta = {
  title: "Dataset Conversations/Chat",
  component: DatasetChat,
  decorators: [
    (Story) => (
      <FixtureProvider>
        <Story />
      </FixtureProvider>
    ),
  ],
} satisfies Meta<typeof DatasetChat>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {
  args: {
    datasetId,
  },
};

export const Replying: Story = {
  args: {
    datasetId,
  },
  render: () => (
    <div className="grid h-[32rem] w-full max-w-4xl gap-4 md:grid-cols-[minmax(0,1fr)_minmax(220px,300px)]">
      <div className="flex min-h-0 flex-col rounded-lg border p-4">
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-3 whitespace-pre-wrap break-words pr-4 [overflow-wrap:anywhere]">
            {messages.map((message) => (
              <div
                className={`rounded-lg p-3 ${message.role === "user" ? "ml-8 bg-muted" : "mr-8 border"}`}
                key={message.id}
              >
                <div className="typeset typeset-docs max-w-[37em]">{message.content}</div>
              </div>
            ))}
            <div className="ml-8 rounded-lg bg-muted p-3">
              <div className="typeset typeset-docs max-w-[37em]">
                How should we interpret this increase?
              </div>
            </div>
            <AgentReplyingIndicator />
          </div>
        </ScrollArea>
        <form className="mt-4 flex shrink-0 gap-2 border-t pt-4">
          <textarea
            aria-label="Message"
            className="min-h-12 flex-1 resize-none rounded border bg-background p-2 text-sm"
            disabled
            placeholder="Ask about the record…"
            value=""
            readOnly
          />
          <Button type="button">Stop</Button>
        </form>
      </div>
      <CandidateQaPanel candidateQa={candidateQa} />
    </div>
  ),
};
