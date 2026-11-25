"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CheckCircle2,
  ClipboardCheck,
  Columns2,
  Download,
  Eye,
  FileText,
  History,
  Image as ImageIcon,
  PenLine,
  Plus,
  Save,
  SlidersHorizontal,
  Trash2,
  Upload,
} from "lucide-react";
import { API_ORIGIN, apiDownloadBlob, apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  InfoCallout,
  Input,
  Modal,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { AssignmentAnalysis, DocumentItem, MediaAssetItem } from "@/types/api";

function AcademicMarkdownPreview({
  markdown,
  imageMap,
}: {
  markdown: string;
  imageMap: Record<string, MediaAssetItem>;
}) {
  const lines = (markdown || "").split("\n");
  return (
    <div className="h-[460px] overflow-y-auto rounded-xl border border-[var(--border-subtle)] bg-white/95 p-6 text-slate-900 shadow-inner space-y-2.5">
      {lines.map((raw, idx) => {
        const line = raw.trim();
        if (!line) return <div key={idx} className="h-1" />;
        if (line === "---") {
          return (
            <div key={idx} className="my-4 border-t-2 border-dashed border-slate-300 pt-1 text-center text-[10px] uppercase tracking-widest text-slate-400">
              Page Break
            </div>
          );
        }
        if (line.startsWith("### ")) {
          return <h3 key={idx} className="text-base font-bold text-slate-800 pt-2">{line.slice(4)}</h3>;
        }
        if (line.startsWith("## ")) {
          return <h2 key={idx} className="text-lg font-bold text-indigo-900 border-b border-slate-200 pb-1 pt-3">{line.slice(3)}</h2>;
        }
        if (line.startsWith("# ")) {
          return <h1 key={idx} className="text-2xl font-extrabold text-slate-950 pb-1">{line.slice(2)}</h1>;
        }
        const imgMatch = line.match(/^!\[([^\]]*)\]\(asset:\/\/([a-zA-Z0-9-]+)\)$/);
        if (imgMatch) {
          const cap = imgMatch[1] || "Figure";
          const asset = imageMap[imgMatch[2]];
          return (
            <figure key={idx} className="my-3 flex flex-col items-center rounded-lg border border-slate-200 bg-slate-50 p-3">
              {asset ? (
                <img
                  src={`${API_ORIGIN}${asset.download_url}`}
                  alt={cap}
                  className="max-h-52 rounded object-contain"
                />
              ) : (
                <div className="py-6 text-xs text-slate-400">[Embedded Figure: {imgMatch[2]}]</div>
              )}
              <figcaption className="mt-1.5 text-xs italic text-slate-600">{cap}</figcaption>
            </figure>
          );
        }
        if (line.startsWith("$$") && line.endsWith("$$")) {
          return (
            <div key={idx} className="my-2 rounded-lg bg-slate-100 px-4 py-2 text-center font-mono text-xs text-slate-800">
              {line.replace(/\$\$/g, "").trim()}
            </div>
          );
        }
        if (line.startsWith("- ") || line.startsWith("* ")) {
          return <p key={idx} className="pl-4 text-sm leading-relaxed">• {line.slice(2)}</p>;
        }
        if (line.startsWith("|")) {
          return <p key={idx} className="font-mono text-xs text-slate-700 bg-slate-50 px-2 py-0.5 rounded">{line}</p>;
        }
        return <p key={idx} className="text-sm leading-relaxed text-slate-800">{line}</p>;
      })}
    </div>
  );
}

