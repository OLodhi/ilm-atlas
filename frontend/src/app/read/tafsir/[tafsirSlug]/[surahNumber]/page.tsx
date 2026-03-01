"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Languages, Loader2 } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { ArabicText } from "@/components/shared/arabic-text";
import { fetchTafsirSurahDetail, fetchSurahs, translateTexts } from "@/lib/api-client";
import { SurahNavSidebar } from "@/components/reader/tafsir/surah-nav-sidebar";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { TafsirSurahDetailResponse, SurahSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

const TRANSLATE_BATCH_SIZE = 10;

export default function TafsirSurahPage() {
  const params = useParams();
  const tafsirSlug = params.tafsirSlug as string;
  const surahNumber = Number(params.surahNumber);

  const [surahs, setSurahs] = useState<SurahSummary[] | null>(null);
  const [detail, setDetail] = useState<TafsirSurahDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Translation state: ayah_number -> translated text
  const [translations, setTranslations] = useState<Record<number, string>>({});
  const [translating, setTranslating] = useState(false);

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
    setTranslations({});
    fetchTafsirSurahDetail(tafsirSlug, surahNumber)
      .then(setDetail)
      .catch(() => setError("Tafsir or surah not found"));
  }, [tafsirSlug, surahNumber]);

  const isArabicOnly = detail?.tafsir.language === "arabic";
  const hasTranslations = Object.keys(translations).length > 0;

  const handleTranslate = useCallback(async () => {
    if (!detail || !isArabicOnly) return;

    // Collect entries that need translation
    const untranslated = detail.entries.filter(
      (e) => e.text_arabic && !(e.ayah_number in translations)
    );
    if (untranslated.length === 0) return;

    setTranslating(true);
    try {
      // Translate in batches of TRANSLATE_BATCH_SIZE
      for (let i = 0; i < untranslated.length; i += TRANSLATE_BATCH_SIZE) {
        const batch = untranslated.slice(i, i + TRANSLATE_BATCH_SIZE);
        const texts = batch.map((e) => e.text_arabic!);
        const results = await translateTexts(texts);
        setTranslations((prev) => {
          const next = { ...prev };
          batch.forEach((e, idx) => {
            if (results[idx]) next[e.ayah_number] = results[idx];
          });
          return next;
        });
      }
    } catch {
      // Partial translations are kept; user can retry
    } finally {
      setTranslating(false);
    }
  }, [detail, isArabicOnly, translations]);

  return (
    <ReaderLayout
      sidebarContent={surahs ? <SurahNavSidebar tafsirSlug={tafsirSlug} surahs={surahs} /> : null}
    >
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
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
            <div className="mt-6 flex items-center justify-between">
              <div>
                <h1 className="text-xl font-semibold">{detail.tafsir.name}</h1>
                <p className="text-sm text-muted-foreground">
                  Surah {detail.surah_name} ({detail.surah_number}) &middot;{" "}
                  {detail.entries.length} entries
                </p>
              </div>

              {isArabicOnly && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTranslate}
                  disabled={translating}
                  className="gap-2"
                >
                  {translating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Languages className="h-4 w-4" />
                  )}
                  {translating
                    ? "Translating..."
                    : hasTranslations
                      ? "Translate remaining"
                      : "Translate to English"}
                </Button>
              )}
            </div>

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
                  {isArabicOnly && entry.text_arabic ? (
                    <>
                      <ArabicText style={{ fontSize: `${settings.arabicFontSize}rem` }}>
                        {entry.text_arabic}
                      </ArabicText>
                      {translations[entry.ayah_number] && (
                        <div className="space-y-1">
                          <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                            <Languages className="h-3 w-3" />
                            Auto-translated
                          </span>
                          <p
                            className="leading-relaxed text-muted-foreground"
                            style={{ fontSize: `${settings.englishFontSize}rem` }}
                          >
                            {translations[entry.ayah_number]}
                          </p>
                        </div>
                      )}
                    </>
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
