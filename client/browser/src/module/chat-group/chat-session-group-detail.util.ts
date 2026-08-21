import type { PersistedMessage } from "../chat-session/chat-session.query";

export function transformPersistedMessages({ messages }: { messages: PersistedMessage[] }) {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: String(message.id),
      role: message.role as "user" | "assistant",
      parts: [{ type: "text" as const, content: message.content }],
    }));
}
