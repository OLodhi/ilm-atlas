"use client";

import { useState, useCallback } from "react";
import { postQuery } from "@/lib/api-client";
import type { QueryResponse } from "@/lib/types";

export function useQueryResearch() {
  const [question, setQuestion] = useState("");
  const [madhab, setMadhab] = useState("all");
  const [category, setCategory] = useState("all");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitQuery = useCallback(async () => {
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await postQuery({
        question: question.trim(),
        madhab,
        category,
      });
      setResponse(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to get response"
      );
    } finally {
      setLoading(false);
    }
  }, [question, madhab, category]);

  return {
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
  };
}
