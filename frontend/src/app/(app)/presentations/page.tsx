"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ArrowDown,
  ArrowUp,
  Download,
  Plus,
  Presentation as PresentationIcon,
  Save,
  Trash2,
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
import type { DocumentItem, PresentationItem, PresentationSlide } from "@/types/api";

export default function PresentationStudioPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeSlideIdx, setActiveSlideIdx] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);

  const [newTitle, setNewTitle] = useState("");
  const [newTheme, setNewTheme] = useState("academic_navy");
  const [sourcePrompt, setSourcePrompt] = useState("");
  const [sourceDocId, setSourceDocId] = useState("");

  const [slideTitle, setSlideTitle] = useState("");
  const [slideBullets, setSlideBullets] = useState("");
  const [slideNotes, setSlideNotes] = useState("");

  const { data: listData } = useQuery({
    queryKey: ["presentations"],
    queryFn: () => apiFetch<{ presentations: PresentationItem[] }>("/presentations"),
  });

  const { data: docsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => apiFetch<{ documents: DocumentItem[] }>("/documents"),
  });

  const activeId = selectedId || listData?.presentations?.[0]?.id || null;

  const { data: detailData, refetch: refetchDetail } = useQuery({
    queryKey: ["presentation", activeId],
    queryFn: () => apiFetch<{ presentation: PresentationItem }>(`/presentations/${activeId}`),
    enabled: Boolean(activeId),
  });

  const slides: PresentationSlide[] = detailData?.presentation?.slides || [];
  const activeSlide = slides[activeSlideIdx] || slides[0];

  useEffect(() => {
    if (activeSlide) {
      setSlideTitle(activeSlide.title);
      setSlideBullets((activeSlide.bullets || []).join("\n"));
      setSlideNotes(activeSlide.speaker_notes || "");
    }
  }, [activeSlide?.id, activeSlide?.title]);

  const createDeck = useMutation({
    mutationFn: () =>
      apiFetch<{ presentation: PresentationItem }>("/presentations", {
        method: "POST",
        body: JSON.stringify({
          title: newTitle,
          theme: newTheme,
          source_prompt: sourcePrompt || null,
          source_document_id: sourceDocId || null,
          slide_count: 6,
        }),
      }),
    onSuccess: (res) => {
      toast.success("Presentation deck created");
      setSelectedId(res.presentation.id);
      setActiveSlideIdx(0);
      setNewTitle("");
      setSourcePrompt("");
      setCreateOpen(false);
      qc.invalidateQueries({ queryKey: ["presentations"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveSlide = useMutation({
    mutationFn: () =>
      apiFetch(`/presentations/${activeId}/slides/${activeSlide.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          layout: activeSlide.layout,
          title: slideTitle,
          bullets: slideBullets
            .split("\n")
            .map((b) => b.trim())
            .filter(Boolean),
          body_text: "",
          speaker_notes: slideNotes,
        }),
      }),
    onSuccess: () => {
      toast.success("Slide updated");
      refetchDetail();
    },
  });

  const addSlide = useMutation({
    mutationFn: () =>
      apiFetch(`/presentations/${activeId}/slides`, {
        method: "POST",
        body: JSON.stringify({
          layout: "title_and_bullets",
          title: `Slide ${slides.length + 1}`,
          bullets: ["Key academic takeaway"],
          speaker_notes: "",
        }),
      }),
    onSuccess: () => {
      refetchDetail();
      setActiveSlideIdx(slides.length);
    },
  });

  const moveSlide = async (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= slides.length) return;
    const ids = slides.map((s) => s.id);
    [ids[idx], ids[target]] = [ids[target], ids[idx]];
    await apiFetch(`/presentations/${activeId}/reorder`, {
      method: "POST",
      body: JSON.stringify({ slide_ids: ids }),
    });
    setActiveSlideIdx(target);
    refetchDetail();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Presentation Studio"
        subtitle="Build academic slide decks from prompts, documents, or research notes and export native PowerPoint (.pptx) & PDF files."
        badge="Module E • python-pptx"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> New Presentation
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Decks + Slide Thumbnails */}
        <div className="space-y-4 lg:col-span-3">
          <GlassCard className="space-y-2 p-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Decks
            </h3>
            {(listData?.presentations || []).length === 0 ? (
              <EmptyState
                icon={<PresentationIcon className="h-5 w-5" />}
                title="No decks"
                description="Generate your first academic slide deck."
                action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create Deck</Button>}
              />
            ) : (
              listData?.presentations.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    setSelectedId(p.id);
                    setActiveSlideIdx(0);
                  }}
                  className={`w-full rounded-xl border p-2.5 text-left text-xs transition ${
                    activeId === p.id
                      ? "border-violet-500/60 bg-violet-600/20"
                      : "border-[var(--border-subtle)] bg-black/20"
                  }`}
                >
                  <p className="truncate font-semibold">{p.title}</p>
                  <p className="text-[11px] text-[var(--text-muted)]">{p.theme}</p>
                </button>
              ))
            )}
          </GlassCard>

          {activeId && (
            <GlassCard className="space-y-2 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Slides ({slides.length})</span>
                <Button size="sm" variant="secondary" onClick={() => addSlide.mutate()}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              <div className="max-h-72 space-y-1.5 overflow-y-auto">
                {slides.map((s, idx) => (
                  <div
                    key={s.id}
                    onClick={() => setActiveSlideIdx(idx)}
                    className={`flex cursor-pointer items-center justify-between rounded-lg border px-2.5 py-2 text-xs ${
                      activeSlide?.id === s.id
                        ? "border-cyan-500/60 bg-cyan-500/15"
                        : "border-[var(--border-subtle)] bg-black/20"
                    }`}
                  >
                    <span className="truncate">{idx + 1}. {s.title}</span>
                    <div className="flex gap-0.5">
                      <button type="button" onClick={(e) => { e.stopPropagation(); moveSlide(idx, -1); }} className="p-0.5 hover:text-cyan-300">
                        <ArrowUp className="h-3 w-3" />
                      </button>
                      <button type="button" onClick={(e) => { e.stopPropagation(); moveSlide(idx, 1); }} className="p-0.5 hover:text-cyan-300">
                        <ArrowDown className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </div>

        {/* Slide Preview & Editor */}
        <div className="lg:col-span-9">
          {!activeSlide ? (
            <GlassCard>
              <p className="text-sm text-[var(--text-muted)]">Create or select a presentation to edit slides and export PPTX/PDF.</p>
            </GlassCard>
          ) : (
            <GlassCard className="space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] pb-3">
                <div>
                  <h2 className="text-base font-bold">{detailData?.presentation.title}</h2>
                  <Badge tone="cyan" className="mt-1">Theme: {detailData?.presentation.theme}</Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" loading={saveSlide.isPending} onClick={() => saveSlide.mutate()}>
                    <Save className="h-3.5 w-3.5" /> Save Slide
                  </Button>
                  <Button
                    size="sm"
                    variant="cyan"
                    onClick={() =>
                      apiDownloadBlob(
                        `/presentations/${activeId}/export?format=pptx`,
                        `${detailData?.presentation.title || "deck"}.pptx`
                      ).then(() => toast.success("Native PowerPoint (.pptx) exported"))
                    }
                  >
                    <Download className="h-3.5 w-3.5" /> Export PPTX
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      apiDownloadBlob(
                        `/presentations/${activeId}/export?format=pdf`,
                        `${detailData?.presentation.title || "deck"}.pdf`
                      ).then(() => toast.success("Slide PDF exported"))
                    }
                  >
                    Export PDF
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={async () => {
                      await apiFetch(`/presentations/${activeId}/slides/${activeSlide.id}`, { method: "DELETE" });
                      setActiveSlideIdx(0);
                      refetchDetail();
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {/* 16:9 Live Slide Preview */}
              <div className="aspect-video w-full rounded-2xl border border-violet-500/35 bg-gradient-to-br from-[#0a1024] via-[#10183a] to-[#081326] p-8 flex flex-col justify-between shadow-xl">
                <div>
                  <div className="h-1.5 w-20 rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 mb-5" />
                  <h3 className="text-2xl sm:text-3xl font-bold text-white">{slideTitle}</h3>
                  <ul className="mt-5 space-y-2.5 text-sm sm:text-base text-slate-200">
                    {slideBullets
                      .split("\n")
                      .filter(Boolean)
                      .map((b, i) => (
                        <li key={i} className="flex items-start gap-2.5">
                          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                          <span>{b}</span>
                        </li>
                      ))}
                  </ul>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>UNIFORGE AI Presentation Studio</span>
                  <span>
                    Slide {activeSlideIdx + 1} / {slides.length}
                  </span>
                </div>
              </div>

              {/* Slide Controls */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-[var(--text-secondary)]">Slide Heading</label>
                  <Input value={slideTitle} onChange={(e) => setSlideTitle(e.target.value)} />
                  <label className="block text-xs font-medium text-[var(--text-secondary)]">
                    Bullet Points (one per line)
                  </label>
                  <Textarea rows={5} value={slideBullets} onChange={(e) => setSlideBullets(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-[var(--text-secondary)]">
                    Speaker Notes (exported natively into PowerPoint notes)
                  </label>
                  <Textarea rows={8} value={slideNotes} onChange={(e) => setSlideNotes(e.target.value)} />
                </div>
              </div>
            </GlassCard>
          )}
        </div>
      </div>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Academic Presentation">
        <div className="space-y-3">
          <Input placeholder="Deck Title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
          <Select value={newTheme} onChange={(e) => setNewTheme(e.target.value)}>
            <option value="academic_navy">Academic Navy (Dark)</option>
            <option value="violet_modern">Violet Modern</option>
            <option value="ieee_slate">IEEE Slate</option>
            <option value="minimal_light">Minimal Light</option>
          </Select>
          <Select value={sourceDocId} onChange={(e) => setSourceDocId(e.target.value)}>
            <option value="">Optional: Generate from existing Document...</option>
            {(docsData?.documents || []).map((d) => (
              <option key={d.id} value={d.id}>
                Document: {d.title}
              </option>
            ))}
          </Select>
          <Textarea
            rows={4}
            placeholder="Or paste topic outline / markdown headings / lecture notes..."
            value={sourcePrompt}
            onChange={(e) => setSourcePrompt(e.target.value)}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={newTitle.trim().length < 2} loading={createDeck.isPending} onClick={() => createDeck.mutate()}>
              Generate Slide Deck
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
