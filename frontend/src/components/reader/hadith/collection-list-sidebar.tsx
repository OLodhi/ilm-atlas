"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import type { CollectionSummary } from "@/lib/types";

interface CollectionListSidebarProps {
  collections: CollectionSummary[];
}

export function CollectionListSidebar({ collections }: CollectionListSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="p-2">
      {collections.map((c) => {
        const href = `/read/hadith/${c.slug}`;
        const active = pathname.startsWith(href);
        return (
          <Link
            key={c.slug}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-amber-50 text-amber-900 font-medium dark:bg-amber-950/30 dark:text-amber-100"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-foreground">
                {c.name}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {c.hadith_count.toLocaleString()} hadiths
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
