"use client";

import { Suspense } from "react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { verifyEmail } from "@/lib/api-client";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );
  const [error, setError] = useState("");

  const calledRef = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("No verification token provided");
      return;
    }

    if (calledRef.current) return;
    calledRef.current = true;

    verifyEmail(token)
      .then(() => {
        setStatus("success");
      })
      .catch((err) => {
        setStatus("error");
        setError(
          err instanceof Error ? err.message : "Verification failed"
        );
      });
  }, [token]);

  return (
    <main className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl text-center">
            Email Verification
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {status === "loading" && (
            <p className="text-sm text-muted-foreground">
              Verifying your email...
            </p>
          )}
          {status === "success" && (
            <>
              <p className="text-sm text-muted-foreground">
                Email verified successfully!
              </p>
              <Link
                href="/login"
                className="text-sm text-foreground hover:underline"
              >
                Go to sign in
              </Link>
            </>
          )}
          {status === "error" && (
            <>
              <p className="text-sm text-destructive">{error}</p>
              <Link
                href="/login"
                className="text-sm text-foreground hover:underline"
              >
                Go to sign in
              </Link>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
          <p className="text-muted-foreground">Loading...</p>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
