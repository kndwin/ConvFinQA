import type { Meta, StoryObj } from "@storybook/react-vite";
import { AgentReplyingIndicator, CandidateQaPanel } from "./chat-session.ui";

const meta = {
  title: "Chat Sessions/Transcript",
  component: CandidateQaPanel,
} satisfies Meta<typeof CandidateQaPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Replying: Story = {
  args: { candidateQa: [] },
  render: () => (
    <div className="space-y-4">
      <AgentReplyingIndicator />
      <CandidateQaPanel
        candidateQa={[{ question: "What changed?", answer: "Revenue increased by 8%." }]}
      />
    </div>
  ),
};

export const MessageScrollerPreview: Story = {
  args: { candidateQa: [] },
  render: () => (
    <div className="space-y-3 rounded-lg border p-4">
      <p className="rounded-lg bg-muted p-3">Summarize the latest revenue movement.</p>
      <p className="rounded-lg border p-3">Revenue is up 8% quarter over quarter.</p>
      <AgentReplyingIndicator />
    </div>
  ),
};
