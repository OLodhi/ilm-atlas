"use client";

import { ChatLayout } from "@/components/chat/chat-layout";
import { AuthGuard } from "@/components/shared/auth-guard";

export default function ChatPage({
  params,
}: {
  params: { sessionId: string };
}) {
  return (
    <AuthGuard>
      <ChatLayout sessionId={params.sessionId} />
    </AuthGuard>
  );
}
