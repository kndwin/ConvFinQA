import type { Meta, StoryObj } from "@storybook/react-vite";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";
import type { DatasetConversation } from "./dataset-conversation.schema";
import { DatasetConversationDetail } from "./dataset-conversation-detail.ui";

const item = {
  id: 42,
  source_id: "AAPL/2023/annual-report",
  split: "train",
  pre_text:
    "Net sales increased by 8% during the year, primarily because of stronger demand in services.",
  post_text: "Operating expenses were $54.8 billion compared with $51.3 billion in the prior year.",
  num_dialogue_turns: 4,
  has_type2_question: true,
  has_duplicate_columns: false,
  has_non_numeric_values: true,
  dialogue_json: JSON.stringify([
    { role: "user", content: "What was the year-over-year increase?" },
    { role: "assistant", content: "Net sales increased by 8%." },
  ]),
  candidate_qa: [
    { question: "What was the year-over-year increase?", answer: "8%" },
    { question: "What was the expected operating expense?", answer: null },
  ],
  features_json: JSON.stringify({ question_type: "comparison", answer: "8%" }),
  doc_json: JSON.stringify({ company: "Example Corp", fiscal_year: 2023 }),
} satisfies DatasetConversation;

const chat = (
  <Card className="min-h-64">
    <CardHeader>
      <CardTitle>Dataset chat</CardTitle>
    </CardHeader>
    <CardContent className="text-sm text-muted-foreground">
      Chat is supplied by the page orchestration boundary.
    </CardContent>
  </Card>
);

const meta = {
  title: "Dataset Conversations/Detail",
  component: DatasetConversationDetail,
  args: { onBack: () => undefined },
} satisfies Meta<typeof DatasetConversationDetail>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {
  args: {
    state: {
      status: "ready",
      item,
      chat,
      activeTab: "record",
      onTabChange: () => undefined,
      rawPayloadOpen: false,
      onRawPayloadToggle: () => undefined,
    },
  },
};

export const RawPayloadOpen: Story = {
  args: {
    state: {
      status: "ready",
      item,
      chat,
      activeTab: "record",
      onTabChange: () => undefined,
      rawPayloadOpen: true,
      onRawPayloadToggle: () => undefined,
    },
  },
};

export const ChatSessions: Story = {
  args: {
    state: {
      status: "ready",
      item,
      chat,
      activeTab: "chat-sessions",
      onTabChange: () => undefined,
      rawPayloadOpen: false,
      onRawPayloadToggle: () => undefined,
    },
  },
};

export const Loading: Story = {
  args: { state: { status: "loading" } },
};

export const Error: Story = {
  args: { state: { status: "error", onRetry: () => undefined } },
};

export const NotFound: Story = {
  args: { state: { status: "not-found" } },
};

export const InvalidId: Story = {
  args: { state: { status: "invalid" } },
};
