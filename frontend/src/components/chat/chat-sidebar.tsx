"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { useChatSessions } from "@/hooks/use-chat-sessions";

interface ChatSidebarProps {
  activeSessionId?: string;
  onSessionCreated?: () => void;
}

export function ChatSidebar({
  activeSessionId,
  onSessionCreated,
}: ChatSidebarProps) {
  const router = useRouter();
  const { sessions, refresh, create, remove } = useChatSessions();

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleNew = async () => {
    const session = await create();
    router.push(`/chat/${session.id}`);
    onSessionCreated?.();
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await remove(id);
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
      <ScrollArea className="flex-1">
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
              <span className="flex-1 truncate">
                {s.title || "New Chat"}
              </span>
              <button
                onClick={(e) => handleDelete(e, s.id)}
                className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
