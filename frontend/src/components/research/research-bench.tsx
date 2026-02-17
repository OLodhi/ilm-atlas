"use client";

import { QueryBar } from "./query-bar";
import { FilterBar } from "./filter-bar";
import { AnswerPanel } from "./answer-panel";
import { CitationsPanel } from "./citations-panel";
import { Separator } from "@/components/ui/separator";
import { useQueryResearch } from "@/hooks/use-query-research";

export function ResearchBench() {
  const {
    question,
    setQuestion,
    madhab,
    setMadhab,
    category,
    setCategory,
    response,
    loading,
    error,
    submitQuery,
  } = useQueryResearch();

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      {/* Query section */}
      <div className="shrink-0 space-y-3 border-b p-4">
        <QueryBar
          question={question}
          onQuestionChange={setQuestion}
          onSubmit={submitQuery}
          loading={loading}
        />
        <FilterBar
          madhab={madhab}
          onMadhabChange={setMadhab}
          category={category}
          onCategoryChange={setCategory}
        />
      </div>

      {/* Results split view */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Answer panel - 60% */}
        <div className="flex-1 overflow-y-auto p-6 lg:basis-3/5">
          <AnswerPanel
            answer={response?.answer ?? null}
            loading={loading}
            error={error}
          />
        </div>

        <Separator orientation="vertical" className="hidden lg:block" />
        <Separator className="lg:hidden" />

        {/* Citations panel - 40% */}
        <div className="min-h-0 flex-1 p-4 lg:basis-2/5">
          <CitationsPanel citations={response?.citations ?? []} />
        </div>
      </div>
    </div>
  );
}
