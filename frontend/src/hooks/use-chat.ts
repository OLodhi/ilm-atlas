"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { getChatSession, streamChatMessage } from "@/lib/api-client";
import { parseApiError } from "@/lib/api-errors";
import { STREAMING_MSG_ID } from "@/lib/constants";
import type { ChatMessage, ChatSessionDetail } from "@/lib/types";

// Module-level map of in-flight streams per session.
// Survives component unmounts so navigating away doesn't lose the stream.
interface PendingStream {
  promise: Promise<void>;
  optimisticMessage: ChatMessage;
}
const pendingStreams = new Map<string, PendingStream>();

export function useChat(sessionId: string) {
  const [session, setSession] = useState<ChatSessionDetail | null>(null);
  const [sending, setSending] = useState(() => pendingStreams.has(sessionId));
  const [error, setError] = useState<string | null>(null);
  const [madhab, setMadhab] = useState("all");
  const [category, setCategory] = useState("all");

  // RAF-throttled token buffer
  const tokenBufferRef = useRef("");
  const rafRef = useRef<number | null>(null);

  // Cleanup RAF on unmount
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  const flushTokenBuffer = useCallback(() => {
    rafRef.current = null;
    const buffered = tokenBufferRef.current;
    if (!buffered) return;
    tokenBufferRef.current = "";

    setSession((prev) => {
      if (!prev) return prev;
      const msgs = prev.messages;
      const last = msgs[msgs.length - 1];
      if (!last || last.id !== STREAMING_MSG_ID) return prev;
      return {
        ...prev,
        messages: [
          ...msgs.slice(0, -1),
          { ...last, content: last.content + buffered },
        ],
      };
    });
  }, []);

  const loadSession = useCallback(async () => {
    setError(null);

    // If there's an in-flight stream for this session, show existing messages
    // plus the optimistic user message while we wait for the response.
    const pending = pendingStreams.get(sessionId);
    if (pending) {
      setSending(true);
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
        // Stream failed — loadSession will still fetch whatever is in the DB
      }
      setSending(false);
    }

    try {
      const data = await getChatSession(sessionId);
      setSession(data);
    } catch (err) {
      setError(parseApiError(err));
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

      const streamPromise = (async () => {
        try {
          await streamChatMessage(
            sessionId,
            { message: text, madhab, category },
            {
              onUserMessage: (data) => {
                // Replace temp user msg with real one, add streaming placeholder
                setSession((prev) => {
                  if (!prev) return prev;
                  const messages = prev.messages.filter(
                    (m) => m.id !== tempUserMsg.id
                  );
                  const realUserMsg: ChatMessage = {
                    id: data.id,
                    role: "user",
                    content: data.content,
                    citations: null,
                    created_at: data.created_at,
                  };
                  const streamingMsg: ChatMessage = {
                    id: STREAMING_MSG_ID,
                    role: "assistant",
                    content: "",
                    citations: null,
                    created_at: new Date().toISOString(),
                  };
                  return {
                    ...prev,
                    messages: [...messages, realUserMsg, streamingMsg],
                  };
                });
              },

              onContentDelta: (data) => {
                tokenBufferRef.current += data.token;
                if (rafRef.current === null) {
                  rafRef.current = requestAnimationFrame(flushTokenBuffer);
                }
              },

              onCitations: (data) => {
                // Flush any remaining tokens first
                if (rafRef.current !== null) {
                  cancelAnimationFrame(rafRef.current);
                  rafRef.current = null;
                }
                const buffered = tokenBufferRef.current;
                tokenBufferRef.current = "";

                setSession((prev) => {
                  if (!prev) return prev;
                  const msgs = prev.messages;
                  const last = msgs[msgs.length - 1];
                  if (!last || last.id !== STREAMING_MSG_ID) return prev;
                  return {
                    ...prev,
                    messages: [
                      ...msgs.slice(0, -1),
                      {
                        ...last,
                        content: last.content + buffered,
                        citations: data.citations,
                      },
                    ],
                  };
                });
              },

              onTitle: (data) => {
                setSession((prev) =>
                  prev ? { ...prev, title: data.title } : prev
                );
              },

              onDone: (data) => {
                // Flush remaining buffer
                if (rafRef.current !== null) {
                  cancelAnimationFrame(rafRef.current);
                  rafRef.current = null;
                }
                const buffered = tokenBufferRef.current;
                tokenBufferRef.current = "";

                // Replace streaming ID with real message ID
                setSession((prev) => {
                  if (!prev) return prev;
                  const msgs = prev.messages;
                  const last = msgs[msgs.length - 1];
                  if (!last || last.id !== STREAMING_MSG_ID) return prev;
                  return {
                    ...prev,
                    messages: [
                      ...msgs.slice(0, -1),
                      {
                        ...last,
                        id: data.message_id,
                        content: last.content + buffered,
                        created_at: data.created_at,
                      },
                    ],
                  };
                });
              },

              onError: (data) => {
                setError(data.detail);
              },
            }
          );
        } catch (err) {
          setError(parseApiError(err));
          // Remove optimistic user message on failure
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  messages: prev.messages.filter(
                    (m) =>
                      m.id !== tempUserMsg.id && m.id !== STREAMING_MSG_ID
                  ),
                }
              : prev
          );
          throw err;
        } finally {
          pendingStreams.delete(sessionId);
          setSending(false);
        }
      })();

      pendingStreams.set(sessionId, {
        promise: streamPromise,
        optimisticMessage: tempUserMsg,
      });

      try {
        await streamPromise;
      } catch {
        // Already handled above
      }
    },
    [sessionId, sending, madhab, category, flushTokenBuffer]
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
