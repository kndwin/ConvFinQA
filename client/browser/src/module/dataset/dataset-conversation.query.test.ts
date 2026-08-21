import { describe, expect, it } from "vitest";
import { datasetConversationQueries } from "./dataset-conversation.query";
import { explorerSearchSchema } from "./dataset-conversation-search.schema";

describe("dataset conversation list query keys", () => {
  it("normalizes tags consistently and keeps different selections distinct", () => {
    const normalized = datasetConversationQueries.list({
      tags: [" alpha ", "alpha", "beta"],
    });
    const stable = datasetConversationQueries.list({ tags: ["alpha", "beta"] });
    const different = datasetConversationQueries.list({ tags: ["alpha"] });

    expect(normalized).toEqual(stable);
    expect(normalized).not.toEqual(different);
  });
});

describe("dataset conversation search URL", () => {
  it("discards malformed overlong tags", () => {
    expect(explorerSearchSchema.parse({ tags: [" ok ", "x".repeat(101), "ok", " "] }).tags).toEqual(
      ["ok"],
    );
  });
});
