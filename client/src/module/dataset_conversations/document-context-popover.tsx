import { Badge } from "@/platform/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/platform/ui/popover";

function displayDocumentContext(docJson: string | null) {
  if (docJson == null || docJson.trim() === "") return "No document context available.";
  try {
    return JSON.stringify(JSON.parse(docJson), null, 2);
  } catch {
    return docJson;
  }
}

export function DocumentContextPopover({ docJson }: { docJson: string | null }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Badge
          aria-label="Show document context"
          as="button"
          className="focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          variant="outline"
        >
          Context
        </Badge>
      </PopoverTrigger>
      <PopoverContent
        aria-describedby="document-context-description"
        aria-labelledby="document-context-title"
        className="flex max-h-[min(32rem,calc(100vh-2rem))] w-[min(36rem,calc(100vw-2rem))] flex-col gap-3"
      >
        <div>
          <h2 className="font-semibold" id="document-context-title">
            Document context
          </h2>
          <p className="mt-1 text-sm text-muted-foreground" id="document-context-description">
            Document context is included every turn. Conversation history and the current question
            are added when a message is sent.
          </p>
        </div>
        <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-mono text-xs [overflow-wrap:anywhere]">
          {displayDocumentContext(docJson)}
        </pre>
      </PopoverContent>
    </Popover>
  );
}
