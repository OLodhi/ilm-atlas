"use client";

import { useState, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Send, Loader2, Square } from "lucide-react";
import { MADHAB_OPTIONS, CATEGORY_OPTIONS } from "@/lib/constants";

interface ChatInputProps {
  onSend: (text: string) => void;
  sending: boolean;
  onStop?: () => void;
  madhab: string;
  onMadhabChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
  usage?: { used: number; limit: number } | null;
}

export function ChatInput({
  onSend,
  sending,
  onStop,
  madhab,
  onMadhabChange,
  category,
  onCategoryChange,
  usage,
}: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSend = useCallback(() => {
    if (!text.trim() || sending) return;
    onSend(text.trim());
    setText("");
  }, [text, sending, onSend]);

  return (
    <div className="mx-4 mb-3 flex justify-center">
      <div className="relative w-full max-w-3xl rounded-xl border bg-background p-3 pb-10 ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2">
        <Textarea
          placeholder="Ask a question about Islam..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          className="min-h-[72px] max-h-[120px] resize-none border-0 shadow-none focus-visible:ring-0 p-0"
          rows={2}
        />
        <div className="absolute bottom-2 left-3 right-3 flex items-center gap-1">
          <Select value={madhab} onValueChange={onMadhabChange}>
            <SelectTrigger className="h-7 w-[120px] border-0 text-xs shadow-none focus:ring-0">
              <SelectValue placeholder="Madhab" />
            </SelectTrigger>
            <SelectContent>
              {MADHAB_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={category} onValueChange={onCategoryChange}>
            <SelectTrigger className="h-7 w-[120px] border-0 text-xs shadow-none focus:ring-0">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              {CATEGORY_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="ml-auto flex flex-col items-end gap-0.5">
            {sending && onStop ? (
              <Button
                onClick={onStop}
                size="icon"
                variant="destructive"
                className="h-8 w-8 shrink-0"
              >
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSend}
                disabled={sending || !text.trim()}
                size="icon"
                className="h-8 w-8 shrink-0"
              >
                {sending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            )}
            {usage && (
              <span className="text-[10px] text-muted-foreground">
                {usage.used}/{usage.limit}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
