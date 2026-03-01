"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { SurahListSidebar } from "@/components/reader/quran/surah-list-sidebar";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchSurahs } from "@/lib/api-client";
import type { SurahSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function QuranPage() {
  const [surahs, setSurahs] = useState<SurahSummary[] | null>(null);

  useEffect(() => {
    fetchSurahs().then(setSurahs).catch(console.error);
  }, []);

  return (
    <ReaderLayout
      sidebarContent={surahs ? <SurahListSidebar surahs={surahs} /> : null}
    >
      <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Quran" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">The Holy Quran</h1>
        <p className="mt-1 text-muted-foreground">
          {surahs ? `${surahs.length} Surahs` : "Loading..."}
        </p>

        {!surahs ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {surahs.map((s) => (
              <Link
                key={s.number}
                href={`/read/quran/${s.number}`}
                className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-emerald-50/50 dark:hover:bg-emerald-950/10"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border-2 border-emerald-200 text-sm font-semibold text-emerald-700 dark:border-emerald-800 dark:text-emerald-300">
                  {s.number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{s.name_english}</div>
                  <div className="text-xs text-muted-foreground">
                    {s.ayah_count} Ayahs &middot; {s.revelation_type}
                  </div>
                </div>
                <div className="shrink-0 font-amiri text-lg" dir="rtl">
                  {s.name_arabic}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </ReaderLayout>
  );
}
