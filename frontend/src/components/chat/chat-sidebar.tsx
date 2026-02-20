"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, Trash2, MessageSquare, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatSessions } from "@/hooks/use-chat-sessions";

interface ChatSidebarProps {
  activeSessionId?: string;
  activeSessionTitle?: string | null;
  onSessionCreated?: () => void;
}

export function ChatSidebar({
  activeSessionId,
  activeSessionTitle,
  onSessionCreated,
}: ChatSidebarProps) {
  const router = useRouter();
  const { sessions, refresh, create, remove, updateTitle } = useChatSessions();

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Sync streamed title into the sidebar list
  useEffect(() => {
    if (activeSessionId && activeSessionTitle) {
      updateTitle(activeSessionId, activeSessionTitle);
    }
  }, [activeSessionId, activeSessionTitle, updateTitle]);

  const handleNew = async () => {
    const session = await create();
    router.push(`/chat/${session.id}`);
    onSessionCreated?.();
  };

  const handleDelete = (id: string, title: string) => {
    const label = title || "New Chat";
    if (!window.confirm(`Delete "${label}"? This cannot be undone.`)) return;
    remove(id);
    if (id === activeSessionId) {
      router.push("/");
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b p-3">
        <Button onClick={handleNew} className="w-full gap-2" variant="outline">
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-1 p-2">
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => router.push(`/chat/${s.id}`)}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted",
                s.id === activeSessionId && "bg-muted font-medium"
              )}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">
                {s.title || "New Chat"}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => handleDelete(s.id, s.title ?? "")}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
