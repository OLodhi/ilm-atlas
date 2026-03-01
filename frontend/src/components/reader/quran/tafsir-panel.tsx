"use client";

import { useEffect, useState } from "react";
import { fetchAyahTafsir } from "@/lib/api-client";
import type { TafsirForAyah } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface TafsirPanelProps {
  surahNumber: number;
  ayahNumber: number;
}

export function TafsirPanel({ surahNumber, ayahNumber }: TafsirPanelProps) {
  const [entries, setEntries] = useState<TafsirForAyah[] | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEntries(null);
    setError(null);
    fetchAyahTafsir(surahNumber, ayahNumber)
      .then((data) => {
        setEntries(data);
        if (data.length > 0) setActiveSlug(data[0].tafsir_slug);
      })
      .catch(() => setError("Failed to load tafsir"));
  }, [surahNumber, ayahNumber]);

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (!entries) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No tafsir available for this ayah.
      </p>
    );
  }

  const active = entries.find((e) => e.tafsir_slug === activeSlug) ?? entries[0];

  return (
    <div className="space-y-3">
      {/* Tafsir tabs */}
      <div className="flex flex-wrap gap-1.5">
        {entries.map((e) => (
          <button
            key={e.tafsir_slug}
            onClick={() => setActiveSlug(e.tafsir_slug)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              e.tafsir_slug === activeSlug
                ? "border-violet-300 bg-violet-50 text-violet-800 dark:border-violet-700 dark:bg-violet-950/30 dark:text-violet-200"
                : "text-muted-foreground hover:bg-accent"
            )}
          >
            {e.tafsir_name}
            <span className="ml-1 opacity-60">({e.language})</span>
          </button>
        ))}
      </div>

      {/* Active tafsir content */}
      {active.text ? (
        <div
          className={cn(
            "rounded-md border-l-4 border-violet-600 bg-violet-50/50 p-4 text-sm leading-relaxed dark:bg-violet-950/10",
            active.language === "arabic" && "font-amiri text-right text-lg leading-loose"
          )}
          dir={active.language === "arabic" ? "rtl" : "ltr"}
        >
          {active.text}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No content available.</p>
      )}
    </div>
  );
}
