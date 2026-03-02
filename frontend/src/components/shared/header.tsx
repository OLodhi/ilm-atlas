"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { User, LogOut, Settings } from "lucide-react";

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [visible, setVisible] = useState(true);
  const lastScrollY = useRef(0);
  const isMobile = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1023px)");
    isMobile.current = mq.matches;
    const onChange = (e: MediaQueryListEvent) => {
      isMobile.current = e.matches;
      if (!e.matches) setVisible(true);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const handleScroll = useCallback((e: Event) => {
    if (!isMobile.current) return;
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const y = target.scrollTop;
    if (Math.abs(y - lastScrollY.current) < 10) return;
    setVisible(y <= 0 || y < lastScrollY.current);
    lastScrollY.current = y;
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", handleScroll, { capture: true });
  }, [handleScroll]);

  async function handleLogout() {
    await logout();
    router.push("/");
  }

  return (
    <div className={cn(
      "shrink-0 overflow-hidden transition-[max-height] duration-300 lg:!max-h-14",
      visible ? "max-h-14" : "max-h-0"
    )}>
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
              pathname === "/" || pathname.startsWith("/chat")
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Chat
          </Link>
          <Link
            href="/read"
            className={cn(
              "transition-colors hover:text-foreground",
              pathname.startsWith("/read")
                ? "text-foreground"
                : "text-muted-foreground"
            )}
          >
            Read
          </Link>
          {isAuthenticated && user?.role === "admin" && (
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
          )}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {isLoading ? null : isAuthenticated ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-2">
                  <User className="h-4 w-4" />
                  <span className="hidden sm:inline">
                    {user?.display_name || user?.email}
                  </span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => router.push("/settings")}>
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/login">Sign In</Link>
              </Button>
              <Button size="sm" asChild>
                <Link href="/register">Sign Up</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
    </div>
  );
}
