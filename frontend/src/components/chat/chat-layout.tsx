"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ChatSidebar } from "./chat-sidebar";
import { ChatThread } from "./chat-thread";
import { ChatInput } from "./chat-input";
import { CitationsPanel } from "@/components/research/citations-panel";
import { Button } from "@/components/ui/button";
import { Menu, X, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useChat } from "@/hooks/use-chat";
import { cn } from "@/lib/utils";

interface ChatLayoutProps {
  sessionId: string;
}

const MIN_PANEL_WIDTH = 250;
const MAX_PANEL_WIDTH = 700;
const DEFAULT_PANEL_WIDTH = 350;

export function ChatLayout({ sessionId }: ChatLayoutProps) {
  const {
    session,
    sending,
    error,
    madhab,
    setMadhab,
    category,
    setCategory,
    selectedMessageId,
    setSelectedMessageId,
    loadSession,
    sendMessage,
    activeCitations,
  } = useChat(sessionId);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelWidth, setPanelWidth] = useState(DEFAULT_PANEL_WIDTH);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Drag-to-resize handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;
      setPanelWidth(Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, newWidth)));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, []);

  const hasCitations = activeCitations.length > 0;

  return (
    <div ref={containerRef} className="flex h-[calc(100vh-3.5rem)]">
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
          onSessionCreated={() => setSidebarOpen(false)}
        />
      </div>

      {/* Main chat area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile menu button + sources toggle */}
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
            selectedMessageId={selectedMessageId}
            onSelectMessage={setSelectedMessageId}
            sending={sending}
          />
        </div>

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          sending={sending}
          madhab={madhab}
          onMadhabChange={setMadhab}
          category={category}
          onCategoryChange={setCategory}
        />
      </div>

      {/* Citations panel — desktop, resizable + collapsible */}
      {hasCitations && (
        <div className="hidden lg:flex">
          {/* Drag handle / separator */}
          <div
            onMouseDown={panelOpen ? handleMouseDown : undefined}
            className={cn(
              "group relative flex w-2 shrink-0 items-center justify-center border-l bg-muted/30 transition-colors hover:bg-muted",
              panelOpen && "cursor-col-resize"
            )}
          >
            {/* Toggle button centered on the separator */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPanelOpen(!panelOpen)}
              className="absolute z-10 h-8 w-8 rounded-full border bg-background shadow-sm opacity-0 transition-opacity group-hover:opacity-100"
            >
              {panelOpen ? (
                <PanelRightClose className="h-3.5 w-3.5" />
              ) : (
                <PanelRightOpen className="h-3.5 w-3.5" />
              )}
            </Button>
            {/* Visible drag indicator dots */}
            {panelOpen && (
              <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <div className="h-0.5 w-0.5 rounded-full bg-muted-foreground/50" />
                <div className="h-0.5 w-0.5 rounded-full bg-muted-foreground/50" />
                <div className="h-0.5 w-0.5 rounded-full bg-muted-foreground/50" />
              </div>
            )}
          </div>

          {/* Panel content */}
          {panelOpen && (
            <div
              className="shrink-0 overflow-hidden p-4"
              style={{ width: panelWidth }}
            >
              <CitationsPanel citations={activeCitations} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
