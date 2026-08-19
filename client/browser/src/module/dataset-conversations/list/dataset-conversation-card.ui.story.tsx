import type { Meta, StoryObj } from "@storybook/react-vite";
import { DatasetConversationCard } from "./dataset-conversation-card.ui";
import type { DatasetConversation } from "../dataset-conversation.model";

const item = {
  id: null,
  source_id: "AAPL/2023/annual-report",
  split: "train",
  pre_text: "Net sales increased by 8% during the year, primarily because of stronger demand.",
  post_text: "Operating expenses were $54.8 billion compared with $51.3 billion previously.",
  num_dialogue_turns: 4,
  has_type2_question: true,
  has_duplicate_columns: false,
  has_non_numeric_values: true,
  dialogue_json: "[]",
  candidate_qa: [],
  features_json: "{}",
  doc_json: null,
} satisfies DatasetConversation;

const meta = {
  title: "Dataset Conversations/Card",
  component: DatasetConversationCard,
} satisfies Meta<typeof DatasetConversationCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WithDataNotes: Story = { args: { item } };
