"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, MailCheck } from "lucide-react";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import { Button, GlassCard, Input } from "@/components/ui/primitives";

function VerifyEmailInner() {
  const params = useSearchParams();
  const urlToken = params.get("token") || "";
  const [token, setToken] = useState(urlToken);
  const [verified, setVerified] = useState(false);
  const [loading, setLoading] = useState(false);

  const verify = async (tok: string) => {
    if (tok.trim().length < 10) return;
    setLoading(true);
    try {
      await apiFetch("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token: tok.trim() }),
      });
      setVerified(true);
      toast.success("Email verified successfully!");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (urlToken.length >= 10) {
      verify(urlToken);
    }
  }, [urlToken]);

  return (
    <GlassCard className="w-full max-w-md p-7 text-center space-y-4">
      {verified ? (
        <>
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
          <h1 className="text-2xl font-bold">Email Verified</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Your UNIFORGE AI academic account is now verified.
          </p>
          <Link href="/dashboard">
            <Button className="w-full" size="lg">Go to Student Dashboard</Button>
          </Link>
        </>
      ) : (
        <>
          <MailCheck className="mx-auto h-10 w-10 text-cyan-400" />
          <h1 className="text-2xl font-bold">Verify Your Email</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Paste the verification token from your email to confirm your academic account.
          </p>
          <Input
            placeholder="Verification token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <Button
            className="w-full"
            size="lg"
            loading={loading}
            disabled={token.trim().length < 10}
            onClick={() => verify(token)}
          >
            Verify Email Address
          </Button>
          <Link href="/login" className="block text-xs text-cyan-400 hover:underline">
            Back to Sign In
          </Link>
        </>
      )}
    </GlassCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg p-4">
      <Suspense fallback={<GlassCard className="p-6 text-xs">Loading...</GlassCard>}>
        <VerifyEmailInner />
      </Suspense>
    </div>
  );
}
