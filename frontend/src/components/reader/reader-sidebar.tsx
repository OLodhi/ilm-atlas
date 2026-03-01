"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { BookOpen, BookText, MessageSquareText } from "lucide-react";

const SOURCE_TYPES = [
  { href: "/read/quran", label: "Quran", icon: BookOpen, color: "text-emerald-600" },
  { href: "/read/hadith", label: "Hadith", icon: BookText, color: "text-amber-600" },
  { href: "/read/tafsir", label: "Tafsir", icon: MessageSquareText, color: "text-violet-600" },
] as const;

interface ReaderSidebarProps {
  children?: React.ReactNode;
}

export function ReaderSidebar({ children }: ReaderSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b p-4">
        <h2 className="text-sm font-semibold">Library</h2>
      </div>

      <div className="shrink-0 border-b p-2">
        {SOURCE_TYPES.map(({ href, label, icon: Icon, color }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              pathname.startsWith(href)
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
            )}
          >
            <Icon className={cn("h-4 w-4", color)} />
            {label}
          </Link>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
