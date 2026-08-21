import type { Meta, StoryObj } from "@storybook/react-vite";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChatGroupPanel } from "./chat-group.ui";
import { chatSessionGroupListOptions } from "./chat-group.query";

const meta = {
  title: "Chat Groups/Group panel",
  component: ChatGroupPanel,
  decorators: [
    (Story) => {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      client.setQueryData(chatSessionGroupListOptions(42).queryKey, []);
      return (
        <QueryClientProvider client={client}>
          <Story />
        </QueryClientProvider>
      );
    },
  ],
} satisfies Meta<typeof ChatGroupPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Empty: Story = { args: { datasetId: 42 } };
