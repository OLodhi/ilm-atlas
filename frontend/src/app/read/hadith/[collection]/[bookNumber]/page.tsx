"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { TypographyControls } from "@/components/reader/typography-controls";
import { HadithCard } from "@/components/reader/hadith/hadith-card";
import { fetchHadithBookDetail, fetchHadithBooks } from "@/lib/api-client";
import { useReaderSettings } from "@/hooks/use-reader-settings";
import type { HadithBookDetailResponse, HadithBookSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithBookPage() {
  const params = useParams();
  const slug = params.collection as string;
  const bookNumber = Number(params.bookNumber);

  const [detail, setDetail] = useState<HadithBookDetailResponse | null>(null);
  const [books, setBooks] = useState<HadithBookSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    settings,
    increaseArabic,
    decreaseArabic,
    increaseEnglish,
    decreaseEnglish,
  } = useReaderSettings();

  useEffect(() => {
    fetchHadithBooks(slug).then(setBooks).catch(console.error);
  }, [slug]);

  useEffect(() => {
    setDetail(null);
    setError(null);
    fetchHadithBookDetail(slug, bookNumber)
      .then(setDetail)
      .catch(() => setError("Book not found"));
  }, [slug, bookNumber]);

  const bookName = detail?.book.name_english || `Book ${bookNumber}`;

  // Find prev/next books
  const bookIndex = books?.findIndex((b) => b.number === bookNumber) ?? -1;
  const prevBook = bookIndex > 0 ? books![bookIndex - 1] : null;
  const nextBook = books && bookIndex < books.length - 1 ? books[bookIndex + 1] : null;

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-4xl p-6">
        <div className="flex items-center justify-between">
          <Breadcrumbs
            items={[
              { label: "Library", href: "/read" },
              { label: "Hadith", href: "/read/hadith" },
              { label: detail?.collection_name ?? slug, href: `/read/hadith/${slug}` },
              { label: bookName },
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
          <div className="mt-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        ) : detail ? (
          <>
            <h1 className="mt-6 text-xl font-semibold">{bookName}</h1>
            {detail.book.name_arabic && (
              <p className="font-amiri text-lg text-muted-foreground" dir="rtl">
                {detail.book.name_arabic}
              </p>
            )}
            <p className="text-sm text-muted-foreground">
              {detail.hadiths.length} Hadiths
            </p>

            <div className="mt-6 space-y-4">
              {detail.hadiths.map((h) => (
                <HadithCard
                  key={h.number}
                  hadith={h}
                  collectionName={detail.collection_name}
                  bookNumber={bookNumber}
                  arabicFontSize={settings.arabicFontSize}
                  englishFontSize={settings.englishFontSize}
                />
              ))}
            </div>

            {/* Prev / Next navigation */}
            <div className="mt-8 flex items-center justify-between border-t pt-4">
              {prevBook ? (
                <Link
                  href={`/read/hadith/${slug}/${prevBook.number}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                  {prevBook.name_english || `Book ${prevBook.number}`}
                </Link>
              ) : (
                <div />
              )}
              {nextBook ? (
                <Link
                  href={`/read/hadith/${slug}/${nextBook.number}`}
                  className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {nextBook.name_english || `Book ${nextBook.number}`}
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
