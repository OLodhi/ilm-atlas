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
import { Send, Loader2 } from "lucide-react";
import { MADHAB_OPTIONS, CATEGORY_OPTIONS } from "@/lib/constants";

interface ChatInputProps {
  onSend: (text: string) => void;
  sending: boolean;
  madhab: string;
  onMadhabChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
}

export function ChatInput({
  onSend,
  sending,
  madhab,
  onMadhabChange,
  category,
  onCategoryChange,
}: ChatInputProps) {
  const [text, setText] = useState("");

  const handleSend = useCallback(() => {
    if (!text.trim() || sending) return;
    onSend(text.trim());
    setText("");
  }, [text, sending, onSend]);

  return (
    <div className="border-t bg-background p-4">
      <div className="mx-auto max-w-3xl space-y-2">
        <div className="flex gap-2">
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
            className="min-h-[48px] max-h-[120px] resize-none"
            rows={1}
          />
          <Button
            onClick={handleSend}
            disabled={sending || !text.trim()}
            size="icon"
            className="shrink-0 self-end"
          >
            {sending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <div className="flex gap-2">
          <Select value={madhab} onValueChange={onMadhabChange}>
            <SelectTrigger className="h-7 w-[140px] text-xs">
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
            <SelectTrigger className="h-7 w-[140px] text-xs">
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
        </div>
      </div>
    </div>
  );
}
