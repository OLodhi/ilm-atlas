"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookText } from "lucide-react";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchHadithCollections } from "@/lib/api-client";
import type { CollectionSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithPage() {
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);

  useEffect(() => {
    fetchHadithCollections().then(setCollections).catch(console.error);
  }, []);

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-4xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Hadith" },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">Hadith Collections</h1>
        <p className="mt-1 text-muted-foreground">
          {collections ? `${collections.length} collections` : "Loading..."}
        </p>

        {!collections ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4">
            {collections.map((c) => (
              <Link
                key={c.slug}
                href={`/read/hadith/${c.slug}`}
                className="flex items-center gap-4 rounded-lg border-l-4 border-l-amber-600 border bg-card p-5 transition-colors hover:bg-amber-50/50 dark:hover:bg-amber-950/10"
              >
                <BookText className="h-8 w-8 shrink-0 text-amber-600" />
                <div className="min-w-0 flex-1">
                  <div className="font-semibold">{c.name}</div>
                  <div className="text-sm text-muted-foreground">
                    by {c.author}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {c.book_count} Books &middot;{" "}
                    {c.hadith_count.toLocaleString()} Hadiths
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
