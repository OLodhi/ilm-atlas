"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ReaderLayout } from "@/components/reader/reader-layout";
import { Breadcrumbs } from "@/components/reader/breadcrumbs";
import { fetchHadithBooks, fetchHadithCollections } from "@/lib/api-client";
import type { HadithBookSummary, CollectionSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

export default function HadithCollectionPage() {
  const params = useParams();
  const slug = params.collection as string;

  const [collection, setCollection] = useState<CollectionSummary | null>(null);
  const [books, setBooks] = useState<HadithBookSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Get collection name from collections list
    fetchHadithCollections()
      .then((cols) => {
        const match = cols.find((c) => c.slug === slug);
        if (match) setCollection(match);
      })
      .catch(console.error);

    fetchHadithBooks(slug)
      .then(setBooks)
      .catch(() => setError("Collection not found"));
  }, [slug]);

  const collectionName = collection?.name ?? slug;

  return (
    <ReaderLayout>
      <div className="mx-auto max-w-3xl p-6">
        <Breadcrumbs
          items={[
            { label: "Library", href: "/read" },
            { label: "Hadith", href: "/read/hadith" },
            { label: collectionName },
          ]}
        />

        <h1 className="mt-4 text-2xl font-semibold">{collectionName}</h1>
        <p className="mt-1 text-muted-foreground">
          {books ? `${books.length} Books` : "Loading..."}
        </p>

        {error && <p className="mt-4 text-destructive">{error}</p>}

        {!books && !error ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : books ? (
          <div className="mt-6 space-y-2">
            {books.map((b) => (
              <Link
                key={b.number}
                href={`/read/hadith/${slug}/${b.number}`}
                className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-amber-50/50 dark:hover:bg-amber-950/10"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-sm font-medium">
                  {b.number}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {b.name_english || `Book ${b.number}`}
                  </div>
                  {b.name_arabic && (
                    <div className="text-sm font-amiri text-muted-foreground" dir="rtl">
                      {b.name_arabic}
                    </div>
                  )}
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {b.hadith_count} hadiths
                </span>
              </Link>
            ))}
          </div>
        ) : null}
      </div>
    </ReaderLayout>
  );
}
