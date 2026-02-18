"use client";

import { useState, useCallback } from "react";
import { getChatSession, sendChatMessage } from "@/lib/api-client";
import type { ChatMessage, ChatSessionDetail, Citation } from "@/lib/types";

export function useChat(sessionId: string) {
  const [session, setSession] = useState<ChatSessionDetail | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [madhab, setMadhab] = useState("all");
  const [category, setCategory] = useState("all");
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(
    null
  );

  const loadSession = useCallback(async () => {
    // Reset state when loading a new session (prevents stale data flash on navigation)
    setSession(null);
    setError(null);
    setSelectedMessageId(null);
    try {
      const data = await getChatSession(sessionId);
      setSession(data);
      // Auto-select the last assistant message
      const lastAssistant = [...data.messages]
        .reverse()
        .find((m) => m.role === "assistant");
      if (lastAssistant) {
        setSelectedMessageId(lastAssistant.id);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load session"
      );
    }
  }, [sessionId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || sending) return;

      setSending(true);
      setError(null);

      // Optimistically add user message
      const tempUserMsg: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: "user",
        content: text,
        citations: null,
        created_at: new Date().toISOString(),
      };
      setSession((prev) =>
        prev
          ? { ...prev, messages: [...prev.messages, tempUserMsg] }
          : prev
      );

      try {
        const result = await sendChatMessage(sessionId, {
          message: text,
          madhab,
          category,
        });

        // Replace temp user message with real one and append assistant response
        setSession((prev) => {
          if (!prev) return prev;
          const messages = prev.messages.filter(
            (m) => m.id !== tempUserMsg.id
          );
          return {
            ...prev,
            title: result.session_title ?? prev.title,
            messages: [...messages, result.user_message, result.message],
          };
        });
        setSelectedMessageId(result.message.id);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to send message"
        );
        // Remove optimistic user message on failure
        setSession((prev) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.filter(
                  (m) => m.id !== tempUserMsg.id
                ),
              }
            : prev
        );
      } finally {
        setSending(false);
      }
    },
    [sessionId, sending, madhab, category]
  );

  // Get citations for the selected (or latest) assistant message
  const activeCitations: Citation[] = (() => {
    if (!session) return [];
    const targetId =
      selectedMessageId ??
      [...session.messages].reverse().find((m) => m.role === "assistant")?.id;
    if (!targetId) return [];
    const msg = session.messages.find((m) => m.id === targetId);
    return msg?.citations ?? [];
  })();

  return {
    session,
    sending,
    error,
    madhab,
    setMadhab,
    category,
    setCategory,
    selectedMessageId,
    setSelectedMessageId,
    loadSession,
    sendMessage,
    activeCitations,
  };
}
