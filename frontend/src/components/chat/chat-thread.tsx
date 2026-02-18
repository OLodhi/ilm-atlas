"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage } from "./chat-message";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

interface ChatThreadProps {
  messages: ChatMessageType[];
  selectedMessageId: string | null;
  onSelectMessage: (id: string) => void;
  sending: boolean;
}

export function ChatThread({
  messages,
  selectedMessageId,
  onSelectMessage,
  sending,
}: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending]);

  if (messages.length === 0 && !sending) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-lg font-medium text-muted-foreground">
            Ilm Atlas
          </p>
          <p className="text-sm text-muted-foreground">
            Ask a question to explore Islamic sources
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-3xl space-y-4 p-4 pb-6">
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isSelected={msg.id === selectedMessageId}
            onSelect={() => onSelectMessage(msg.id)}
          />
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="max-w-[85%] space-y-2 rounded-2xl rounded-bl-md bg-muted px-4 py-3">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-4 w-40" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
