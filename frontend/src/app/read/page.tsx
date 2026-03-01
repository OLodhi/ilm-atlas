"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, BookText, MessageSquareText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchLibraryStats } from "@/lib/api-client";
import type { LibraryStats } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

const SOURCE_CARDS = [
  {
    href: "/read/quran",
    title: "Quran",
    icon: BookOpen,
    color: "border-emerald-600",
    bgHover: "hover:bg-emerald-50 dark:hover:bg-emerald-950/20",
    iconColor: "text-emerald-600",
    getStat: (s: LibraryStats) =>
      `${s.quran_surah_count} Surahs \u00b7 ${s.quran_ayah_count.toLocaleString()} Ayahs`,
  },
  {
    href: "/read/hadith",
    title: "Hadith",
    icon: BookText,
    color: "border-amber-600",
    bgHover: "hover:bg-amber-50 dark:hover:bg-amber-950/20",
    iconColor: "text-amber-600",
    getStat: (s: LibraryStats) =>
      `${s.hadith_collection_count} Collections \u00b7 ${s.hadith_count.toLocaleString()} Hadiths`,
  },
  {
    href: "/read/tafsir",
    title: "Tafsir",
    icon: MessageSquareText,
    color: "border-violet-600",
    bgHover: "hover:bg-violet-50 dark:hover:bg-violet-950/20",
    iconColor: "text-violet-600",
    getStat: (s: LibraryStats) =>
      `${s.tafsir_count} Tafsirs \u00b7 ${s.tafsir_entry_count.toLocaleString()} Entries`,
  },
] as const;

export default function ReadPage() {
  const [stats, setStats] = useState<LibraryStats | null>(null);

  useEffect(() => {
    fetchLibraryStats().then(setStats).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
        <Breadcrumbs items={[{ label: "Library" }]} />

        <h1 className="mt-4 text-2xl font-semibold">Source Library</h1>
        <p className="mt-1 text-muted-foreground">
          Browse and read the Quran, Hadith collections, and Tafsir commentaries.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {SOURCE_CARDS.map(({ href, title, icon: Icon, color, bgHover, iconColor, getStat }) => (
            <Link
              key={href}
              href={href}
              className={`rounded-lg border-l-4 ${color} border bg-card p-5 transition-colors ${bgHover}`}
            >
              <Icon className={`h-8 w-8 ${iconColor}`} />
              <h2 className="mt-3 font-semibold">{title}</h2>
              {stats ? (
                <p className="mt-1 text-sm text-muted-foreground">
                  {getStat(stats)}
                </p>
              ) : (
                <Skeleton className="mt-1 h-4 w-32" />
              )}
            </Link>
          ))}
        </div>
      </div>
    </ReaderLayout>
  );
}
