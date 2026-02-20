"use client";

import { useEffect, useState, useCallback } from "react";
import { ChatSidebar } from "./chat-sidebar";
import { ChatThread } from "./chat-thread";
import { ChatInput } from "./chat-input";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useChat } from "@/hooks/use-chat";
import { useUsage } from "@/hooks/use-usage";

interface ChatLayoutProps {
  sessionId: string;
}

export function ChatLayout({ sessionId }: ChatLayoutProps) {
  const {
    session,
    sending,
    error,
    madhab,
    setMadhab,
    category,
    setCategory,
    loadSession,
    sendMessage,
  } = useChat(sessionId);

  const { usage, refresh: refreshUsage } = useUsage();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleSend = useCallback(
    async (text: string) => {
      await sendMessage(text);
      refreshUsage();
    },
    [sendMessage, refreshUsage]
  );

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } fixed inset-y-[3.5rem] left-0 z-50 w-[280px] border-r bg-background transition-transform lg:static lg:translate-x-0`}
      >
        <ChatSidebar
          activeSessionId={sessionId}
          activeSessionTitle={session?.title}
          onSessionCreated={() => setSidebarOpen(false)}
        />
      </div>

      {/* Main chat area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile menu button */}
        <div className="flex shrink-0 items-center border-b px-4 py-2 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </Button>
          <span className="ml-2 flex-1 truncate text-sm font-medium">
            {session?.title || "New Chat"}
          </span>
        </div>

        {/* Error display */}
        {error && (
          <div className="shrink-0 border-b border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Thread */}
        <div className="min-h-0 flex-1">
          <ChatThread
            messages={session?.messages ?? []}
            sending={sending}
          />
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          sending={sending}
          madhab={madhab}
          onMadhabChange={setMadhab}
          category={category}
          onCategoryChange={setCategory}
        />
        {usage && (
          <div className="shrink-0 border-t px-4 py-1.5 text-center text-xs text-muted-foreground">
            {usage.used}/{usage.limit} queries today
          </div>
        )}
      </div>
    </div>
  );
}
