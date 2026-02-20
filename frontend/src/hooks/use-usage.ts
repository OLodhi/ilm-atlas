"use client";

import { useState, useEffect, useCallback } from "react";
import { getUsage, type UsageInfo } from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

export function useUsage() {
  const { isAuthenticated } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const data = await getUsage();
      setUsage(data);
    } catch {
      // ignore
    }
  }, [isAuthenticated]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { usage, refresh };
}
