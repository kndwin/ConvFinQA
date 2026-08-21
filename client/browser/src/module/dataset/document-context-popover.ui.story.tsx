import type { Meta, StoryObj } from "@storybook/react-vite";
import { DocumentContextPopover } from "./document-context-popover.ui";

const meta = {
  title: "Datasets/Document context",
  component: DocumentContextPopover,
} satisfies Meta<typeof DocumentContextPopover>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Available: Story = {
  args: {
    docJson: JSON.stringify({ source: "annual-report", section: "Revenue" }),
  },
};
