"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Mail, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { resendVerification } from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

interface EmailVerificationModalProps {
  email: string;
  open: boolean;
  onClose: () => void;
  onVerified: () => void;
}

export function EmailVerificationModal({
  email,
  open,
  onClose,
  onVerified,
}: EmailVerificationModalProps) {
  const { refreshUser } = useAuth();
  const [resendStatus, setResendStatus] = useState<
    "idle" | "sending" | "sent" | "error"
  >("idle");
  const [checking, setChecking] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleResend() {
    setResendStatus("sending");
    setErrorMessage("");
    try {
      await resendVerification();
      setResendStatus("sent");
    } catch (err) {
      setResendStatus("error");
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to resend email"
      );
    }
  }

  async function handleCheckVerified() {
    setChecking(true);
    setErrorMessage("");
    try {
      await refreshUser();
      // If refreshUser succeeds and email is now verified,
      // the parent component will detect the change and close the modal.
      // We call onVerified as a signal, but the parent re-renders from auth context.
      onVerified();
    } catch {
      setErrorMessage("Could not check verification status. Please try again.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="items-center text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Mail className="h-6 w-6 text-primary" />
          </div>
          <DialogTitle>Verify your email to start chatting</DialogTitle>
          <DialogDescription className="text-center">
            We&apos;ve sent a verification email to{" "}
            <span className="font-medium text-foreground">{email}</span>. Please
            check your inbox (and spam folder).
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3 pt-2">
          <Button
            variant="outline"
            onClick={handleResend}
            disabled={resendStatus === "sending" || resendStatus === "sent"}
          >
            {resendStatus === "sending" && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {resendStatus === "sent" && (
              <CheckCircle2 className="mr-2 h-4 w-4 text-green-500" />
            )}
            {resendStatus === "sent"
              ? "Verification email sent"
              : "Resend verification email"}
          </Button>

          <Button onClick={handleCheckVerified} disabled={checking}>
            {checking && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            I&apos;ve verified my email
          </Button>

          {resendStatus === "error" && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {errorMessage}
            </div>
          )}
          {errorMessage && resendStatus !== "error" && (
            <div className="flex items-center gap-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {errorMessage}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
