import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { DatasetConversationPage } from "./dataset-conversation.ui";
import { datasetConversationListOptions } from "../dataset-conversation.query";
import type { DatasetConversation } from "../dataset-conversation.model";
import { routeTree } from "@/platform/router/route-tree.gen";

const rows = [
  {
    id: 42,
    source_id: "AAPL/2023/annual-report",
    split: "train",
    pre_text: "Net sales increased by 8%.",
    post_text: "Operating expenses were stable.",
    num_dialogue_turns: 4,
    has_type2_question: true,
    has_duplicate_columns: false,
    has_non_numeric_values: false,
    dialogue_json: "[]",
    candidate_qa: [],
    features_json: "{}",
    doc_json: null,
  },
] satisfies DatasetConversation[];

function RoutedFixture({ children: _children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  client.setQueryData(datasetConversationListOptions({ offset: 0, limit: 13 }).queryKey, rows);
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: ["/?q=&split=all&page=1"] }),
  });
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

const meta = {
  title: "Dataset Conversations/Page",
  component: DatasetConversationPage,
  decorators: [
    (Story) => (
      <RoutedFixture>
        <Story />
      </RoutedFixture>
    ),
  ],
} satisfies Meta<typeof DatasetConversationPage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};
