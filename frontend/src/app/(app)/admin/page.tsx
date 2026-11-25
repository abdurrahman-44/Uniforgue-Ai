"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  Database,
  FileWarning,
  Key,
  ShieldCheck,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import {
  Badge,
  Button,
  GlassCard,
  Input,
  PageHeader,
  Select,
  StatCard,
} from "@/components/ui/primitives";

export default function AdminConsolePage() {
  const user = useAuthStore((s) => s.user);
  const qc = useQueryClient();

  const [provName, setProvName] = useState("openai_astra");
  const [provCategory, setProvCategory] = useState("ai");
  const [provEndpoint, setProvEndpoint] = useState("https://api.openai.com/v1");
  const [provModel, setProvModel] = useState("gpt-6-astra");
  const [provKey, setProvKey] = useState("");

  const PROVIDER_PRESETS: Record<string, { category: string; endpoint: string; model: string }> = {
    openai_astra: { category: "ai", endpoint: "https://api.openai.com/v1", model: "gpt-6-astra" },
    custom_openai: { category: "ai", endpoint: "https://openrouter.ai/api/v1", model: "openai/gpt-4o-mini" },
    ollama: { category: "ai", endpoint: "http://localhost:11434", model: "llama3.2" },
    pollinations: {
      category: "image",
      endpoint: "https://image.pollinations.ai/prompt",
      model: "flux",
    },
    huggingface: {
      category: "image",
      endpoint: "https://router.huggingface.co/hf-inference/models",
      model: "black-forest-labs/FLUX.1-schnell",
    },
    openai: { category: "image", endpoint: "https://api.openai.com/v1", model: "gpt-image-1" },
    comfyui: { category: "image", endpoint: "http://127.0.0.1:7860", model: "sdxl-local" },
  };

  const handleProviderSelect = (name: string) => {
    setProvName(name);
    const preset = PROVIDER_PRESETS[name];
    if (preset) {
      setProvCategory(preset.category);
      setProvEndpoint(preset.endpoint);
      setProvModel(preset.model);
    }
  };

  const isAdmin = user?.role === "admin";

  const { data: overview } = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () =>
      apiFetch<{
        metrics: {
          total_users: number;
          suspended_users: number;
          total_projects: number;
          total_documents: number;
          total_storage_bytes: number;
          open_reports: number;
          total_jobs: number;
          failed_jobs: number;
        };
        usage_analytics: Record<string, number>;
      }>("/admin/overview"),
    enabled: isAdmin,
  });

  const { data: usersData } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () =>
      apiFetch<{
        users: { id: string; email: string; full_name: string; role: string; is_suspended: boolean }[];
      }>("/admin/users"),
    enabled: isAdmin,
  });

  const { data: providersData } = useQuery({
    queryKey: ["admin-providers"],
    queryFn: () =>
      apiFetch<{
        providers: {
          id: string;
          name: string;
          category: string;
          model_identifier: string;
          masked_api_key: string;
          is_enabled: boolean;
        }[];
      }>("/admin/providers"),
    enabled: isAdmin,
  });

  const { data: reportsData } = useQuery({
    queryKey: ["admin-reports"],
    queryFn: () =>
      apiFetch<{
        reports: { id: string; target_type: string; target_id: string; reason: string; status: string }[];
      }>("/admin/reports"),
    enabled: isAdmin,
  });

  const { data: auditData } = useQuery({
    queryKey: ["admin-audit"],
    queryFn: () =>
      apiFetch<{
        audit_logs: { id: string; action: string; resource_type: string; created_at: string }[];
      }>("/admin/audit-logs"),
    enabled: isAdmin,
  });

  const saveProvider = useMutation({
    mutationFn: () =>
      apiFetch("/admin/providers", {
        method: "POST",
        body: JSON.stringify({
          name: provName,
          category: provCategory,
          endpoint_url: provEndpoint || null,
          model_identifier: provModel || null,
          api_key: provKey || null,
          is_enabled: true,
          is_primary: true,
        }),
      }),
    onSuccess: () => {
      toast.success("Provider configuration encrypted and saved on server");
      setProvKey("");
      qc.invalidateQueries({ queryKey: ["admin-providers"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!isAdmin) {
    return (
      <GlassCard className="p-8 text-center">
        <ShieldCheck className="mx-auto mb-3 h-10 w-10 text-rose-400" />
        <h1 className="text-lg font-bold">Administrator Access Required</h1>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          Role-Based Access Control (RBAC) restricts this console exclusively to administrator accounts.
        </p>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration & Governance Console"
        subtitle="Manage users, RBAC roles, server-side encrypted AI/media providers, generation jobs, storage health, moderation reports, and audit logs."
        badge="Module L • Admin RBAC"
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Users" value={overview?.metrics.total_users ?? 0} sublabel={`${overview?.metrics.suspended_users ?? 0} suspended`} icon={<Users className="h-5 w-5" />} />
        <StatCard label="Projects & Docs" value={`${overview?.metrics.total_projects ?? 0} / ${overview?.metrics.total_documents ?? 0}`} icon={<Database className="h-5 w-5" />} />
        <StatCard label="Storage Used" value={`${((overview?.metrics.total_storage_bytes || 0) / (1024 * 1024)).toFixed(1)} MB`} icon={<Activity className="h-5 w-5" />} />
        <StatCard label="Open Reports" value={overview?.metrics.open_reports ?? 0} sublabel={`${overview?.metrics.failed_jobs ?? 0} failed jobs`} icon={<FileWarning className="h-5 w-5" />} />
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Provider Secrets Configuration (Encrypted Server-Side) */}
        <GlassCard className="lg:col-span-5 space-y-4">
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4 text-cyan-400" />
            <h2 className="text-base font-semibold">AI & Media Provider Configuration</h2>
          </div>
          <p className="text-xs text-[var(--text-muted)]">
            API keys are encrypted at rest with Fernet on the server and NEVER exposed in browser code.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <Select value={provName} onChange={(e) => handleProviderSelect(e.target.value)}>
              <option value="openai_astra">openai_astra (GPT-6 Astra)</option>
              <option value="custom_openai">custom_openai</option>
              <option value="ollama">ollama (Local Free)</option>
              <option value="pollinations">pollinations (Free FLUX Image — No Key Needed)</option>
              <option value="huggingface">huggingface (Image)</option>
              <option value="openai">openai (Image)</option>
              <option value="comfyui">comfyui (Self-hosted A1111)</option>
            </Select>
            <Select value={provCategory} onChange={(e) => setProvCategory(e.target.value)}>
              <option value="ai">AI Language</option>
              <option value="image">Image Generation</option>
              <option value="video">Video Generation</option>
            </Select>
          </div>
          <Input placeholder="Endpoint URL" value={provEndpoint} onChange={(e) => setProvEndpoint(e.target.value)} />
          <Input placeholder="Model Identifier (e.g., gpt-6-astra)" value={provModel} onChange={(e) => setProvModel(e.target.value)} />
          <Input type="password" placeholder="API Key (stored encrypted on server)" value={provKey} onChange={(e) => setProvKey(e.target.value)} />
          <Button size="sm" loading={saveProvider.isPending} onClick={() => saveProvider.mutate()}>
            Save Encrypted Provider Config
          </Button>

          <div className="space-y-1.5 border-t border-[var(--border-subtle)] pt-3 text-xs">
            {(providersData?.providers || []).map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-2 rounded-lg bg-black/25 px-3 py-2">
                <span className="truncate">{p.name} ({p.model_identifier})</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-cyan-300">{p.masked_api_key || "no key"}</span>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      await apiFetch(`/admin/providers/${p.id}`, { method: "DELETE" });
                      toast.success(`Removed provider '${p.name}'`);
                      qc.invalidateQueries({ queryKey: ["admin-providers"] });
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* User Management */}
        <GlassCard className="lg:col-span-7 space-y-3">
          <h2 className="text-base font-semibold">User & Role Management</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                  <th className="py-2">User</th>
                  <th className="py-2">Role</th>
                  <th className="py-2">Status</th>
                  <th className="py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-subtle)]">
                {(usersData?.users || []).map((u) => (
                  <tr key={u.id}>
                    <td className="py-2.5">
                      <p className="font-semibold">{u.full_name || u.email}</p>
                      <p className="text-[11px] text-[var(--text-muted)]">{u.email}</p>
                    </td>
                    <td className="py-2.5">
                      <Badge tone={u.role === "admin" ? "amber" : "violet"}>{u.role}</Badge>
                    </td>
                    <td className="py-2.5">
                      <Badge tone={u.is_suspended ? "rose" : "emerald"}>
                        {u.is_suspended ? "Suspended" : "Active"}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-right">
                      {u.id !== user.id && (
                        <Button
                          size="sm"
                          variant={u.is_suspended ? "secondary" : "danger"}
                          onClick={async () => {
                            await apiFetch(`/admin/users/${u.id}`, {
                              method: "PATCH",
                              body: JSON.stringify({
                                is_suspended: !u.is_suspended,
                                suspension_reason: !u.is_suspended ? "Suspended by administrator" : null,
                              }),
                            });
                            toast.success("User status updated");
                            qc.invalidateQueries({ queryKey: ["admin-users"] });
                          }}
                        >
                          {u.is_suspended ? "Unsuspend" : "Suspend"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>

      {/* Reports & Audit Logs */}
      <div className="grid gap-6 lg:grid-cols-2">
        <GlassCard className="space-y-3">
          <h2 className="text-base font-semibold">Community Moderation Reports</h2>
          {(reportsData?.reports || []).length === 0 ? (
            <p className="text-xs text-[var(--text-muted)]">No open moderation reports.</p>
          ) : (
            reportsData?.reports.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-xl bg-black/25 p-3 text-xs">
                <div>
                  <p className="font-semibold">{r.reason}</p>
                  <p className="text-[var(--text-muted)]">{r.target_type} • {r.status}</p>
                </div>
                {r.status === "open" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      await apiFetch(`/admin/reports/${r.id}`, {
                        method: "PATCH",
                        body: JSON.stringify({ status: "resolved", hide_target_post: true }),
                      });
                      toast.success("Report resolved");
                      qc.invalidateQueries({ queryKey: ["admin-reports"] });
                    }}
                  >
                    Resolve & Hide
                  </Button>
                )}
              </div>
            ))
          )}
        </GlassCard>

        <GlassCard className="space-y-3">
          <h2 className="text-base font-semibold">Security Audit Trail</h2>
          <div className="max-h-64 space-y-1.5 overflow-y-auto text-xs">
            {(auditData?.audit_logs || []).slice(0, 20).map((a) => (
              <div key={a.id} className="flex justify-between rounded-lg bg-black/20 px-3 py-1.5">
                <span className="font-mono text-cyan-300">{a.action}</span>
                <span className="text-[var(--text-muted)]">{a.resource_type}</span>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
