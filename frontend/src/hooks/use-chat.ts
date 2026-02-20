"use client";

import { useState, useCallback } from "react";
import { getChatSession, sendChatMessage } from "@/lib/api-client";
import type { ChatMessage, ChatSessionDetail } from "@/lib/types";

// Module-level map of in-flight send requests per session.
// Survives component unmounts so navigating away doesn't lose the request.
interface PendingSend {
  promise: Promise<void>;
  optimisticMessage: ChatMessage;
}
const pendingSends = new Map<string, PendingSend>();

export function useChat(sessionId: string) {
  const [session, setSession] = useState<ChatSessionDetail | null>(null);
  const [sending, setSending] = useState(() => pendingSends.has(sessionId));
  const [error, setError] = useState<string | null>(null);
  const [madhab, setMadhab] = useState("all");
  const [category, setCategory] = useState("all");

  const loadSession = useCallback(async () => {
    setError(null);

    // If there's an in-flight send for this session, show existing messages
    // plus the optimistic user message while we wait for the response.
    const pending = pendingSends.get(sessionId);
    if (pending) {
      setSending(true);
      // Load current session data and append the optimistic user message
      // so the user sees their question while the response generates.
      try {
        const current = await getChatSession(sessionId);
        setSession({
          ...current,
          messages: [...current.messages, pending.optimisticMessage],
        });
      } catch {
        // If fetch fails, just show the optimistic message
      }
      try {
        await pending.promise;
      } catch {
        // Send failed — loadSession will still fetch whatever is in the DB
      }
      setSending(false);
    }

    try {
      const data = await getChatSession(sessionId);
      setSession(data);
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

      // Create the send promise and store it module-level so it
      // survives component unmounts during navigation.
      const sendPromise = (async () => {
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
          throw err; // Re-throw so pendingSends waiters see the failure
        } finally {
          pendingSends.delete(sessionId);
          setSending(false);
        }
      })();

      pendingSends.set(sessionId, {
        promise: sendPromise,
        optimisticMessage: tempUserMsg,
      });

      // Await locally so errors are caught within this component instance
      try {
        await sendPromise;
      } catch {
        // Already handled above
      }
    },
    [sessionId, sending, madhab, category]
  );

  return {
    session,
    sending,
    error,
    madhab,
    setMadhab,
    category,
    setCategory,
    loadSession,
    sendMessage,
  };
}
