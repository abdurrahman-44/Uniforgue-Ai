"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  FileUp,
  FolderKanban,
  Layers,
  Plus,
  Shield,
  Trash2,
  UserPlus,
} from "lucide-react";
import { apiDownloadBlob, apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  Input,
  Modal,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { AcademicProject, Workspace } from "@/types/api";

interface ProjectHubResponse {
  project: AcademicProject;
  documents: { id: string; title: string; doc_type: string; word_count: number }[];
  diagrams: { id: string; title: string; diagram_type: string }[];
  presentations: { id: string; title: string; theme: string }[];
  research_sources: { id: string; title: string; year: number | null; provenance_status: string }[];
  files: { id: string; filename: string; asset_type: string; size_bytes: number }[];
  tasks: { id: string; title: string; status: string; priority: string }[];
  context_items: {
    id: string;
    source_type: string;
    title: string;
    include_in_ai_context: boolean;
    token_estimate: number;
  }[];
}

export default function ProjectsHubPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [wsModal, setWsModal] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);

  const [title, setTitle] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [citationStyle, setCitationStyle] = useState("APA 7");
  const [wsName, setWsName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");

  const { data: wsData } = useQuery({
    queryKey: ["workspaces"],
    queryFn: () => apiFetch<{ workspaces: Workspace[] }>("/workspaces"),
  });

  const { data: projData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<{ projects: AcademicProject[] }>("/projects"),
  });

  const activeId = selectedId || projData?.projects?.[0]?.id || null;

  const { data: hubData, refetch: refetchHub } = useQuery({
    queryKey: ["project-hub", activeId],
    queryFn: () => apiFetch<ProjectHubResponse>(`/projects/${activeId}`),
    enabled: Boolean(activeId),
  });

  const createProject = useMutation({
    mutationFn: () =>
      apiFetch<{ project: AcademicProject }>("/projects", {
        method: "POST",
        body: JSON.stringify({
          title,
          course_code: courseCode || null,
          subject: subject || null,
          description: description || null,
          citation_style: citationStyle,
        }),
      }),
    onSuccess: (res) => {
      toast.success(`Project "${res.project.title}" created`);
      setSelectedId(res.project.id);
      setTitle("");
      setCourseCode("");
      setSubject("");
      setDescription("");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createWs = useMutation({
    mutationFn: () =>
      apiFetch("/workspaces", {
        method: "POST",
        body: JSON.stringify({ name: wsName }),
      }),
    onSuccess: () => {
      toast.success("Team workspace created");
      setWsName("");
      setWsModal(false);
      qc.invalidateQueries({ queryKey: ["workspaces"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteProject = useMutation({
    mutationFn: (id: string) => apiFetch(`/projects/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Project deleted");
      setSelectedId(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const addContextNote = useMutation({
    mutationFn: () =>
      apiFetch(`/projects/${activeId}/context`, {
        method: "POST",
        body: JSON.stringify({
          source_type: "note",
          title: noteTitle,
          content_excerpt: noteBody,
          include_in_ai_context: true,
        }),
      }),
    onSuccess: () => {
      toast.success("Added to isolated project AI context");
      setNoteTitle("");
      setNoteBody("");
      refetchHub();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeId) return;
    const form = new FormData();
    form.append("file", file);
    form.append("project_id", activeId);
    form.append("add_to_project_context", "true");
    try {
      await apiFetch("/files/upload", { method: "POST", body: form });
      toast.success(`Uploaded "${file.name}" & indexed for project context`);
      refetchHub();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Unified Academic Workspace Hub"
        subtitle="Organize courses, thesis projects, connected files, research, diagrams, and strictly isolated AI context."
        badge="Module J"
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => setWsModal(true)}>
              <Layers className="h-4 w-4" /> New Workspace
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> New Academic Project
            </Button>
          </>
        }
      />

      {/* Workspaces Bar */}
      <div className="flex flex-wrap items-center gap-2">
        {(wsData?.workspaces || []).map((w) => (
          <Badge key={w.id} tone={w.is_personal ? "violet" : "cyan"}>
            {w.name} {w.is_personal ? "(Private)" : "(Team)"}
          </Badge>
        ))}
        {wsData?.workspaces?.[0] && (
          <Button variant="ghost" size="sm" onClick={() => setInviteOpen(true)}>
            <UserPlus className="h-3.5 w-3.5" /> Invite Collaborator
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Project List */}
        <div className="space-y-3 lg:col-span-4">
          {(projData?.projects || []).length === 0 ? (
            <EmptyState
              icon={<FolderKanban className="h-6 w-6" />}
              title="No projects yet"
              description="Create a university project to link documents, diagrams, slides, files, and isolated AI context."
              action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create Project</Button>}
            />
          ) : (
            projData?.projects.map((p) => (
              <div
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`cursor-pointer rounded-2xl border p-4 transition ${
                  activeId === p.id
                    ? "border-violet-500/60 bg-violet-600/15"
                    : "border-[var(--border-subtle)] bg-black/20 hover:border-violet-500/30"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-sm">{p.title}</p>
                    <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                      {p.course_code || "Course"} • {p.citation_style}
                    </p>
                  </div>
                  <Badge tone="cyan">{p.status}</Badge>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Connected Project Hub */}
        <div className="lg:col-span-8">
          {!hubData ? (
            <GlassCard>
              <p className="text-sm text-[var(--text-muted)]">
                Select or create a project to view its connected academic artifacts and AI context controls.
              </p>
            </GlassCard>
          ) : (
            <div className="space-y-5">
              <GlassCard>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-bold">{hubData.project.title}</h2>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {hubData.project.description || "Unified workspace connecting every artifact for this project."}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-cyan-600/80 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-500">
                      <FileUp className="h-3.5 w-3.5" /> Upload PDF/DOCX
                      <input type="file" className="hidden" onChange={handleFileUpload} />
                    </label>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => deleteProject.mutate(hubData.project.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5 text-center text-xs">
                  <div className="rounded-xl bg-black/25 p-2.5">
                    <p className="text-lg font-bold text-violet-300">{hubData.documents.length}</p>
                    <p className="text-[var(--text-muted)]">Documents</p>
                  </div>
                  <div className="rounded-xl bg-black/25 p-2.5">
                    <p className="text-lg font-bold text-cyan-300">{hubData.diagrams.length}</p>
                    <p className="text-[var(--text-muted)]">Diagrams</p>
                  </div>
                  <div className="rounded-xl bg-black/25 p-2.5">
                    <p className="text-lg font-bold text-emerald-300">{hubData.presentations.length}</p>
                    <p className="text-[var(--text-muted)]">Slide Decks</p>
                  </div>
                  <div className="rounded-xl bg-black/25 p-2.5">
                    <p className="text-lg font-bold text-amber-300">{hubData.research_sources.length}</p>
                    <p className="text-[var(--text-muted)]">Sources</p>
                  </div>
                  <div className="rounded-xl bg-black/25 p-2.5">
                    <p className="text-lg font-bold text-sky-300">{hubData.files.length}</p>
                    <p className="text-[var(--text-muted)]">Files</p>
                  </div>
                </div>
              </GlassCard>

              {/* Isolated Project AI Context Control */}
              <GlassCard>
                <div className="mb-3 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold">
                    Isolated Project AI Context Controls
                  </h3>
                </div>
                <p className="mb-3 text-xs text-[var(--text-muted)]">
                  Only checked items below are retrieved when using AI for this project. Other projects remain completely isolated.
                </p>

                <div className="space-y-2 mb-4">
                  {hubData.context_items.length === 0 ? (
                    <p className="text-xs text-[var(--text-muted)]">
                      Upload a PDF/DOCX above or add a project note below to populate project context.
                    </p>
                  ) : (
                    hubData.context_items.map((c) => (
                      <label
                        key={c.id}
                        className="flex items-center justify-between rounded-xl bg-black/20 px-3 py-2 text-xs"
                      >
                        <span className="flex items-center gap-2.5">
                          <input
                            type="checkbox"
                            checked={c.include_in_ai_context}
                            onChange={async (e) => {
                              await apiFetch(`/projects/${hubData.project.id}/context/${c.id}`, {
                                method: "PATCH",
                                body: JSON.stringify({ include_in_ai_context: e.target.checked }),
                              });
                              refetchHub();
                            }}
                          />
                          <span className="font-medium">{c.title}</span>
                          <Badge tone="slate">{c.source_type}</Badge>
                        </span>
                        <span className="text-[var(--text-muted)]">~{c.token_estimate} tokens</span>
                      </label>
                    ))
                  )}
                </div>

                <div className="grid gap-2 border-t border-[var(--border-subtle)] pt-3">
                  <Input
                    placeholder="Add context note title (e.g., Methodology Constraints)"
                    value={noteTitle}
                    onChange={(e) => setNoteTitle(e.target.value)}
                  />
                  <Textarea
                    rows={2}
                    placeholder="Paste key requirements, experimental notes, or rubric details..."
                    value={noteBody}
                    onChange={(e) => setNoteBody(e.target.value)}
                  />
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      disabled={!noteTitle.trim() || !noteBody.trim()}
                      loading={addContextNote.isPending}
                      onClick={() => addContextNote.mutate()}
                    >
                      Add to Project Context
                    </Button>
                  </div>
                </div>
              </GlassCard>

              {/* Project Files */}
              {hubData.files.length > 0 && (
                <GlassCard>
                  <h3 className="mb-3 text-sm font-semibold">Project Files</h3>
                  <div className="divide-y divide-[var(--border-subtle)] text-xs">
                    {hubData.files.map((f) => (
                      <div key={f.id} className="flex items-center justify-between py-2">
                        <span>
                          {f.filename} ({(f.size_bytes / 1024).toFixed(1)} KB)
                        </span>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            const { download_url } = await apiFetch<{ download_url: string }>(
                              `/files/${f.id}/signed-url`
                            );
                            await apiDownloadBlob(download_url, f.filename);
                          }}
                        >
                          Download
                        </Button>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Create Project Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Academic Project">
        <div className="space-y-3">
          <Input placeholder="Project Title (e.g., Smart Bus Booking System)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Course Code (CS499)" value={courseCode} onChange={(e) => setCourseCode(e.target.value)} />
            <Input placeholder="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <Select value={citationStyle} onChange={(e) => setCitationStyle(e.target.value)}>
            <option value="APA 7">APA 7</option>
            <option value="IEEE">IEEE</option>
            <option value="Harvard">Harvard</option>
            <option value="MLA">MLA</option>
            <option value="Chicago">Chicago</option>
          </Select>
          <Textarea rows={3} placeholder="Short project scope & goals..." value={description} onChange={(e) => setDescription(e.target.value)} />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={title.trim().length < 2} loading={createProject.isPending} onClick={() => createProject.mutate()}>
              Create Project
            </Button>
          </div>
        </div>
      </Modal>

      {/* New Workspace Modal */}
      <Modal open={wsModal} onClose={() => setWsModal(false)} title="Create Team Workspace">
        <div className="space-y-3">
          <Input placeholder="Workspace Name (e.g., Robotics Capstone Team)" value={wsName} onChange={(e) => setWsName(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setWsModal(false)}>Cancel</Button>
            <Button disabled={wsName.trim().length < 2} loading={createWs.isPending} onClick={() => createWs.mutate()}>
              Create Workspace
            </Button>
          </div>
        </div>
      </Modal>

      {/* Invite Collaborator Modal */}
      <Modal open={inviteOpen} onClose={() => setInviteOpen(false)} title="Invite Workspace Collaborator">
        <div className="space-y-3">
          <Input type="email" placeholder="teammate@university.edu" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setInviteOpen(false)}>Cancel</Button>
            <Button
              disabled={!inviteEmail.includes("@")}
              onClick={async () => {
                try {
                  const wsId = wsData?.workspaces?.[0]?.id;
                  if (!wsId) return;
                  await apiFetch(`/workspaces/${wsId}/members`, {
                    method: "POST",
                    body: JSON.stringify({ email: inviteEmail, role: "editor" }),
                  });
                  toast.success("Collaborator added to workspace");
                  setInviteEmail("");
                  setInviteOpen(false);
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Could not invite user");
                }
              }}
            >
              Add Editor
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
