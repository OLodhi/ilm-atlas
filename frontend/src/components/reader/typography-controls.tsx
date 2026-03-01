"use client";

import { Button } from "@/components/ui/button";
import { Minus, Plus } from "lucide-react";

interface TypographyControlsProps {
  arabicSize: number;
  englishSize: number;
  onIncreaseArabic: () => void;
  onDecreaseArabic: () => void;
  onIncreaseEnglish: () => void;
  onDecreaseEnglish: () => void;
}

export function TypographyControls({
  arabicSize,
  englishSize,
  onIncreaseArabic,
  onDecreaseArabic,
  onIncreaseEnglish,
  onDecreaseEnglish,
}: TypographyControlsProps) {
  return (
    <div className="flex shrink-0 items-center gap-4 text-sm text-muted-foreground">
      <div className="flex items-center gap-1">
        <span className="font-amiri text-base" dir="rtl">ع</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDecreaseArabic}>
          <Minus className="h-3 w-3" />
        </Button>
        <span className="w-10 text-center text-xs">{arabicSize.toFixed(2)}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onIncreaseArabic}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>
      <div className="h-4 w-px bg-border" />
      <div className="flex items-center gap-1">
        <span className="text-xs font-medium">A</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onDecreaseEnglish}>
          <Minus className="h-3 w-3" />
        </Button>
        <span className="w-10 text-center text-xs">{englishSize.toFixed(2)}</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onIncreaseEnglish}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}
