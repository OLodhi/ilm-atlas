"use client";

import { ChatLayout } from "@/components/chat/chat-layout";
import { AuthGuard } from "@/components/shared/auth-guard";
import { EmailVerificationModal } from "@/components/shared/email-verification-modal";
import { useAuth } from "@/contexts/auth-context";

export default function ChatPage({
  params,
}: {
  params: { sessionId: string };
}) {
  const { user } = useAuth();
  const emailVerified = user?.email_verified ?? true;

  return (
    <AuthGuard>
      <ChatLayout
        sessionId={params.sessionId}
        emailVerified={emailVerified}
      />
      {!emailVerified && user && (
        <EmailVerificationModal
          email={user.email}
          onVerified={() => {}}
        />
      )}
    </AuthGuard>
  );
}
