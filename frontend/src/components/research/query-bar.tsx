"use client";

import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Search, Loader2 } from "lucide-react";

interface QueryBarProps {
  question: string;
  onQuestionChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function QueryBar({
  question,
  onQuestionChange,
  onSubmit,
  loading,
}: QueryBarProps) {
  return (
    <div className="flex gap-2">
      <Textarea
        placeholder="Ask a question about Islam... (e.g., What does the Quran say about patience?)"
        value={question}
        onChange={(e) => onQuestionChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        className="min-h-[60px] resize-none"
        rows={2}
      />
      <Button
        onClick={onSubmit}
        disabled={loading || !question.trim()}
        className="self-end px-6"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Search className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}
