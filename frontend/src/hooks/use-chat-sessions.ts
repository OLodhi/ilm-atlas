"use client";

import { useState, useCallback } from "react";
import {
  listChatSessions,
  createChatSession,
  deleteChatSession,
  renameChatSession,
} from "@/lib/api-client";
import type { ChatSession } from "@/lib/types";

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listChatSessions();
      setSessions(data.sessions);
    } catch {
      // Silently fail — sidebar is non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (): Promise<ChatSession> => {
    const session = await createChatSession();
    setSessions((prev) => [session, ...prev]);
    return session;
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteChatSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const rename = useCallback(async (id: string, title: string) => {
    const updated = await renameChatSession(id, title);
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title: updated.title } : s))
    );
  }, []);

  const updateTitle = useCallback((id: string, title: string) => {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, title } : s))
    );
  }, []);

  return {
    sessions,
    loading,
    refresh,
    create,
    remove,
    rename,
    updateTitle,
  };
}
