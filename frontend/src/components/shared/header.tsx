"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

export function Header() {
  const pathname = usePathname();

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center px-4">
        <Link href="/" className="mr-8 font-semibold tracking-tight">
          Ilm Atlas
        </Link>
        <nav className="flex gap-6 text-sm">
          <Link
            href="/"
            className={cn(
              "transition-colors hover:text-foreground",
              pathname === "/"
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Research
          </Link>
          <Link
            href="/admin"
            className={cn(
              "transition-colors hover:text-foreground",
              pathname === "/admin"
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Admin
          </Link>
        </nav>
      </div>
    </header>
  );
}
