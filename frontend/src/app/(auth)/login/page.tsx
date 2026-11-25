"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Lock, Mail } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Button, GlassCard, Input } from "@/components/ui/primitives";
import type { User } from "@/types/api";

const loginSchema = z.object({
  email: z.string().email("Enter a valid academic email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginForm) => {
    try {
      const data = await apiFetch<{
        user: User;
        access_token: string;
        refresh_token: string;
      }>("/auth/login", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setAuth(data.user, data.access_token, data.refresh_token);
      toast.success(`Welcome back, ${data.user.profile.full_name}`);
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to sign in");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg p-4">
      <GlassCard className="w-full max-w-md p-7">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-cyan-500 text-lg font-bold text-white">
            U
          </div>
          <h1 className="text-2xl font-bold">Sign in to UNIFORGE AI</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            Access your private academic workspaces and studios
          </p>
        </div>

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

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-medium text-[var(--text-secondary)]">
                Password
              </label>
              <Link href="/forgot-password" className="text-xs text-cyan-400 hover:underline">
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--text-muted)]" />
              <Input
                type="password"
                placeholder="••••••••"
                className="pl-9"
                {...register("password")}
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-xs text-rose-400">{errors.password.message}</p>
            )}
          </div>

          <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
            Sign In
          </Button>
        </form>

        <p className="mt-5 text-center text-xs text-[var(--text-muted)]">
          New to UNIFORGE AI?{" "}
          <Link href="/register" className="font-semibold text-cyan-400 hover:underline">
            Create a free student account
          </Link>
        </p>
      </GlassCard>
    </div>
  );
}
