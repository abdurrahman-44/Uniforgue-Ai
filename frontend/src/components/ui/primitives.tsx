"use client";

import React from "react";
import { clsx } from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";

export function GlassCard({
  children,
  className,
  hover = false,
}: {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <div
      className={clsx(
        "glass-panel rounded-2xl p-5 shadow-lg shadow-black/10",
        hover && "glass-panel-hover",
        className
      )}
    >
      {children}
    </div>
  );
}

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "cyan";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className,
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      "bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-md shadow-violet-900/30",
    cyan: "bg-gradient-to-r from-cyan-600 to-sky-600 hover:from-cyan-500 hover:to-sky-500 text-white shadow-md shadow-cyan-900/30",
    secondary:
      "bg-white/5 hover:bg-white/10 border border-[var(--border-subtle)] text-[var(--text-primary)]",
    ghost: "hover:bg-white/5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
    danger: "bg-rose-600/90 hover:bg-rose-500 text-white",
  };
  const sizes = {
    sm: "px-3 py-1.5 text-xs rounded-lg gap-1.5",
    md: "px-4 py-2 text-sm rounded-xl gap-2",
    lg: "px-5 py-2.5 text-sm font-semibold rounded-xl gap-2",
  };
  return (
    <button
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center font-medium transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-violet-500/60",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={clsx(
      "w-full rounded-xl border border-[var(--border-subtle)] bg-black/20 px-3.5 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={clsx(
      "w-full rounded-xl border border-[var(--border-subtle)] bg-black/20 px-3.5 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={clsx(
        "w-full rounded-xl border border-[var(--border-subtle)] bg-[#0c132a] px-3.5 py-2.5 text-sm text-[var(--text-primary)] focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Badge({
  children,
  tone = "violet",
  className,
}: {
  children: React.ReactNode;
  tone?: "violet" | "cyan" | "emerald" | "amber" | "rose" | "slate";
  className?: string;
}) {
  const tones = {
    violet: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    cyan: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
    emerald: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    rose: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    slate: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  badge,
  actions,
}: {
  title: string;
  subtitle: string;
  badge?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="flex items-center gap-2.5">
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            {title}
          </h1>
          {badge && <Badge tone="cyan">{badge}</Badge>}
        </div>
        <p className="mt-1 text-sm text-[var(--text-muted)]">{subtitle}</p>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border-subtle)] bg-black/10 px-6 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/15 text-violet-400">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-[var(--text-muted)]">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ProviderBanner({
  available,
  title,
  message,
}: {
  available: boolean;
  title: string;
  message: string;
}) {
  return (
    <div
      className={clsx(
        "mb-5 flex items-start gap-3 rounded-xl border px-4 py-3 text-xs",
        available
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
          : "border-amber-500/30 bg-amber-500/10 text-amber-200"
      )}
    >
      {available ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
      ) : (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      )}
      <div>
        <p className="font-semibold">{title}</p>
        <p className="mt-0.5 opacity-90">{message}</p>
      </div>
    </div>
  );
}

export function InfoCallout({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-cyan-500/25 bg-cyan-500/10 px-3.5 py-2.5 text-xs text-cyan-200">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
      <span>{text}</span>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
    >
      <div className="glass-panel w-full max-w-lg rounded-2xl p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="rounded-lg p-1 text-[var(--text-muted)] hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sublabel,
  icon,
}: {
  label: string;
  value: string | number;
  sublabel?: string;
  icon: React.ReactNode;
}) {
  return (
    <GlassCard hover className="flex items-center justify-between p-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {label}
        </p>
        <p className="mt-1 text-2xl font-bold text-[var(--text-primary)]">{value}</p>
        {sublabel && <p className="mt-0.5 text-xs text-[var(--text-muted)]">{sublabel}</p>}
      </div>
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600/25 to-cyan-500/20 text-cyan-300">
        {icon}
      </div>
    </GlassCard>
  );
}
