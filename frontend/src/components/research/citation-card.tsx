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
          <div className="space-y-1">
            {citation.auto_translated && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                <svg
                  viewBox="0 0 16 16"
                  fill="currentColor"
                  className="h-3 w-3"
                  aria-hidden="true"
                >
                  <path d="M8.5 1.5a.5.5 0 0 0-1 0V2H6a.5.5 0 0 0 0 1h.25L5.1 6.283A2.5 2.5 0 0 0 3.5 5.5a.5.5 0 0 0 0 1A1.5 1.5 0 0 1 5 8c0 .516-.26.973-.656 1.242a.5.5 0 1 0 .556.832C5.442 9.717 5.8 9.049 5.944 8.29L6.28 7h1.44l.336 1.29c.145.76.503 1.427 1.044 1.784a.5.5 0 1 0 .556-.832A1.5 1.5 0 0 1 9 8a1.5 1.5 0 0 1 1.5-1.5.5.5 0 0 0 0-1 2.5 2.5 0 0 0-1.6.783L7.75 3H8a.5.5 0 0 0 0-1h-.5V1.5zM6.72 7l.43-1.643L7.58 7H6.72z" />
                  <path d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 13.5 6H12v1h1.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-6a.5.5 0 0 1 .5-.5H4V6H2.5A1.5 1.5 0 0 0 1 7.5v6z" />
                </svg>
                Auto-translated
              </span>
            )}
            <p className="text-sm text-muted-foreground leading-relaxed">
              {citation.text_english}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
