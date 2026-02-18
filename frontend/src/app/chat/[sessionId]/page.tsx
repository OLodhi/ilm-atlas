"use client";

import { ChatLayout } from "@/components/chat/chat-layout";

export default function ChatPage({
  params,
}: {
  params: { sessionId: string };
}) {
  return <ChatLayout sessionId={params.sessionId} />;
}
