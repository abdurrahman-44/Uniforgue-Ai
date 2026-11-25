"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { apiFetch, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Button, GlassCard, Input, Select } from "@/components/ui/primitives";
import type { User } from "@/types/api";

const registerSchema = z.object({
  full_name: z.string().min(2, "Full name must be at least 2 characters"),
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  university: z.string().optional(),
  department: z.string().optional(),
  academic_level: z.string(),
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: { academic_level: "undergraduate" },
  });

  const onSubmit = async (values: RegisterForm) => {
    try {
      const data = await apiFetch<{
        user: User;
        access_token: string;
        refresh_token: string;
      }>("/auth/register", {
        method: "POST",
        body: JSON.stringify(values),
      });
      setAuth(data.user, data.access_token, data.refresh_token);
      toast.success("Account created! Your private academic workspace is ready.");
      router.push("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Registration failed");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg p-4">
      <GlassCard className="w-full max-w-md p-7">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-cyan-500 text-lg font-bold text-white">
            U
          </div>
          <h1 className="text-2xl font-bold">Create Free Student Account</h1>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            No credit card. No subscription. Privacy-first academic tools.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3.5">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Full Name
            </label>
            <Input placeholder="Amina Al-Mansoor" {...register("full_name")} />
            {errors.full_name && (
              <p className="mt-1 text-xs text-rose-400">{errors.full_name.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Email Address
            </label>
            <Input type="email" placeholder="amina@university.edu" {...register("email")} />
            {errors.email && (
              <p className="mt-1 text-xs text-rose-400">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Password (min. 8 characters)
            </label>
            <Input type="password" placeholder="••••••••••••" {...register("password")} />
            {errors.password && (
              <p className="mt-1 text-xs text-rose-400">{errors.password.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                University (optional)
              </label>
              <Input placeholder="MIT / Oxford / ..." {...register("university")} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
                Department (optional)
              </label>
              <Input placeholder="Computer Science" {...register("department")} />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
              Academic Level
            </label>
            <Select {...register("academic_level")}>
              <option value="undergraduate">Undergraduate</option>
              <option value="masters">Master&apos;s / Postgraduate</option>
              <option value="phd">Doctoral / PhD Researcher</option>
              <option value="diploma">Diploma / Foundation</option>
            </Select>
          </div>

          <Button type="submit" className="w-full" size="lg" loading={isSubmitting}>
            Create Free Account
          </Button>
        </form>

        <p className="mt-5 text-center text-xs text-[var(--text-muted)]">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-cyan-400 hover:underline">
            Sign in
          </Link>
        </p>
      </GlassCard>
    </div>
  );
}
