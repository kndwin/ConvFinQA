import { describe, expect, it } from "vitest";
import { normalizeChatSessionTags } from "./chat-session-tags.util";

describe("normalizeChatSessionTags", () => {
  it("trims, removes blanks, stably deduplicates, and caps at 50", () => {
    const values = [
      " first ",
      "",
      "first",
      " second ",
      "   ",
      ...Array.from({ length: 50 }, (_, i) => `tag-${i}`),
    ];
    const normalized = normalizeChatSessionTags(values);

    expect(normalized).toHaveLength(50);
    expect(normalized.slice(0, 2)).toEqual(["first", "second"]);
    expect(normalized).toEqual([...new Set(normalized)]);
    expect(normalized).not.toContain("tag-49");
  });
});
