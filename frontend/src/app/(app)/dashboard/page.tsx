"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BookOpen,
  CheckCircle2,
  Circle,
  FileText,
  Film,
  FolderKanban,
  GraduationCap,
  Image as ImageIcon,
  Network,
  Plus,
  Presentation,
  Search,
  Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  Input,
  Modal,
  PageHeader,
  Select,
  StatCard,
} from "@/components/ui/primitives";
import type { TaskItem } from "@/types/api";

interface DashboardResponse {
  welcome: {
    full_name: string;
    university: string | null;
    department: string | null;
    academic_level: string;
  };
  stats: {
    projects: number;
    documents: number;
    diagrams: number;
    presentations: number;
    research_sources: number;
    task_completion_percent: number;
    storage_used_bytes: number;
    storage_quota_bytes: number;
  };
  fair_use_status: Record<string, { used: number; limit: number }>;
  workspaces: { id: string; name: string; slug: string; is_personal: boolean }[];
  projects: { id: string; title: string; course_code: string | null; subject: string | null; status: string; updated_at: string }[];
  recent_documents: { id: string; title: string; doc_type: string; citation_style: string; word_count: number; updated_at: string }[];
  recent_media: { id: string; filename: string; asset_type: string; size_bytes: number; created_at: string }[];
  upcoming_tasks: TaskItem[];
  recent_jobs: { id: string; job_type: string; provider: string; status: string; progress_percent: number; error_message: string | null }[];
  recent_activity: { id: string; action: string; resource_type: string; created_at: string }[];
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const [searchQ, setSearchQ] = useState("");
  const [taskModal, setTaskModal] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskPriority, setTaskPriority] = useState("medium");

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<DashboardResponse>("/users/dashboard"),
  });

  const { data: searchRes } = useQuery({
    queryKey: ["global-search", searchQ],
    queryFn: () =>
      apiFetch<{
        projects: { id: string; title: string }[];
        documents: { id: string; title: string }[];
        diagrams: { id: string; title: string }[];
        research_sources: { id: string; title: string }[];
      }>(`/users/search?q=${encodeURIComponent(searchQ)}`),
    enabled: searchQ.trim().length >= 2,
  });

  const createTask = useMutation({
    mutationFn: () =>
      apiFetch("/tasks", {
        method: "POST",
        body: JSON.stringify({ title: taskTitle, priority: taskPriority }),
      }),
    onSuccess: () => {
      toast.success("Assignment task added");
      setTaskTitle("");
      setTaskModal(false);
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const toggleTask = useMutation({
    mutationFn: (t: TaskItem) =>
      apiFetch(`/tasks/${t.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: t.status === "done" ? "todo" : "done" }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard"] }),
  });

  const storageMb = ((data?.stats.storage_used_bytes || 0) / (1024 * 1024)).toFixed(1);
  const quotaMb = ((data?.stats.storage_quota_bytes || 524288000) / (1024 * 1024)).toFixed(0);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${data?.welcome.full_name || "Scholar"}`}
        subtitle={
          data?.welcome.university
            ? `${data.welcome.university}${data.welcome.department ? ` • ${data.welcome.department}` : ""} • Free Academic Access`
            : "Your connected academic workspace — research, write, visualize, and study in one place."
        }
        badge="100% Free Platform"
        actions={
          <>
            <Link href="/projects">
              <Button variant="secondary" size="sm">
                <FolderKanban className="h-4 w-4" /> New Project
              </Button>
            </Link>
            <Link href="/documents">
              <Button size="sm">
                <FileText className="h-4 w-4" /> New Document
              </Button>
            </Link>
          </>
        }
      />

      {/* Global Academic Search */}
      <GlassCard className="p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-cyan-400" />
          <Input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search across all your projects, documents, diagrams, research sources & study notes..."
            className="pl-10"
          />
        </div>
        {searchQ.trim().length >= 2 && searchRes && (
          <div className="mt-3 grid gap-3 border-t border-[var(--border-subtle)] pt-3 sm:grid-cols-2 lg:grid-cols-4 text-xs">
            <div>
              <p className="font-semibold text-cyan-300 mb-1">Projects ({searchRes.projects.length})</p>
              {searchRes.projects.map((p) => (
                <Link key={p.id} href="/projects" className="block truncate py-0.5 hover:text-white text-[var(--text-secondary)]">
                  • {p.title}
                </Link>
              ))}
            </div>
            <div>
              <p className="font-semibold text-violet-300 mb-1">Documents ({searchRes.documents.length})</p>
              {searchRes.documents.map((d) => (
                <Link key={d.id} href="/documents" className="block truncate py-0.5 hover:text-white text-[var(--text-secondary)]">
                  • {d.title}
                </Link>
              ))}
            </div>
            <div>
              <p className="font-semibold text-emerald-300 mb-1">Diagrams ({searchRes.diagrams.length})</p>
              {searchRes.diagrams.map((g) => (
                <Link key={g.id} href="/diagrams" className="block truncate py-0.5 hover:text-white text-[var(--text-secondary)]">
                  • {g.title}
                </Link>
              ))}
            </div>
            <div>
              <p className="font-semibold text-amber-300 mb-1">Sources ({searchRes.research_sources.length})</p>
              {searchRes.research_sources.map((s) => (
                <Link key={s.id} href="/research" className="block truncate py-0.5 hover:text-white text-[var(--text-secondary)]">
                  • {s.title}
                </Link>
              ))}
            </div>
          </div>
        )}
      </GlassCard>

      {/* Live DB Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Projects" value={isLoading ? "…" : data?.stats.projects ?? 0} icon={<FolderKanban className="h-5 w-5" />} />
        <StatCard label="Documents" value={isLoading ? "…" : data?.stats.documents ?? 0} icon={<FileText className="h-5 w-5" />} />
        <StatCard label="Diagrams" value={isLoading ? "…" : data?.stats.diagrams ?? 0} icon={<Network className="h-5 w-5" />} />
        <StatCard label="Sources" value={isLoading ? "…" : data?.stats.research_sources ?? 0} icon={<BookOpen className="h-5 w-5" />} />
        <StatCard
          label="Storage"
          value={`${storageMb} MB`}
          sublabel={`of ${quotaMb} MB free quota`}
          icon={<Sparkles className="h-5 w-5" />}
        />
      </div>

      {/* Quick-Create Studio Launchers */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { href: "/documents", label: "Document Studio", icon: FileText },
          { href: "/research", label: "Research Search", icon: BookOpen },
          { href: "/diagrams", label: "Diagram Canvas", icon: Network },
          { href: "/presentations", label: "Slide Deck", icon: Presentation },
          { href: "/learning", label: "Study & Quizzes", icon: GraduationCap },
          { href: "/videos", label: "Video Studio", icon: Film },
        ].map((q) => {
          const Icon = q.icon;
          return (
            <Link key={q.href} href={q.href}>
              <GlassCard hover className="flex items-center gap-2.5 p-3.5">
                <Icon className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-semibold">{q.label}</span>
              </GlassCard>
            </Link>
          );
        })}
      </div>

      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Academic Projects & Recent Documents */}
        <div className="space-y-6 lg:col-span-8">
          <GlassCard>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold">Academic Projects</h2>
              <Link href="/projects" className="text-xs text-cyan-400 hover:underline">
                Manage all →
              </Link>
            </div>
            {(data?.projects || []).length === 0 ? (
              <EmptyState
                icon={<FolderKanban className="h-6 w-6" />}
                title="No academic projects yet"
                description="Create a project like 'Smart Bus Booking System' to connect research, documents, diagrams, slides, and tasks."
                action={
                  <Link href="/projects">
                    <Button size="sm">Create First Project</Button>
                  </Link>
                }
              />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {data?.projects.map((p) => (
                  <Link key={p.id} href="/projects">
                    <div className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-4 hover:border-violet-500/40 transition">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-semibold text-sm truncate">{p.title}</p>
                        <Badge tone="cyan">{p.status}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                        {p.course_code || "General"} {p.subject ? `• ${p.subject}` : ""}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </GlassCard>

          <GlassCard>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold">Recent Documents</h2>
              <Link href="/documents" className="text-xs text-cyan-400 hover:underline">
                Open Document Studio →
              </Link>
            </div>
            {(data?.recent_documents || []).length === 0 ? (
              <EmptyState
                icon={<FileText className="h-6 w-6" />}
                title="No documents drafted yet"
                description="Start an APA 7, IEEE, Harvard, MLA, or Chicago paper with real PDF and DOCX export."
                action={
                  <Link href="/documents">
                    <Button size="sm">Create Document</Button>
                  </Link>
                }
              />
            ) : (
              <div className="divide-y divide-[var(--border-subtle)]">
                {data?.recent_documents.map((d) => (
                  <div key={d.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium">{d.title}</p>
                      <p className="text-xs text-[var(--text-muted)]">
                        {d.doc_type.replace("_", " ")} • {d.citation_style} • {d.word_count} words
                      </p>
                    </div>
                    <Link href="/documents">
                      <Button variant="ghost" size="sm">Open</Button>
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>
        </div>

        {/* Right Column: Tasks + Fair-Use Status + Recent Media */}
        <div className="space-y-6 lg:col-span-4">
          <GlassCard>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold">Upcoming Assignments & Tasks</h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Completion: {data?.stats.task_completion_percent ?? 0}%
                </p>
              </div>
              <Button size="sm" variant="secondary" onClick={() => setTaskModal(true)}>
                <Plus className="h-3.5 w-3.5" /> Add
              </Button>
            </div>
            {(data?.upcoming_tasks || []).length === 0 ? (
              <p className="py-6 text-center text-xs text-[var(--text-muted)]">
                No tasks tracked yet. Add deadlines to stay on schedule.
              </p>
            ) : (
              <div className="space-y-2">
                {data?.upcoming_tasks.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between gap-2 rounded-xl bg-black/20 px-3 py-2.5"
                  >
                    <button
                      onClick={() => toggleTask.mutate(t)}
                      className="flex items-center gap-2 text-left text-xs"
                    >
                      {t.status === "done" ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                      ) : (
                        <Circle className="h-4 w-4 shrink-0 text-[var(--text-muted)]" />
                      )}
                      <span className={t.status === "done" ? "line-through text-[var(--text-muted)]" : ""}>
                        {t.title}
                      </span>
                    </button>
                    <Badge tone={t.priority === "urgent" ? "rose" : t.priority === "high" ? "amber" : "slate"}>
                      {t.priority}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </GlassCard>

          <GlassCard>
            <h2 className="mb-3 text-base font-semibold">Daily Fair-Use Status</h2>
            <p className="mb-3 text-xs text-[var(--text-muted)]">
              Transparent free quotas reset every 24 hours. No paid plans required.
            </p>
            <div className="space-y-3">
              {Object.entries(data?.fair_use_status || {}).map(([key, val]) => {
                const pct = Math.min(100, Math.round((val.used / Math.max(1, val.limit)) * 100));
                return (
                  <div key={key}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="capitalize text-[var(--text-secondary)]">
                        {key.replace("_", " ")}
                      </span>
                      <span className="text-[var(--text-muted)]">
                        {val.used} / {val.limit}
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-white/10">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-violet-500 to-cyan-400"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </GlassCard>

          <GlassCard>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold">Recent Media & Activity</h2>
              <ImageIcon className="h-4 w-4 text-cyan-400" />
            </div>
            {(data?.recent_activity || []).length === 0 ? (
              <p className="text-xs text-[var(--text-muted)]">Activity will appear here as you work.</p>
            ) : (
              <ul className="space-y-1.5 text-xs text-[var(--text-secondary)]">
                {data?.recent_activity.slice(0, 6).map((a) => (
                  <li key={a.id} className="flex justify-between">
                    <span className="font-mono text-[11px] text-cyan-300">{a.action}</span>
                    <span className="text-[var(--text-muted)]">{a.resource_type}</span>
                  </li>
                ))}
              </ul>
            )}
          </GlassCard>
        </div>
      </div>

      <Modal open={taskModal} onClose={() => setTaskModal(false)} title="Add Academic Task">
        <div className="space-y-3">
          <Input
            placeholder="e.g., Submit CS499 Literature Review draft"
            value={taskTitle}
            onChange={(e) => setTaskTitle(e.target.value)}
          />
          <Select value={taskPriority} onChange={(e) => setTaskPriority(e.target.value)}>
            <option value="low">Low Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="high">High Priority</option>
            <option value="urgent">Urgent</option>
          </Select>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setTaskModal(false)}>Cancel</Button>
            <Button
              loading={createTask.isPending}
              disabled={!taskTitle.trim()}
              onClick={() => createTask.mutate()}
            >
              Save Task
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
