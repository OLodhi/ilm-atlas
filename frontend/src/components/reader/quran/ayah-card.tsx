"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { ArabicText } from "@/components/shared/arabic-text";
import { TafsirPanel } from "./tafsir-panel";
import type { AyahResponse } from "@/lib/types";

interface AyahCardProps {
  ayah: AyahResponse;
  surahNumber: number;
  arabicFontSize: number;
  englishFontSize: number;
}

export function AyahCard({
  ayah,
  surahNumber,
  arabicFontSize,
  englishFontSize,
}: AyahCardProps) {
  const [tafsirOpen, setTafsirOpen] = useState(false);

  return (
    <div className="border-b py-6 last:border-b-0">
      {/* Ayah number badge */}
      <div className="mb-3 flex items-center justify-between">
        <span className="flex h-8 w-8 items-center justify-center rounded-full border text-xs font-medium text-muted-foreground">
          {ayah.number}
        </span>
      </div>

      {/* Arabic text */}
      {ayah.text_arabic && (
        <ArabicText variant="quran" className="mb-3" style={{ fontSize: `${arabicFontSize}rem` }}>
          {ayah.text_arabic}
        </ArabicText>
      )}

      {/* English translation */}
      {ayah.text_english && (
        <p
          className="text-muted-foreground leading-relaxed"
          style={{ fontSize: `${englishFontSize}rem` }}
        >
          {ayah.text_english}
        </p>
      )}

      {/* Tafsir toggle */}
      <button
        onClick={() => setTafsirOpen(!tafsirOpen)}
        className="mt-3 flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 transition-colors dark:text-violet-400"
      >
        {tafsirOpen ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
        {tafsirOpen ? "Hide Tafsir" : "View Tafsir"}
      </button>

      {/* Tafsir panel (loaded on demand) */}
      {tafsirOpen && (
        <div className="mt-3">
          <TafsirPanel surahNumber={surahNumber} ayahNumber={ayah.number} />
        </div>
      )}
    </div>
  );
}
