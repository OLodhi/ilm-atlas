import { ArabicText } from "@/components/shared/arabic-text";
import type { HadithResponseType } from "@/lib/types";

interface HadithCardProps {
  hadith: HadithResponseType;
  collectionName: string;
  bookNumber: number;
  arabicFontSize: number;
  englishFontSize: number;
}

export function HadithCard({
  hadith,
  collectionName,
  bookNumber,
  arabicFontSize,
  englishFontSize,
}: HadithCardProps) {
  return (
    <div className="border-l-4 border-l-amber-600 rounded-lg border bg-card p-5">
      {/* English text (primary) */}
      {hadith.text_english && (
        <p
          className="leading-relaxed"
          style={{ fontSize: `${englishFontSize}rem` }}
        >
          {hadith.text_english}
        </p>
      )}

      {/* Arabic text */}
      {hadith.text_arabic && (
        <ArabicText className="mt-4" style={{ fontSize: `${arabicFontSize}rem` }}>
          {hadith.text_arabic}
        </ArabicText>
      )}

      {/* Reference line */}
      <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <span>{collectionName}</span>
        <span>&middot;</span>
        <span>Book {bookNumber}, Hadith {hadith.number}</span>
      </div>
    </div>
  );
}
