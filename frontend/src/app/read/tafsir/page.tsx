"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquareText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchTafsirList } from "@/lib/api-client";
import type { TafsirSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function TafsirPage() {
  const [tafsirs, setTafsirs] = useState<TafsirSummary[] | null>(null);

  useEffect(() => {
    fetchTafsirList().then(setTafsirs).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Tafsir" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">Tafsir Commentaries</h1>
        <p className="mt-1 text-muted-foreground">
          {tafsirs ? `${tafsirs.length} tafsirs available` : "Loading..."}
        </p>

        {!tafsirs ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4">
            {tafsirs.map((t) => (
              <Link
                key={t.slug}
                href={`/read/tafsir/${t.slug}/1`}
                className="flex items-center gap-4 rounded-lg border-l-4 border-l-violet-600 border bg-card p-5 transition-colors hover:bg-violet-50/50 dark:hover:bg-violet-950/10"
              >
                <MessageSquareText className="h-8 w-8 shrink-0 text-violet-600" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{t.name}</div>
                  <div className="text-sm text-muted-foreground">
                    by {t.author}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {t.surah_count} Surahs &middot; {t.language}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </ReaderLayout>
  );
}
