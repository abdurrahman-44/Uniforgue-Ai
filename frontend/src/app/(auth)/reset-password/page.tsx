"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { Button, GlassCard, Input } from "@/components/ui/primitives";

const resetSchema = z
  .object({
    token: z.string().min(10, "Reset token is required"),
    new_password: z.string().min(8, "New password must be at least 8 characters"),
    confirm_password: z.string().min(8, "Confirm your new password"),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ResetForm = z.infer<typeof resetSchema>;

function ResetPasswordInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initialToken = params.get("token") || "";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetForm>({
    resolver: zodResolver(resetSchema),
    defaultValues: { token: initialToken },
  });

  const onSubmit = async (values: ResetForm) => {
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          token: values.token,
          new_password: values.new_password,
        }),
      });
      toast.success("Password updated and all prior sessions revoked. Sign in now.");
      router.push("/login");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Password reset failed");
    }
  };

  return (
    <GlassCard className="w-full max-w-md p-7 space-y-5">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Choose a New Password</h1>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          All existing sessions will be revoked for your security.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Reset Token
          </label>
          <Input placeholder="Paste reset token" {...register("token")} />
          {errors.token && <p className="mt-1 text-xs text-rose-400">{errors.token.message}</p>}
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            New Password
          </label>
          <div className="relative">
            <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--text-muted)]" />
            <Input type="password" placeholder="Minimum 8 characters" className="pl-9" {...register("new_password")} />
          </div>
          {errors.new_password && (
            <p className="mt-1 text-xs text-rose-400">{errors.new_password.message}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
            Confirm New Password
          </label>
          <Input type="password" placeholder="Re-enter password" {...register("confirm_password")} />
          {errors.confirm_password && (
            <p className="mt-1 text-xs text-rose-400">{errors.confirm_password.message}</p>
          )}
        </div>

        <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
          Update Password
        </Button>
      </form>

      <p className="text-center text-xs text-[var(--text-muted)]">
        <Link href="/login" className="text-cyan-400 hover:underline">
          Back to Sign In
        </Link>
      </p>
    </GlassCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg p-4">
      <Suspense fallback={<GlassCard className="p-6 text-xs">Loading...</GlassCard>}>
        <ResetPasswordInner />
      </Suspense>
    </div>
  );
}
