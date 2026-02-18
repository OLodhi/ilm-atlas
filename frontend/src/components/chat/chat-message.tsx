"use client";

import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

interface ChatMessageProps {
  message: ChatMessageType;
  isSelected: boolean;
  onSelect: () => void;
}

export function ChatMessage({ message, isSelected, onSelect }: ChatMessageProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  const hasCitations = message.citations && message.citations.length > 0;

  return (
    <div className="flex justify-start">
      <div
        className={cn(
          "max-w-[85%] rounded-2xl rounded-bl-md bg-muted px-4 py-3 transition-colors",
          hasCitations && "cursor-pointer hover:bg-muted/80",
          isSelected && hasCitations && "ring-2 ring-primary/30"
        )}
        onClick={hasCitations ? onSelect : undefined}
      >
        <div className="prose prose-stone max-w-none text-sm leading-relaxed prose-p:my-2 prose-headings:my-3 prose-blockquote:my-2 prose-ul:my-2 prose-ol:my-2">
          <Markdown remarkPlugins={[remarkBreaks]}>{message.content}</Markdown>
        </div>
        {hasCitations && (
          <div className="mt-2 text-[11px] text-muted-foreground">
            {message.citations!.length} source{message.citations!.length !== 1 ? "s" : ""}
          </div>
        )}
      </div>
    </div>
  );
}
