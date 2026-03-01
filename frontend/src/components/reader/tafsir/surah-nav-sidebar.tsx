"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { SurahSummary } from "@/lib/types";

interface SurahNavSidebarProps {
  tafsirSlug: string;
  surahs: SurahSummary[];
}

export function SurahNavSidebar({ tafsirSlug, surahs }: SurahNavSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="p-2">
      {surahs.map((s) => {
        const href = `/read/tafsir/${tafsirSlug}/${s.number}`;
        const active = pathname === href;
        return (
          <Link
            key={s.number}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-violet-50 text-violet-900 font-medium dark:bg-violet-950/30 dark:text-violet-100"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border text-xs font-medium">
              {s.number}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {s.name_english}
              </div>
              <div className="truncate text-xs font-amiri" dir="rtl">
                {s.name_arabic}
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
