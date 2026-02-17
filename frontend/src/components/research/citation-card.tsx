import { Card, CardContent } from "@/components/ui/card";
import { ArabicText } from "@/components/shared/arabic-text";
import { cn } from "@/lib/utils";
import {
  CHUNK_TYPE_COLORS,
  CHUNK_TYPE_BADGE_VARIANTS,
} from "@/lib/constants";
import type { Citation } from "@/lib/types";

interface CitationCardProps {
  citation: Citation;
}

export function CitationCard({ citation }: CitationCardProps) {
  const borderColor = CHUNK_TYPE_COLORS[citation.chunk_type] ?? CHUNK_TYPE_COLORS.paragraph;
  const badgeStyle = CHUNK_TYPE_BADGE_VARIANTS[citation.chunk_type] ?? CHUNK_TYPE_BADGE_VARIANTS.paragraph;

  return (
    <Card className={cn("border-l-4", borderColor)}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-muted-foreground">
            {citation.source}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
              badgeStyle
            )}
          >
            {citation.chunk_type}
          </span>
        </div>

        {citation.text_arabic && (
          <ArabicText
            variant={citation.chunk_type === "ayah" ? "quran" : "default"}
          >
            {citation.text_arabic}
          </ArabicText>
        )}

        {citation.text_english && (
          <p className="text-sm text-muted-foreground leading-relaxed">
            {citation.text_english}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
