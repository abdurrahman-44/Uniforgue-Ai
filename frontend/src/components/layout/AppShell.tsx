"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clsx } from "clsx";
import {
  Bell,
  BookOpen,
  Boxes,
  Command,
  FileText,
  Film,
  FolderKanban,
  GraduationCap,
  Image as ImageIcon,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Network,
  Presentation,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { NotificationItem } from "@/types/api";

const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/projects", label: "Academic Hub", icon: FolderKanban },
      { href: "/project-dev", label: "Project Dev Studio", icon: Boxes },
    ],
  },
  {
    label: "Academic Studios",
    items: [
      { href: "/documents", label: "Document Studio", icon: FileText },
      { href: "/research", label: "Research Studio", icon: BookOpen },
      { href: "/diagrams", label: "Diagram Studio", icon: Network },
      { href: "/presentations", label: "Presentation Studio", icon: Presentation },
      { href: "/learning", label: "Learning Studio", icon: GraduationCap },
    ],
  },
  {
    label: "Creative Media & AI",
    items: [
      { href: "/ai-assistant", label: "GPT-6 Astra Studio", icon: Sparkles },
      { href: "/images", label: "Image Studio", icon: ImageIcon },
      { href: "/videos", label: "Video Studio", icon: Film },
    ],
  },
  {
    label: "Ecosystem",
    items: [
      { href: "/community", label: "Community", icon: Users },
      { href: "/settings", label: "Profile & Settings", icon: Settings },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, accessToken, theme, setTheme, clearAuth } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdQuery, setCmdQuery] = useState("");
  const [notifOpen, setNotifOpen] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      router.replace("/login");
    }
  }, [accessToken, router]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
      if (e.key === "Escape") {
        setCmdOpen(false);
        setNotifOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const { data: notifData, refetch: refetchNotifs } = useQuery({
    queryKey: ["notifications"],
    queryFn: () =>
      apiFetch<{ notifications: NotificationItem[]; unread_count: number }>("/notifications"),
    enabled: Boolean(accessToken),
  });

  const handleLogout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // clear locally regardless
    }
    clearAuth();
    router.push("/login");
  };

  const allNavItems = [
    ...NAV_GROUPS.flatMap((g) => g.items),
    ...(user?.role === "admin"
      ? [{ href: "/admin", label: "Admin Console", icon: ShieldCheck }]
      : []),
  ];

  const filteredCmd = allNavItems.filter((item) =>
    item.label.toLowerCase().includes(cmdQuery.toLowerCase())
  );

  if (!accessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center uniforge-ambient-bg">
        <p className="text-sm text-[var(--text-muted)]">Redirecting to sign in...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen uniforge-ambient-bg flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-secondary)]/80 backdrop-blur-xl">
        <div className="flex h-16 items-center gap-2.5 border-b border-[var(--border-subtle)] px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 text-white font-bold shadow-md shadow-violet-900/40">
            U
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight">UNIFORGE AI</p>
            <p className="text-[10px] text-cyan-400">Free Academic Ecosystem</p>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5" aria-label="Main navigation">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={clsx(
                        "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-all",
                        active
                          ? "bg-gradient-to-r from-violet-600/25 to-cyan-500/15 text-white border border-violet-500/35"
                          : "text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]"
                      )}
                    >
                      <Icon className={clsx("h-4 w-4", active ? "text-cyan-300" : "text-[var(--text-muted)]")} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          {user?.role === "admin" && (
            <div>
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-amber-400">
                Governance
              </p>
              <Link
                href="/admin"
                className={clsx(
                  "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-all",
                  pathname.startsWith("/admin")
                    ? "bg-amber-500/20 text-amber-200 border border-amber-500/40"
                    : "text-amber-300/80 hover:bg-amber-500/10"
                )}
              >
                <ShieldCheck className="h-4 w-4" />
                <span>Admin Console</span>
              </Link>
            </div>
          )}
        </nav>

        <div className="border-t border-[var(--border-subtle)] p-3">
          <div className="flex items-center justify-between rounded-xl bg-black/20 px-3 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-[var(--text-primary)]">
                {user?.profile?.full_name || user?.email}
              </p>
              <p className="truncate text-[11px] text-[var(--text-muted)] capitalize">
                {user?.role || "student"} • Free Access
              </p>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              aria-label="Sign out"
              className="rounded-lg p-1.5 text-[var(--text-muted)] hover:bg-rose-500/15 hover:text-rose-400"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div className="fixed inset-0 bg-black/70" onClick={() => setMobileOpen(false)} />
          <div className="relative z-10 w-64 bg-[var(--bg-secondary)] border-r border-[var(--border-subtle)] p-4 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <span className="font-bold text-sm">UNIFORGE AI</span>
              <button onClick={() => setMobileOpen(false)} aria-label="Close menu">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1">
              {allNavItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-white/5"
                  >
                    <Icon className="h-4 w-4 text-cyan-400" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-primary)]/80 px-4 sm:px-6 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
              className="rounded-lg p-2 text-[var(--text-secondary)] hover:bg-white/5 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <button
              onClick={() => setCmdOpen(true)}
              className="flex items-center gap-2 rounded-xl border border-[var(--border-subtle)] bg-black/20 px-3 py-1.5 text-xs text-[var(--text-muted)] hover:border-violet-500/40"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Jump to studio or command...</span>
              <kbd className="ml-2 hidden sm:inline-flex items-center gap-0.5 rounded bg-white/10 px-1.5 py-0.5 text-[10px]">
                <Command className="h-2.5 w-2.5" />K
              </kbd>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label="Toggle theme"
              className="rounded-xl border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] hover:bg-white/5"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            <div className="relative">
              <button
                onClick={() => setNotifOpen((v) => !v)}
                aria-label="Notifications"
                className="relative rounded-xl border border-[var(--border-subtle)] p-2 text-[var(--text-secondary)] hover:bg-white/5"
              >
                <Bell className="h-4 w-4" />
                {(notifData?.unread_count || 0) > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-violet-600 text-[10px] font-bold text-white">
                    {notifData?.unread_count}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="glass-panel absolute right-0 mt-2 w-80 rounded-2xl p-3 shadow-2xl">
                  <div className="mb-2 flex items-center justify-between px-1">
                    <span className="text-xs font-semibold">Notifications</span>
                    <button
                      onClick={async () => {
                        await apiFetch("/notifications/read-all", { method: "POST" });
                        refetchNotifs();
                      }}
                      className="text-[11px] text-cyan-400 hover:underline"
                    >
                      Mark all read
                    </button>
                  </div>
                  <div className="max-h-72 space-y-1.5 overflow-y-auto">
                    {(notifData?.notifications || []).length === 0 ? (
                      <p className="py-4 text-center text-xs text-[var(--text-muted)]">
                        No notifications yet.
                      </p>
                    ) : (
                      (notifData?.notifications || []).map((n) => (
                        <div
                          key={n.id}
                          className={clsx(
                            "rounded-xl p-2.5 text-xs",
                            n.is_read ? "bg-white/[0.02]" : "bg-violet-500/15 border border-violet-500/25"
                          )}
                        >
                          <p className="font-semibold">{n.title}</p>
                          <p className="mt-0.5 text-[var(--text-muted)]">{n.message}</p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 max-w-[1440px] w-full mx-auto">
          {children}
        </main>
      </div>

      {/* Command Menu (Ctrl+K) */}
      {cmdOpen && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-24 p-4 backdrop-blur-sm"
          onClick={() => setCmdOpen(false)}
        >
          <div
            className="glass-panel w-full max-w-lg rounded-2xl p-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] pb-3">
              <Search className="h-4 w-4 text-cyan-400" />
              <input
                autoFocus
                value={cmdQuery}
                onChange={(e) => setCmdQuery(e.target.value)}
                placeholder="Type a studio name (Document, Research, Diagram, Video...)"
                className="w-full bg-transparent text-sm text-[var(--text-primary)] focus:outline-none"
              />
            </div>
            <div className="mt-3 max-h-72 space-y-1 overflow-y-auto">
              {filteredCmd.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.href}
                    onClick={() => {
                      setCmdOpen(false);
                      setCmdQuery("");
                      router.push(item.href);
                    }}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm hover:bg-violet-500/20"
                  >
                    <Icon className="h-4 w-4 text-cyan-400" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
