import { describe, expect, it } from "vitest";
import type { PersistedMessage } from "../chat-session/chat-session.query";
import { transformPersistedMessages } from "./chat-session-group-detail.util";

const message = (
  id: number,
  role: PersistedMessage["role"],
  content: string,
): PersistedMessage => ({
  id,
  chat_session_id: 1,
  role,
  content,
  created_at: "2026-01-01T00:00:00Z",
});

describe("transformPersistedMessages", () => {
  it("converts user and assistant messages to transcript messages", () => {
    expect(
      transformPersistedMessages({
        messages: [message(1, "user", "Hello"), message(2, "assistant", "Hi")],
      }),
    ).toEqual([
      { id: "1", role: "user", parts: [{ type: "text", content: "Hello" }] },
      { id: "2", role: "assistant", parts: [{ type: "text", content: "Hi" }] },
    ]);
  });

  it("filters unsupported roles while preserving order and content", () => {
    expect(
      transformPersistedMessages({
        messages: [
          message(1, "system", "Ignore"),
          message(2, "assistant", "Second"),
          message(3, "user", "Third"),
        ],
      }),
    ).toEqual([
      { id: "2", role: "assistant", parts: [{ type: "text", content: "Second" }] },
      { id: "3", role: "user", parts: [{ type: "text", content: "Third" }] },
    ]);
  });

  it("returns an empty list for empty input", () => {
    expect(transformPersistedMessages({ messages: [] })).toEqual([]);
  });
});
