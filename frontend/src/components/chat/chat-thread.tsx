"use client";

import { useEffect, useRef, useCallback } from "react";
import { ChatMessage } from "./chat-message";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

interface ChatThreadProps {
  messages: ChatMessageType[];
  sending: boolean;
}

export function ChatThread({ messages, sending }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  const checkNearBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const threshold = 150;
    isNearBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }, []);

  // Track scroll position to decide whether to auto-scroll
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", checkNearBottom, { passive: true });
    return () => el.removeEventListener("scroll", checkNearBottom);
  }, [checkNearBottom]);

  // Content-aware auto-scroll: triggers on message count, sending state,
  // and last message content length (for streaming token updates)
  const lastMsg = messages[messages.length - 1];
  const scrollTrigger = lastMsg
    ? `${lastMsg.id}-${lastMsg.content.length}`
    : "";

  useEffect(() => {
    if (isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, sending, scrollTrigger]);

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

  // Show skeleton only when sending and last message is NOT an assistant
  // (during streaming the assistant bubble is already visible with content)
  const showSkeleton =
    sending && (!lastMsg || lastMsg.role !== "assistant");

  return (
    <div ref={scrollRef} data-chat-scroll className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-4 p-4 pb-6">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        {showSkeleton && (
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
    </div>
  );
}
