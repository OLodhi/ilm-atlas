"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";
import { createChatSession, listChatSessions } from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

export default function Home() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();
  const [creating, setCreating] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setChecking(false);
      return;
    }
    listChatSessions()
      .then((res) => {
        if (res.sessions.length > 0) {
          router.replace(`/chat/${res.sessions[0].id}`);
        } else {
          setChecking(false);
        }
      })
      .catch(() => setChecking(false));
  }, [user, authLoading, router]);

  const handleNewChat = async () => {
    setCreating(true);
    try {
      const session = await createChatSession();
      router.push(`/chat/${session.id}`);
    } catch {
      setCreating(false);
    }
  };

  if (checking) return null;

  return (
    <main className="flex h-[calc(100vh-3.5rem)] items-center justify-center">
      <div className="text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Ilm Atlas</h1>
          <p className="text-muted-foreground">
            Explore Islamic sources grounded in the Quran, Sunnah, and scholarly
            consensus
          </p>
        </div>
        <Button
          onClick={handleNewChat}
          disabled={creating}
          size="lg"
          className="gap-2"
        >
          <MessageSquare className="h-5 w-5" />
          {creating ? "Creating..." : "New Chat"}
        </Button>
      </div>
    </main>
  );
}