export default function DocumentStudioPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"edit" | "split" | "preview">("split");
  const [createOpen, setCreateOpen] = useState(false);
  const [analyzerOpen, setAnalyzerOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [imageModalOpen, setImageModalOpen] = useState(false);
  const [formatModalOpen, setFormatModalOpen] = useState(false);

  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("research_paper");
  const [newStyle, setNewStyle] = useState("APA 7");

  const [editorTitle, setEditorTitle] = useState("");
  const [editorMd, setEditorMd] = useState("");
  const [editorStyle, setEditorStyle] = useState("APA 7");
  const [figureCaption, setFigureCaption] = useState("Figure 1: System Overview");
  const [autosaveState, setAutosaveState] = useState<"saved" | "dirty" | "saving">("saved");
  const hydratedDocRef = useRef<string | null>(null);

  // Cover & university formatting profile
  const [institution, setInstitution] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [courseName, setCourseName] = useState("");
  const [pageSize, setPageSize] = useState("A4");
  const [fontSize, setFontSize] = useState("11");
  const [lineSpacing, setLineSpacing] = useState("1.5");
  const [includeToc, setIncludeToc] = useState(true);

  const [briefText, setBriefText] = useState("");
  const [analysis, setAnalysis] = useState<AssignmentAnalysis | null>(null);

  const { data: listData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => apiFetch<{ documents: DocumentItem[] }>("/documents"),
  });

  const { data: galleryData } = useQuery({
    queryKey: ["image-gallery"],
    queryFn: () => apiFetch<{ images: MediaAssetItem[] }>("/images/gallery"),
  });

  const imageMap: Record<string, MediaAssetItem> = {};
  for (const img of galleryData?.images || []) {
    imageMap[img.id] = img;
  }

  const activeId = selectedId || listData?.documents?.[0]?.id || null;

  const { data: docDetail, refetch: refetchDoc } = useQuery({
    queryKey: ["document", activeId],
    queryFn: () => apiFetch<{ document: DocumentItem }>(`/documents/${activeId}`),
    enabled: Boolean(activeId),
  });

  const { data: versionsData, refetch: refetchVersions } = useQuery({
    queryKey: ["document-versions", activeId],
    queryFn: () =>
      apiFetch<{
        versions: { id: string; version_number: number; title: string; word_count: number; change_summary: string; created_at: string }[];
      }>(`/documents/${activeId}/versions`),
    enabled: Boolean(activeId && versionsOpen),
  });

  useEffect(() => {
    const doc = docDetail?.document;
    if (!doc) return;
    hydratedDocRef.current = doc.id;
    setEditorTitle(doc.title);
    setEditorMd(doc.content_markdown || "");
    setEditorStyle(doc.citation_style);
    setAnalysis(doc.assignment_requirements || null);
    const cp = (doc.cover_page || {}) as Record<string, unknown>;
    const fp = (doc.formatting_profile || {}) as Record<string, unknown>;
    setInstitution(String(cp.institution || ""));
    setAuthorName(String(cp.author || ""));
    setCourseName(String(cp.course || ""));
    setPageSize(String(fp.page_size || "A4"));
    setFontSize(String(fp.font_size || "11"));
    setLineSpacing(String(fp.line_spacing || "1.5"));
    setIncludeToc(fp.include_toc !== false);
    setAutosaveState("saved");
  }, [docDetail?.document?.id, docDetail?.document?.version_number]);

  // Debounced silent autosave (2.5 seconds after typing stops)
  useEffect(() => {
    if (!activeId || hydratedDocRef.current !== activeId || autosaveState !== "dirty") return;
    const timer = setTimeout(async () => {
      setAutosaveState("saving");
      try {
        await apiFetch(`/documents/${activeId}`, {
          method: "PATCH",
          body: JSON.stringify({
            title: editorTitle,
            citation_style: editorStyle,
            content_markdown: editorMd,
            save_version: false,
          }),
        });
        setAutosaveState("saved");
      } catch {
        setAutosaveState("dirty");
      }
    }, 2500);
    return () => clearTimeout(timer);
  }, [activeId, editorTitle, editorStyle, editorMd, autosaveState]);

  const createDoc = useMutation({
    mutationFn: () =>
      apiFetch<{ document: DocumentItem }>("/documents", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle,
          doc_type: newType,
          citation_style: newStyle,
          use_template: true,
        }),
      }),
    onSuccess: (res) => {
      toast.success("Academic document created from template");
      setSelectedId(res.document.id);
      setNewTitle("");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveDoc = useMutation({
    mutationFn: () =>
      apiFetch<{ document: DocumentItem }>(`/documents/${activeId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editorTitle,
          citation_style: editorStyle,
          content_markdown: editorMd,
          cover_page: {
            enabled: true,
            institution,
            author: authorName,
            course: courseName,
          },
          formatting_profile: {
            page_size: pageSize,
            font_size: Number(fontSize) || 11,
            line_spacing: Number(lineSpacing) || 1.5,
            include_toc: includeToc,
          },
          save_version: true,
        }),
      }),
    onSuccess: () => {
      setAutosaveState("saved");
      toast.success("Saved new document version");
      qc.invalidateQueries({ queryKey: ["documents"] });
      refetchDoc();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const runAnalyzer = useMutation({
    mutationFn: (payload: { brief_text?: string; brief_asset_id?: string }) =>
      apiFetch<{ analysis: AssignmentAnalysis }>("/documents/analyze-assignment", {
        method: "POST",
        body: JSON.stringify({ ...payload, document_id: activeId }),
      }),
    onSuccess: (res) => {
      setAnalysis(res.analysis);
      toast.success(`Assignment rubric analyzed (${res.analysis.coverage_percent}% coverage)`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleBriefFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const up = await apiFetch<{ file: { id: string } }>("/files/upload", {
        method: "POST",
        body: fd,
      });
      runAnalyzer.mutate({ brief_asset_id: up.file.id, brief_text: briefText || undefined });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Brief upload failed");
    }
    e.target.value = "";
  };

  const wordCount = editorMd.trim() ? editorMd.trim().split(/\s+/).length : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Academic Document Studio"
        subtitle="Write university papers with APA 7, IEEE, Harvard, MLA & Chicago profiles, live split preview, embedded figures, autosave, rubric analysis & real PDF/DOCX exports."
        badge="Module D"
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => setAnalyzerOpen(true)}>
              <ClipboardCheck className="h-4 w-4" /> Assignment Analyzer
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> New Document
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-2.5 lg:col-span-3">
          {(listData?.documents || []).length === 0 ? (
            <EmptyState
              icon={<FileText className="h-6 w-6" />}
              title="No documents"
              description="Create your first academic paper, lab report, or thesis draft."
              action={<Button size="sm" onClick={() => setCreateOpen(true)}>New Document</Button>}
            />
          ) : (
            listData?.documents.map((d) => (
              <div
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                className={`cursor-pointer rounded-xl border p-3.5 transition ${
                  activeId === d.id
                    ? "border-violet-500/60 bg-violet-600/15"
                    : "border-[var(--border-subtle)] bg-black/20 hover:border-violet-500/30"
                }`}
              >
                <p className="truncate text-sm font-semibold">{d.title}</p>
                <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                  <span>{d.citation_style} • v{d.version_number}</span>
                  <span>{d.word_count} words</span>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="lg:col-span-9">
          {!activeId ? (
            <GlassCard>
              <p className="text-sm text-[var(--text-muted)]">
                Create or select a document to start drafting and exporting submission-ready files.
              </p>
            </GlassCard>
          ) : (
            <GlassCard className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
                <div className="flex flex-1 flex-wrap items-center gap-2">
                  <Input
                    value={editorTitle}
                    onChange={(e) => {
                      setEditorTitle(e.target.value);
                      setAutosaveState("dirty");
                    }}
                    className="max-w-xs font-semibold"
                  />
                  <Select
                    value={editorStyle}
                    onChange={(e) => {
                      setEditorStyle(e.target.value);
                      setAutosaveState("dirty");
                    }}
                    className="w-28"
                  >
                    <option value="APA 7">APA 7</option>
                    <option value="IEEE">IEEE</option>
                    <option value="Harvard">Harvard</option>
                    <option value="MLA">MLA</option>
                    <option value="Chicago">Chicago</option>
                  </Select>
                  <Badge tone="cyan">{wordCount} words</Badge>
                  <Badge tone={autosaveState === "saved" ? "emerald" : "amber"}>
                    {autosaveState === "saving" ? "Autosaving..." : autosaveState === "saved" ? "Autosaved" : "Unsaved edits"}
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <Button size="sm" loading={saveDoc.isPending} onClick={() => saveDoc.mutate()}>
                    <Save className="h-3.5 w-3.5" /> Save v{(docDetail?.document.version_number || 1) + 1}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setFormatModalOpen(true)}>
                    <SlidersHorizontal className="h-3.5 w-3.5" /> Profile
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setVersionsOpen(true);
                      refetchVersions();
                    }}
                  >
                    <History className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    variant="cyan"
                    onClick={() =>
                      apiDownloadBlob(`/documents/${activeId}/export?format=pdf`, `${editorTitle || "paper"}.pdf`)
                        .then(() => toast.success("PDF exported with cover page, tables & figures"))
                        .catch((e) => toast.error(e.message))
                    }
                  >
                    <Download className="h-3.5 w-3.5" /> PDF
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      apiDownloadBlob(`/documents/${activeId}/export?format=docx`, `${editorTitle || "paper"}.docx`)
                        .then(() => toast.success("DOCX exported"))
                        .catch((e) => toast.error(e.message))
                    }
                  >
                    DOCX
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      apiDownloadBlob(`/documents/${activeId}/export?format=md`, `${editorTitle || "paper"}.md`)
                    }
                  >
                    MD
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      await apiFetch(`/documents/${activeId}`, { method: "DELETE" });
                      toast.success("Document deleted");
                      setSelectedId(null);
                      qc.invalidateQueries({ queryKey: ["documents"] });
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {/* Formatting Toolbar + View Mode Switcher */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { label: "H1", insert: "\n# Heading 1\n" },
                    { label: "H2", insert: "\n## Section Heading\n" },
                    { label: "Table", insert: "\n| Column A | Column B |\n| --- | --- |\n| Value 1 | Value 2 |\n" },
                    { label: "Equation", insert: "\n$$ E = mc^2 $$\n" },
                    { label: "Page Break", insert: "\n---\n" },
                  ].map((tool) => (
                    <button
                      key={tool.label}
                      type="button"
                      onClick={() => {
                        setEditorMd((prev) => prev + tool.insert);
                        setAutosaveState("dirty");
                      }}
                      className="rounded-lg border border-[var(--border-subtle)] bg-black/20 px-2.5 py-1 hover:border-violet-500/40"
                    >
                      + {tool.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setImageModalOpen(true)}
                    className="inline-flex items-center gap-1 rounded-lg border border-cyan-500/35 bg-cyan-500/10 px-2.5 py-1 text-cyan-300 hover:bg-cyan-500/20"
                  >
                    <ImageIcon className="h-3.5 w-3.5" /> + Insert Figure
                  </button>
                </div>

                <div className="flex rounded-lg border border-[var(--border-subtle)] bg-black/25 p-0.5">
                  {[
                    { id: "edit", label: "Edit", icon: PenLine },
                    { id: "split", label: "Split", icon: Columns2 },
                    { id: "preview", label: "Preview", icon: Eye },
                  ].map((m) => {
                    const Icon = m.icon;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setViewMode(m.id as typeof viewMode)}
                        className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 ${
                          viewMode === m.id ? "bg-violet-600 text-white" : "text-[var(--text-muted)]"
                        }`}
                      >
                        <Icon className="h-3 w-3" /> {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Split / Edit / Preview Pane */}
              <div className={`grid gap-4 ${viewMode === "split" ? "lg:grid-cols-2" : "grid-cols-1"}`}>
                {viewMode !== "preview" && (
                  <Textarea
                    rows={20}
                    value={editorMd}
                    onChange={(e) => {
                      setEditorMd(e.target.value);
                      setAutosaveState("dirty");
                    }}
                    className="h-[460px] font-mono text-xs leading-relaxed"
                    placeholder="Write your academic paper in Markdown (headings, pipe tables, $$ equations, lists, figures, page breaks)..."
                  />
                )}
                {viewMode !== "edit" && (
                  <AcademicMarkdownPreview markdown={editorMd} imageMap={imageMap} />
                )}
              </div>

              {analysis && (
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-cyan-300">
                      Assignment Requirement Compliance: {analysis.coverage_percent}%
                    </h3>
                    <Badge tone={analysis.missing_requirements.length === 0 ? "emerald" : "amber"}>
                      {analysis.missing_requirements.length} missing items
                    </Badge>
                  </div>
                  <div className="grid gap-1.5 sm:grid-cols-2 text-xs">
                    {analysis.checklist.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <CheckCircle2
                          className={`h-3.5 w-3.5 shrink-0 ${
                            item.status === "satisfied" ? "text-emerald-400" : "text-amber-400"
                          }`}
                        />
                        <span>{item.item}</span>
                      </div>
                    ))}
                  </div>
                  <InfoCallout text={analysis.disclaimer} />
                </div>
              )}
            </GlassCard>
          )}
        </div>
      </div>

      {/* Create Document Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Academic Document">
        <div className="space-y-3">
          <Input placeholder="Document Title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Select value={newType} onChange={(e) => setNewType(e.target.value)}>
            <option value="assignment">University Assignment</option>
            <option value="research_paper">Research Paper</option>
            <option value="project_proposal">Project Proposal</option>
            <option value="fyp_report">Final-Year Project Report</option>
            <option value="lab_report">Laboratory Report</option>
            <option value="case_study">Case Study</option>
            <option value="technical_documentation">Technical Documentation / SRS</option>
            <option value="internship_report">Internship Report</option>
            <option value="business_report">Business Report</option>
            <option value="reflective_journal">Reflective Journal</option>
          </Select>
          <Select value={newStyle} onChange={(e) => setNewStyle(e.target.value)}>
            <option value="APA 7">APA 7</option>
            <option value="IEEE">IEEE</option>
            <option value="Harvard">Harvard</option>
            <option value="MLA">MLA</option>
            <option value="Chicago">Chicago</option>
          </Select>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={newTitle.trim().length < 2} loading={createDoc.isPending} onClick={() => createDoc.mutate()}>
              Create From Template
            </Button>
          </div>
        </div>
      </Modal>

      {/* Insert Embedded Figure Modal */}
      <Modal open={imageModalOpen} onClose={() => setImageModalOpen(false)} title="Insert Figure & Caption (Embeds in PDF/DOCX)">
        <div className="space-y-3">
          <Input
            placeholder="Figure caption (e.g., Figure 1: System Architecture)"
            value={figureCaption}
            onChange={(e) => setFigureCaption(e.target.value)}
          />
          {(galleryData?.images || []).length === 0 ? (
            <p className="text-xs text-[var(--text-muted)]">
              Upload or generate an image in Image Studio first to embed it natively in your document.
            </p>
          ) : (
            <div className="grid max-h-64 grid-cols-3 gap-2 overflow-y-auto">
              {galleryData?.images.map((img) => (
                <button
                  key={img.id}
                  type="button"
                  onClick={() => {
                    setEditorMd((prev) => `${prev}\n\n![${figureCaption || img.filename}](asset://${img.id})\n`);
                    setAutosaveState("dirty");
                    setImageModalOpen(false);
                    toast.success("Embedded figure inserted!");
                  }}
                  className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-black/30 p-1.5 hover:border-cyan-400"
                >
                  <img src={`${API_ORIGIN}${img.download_url}`} alt={img.filename} className="h-20 w-full rounded object-cover" />
                  <p className="mt-1 truncate text-[10px]">{img.filename}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </Modal>

      {/* Cover Page & University Formatting Profile Modal */}
      <Modal open={formatModalOpen} onClose={() => setFormatModalOpen(false)} title="Cover Page & University Formatting Profile">
        <div className="space-y-3">
          <Input placeholder="University / Institution Name" value={institution} onChange={(e) => setInstitution(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Author Full Name" value={authorName} onChange={(e) => setAuthorName(e.target.value)} />
            <Input placeholder="Course Code / Title" value={courseName} onChange={(e) => setCourseName(e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Select value={pageSize} onChange={(e) => setPageSize(e.target.value)}>
              <option value="A4">A4 Page</option>
              <option value="LETTER">US Letter</option>
            </Select>
            <Select value={fontSize} onChange={(e) => setFontSize(e.target.value)}>
              <option value="10">10pt</option>
              <option value="11">11pt</option>
              <option value="12">12pt</option>
            </Select>
            <Select value={lineSpacing} onChange={(e) => setLineSpacing(e.target.value)}>
              <option value="1.15">1.15x Spacing</option>
              <option value="1.5">1.5x Spacing</option>
              <option value="2.0">Double (2.0x)</option>
            </Select>
          </div>
          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <input type="checkbox" checked={includeToc} onChange={(e) => setIncludeToc(e.target.checked)} />
            Include Table of Contents in PDF export
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setFormatModalOpen(false)}>Close</Button>
            <Button
              loading={saveDoc.isPending}
              onClick={() => {
                saveDoc.mutate();
                setFormatModalOpen(false);
              }}
            >
              Apply Formatting Profile
            </Button>
          </div>
        </div>
      </Modal>

      {/* Assignment Analyzer Modal */}
      <Modal open={analyzerOpen} onClose={() => setAnalyzerOpen(false)} title="Assignment Requirement Analyzer">
        <div className="space-y-3">
          <p className="text-xs text-[var(--text-muted)]">
            Upload your assignment brief PDF/DOCX or paste marking rubric instructions to compare against your active document.
          </p>
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-cyan-500/40 bg-cyan-500/5 py-4 text-xs font-medium text-cyan-300 hover:bg-cyan-500/10">
            <Upload className="h-4 w-4" /> Upload Assignment Brief (PDF / DOCX / TXT)
            <input type="file" accept=".pdf,.docx,.txt,.md" className="hidden" onChange={handleBriefFile} />
          </label>
          <Textarea
            rows={5}
            placeholder="Or paste assignment instructions, required sections, word limits, and rubric criteria..."
            value={briefText}
            onChange={(e) => setBriefText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setAnalyzerOpen(false)}>Close</Button>
            <Button
              disabled={!briefText.trim()}
              loading={runAnalyzer.isPending}
              onClick={() => {
                runAnalyzer.mutate({ brief_text: briefText });
                setAnalyzerOpen(false);
              }}
            >
              Analyze Requirements
            </Button>
          </div>
        </div>
      </Modal>

      {/* Version History Modal */}
      <Modal open={versionsOpen} onClose={() => setVersionsOpen(false)} title="Document Version History">
        <div className="max-h-80 space-y-2 overflow-y-auto">
          {(versionsData?.versions || []).map((v) => (
            <div key={v.id} className="flex items-center justify-between rounded-xl bg-black/25 p-3 text-xs">
              <div>
                <p className="font-semibold">v{v.version_number} — {v.change_summary}</p>
                <p className="text-[var(--text-muted)]">{v.word_count} words</p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  await apiFetch(`/documents/${activeId}/versions/${v.id}/restore`, { method: "POST" });
                  toast.success(`Restored version ${v.version_number}`);
                  setVersionsOpen(false);
                  refetchDoc();
                }}
              >
                Restore
              </Button>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
