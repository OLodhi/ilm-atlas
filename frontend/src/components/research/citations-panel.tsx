import { ScrollArea } from "@/components/ui/scroll-area";
import { CitationCard } from "./citation-card";
import type { Citation } from "@/lib/types";

interface CitationsPanelProps {
  citations: Citation[];
}

export function CitationsPanel({ citations }: CitationsPanelProps) {
  if (citations.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
        Sources will appear here
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="space-y-3 p-1">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
          Sources ({citations.length})
        </h3>
        {citations.map((citation, i) => (
          <CitationCard key={i} citation={citation} />
        ))}
      </div>
    </ScrollArea>
  );
}
