const MAX_CHAT_SESSION_TAGS = 50;

export function normalizeChatSessionTags(values: readonly string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))].slice(
    0,
    MAX_CHAT_SESSION_TAGS,
  );
}
