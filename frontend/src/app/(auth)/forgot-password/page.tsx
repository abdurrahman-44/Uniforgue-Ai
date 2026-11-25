"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ArrowLeft, Mail } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { Button, GlassCard, InfoCallout, Input } from "@/components/ui/primitives";

const forgotSchema = z.object({
  email: z.string().email("Enter a valid academic email address"),
});

type ForgotForm = z.infer<typeof forgotSchema>;

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({ resolver: zodResolver(forgotSchema) });

  const onSubmit = async (values: ForgotForm) => {
    try {
      const res = await apiFetch<{ message: string; dev_reset_token?: string }>(
        "/auth/forgot-password",
        { method: "POST", body: JSON.stringify(values) }
      );
      setSubmitted(true);
      setDevToken(res.dev_reset_token || null);
      toast.success("Password reset instructions issued.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Unable to process request");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg p-4">
      <GlassCard className="w-full max-w-md p-7 space-y-5">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Reset Your Password</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Enter your registered email to receive a secure password reset token.
          </p>
        </div>

        {submitted ? (
          <div className="space-y-4">
            <InfoCallout text="If an account matches that email, a reset link has been issued (valid for 1 hour)." />
            {devToken && (
              <div className="rounded-xl border border-violet-500/35 bg-violet-500/10 p-3 text-xs space-y-2">
                <p className="font-semibold text-violet-200">Development Reset Token Issued:</p>
                <p className="break-all font-mono text-[11px] text-cyan-300">{devToken}</p>
                <Link href={`/reset-password?token=${encodeURIComponent(devToken)}`}>
                  <Button size="sm" className="w-full mt-1">Continue to Reset Password</Button>
                </Link>
              </div>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--text-muted)]" />
                <Input
                  type="email"
                  placeholder="student@university.edu"
                  className="pl-9"
                  {...register("email")}
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-xs text-rose-400">{errors.email.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
              Send Reset Instructions
            </Button>
          </form>
        )}

        <div className="text-center">
          <Link href="/login" className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:underline">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Sign In
          </Link>
        </div>
      </GlassCard>
    </div>
  );
}
