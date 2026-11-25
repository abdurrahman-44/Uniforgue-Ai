"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, Save, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import {
  Badge,
  Button,
  GlassCard,
  Input,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui/primitives";

export default function SettingsPage() {
  const router = useRouter();
  const { user, theme, setTheme, setUser, clearAuth } = useAuthStore();

  const [fullName, setFullName] = useState(user?.profile.full_name || "");
  const [university, setUniversity] = useState(user?.profile.university || "");
  const [department, setDepartment] = useState(user?.profile.department || "");
  const [academicLevel, setAcademicLevel] = useState(user?.profile.academic_level || "undergraduate");
  const [bio, setBio] = useState(user?.profile.bio || "");
  const [language, setLanguage] = useState(user?.settings.language || "en");
  const [citationStyle, setCitationStyle] = useState(user?.settings.default_citation_style || "APA 7");

  const { data: sessionsData, refetch: refetchSessions } = useQuery({
    queryKey: ["sessions"],
    queryFn: () =>
      apiFetch<{
        sessions: { id: string; user_agent: string; ip_address: string; is_current: boolean; created_at: string }[];
      }>("/auth/sessions"),
  });

  const saveProfile = useMutation({
    mutationFn: async () => {
      await apiFetch("/users/profile", {
        method: "PATCH",
        body: JSON.stringify({ full_name: fullName, university, department, academic_level: academicLevel, bio }),
      });
      await apiFetch("/users/settings", {
        method: "PATCH",
        body: JSON.stringify({ theme, language, default_citation_style: citationStyle }),
      });
      const me = await apiFetch<{ user: typeof user }>("/auth/me");
      if (me.user) setUser(me.user);
    },
    onSuccess: () => toast.success("Profile and preferences saved"),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Profile, Preferences & Security"
        subtitle="Manage your academic profile, formatting defaults, theme, language, active sessions, and privacy controls."
      />

      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-7 space-y-4">
          <h2 className="text-base font-semibold">Academic Profile</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Full Name</label>
              <Input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Academic Level</label>
              <Select value={academicLevel} onChange={(e) => setAcademicLevel(e.target.value)}>
                <option value="undergraduate">Undergraduate</option>
                <option value="masters">Master&apos;s</option>
                <option value="phd">PhD / Doctoral</option>
                <option value="diploma">Diploma</option>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">University</label>
              <Input value={university} onChange={(e) => setUniversity(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Department</label>
              <Input value={department} onChange={(e) => setDepartment(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-[var(--text-secondary)]">Academic Bio</label>
            <Textarea rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
          </div>

          <h3 className="pt-2 text-sm font-semibold">Workspace Preferences</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Theme</label>
              <Select value={theme} onChange={(e) => setTheme(e.target.value as "dark" | "light")}>
                <option value="dark">Dark Glassmorphism</option>
                <option value="light">Light Academic</option>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Language</label>
              <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
                <option value="en">English</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
                <option value="de">Deutsch</option>
                <option value="ar">العربية</option>
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Default Citation Style</label>
              <Select value={citationStyle} onChange={(e) => setCitationStyle(e.target.value)}>
                <option value="APA 7">APA 7</option>
                <option value="IEEE">IEEE</option>
                <option value="Harvard">Harvard</option>
                <option value="MLA">MLA</option>
                <option value="Chicago">Chicago</option>
              </Select>
            </div>
          </div>

          <Button loading={saveProfile.isPending} onClick={() => saveProfile.mutate()}>
            <Save className="h-4 w-4" /> Save Profile & Preferences
          </Button>
        </GlassCard>

        <div className="space-y-6 lg:col-span-5">
          <GlassCard className="space-y-3">
            <div className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-cyan-400" />
              <h2 className="text-base font-semibold">Active Sessions</h2>
            </div>
            <div className="space-y-2 text-xs">
              {(sessionsData?.sessions || []).map((s) => (
                <div key={s.id} className="flex items-center justify-between rounded-xl bg-black/25 p-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{s.user_agent || "Web Browser"}</p>
                    <p className="text-[var(--text-muted)]">IP: {s.ip_address || "local"}</p>
                  </div>
                  {s.is_current ? (
                    <Badge tone="emerald">Current</Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await apiFetch(`/auth/sessions/${s.id}`, { method: "DELETE" });
                        toast.success("Session revoked");
                        refetchSessions();
                      }}
                    >
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="border-rose-500/30 space-y-3">
            <h2 className="text-base font-semibold text-rose-300">Privacy & Account Deletion</h2>
            <p className="text-xs text-[var(--text-muted)]">
              Private student documents are never used for model training. You may permanently deactivate your account and revoke all active sessions at any time.
            </p>
            <Button
              variant="danger"
              size="sm"
              onClick={async () => {
                if (!window.confirm("Delete your UNIFORGE AI account and revoke all sessions?")) return;
                await apiFetch("/users/account", { method: "DELETE" });
                clearAuth();
                router.push("/");
              }}
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete My Account
            </Button>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
