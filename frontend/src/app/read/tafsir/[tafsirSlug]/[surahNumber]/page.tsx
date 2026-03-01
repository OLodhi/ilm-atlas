"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { ArabicText } from "@/components/shared/arabic-text";
import { fetchTafsirSurahDetail } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { TafsirSurahDetailResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function TafsirSurahPage() {
  const params = useParams();
  const tafsirSlug = params.tafsirSlug as string;
  const surahNumber = Number(params.surahNumber);

  const [detail, setDetail] = useState<TafsirSurahDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchTafsirSurahDetail(tafsirSlug, surahNumber)
      .then(setDetail)
      .catch(() => setError("Tafsir or surah not found"));
  }, [tafsirSlug, surahNumber]);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-4xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Tafsir", href: "/read/tafsir" },
              { label: detail?.tafsir.name ?? tafsirSlug },
              { label: detail ? `Surah ${detail.surah_name}` : `Surah ${surahNumber}` },
            ]}
          />
          <TypographyControls
            arabicSize={settings.arabicFontSize}
            englishSize={settings.englishFontSize}
            onIncreaseArabic={increaseArabic}
            onDecreaseArabic={decreaseArabic}
            onIncreaseEnglish={increaseEnglish}
            onDecreaseEnglish={decreaseEnglish}
          />
        </div>

        {error && <p className="mt-4 text-destructive">{error}</p>}

        {!detail && !error ? (
          <div className="mt-6 space-y-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : detail ? (
          <>
            <h1 className="mt-6 text-xl font-semibold">{detail.tafsir.name}</h1>
            <p className="text-sm text-muted-foreground">
              Surah {detail.surah_name} ({detail.surah_number}) &middot;{" "}
              {detail.entries.length} entries
            </p>

            <div className="mt-8 space-y-8">
              {detail.entries.map((entry) => (
                <div key={entry.ayah_number} className="space-y-3">
                  {/* Ayah reference badge */}
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-0.5 text-xs font-medium text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">
                      {detail.surah_number}:{entry.ayah_number}
                    </span>
                  </div>

                  {/* Tafsir content */}
                  {detail.tafsir.language === "arabic" && entry.text_arabic ? (
                    <ArabicText style={{ fontSize: `${settings.arabicFontSize}rem` }}>
                      {entry.text_arabic}
                    </ArabicText>
                  ) : entry.text_english ? (
                    <p
                      className="leading-relaxed"
                      style={{ fontSize: `${settings.englishFontSize}rem` }}
                    >
                      {entry.text_english}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">
                      No content available.
                    </p>
                  )}

                  <div className="border-b" />
                </div>
              ))}
            </div>

            {/* Prev / Next surah navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {surahNumber > 1 ? (
                <Link
                  href={`/read/tafsir/${tafsirSlug}/${surahNumber - 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Surah {surahNumber - 1}
                </Link>
              ) : (
                <div />
              )}
              {surahNumber < 114 ? (
                <Link
                  href={`/read/tafsir/${tafsirSlug}/${surahNumber + 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Surah {surahNumber + 1}
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ) : (
                <div />
              )}
            </div>
          </>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
