import { assign, setup } from "xstate";

export const chatSessionSelectionMachine = setup({
  types: {
    context: {} as { selected?: number },
    events: {} as
      | { type: "dataset.reset" }
      | { type: "sessions.synchronized"; sessionIds: number[] }
      | { type: "session.selected"; sessionId: number }
      | { type: "session.created"; sessionId: number },
  },
  actions: {
    reset: assign({ selected: undefined }),
    synchronize: assign(({ context, event }) => {
      if (event.type !== "sessions.synchronized") return {};
      return {
        selected:
          context.selected !== undefined && event.sessionIds.includes(context.selected)
            ? context.selected
            : event.sessionIds[0],
      };
    }),
    select: assign(({ event }) => {
      if (event.type !== "session.selected" && event.type !== "session.created") return {};
      return { selected: event.sessionId };
    }),
  },
}).createMachine({
  id: "chatSessionSelection",
  context: { selected: undefined },
  on: {
    "dataset.reset": { actions: "reset" },
    "sessions.synchronized": { actions: "synchronize" },
    "session.selected": { actions: "select" },
    "session.created": { actions: "select" },
  },
});

export const chatSessionTranscriptMachine = setup({
  types: {
    context: {} as { input: string; sendError?: string },
    events: {} as
      | { type: "input.changed"; value: string }
      | { type: "send.started" }
      | { type: "send.failed"; draft: string; error: string },
  },
  actions: {
    inputChanged: assign(({ event }) =>
      event.type === "input.changed" ? { input: event.value } : {},
    ),
    sendStarted: assign({ input: "", sendError: undefined }),
    sendFailed: assign(({ event }) =>
      event.type === "send.failed" ? { input: event.draft, sendError: event.error } : {},
    ),
  },
}).createMachine({
  id: "chatSessionTranscript",
  context: { input: "", sendError: undefined },
  on: {
    "input.changed": { actions: "inputChanged" },
    "send.started": { actions: "sendStarted" },
    "send.failed": { actions: "sendFailed" },
  },
});
