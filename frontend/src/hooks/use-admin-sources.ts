"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchSources } from "@/lib/api-client";
import type { SourceResponse } from "@/lib/types";

export function useAdminSources() {
  const [sources, setSources] = useState<SourceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchSources();
      setSources(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load sources"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();

    // Poll every 10 seconds for status updates
    intervalRef.current = setInterval(load, 10000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [load]);

  return { sources, loading, error, refresh: load };
}
