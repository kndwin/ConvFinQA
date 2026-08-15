import { ArrowUpRight } from "lucide-react";
import { Badge } from "@/platform/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/platform/ui/card";
import { Link } from "@tanstack/react-router";
import type { DatasetConversation } from "./dataset-conversation.model";
export function DatasetConversationCard({ item }: { item: DatasetConversation }) {
  const flags = [
    [item.has_type2_question, "Type 2"],
    [item.has_duplicate_columns, "Duplicates"],
    [item.has_non_numeric_values, "Non-numeric"],
  ] as const;
  const card = (
    <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:border-primary/50 group-hover:shadow-md">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="break-all text-lg">{item.source_id}</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Database ID: {item.id ?? "unavailable"}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge>{item.split}</Badge>
          <Badge variant="outline">{item.num_dialogue_turns ?? 0} turns</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
          {item.pre_text || item.post_text || "No source context available."}
        </p>
        {item.post_text && (
          <p className="mt-2 line-clamp-1 text-xs text-muted-foreground">
            Follow-up: {item.post_text}
          </p>
        )}
        {flags.some(([value]) => value) && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Data notes</p>
            <div className="flex flex-wrap gap-2">
              {flags
                .filter(([value]) => value)
                .map(([, label]) => (
                  <Badge variant="outline" key={label}>
                    {label}
                  </Badge>
                ))}
            </div>
          </div>
        )}
        {item.id != null && (
          <p className="mt-4 text-sm font-medium text-primary group-hover:underline">
            Open dataset <ArrowUpRight size={15} className="inline" />
          </p>
        )}
      </CardContent>
    </Card>
  );
  if (item.id == null) return card;
  return (
    <Link
      to="/dataset-conversations/$datasetConversationId"
      params={{ datasetConversationId: String(item.id) }}
      className="group block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      aria-label={`Open dataset record ${item.source_id}`}
    >
      {card}
    </Link>
  );
}
