import { setup } from "xstate";

export const datasetConversationDetailMachine = setup({
  types: {
    events: {} as
      | { type: "rawPayload.toggled" }
      | { type: "tab.recordSelected" }
      | { type: "tab.chatSessionsSelected" },
  },
}).createMachine({
  id: "datasetConversationDetail",
  type: "parallel",
  states: {
    tab: {
      initial: "record",
      states: {
        record: {
          on: { "tab.chatSessionsSelected": "chatSessions" },
        },
        chatSessions: {
          on: { "tab.recordSelected": "record" },
        },
      },
    },
    rawPayload: {
      initial: "closed",
      states: {
        closed: {
          on: { "rawPayload.toggled": "open" },
        },
        open: {
          on: { "rawPayload.toggled": "closed" },
        },
      },
    },
  },
});
