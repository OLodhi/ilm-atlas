"use client";

import { useEffect, useState, useCallback } from "react";
import { ChatSidebar } from "./chat-sidebar";
import { ChatThread } from "./chat-thread";
import { ChatInput } from "./chat-input";
import { Button } from "@/components/ui/button";
import { Menu, X } from "lucide-react";
import { useChat } from "@/hooks/use-chat";
import { useUsage } from "@/hooks/use-usage";
import { useAuth } from "@/contexts/auth-context";
import { EmailVerificationModal } from "@/components/shared/email-verification-modal";

interface ChatLayoutProps {
  sessionId: string;
  emailVerified?: boolean;
}

export function ChatLayout({ sessionId, emailVerified }: ChatLayoutProps) {
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
    abortStream,
  } = useChat(sessionId);

  const { user } = useAuth();
  const { usage, refresh: refreshUsage } = useUsage();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showVerifyModal, setShowVerifyModal] = useState(false);

  const handleSend = useCallback(
    async (text: string) => {
      if (emailVerified === false) {
        setShowVerifyModal(true);
        return;
      }
      await sendMessage(text);
      refreshUsage();
    },
    [emailVerified, sendMessage, refreshUsage]
  );

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Escape key cancels streaming
  useEffect(() => {
    if (!sending) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        abortStream();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sending, abortStream]);

  return (
    <div className="flex h-full">
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
          onNewChat={emailVerified === false ? () => setShowVerifyModal(true) : undefined}
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
        <div className="min-h-0 flex-1 pb-1">
          <ChatThread
            messages={session?.messages ?? []}
            sending={sending}
          />
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          sending={sending}
          onStop={abortStream}
          madhab={madhab}
          onMadhabChange={setMadhab}
          category={category}
          onCategoryChange={setCategory}
          usage={usage}
        />
      </div>
      {user && (
        <EmailVerificationModal
          email={user.email}
          open={showVerifyModal}
          onClose={() => setShowVerifyModal(false)}
          onVerified={() => setShowVerifyModal(false)}
        />
      )}
    </div>
  );
}
