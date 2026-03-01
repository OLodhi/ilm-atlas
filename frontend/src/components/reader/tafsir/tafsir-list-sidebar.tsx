"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { TafsirSummary } from "@/lib/types";

interface TafsirListSidebarProps {
  tafsirs: TafsirSummary[];
}

export function TafsirListSidebar({ tafsirs }: TafsirListSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="p-2">
      {tafsirs.map((t) => {
        const href = `/read/tafsir/${t.slug}`;
        const active = pathname.startsWith(href);
        return (
          <Link
            key={t.slug}
            href={`${href}/1`}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-violet-50 text-violet-900 font-medium dark:bg-violet-950/30 dark:text-violet-100"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {t.name}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {t.author} &middot; {t.language}
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
