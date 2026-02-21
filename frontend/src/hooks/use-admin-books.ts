"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchBooks } from "@/lib/api-client";
import { parseApiError } from "@/lib/api-errors";
import type { BookResponse } from "@/lib/types";

export function useAdminBooks() {
  const [books, setBooks] = useState<BookResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchBooks();
      setBooks(data);
      setError(null);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { books, loading, error, refresh: load };
}
