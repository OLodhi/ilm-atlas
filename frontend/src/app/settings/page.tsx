"use client";

import { useState, useEffect, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AuthGuard } from "@/components/shared/auth-guard";
import { useAuth } from "@/contexts/auth-context";
import {
  updateMe,
  getUsage,
  resendVerification,
  deleteAccount,
  type UsageInfo,
} from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";

function SettingsContent() {
  const { user, refreshUser } = useAuth();
  const router = useRouter();

  // Profile
  const [displayName, setDisplayName] = useState("");
  const [profileMsg, setProfileMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);

  // Email verification
  const [emailMsg, setEmailMsg] = useState("");
  const [emailErr, setEmailErr] = useState("");
  const [emailSending, setEmailSending] = useState(false);

  // Password
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");
  const [passwordErr, setPasswordErr] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);

  // Usage
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  // Delete
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState("");

  useEffect(() => {
    if (user?.display_name) {
      setDisplayName(user.display_name);
    }
  }, [user?.display_name]);

  useEffect(() => {
    async function loadUsage() {
      try {
        const data = await getUsage();
        setUsage(data);
      } catch {
        // ignore
      }
    }
    loadUsage();
  }, []);

  async function handleProfileSave(e: FormEvent) {
    e.preventDefault();
    setProfileMsg("");
    setProfileErr("");
    setProfileSaving(true);
    try {
      await updateMe({ display_name: displayName });
      await refreshUser();
      setProfileMsg("Display name updated.");
    } catch (err) {
      setProfileErr(
        err instanceof Error ? err.message : "Failed to update profile"
      );
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleResendVerification() {
    setEmailMsg("");
    setEmailErr("");
    setEmailSending(true);
    try {
      const result = await resendVerification();
      setEmailMsg(result.message || "Verification email sent.");
    } catch (err) {
      setEmailErr(
        err instanceof Error ? err.message : "Failed to send verification email"
      );
    } finally {
      setEmailSending(false);
    }
  }

  async function handlePasswordSave(e: FormEvent) {
    e.preventDefault();
    setPasswordMsg("");
    setPasswordErr("");

    if (newPassword !== confirmPassword) {
      setPasswordErr("New passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordErr("New password must be at least 8 characters.");
      return;
    }

    setPasswordSaving(true);
    try {
      await updateMe({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMsg("Password updated successfully.");
    } catch (err) {
      setPasswordErr(
        err instanceof Error ? err.message : "Failed to update password"
      );
    } finally {
      setPasswordSaving(false);
    }
  }

  async function handleDeleteAccount() {
    setDeleteErr("");
    setDeleting(true);
    try {
      await deleteAccount();
      router.push("/");
    } catch (err) {
      setDeleteErr(
        err instanceof Error ? err.message : "Failed to delete account"
      );
      setDeleting(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      {/* Profile section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your display name.</CardDescription>
        </CardHeader>
        <form onSubmit={handleProfileSave}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
              />
            </div>
            {profileMsg && (
              <p className="text-sm text-green-600">{profileMsg}</p>
            )}
            {profileErr && (
              <p className="text-sm text-destructive">{profileErr}</p>
            )}
            <Button type="submit" disabled={profileSaving}>
              {profileSaving ? "Saving..." : "Save"}
            </Button>
          </CardContent>
        </form>
      </Card>

      {/* Email section */}
      <Card>
        <CardHeader>
          <CardTitle>Email</CardTitle>
          <CardDescription>Your email address and verification status.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm">{user?.email}</span>
            {user?.email_verified ? (
              <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
                Verified
              </span>
            ) : (
              <span className="rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
                Not verified
              </span>
            )}
          </div>
          {!user?.email_verified && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleResendVerification}
              disabled={emailSending}
            >
              {emailSending ? "Sending..." : "Resend verification email"}
            </Button>
          )}
          {emailMsg && (
            <p className="text-sm text-green-600">{emailMsg}</p>
          )}
          {emailErr && (
            <p className="text-sm text-destructive">{emailErr}</p>
          )}
        </CardContent>
      </Card>

      {/* Password section */}
      <Card>
        <CardHeader>
          <CardTitle>Password</CardTitle>
          <CardDescription>Change your password.</CardDescription>
        </CardHeader>
        <form onSubmit={handlePasswordSave}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current Password</Label>
              <Input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">New Password</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            {passwordMsg && (
              <p className="text-sm text-green-600">{passwordMsg}</p>
            )}
            {passwordErr && (
              <p className="text-sm text-destructive">{passwordErr}</p>
            )}
            <Button type="submit" disabled={passwordSaving}>
              {passwordSaving ? "Updating..." : "Update Password"}
            </Button>
          </CardContent>
        </form>
      </Card>

      {/* Usage section */}
      <Card>
        <CardHeader>
          <CardTitle>Usage</CardTitle>
          <CardDescription>Your daily query usage.</CardDescription>
        </CardHeader>
        <CardContent>
          {usage ? (
            <p className="text-sm">
              <span className="font-medium">{usage.used}</span>
              {" / "}
              <span className="font-medium">{usage.limit}</span>
              {" queries used today"}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">Loading usage...</p>
          )}
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="text-destructive">Danger Zone</CardTitle>
          <CardDescription>
            Permanently delete your account and all associated data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive">Delete Account</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Are you absolutely sure?</DialogTitle>
                <DialogDescription>
                  This action cannot be undone. This will permanently delete your
                  account and remove all your data including chat sessions.
                </DialogDescription>
              </DialogHeader>
              {deleteErr && (
                <p className="text-sm text-destructive">{deleteErr}</p>
              )}
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" disabled={deleting}>
                    Cancel
                  </Button>
                </DialogClose>
                <Button
                  variant="destructive"
                  onClick={handleDeleteAccount}
                  disabled={deleting}
                >
                  {deleting ? "Deleting..." : "Yes, delete my account"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </main>
  );
}

export default function SettingsPage() {
  return (
    <AuthGuard>
      <SettingsContent />
    </AuthGuard>
  );
}
