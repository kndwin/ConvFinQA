import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/platform/ui/badge";
import { Button } from "@/platform/ui/button";
import { Input } from "@/platform/ui/input";
import { chatSessionTagsOptions } from "./chat-session.query";
import { normalizeChatSessionTags } from "./chat-session-tags.util";

const MAX_CHAT_SESSION_TAGS = 50;

export function ChatSessionTags({
  value,
  onChange,
  id,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  id?: string;
}) {
  const [draft, setDraft] = useState("");
  const suggestions = useQuery(chatSessionTagsOptions());
  const tags = normalizeChatSessionTags(value);
  const add = (raw: string) => {
    const next = raw.trim();
    if (!next || next.length > 100 || tags.includes(next) || tags.length >= MAX_CHAT_SESSION_TAGS)
      return;
    onChange([...tags, next]);
    setDraft("");
  };
  const available = (suggestions.data ?? [])
    .map((tag) => tag.value)
    .filter(
      (tag) =>
        !tags.includes(tag) &&
        (!draft.trim() || tag.toLowerCase().includes(draft.trim().toLowerCase())),
    )
    .slice(0, 8);
  return (
    <div className="space-y-2" id={id}>
      <label className="text-xs font-medium" htmlFor={`${id ?? "chat-tags"}-input`}>
        Tags
      </label>
      <div className="flex gap-2">
        <Input
          id={`${id ?? "chat-tags"}-input`}
          value={draft}
          maxLength={100}
          placeholder="Add a tag"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              add(draft);
            }
          }}
          aria-describedby={`${id ?? "chat-tags"}-help`}
        />
        <Button type="button" variant="outline" onClick={() => add(draft)} disabled={!draft.trim()}>
          Add
        </Button>
      </div>
      <div className="flex flex-wrap gap-1">
        {tags.map((tag) => (
          <Badge key={tag} variant="secondary">
            {tag}
            <button
              type="button"
              className="ml-1 rounded-full"
              aria-label={`Remove tag ${tag}`}
              onClick={() => onChange(tags.filter((item) => item !== tag))}
            >
              <X size={12} />
            </button>
          </Badge>
        ))}
      </div>
      {suggestions.isLoading && (
        <p className="text-xs text-muted-foreground">Loading suggestions…</p>
      )}
      {suggestions.isError && (
        <p className="text-xs text-muted-foreground">
          Tag suggestions unavailable; you can still enter tags.
        </p>
      )}
      {available.length > 0 && (
        <div className="flex flex-wrap gap-1" aria-label="Tag suggestions">
          {available.map((tag) => (
            <Button
              key={tag}
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={() => add(tag)}
            >
              {tag}
            </Button>
          ))}
        </div>
      )}
      <p id={`${id ?? "chat-tags"}-help`} className="text-xs text-muted-foreground">
        Optional, up to 50 tags (1–100 characters each).
      </p>
    </div>
  );
}
