import Markdown from "react-markdown";
import { Skeleton } from "@/components/ui/skeleton";

interface AnswerPanelProps {
  answer: string | null;
  loading: boolean;
  error: string | null;
}

export function AnswerPanel({ answer, loading, error }: AnswerPanelProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!answer) {
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
    <div className="prose prose-stone max-w-none text-sm leading-relaxed">
      <Markdown>{answer}</Markdown>
    </div>
  );
}
