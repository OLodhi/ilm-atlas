"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { SurahListSidebar } from "@/components/reader/quran/surah-list-sidebar";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { AyahCard } from "@/components/reader/quran/ayah-card";
import { fetchSurahs, fetchSurahDetail } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { SurahSummary, SurahDetailResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function SurahPage() {
  const params = useParams();
  const surahNumber = Number(params.surahNumber);

  const [surahs, setSurahs] = useState<SurahSummary[] | null>(null);
  const [detail, setDetail] = useState<SurahDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    fetchSurahs().then(setSurahs).catch(console.error);
  }, []);

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchSurahDetail(surahNumber)
      .then(setDetail)
      .catch(() => setError("Failed to load surah"));
  }, [surahNumber]);

  return (
    <ReaderLayout
      sidebarContent={surahs ? <SurahListSidebar surahs={surahs} /> : null}
    >
      <div className="mx-auto max-w-4xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Quran", href: "/read/quran" },
              { label: detail?.surah.name_english ?? `Surah ${surahNumber}` },
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

        {error && (
          <p className="mt-4 text-destructive">{error}</p>
        )}

        {!detail && !error ? (
          <div className="mt-6 space-y-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-2 border-b pb-6">
                <Skeleton className="h-6 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ))}
          </div>
        ) : detail ? (
          <>
            {/* Surah header */}
            <div className="mt-6 text-center">
              <h1 className="font-amiri text-3xl" dir="rtl">
                {detail.surah.name_arabic}
              </h1>
              <h2 className="mt-1 text-lg font-medium">
                {detail.surah.name_english}
              </h2>
              <p className="text-sm text-muted-foreground">
                {detail.surah.ayah_count} Ayahs &middot;{" "}
                {detail.surah.revelation_type}
              </p>
            </div>

            {/* Ayahs */}
            <div className="mt-8">
              {detail.ayahs.map((ayah) => (
                <AyahCard
                  key={ayah.number}
                  ayah={ayah}
                  surahNumber={surahNumber}
                  arabicFontSize={settings.arabicFontSize}
                  englishFontSize={settings.englishFontSize}
                />
              ))}
            </div>

            {/* Prev / Next navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {surahNumber > 1 ? (
                <Link
                  href={`/read/quran/${surahNumber - 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  {surahs?.[surahNumber - 2]?.name_english ?? `Surah ${surahNumber - 1}`}
                </Link>
              ) : (
                <div />
              )}
              {surahNumber < 114 ? (
                <Link
                  href={`/read/quran/${surahNumber + 1}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {surahs?.[surahNumber]?.name_english ?? `Surah ${surahNumber + 1}`}
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
