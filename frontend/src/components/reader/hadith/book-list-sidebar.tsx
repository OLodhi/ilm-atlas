"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { HadithBookSummary } from "@/lib/types";

interface BookListSidebarProps {
  collectionSlug: string;
  books: HadithBookSummary[];
}

export function BookListSidebar({ collectionSlug, books }: BookListSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="p-2">
      {books.map((b) => {
        const href = `/read/hadith/${collectionSlug}/${b.number}`;
        const active = pathname === href;
        return (
          <Link
            key={b.number}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-amber-50 text-amber-900 font-medium dark:bg-amber-950/30 dark:text-amber-100"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border text-xs font-medium">
              {b.number}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {b.name_english || `Book ${b.number}`}
              </div>
              {b.name_arabic && (
                <div className="truncate text-xs font-amiri" dir="rtl">
                  {b.name_arabic}
                </div>
              )}
            </div>
            <span className="shrink-0 text-xs">{b.hadith_count}</span>
          </Link>
        );
      })}
    </div>
  );
}
