import type { Meta, StoryObj } from "@storybook/react-vite";
import type { OpenAIModel } from "./dataset-chat.query";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Button } from "@/platform/ui/button";
import { ScrollArea } from "@/platform/ui/scroll-area";
import { AgentReplyingIndicator, CandidateQaPanel, DatasetChat } from "./dataset-chat.ui";
import { datasetChatMessagesOptions, datasetChatSessionsOptions } from "./dataset-chat.query";
import type { Session, PersistedMessage } from "./dataset-chat.query";
import { chatSessionGroupListOptions } from "../chat-session-groups/chat-session-groups.query";
import { Message, MessageContent, MessageHeader } from "@/platform/ui/message";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/platform/ui/message-scroller";
import { CircleDot } from "lucide-react";
import { ToolActivity } from "./dataset-chat.ui";

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

export const MessageScrollerPreview: Story = {
  args: { datasetId },
  render: () => (
    <div className="h-[34rem] w-full max-w-2xl rounded-lg border bg-background p-4">
      <MessageScrollerProvider autoScroll defaultScrollPosition="last-anchor">
        <MessageScroller>
          <MessageScrollerViewport>
            <MessageScrollerContent className="pr-2">
              {[
                ["user", "Summarize the latest revenue movement."],
                ["assistant", "Revenue is up 8% quarter over quarter, led by enterprise renewals."],
                ["user", "Which segment contributed most?"],
                ["assistant", "I’ll compare the segment totals and renewal mix."],
              ].map(([role, text], index) => (
                <MessageScrollerItem
                  key={`${role}-${text}`}
                  messageId={`history-${index}`}
                  scrollAnchor={role === "user"}
                >
                  <Message align={role === "user" ? "end" : "start"}>
                    <MessageContent>
                      <MessageHeader>{role === "user" ? "You" : "Assistant"}</MessageHeader>
                      <div
                        className={
                          role === "user"
                            ? "ml-auto max-w-[85%] rounded-lg bg-muted px-3 py-2"
                            : "max-w-[90%] px-3 py-1"
                        }
                      >
                        {text}
                      </div>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              ))}
              <MessageScrollerItem messageId="tool-lifecycle">
                <Message align="start">
                  <MessageContent>
                    <MessageHeader>Assistant</MessageHeader>
                    <div className="max-w-[90%] px-3 py-1">
                      <div className="space-y-2">
                        <div className="typeset typeset-docs">
                          I’ll compare the segment totals and renewal mix.
                        </div>
                        <ToolActivity
                          part={{
                            type: "tool-call",
                            id: "segment-call",
                            name: "segment_totals",
                            state: "completed",
                            arguments: {
                              period: "latest quarter",
                              includeRenewals: true,
                            },
                          }}
                        />
                        <ToolActivity
                          part={{
                            type: "tool-result",
                            toolCallId: "segment-call",
                            state: "completed",
                            content: "$4.2M enterprise / $1.8M self-serve",
                          }}
                        />
                      </div>
                    </div>
                  </MessageContent>
                </Message>
              </MessageScrollerItem>
              <MessageScrollerItem messageId="streaming">
                <AgentReplyingIndicator />
              </MessageScrollerItem>
              <MessageScrollerItem messageId="latest" scrollAnchor>
                <Message align="start">
                  <MessageContent>
                    <MessageHeader>Assistant</MessageHeader>
                    <div className="px-3 py-1">
                      Enterprise contributed the majority of the increase, with renewals accounting
                      for most of the movement.
                    </div>
                  </MessageContent>
                </Message>
              </MessageScrollerItem>
              <MessageScrollerItem messageId="follow-up">
                <div className="flex items-center gap-2 px-3 text-sm text-muted-foreground">
                  <CircleDot aria-hidden="true" className="size-4" />
                  <span>Ready for the next question</span>
                </div>
              </MessageScrollerItem>
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>
    </div>
  ),
};
