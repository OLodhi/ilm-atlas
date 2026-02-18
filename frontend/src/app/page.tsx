"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";
import { createChatSession } from "@/lib/api-client";

export default function Home() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);

  const handleNewChat = async () => {
    setCreating(true);
    try {
      const session = await createChatSession();
      router.push(`/chat/${session.id}`);
    } catch {
      setCreating(false);
    }
  };

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
