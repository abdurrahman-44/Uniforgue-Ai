"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BookMarked,
  Calendar,
  CheckCircle2,
  GraduationCap,
  Layers,
  Plus,
  RotateCcw,
  Upload,
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
  Textarea,
} from "@/components/ui/primitives";

interface StudyMaterial {
  id: string;
  subject: string;
  title: string;
  summary: string;
  content_markdown: string;
  revision_schedule: { session: number; scheduled_date: string; focus: string; completed: boolean }[];
  mastery_percent: number;
}

interface FlashcardItem {
  id: string;
  front: string;
  back: string;
  hint: string | null;
  confidence_level: number;
  times_reviewed: number;
}

interface QuizItem {
  id: string;
  subject: string;
  title: string;
  quiz_type: string;
  questions_json: {
    id: string;
    type: string;
    prompt: string;
    options?: string[];
    explanation: string;
  }[];
}

export default function LearningStudioPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"notes" | "flashcards" | "quizzes">("notes");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedMatId, setSelectedMatId] = useState<string | null>(null);
  const [flippedId, setFlippedId] = useState<string | null>(null);

  const [subject, setSubject] = useState("");
  const [title, setTitle] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [uploadedAssetId, setUploadedAssetId] = useState<string | null>(null);

  const [activeQuizId, setActiveQuizId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [gradeResult, setGradeResult] = useState<{
    score: number;
    correct_count: number;
    total_questions: number;
    feedback: { question_id: string; is_correct: boolean; correct_answer: string; explanation: string }[];
  } | null>(null);

  const { data: matData } = useQuery({
    queryKey: ["study-materials"],
    queryFn: () => apiFetch<{ materials: StudyMaterial[] }>("/learning/materials"),
  });

  const activeMat =
    matData?.materials.find((m) => m.id === selectedMatId) || matData?.materials?.[0] || null;

  const { data: cardsData, refetch: refetchCards } = useQuery({
    queryKey: ["flashcards", activeMat?.id],
    queryFn: () =>
      apiFetch<{ flashcards: FlashcardItem[] }>(`/learning/materials/${activeMat?.id}/flashcards`),
    enabled: Boolean(activeMat?.id),
  });

  const { data: quizData, refetch: refetchQuizzes } = useQuery({
    queryKey: ["quizzes"],
    queryFn: () =>
      apiFetch<{
        quizzes: QuizItem[];
        recent_attempts: { id: string; quiz_id: string; score: number; correct_count: number; total_questions: number }[];
      }>("/learning/quizzes"),
  });

  const activeQuiz =
    quizData?.quizzes.find((q) => q.id === activeQuizId) || quizData?.quizzes?.[0] || null;

  const createMaterial = useMutation({
    mutationFn: () =>
      apiFetch("/learning/materials", {
        method: "POST",
        body: JSON.stringify({
          subject,
          title,
          source_text: sourceText,
          source_asset_id: uploadedAssetId,
          auto_generate_flashcards: true,
          auto_generate_quiz: true,
        }),
      }),
    onSuccess: () => {
      toast.success("Study pack created with summary, flashcards, quiz & revision schedule!");
      setCreateOpen(false);
      setSubject("");
      setTitle("");
      setSourceText("");
      setUploadedAssetId(null);
      qc.invalidateQueries({ queryKey: ["study-materials"] });
      refetchQuizzes();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const submitQuiz = useMutation({
    mutationFn: () =>
      apiFetch<{ attempt: NonNullable<typeof gradeResult> }>(
        `/learning/quizzes/${activeQuiz?.id}/attempt`,
        {
          method: "POST",
          body: JSON.stringify({ answers }),
        }
      ),
    onSuccess: (res) => {
      setGradeResult(res.attempt);
      toast.success(`Quiz graded: ${res.attempt.score}%`);
      qc.invalidateQueries({ queryKey: ["study-materials"] });
      refetchQuizzes();
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Learning & Exam Studio"
        subtitle="Summarize lecture PDFs, master concepts with spaced-repetition flashcards, take auto-graded quizzes with explanations, and follow revision schedules."
        badge="Module I"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> New Study Pack (PDF / Notes)
          </Button>
        }
      />

      {/* Mode Tabs */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "notes", label: "Lecture Notes & Schedule", icon: BookMarked },
          { id: "flashcards", label: `Flashcards (${cardsData?.flashcards?.length || 0})`, icon: Layers },
          { id: "quizzes", label: `Practice Quizzes & Exams (${quizData?.quizzes?.length || 0})`, icon: GraduationCap },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <Button
              key={t.id}
              size="sm"
              variant={tab === t.id ? "primary" : "secondary"}
              onClick={() => setTab(t.id as typeof tab)}
            >
              <Icon className="h-3.5 w-3.5" /> {t.label}
            </Button>
          );
        })}
      </div>

      {tab === "notes" && (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-2.5 lg:col-span-4">
            {(matData?.materials || []).length === 0 ? (
              <EmptyState
                icon={<GraduationCap className="h-6 w-6" />}
                title="No study materials yet"
                description="Upload a lecture PDF or paste chapter notes to generate summaries, flashcards, and practice tests."
                action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create Study Pack</Button>}
              />
            ) : (
              matData?.materials.map((m) => (
                <div
                  key={m.id}
                  onClick={() => setSelectedMatId(m.id)}
                  className={`cursor-pointer rounded-xl border p-4 ${
                    activeMat?.id === m.id
                      ? "border-violet-500/60 bg-violet-600/15"
                      : "border-[var(--border-subtle)] bg-black/20"
                  }`}
                >
                  <div className="flex justify-between gap-2">
                    <Badge tone="cyan">{m.subject}</Badge>
                    <Badge tone="emerald">{m.mastery_percent}% mastery</Badge>
                  </div>
                  <p className="mt-2 font-semibold text-sm">{m.title}</p>
                </div>
              ))
            )}
          </div>

          <div className="space-y-5 lg:col-span-8">
            {activeMat ? (
              <>
                <GlassCard className="space-y-3">
                  <h2 className="text-lg font-bold">{activeMat.title}</h2>
                  <p className="text-xs leading-relaxed text-[var(--text-secondary)]">{activeMat.summary}</p>
                  <pre className="whitespace-pre-wrap rounded-xl bg-black/30 p-4 font-sans text-xs text-[var(--text-secondary)]">
                    {activeMat.content_markdown}
                  </pre>
                </GlassCard>

                <GlassCard className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-cyan-400" />
                    <h3 className="text-sm font-semibold">Spaced-Repetition Revision Schedule</h3>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(activeMat.revision_schedule || []).map((s) => (
                      <div key={s.session} className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-3 text-xs">
                        <p className="font-semibold text-cyan-300">Session {s.session} • {s.scheduled_date}</p>
                        <p className="mt-1 text-[var(--text-secondary)]">{s.focus}</p>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              </>
            ) : (
              <GlassCard>
                <p className="text-sm text-[var(--text-muted)]">Select or create a study pack to view notes and revision plan.</p>
              </GlassCard>
            )}
          </div>
        </div>
      )}

      {tab === "flashcards" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(cardsData?.flashcards || []).length === 0 ? (
            <div className="col-span-full">
              <EmptyState
                icon={<Layers className="h-6 w-6" />}
                title="No flashcards for this subject"
                description="Create a Study Pack with lecture notes or a PDF to auto-generate flashcards."
              />
            </div>
          ) : (
            cardsData?.flashcards.map((c) => {
              const flipped = flippedId === c.id;
              return (
                <GlassCard key={c.id} className="flex flex-col justify-between space-y-4">
                  <div
                    onClick={() => setFlippedId(flipped ? null : c.id)}
                    className="cursor-pointer min-h-[120px]"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <Badge tone={flipped ? "emerald" : "violet"}>{flipped ? "Answer" : "Question"}</Badge>
                      <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-muted)]">
                        <RotateCcw className="h-3 w-3" /> Tap to flip
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed">{flipped ? c.back : c.front}</p>
                  </div>
                  <div className="border-t border-[var(--border-subtle)] pt-3">
                    <p className="mb-1.5 text-[11px] text-[var(--text-muted)]">
                      Rate recall confidence (reviewed {c.times_reviewed}x):
                    </p>
                    <div className="flex gap-1.5">
                      {[1, 2, 3, 4, 5].map((lvl) => (
                        <button
                          key={lvl}
                          onClick={async () => {
                            await apiFetch(`/learning/flashcards/${c.id}/review`, {
                              method: "POST",
                              body: JSON.stringify({ confidence_level: lvl }),
                            });
                            toast.success(`Scheduled next spaced review (confidence ${lvl}/5)`);
                            refetchCards();
                          }}
                          className={`flex-1 rounded-lg py-1 text-xs font-semibold ${
                            c.confidence_level === lvl
                              ? "bg-violet-600 text-white"
                              : "bg-white/5 hover:bg-white/15"
                          }`}
                        >
                          {lvl}
                        </button>
                      ))}
                    </div>
                  </div>
                </GlassCard>
              );
            })
          )}
        </div>
      )}

      {tab === "quizzes" && (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-2.5 lg:col-span-4">
            {(quizData?.quizzes || []).map((q) => (
              <div
                key={q.id}
                onClick={() => {
                  setActiveQuizId(q.id);
                  setAnswers({});
                  setGradeResult(null);
                }}
                className={`cursor-pointer rounded-xl border p-3.5 ${
                  activeQuiz?.id === q.id
                    ? "border-violet-500/60 bg-violet-600/15"
                    : "border-[var(--border-subtle)] bg-black/20"
                }`}
              >
                <p className="text-sm font-semibold">{q.title}</p>
                <p className="text-xs text-[var(--text-muted)]">
                  {q.subject} • {q.questions_json.length} questions
                </p>
              </div>
            ))}
          </div>

          <div className="lg:col-span-8">
            {!activeQuiz ? (
              <GlassCard>
                <p className="text-sm text-[var(--text-muted)]">Create a Study Pack to generate an interactive practice quiz.</p>
              </GlassCard>
            ) : (
              <GlassCard className="space-y-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold">{activeQuiz.title}</h2>
                  {gradeResult && (
                    <Badge tone="emerald">
                      Score: {gradeResult.score}% ({gradeResult.correct_count}/{gradeResult.total_questions})
                    </Badge>
                  )}
                </div>

                <div className="space-y-4">
                  {activeQuiz.questions_json.map((q, idx) => {
                    const fb = gradeResult?.feedback.find((f) => f.question_id === q.id);
                    return (
                      <div key={q.id} className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-4 space-y-2.5">
                        <p className="text-sm font-medium">
                          {idx + 1}. {q.prompt}
                        </p>
                        {q.options ? (
                          <div className="grid gap-2 sm:grid-cols-2">
                            {q.options.map((opt, optIdx) => (
                              <label
                                key={optIdx}
                                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                                  answers[q.id] === optIdx
                                    ? "border-cyan-500 bg-cyan-500/15"
                                    : "border-[var(--border-subtle)] bg-black/20"
                                }`}
                              >
                                <input
                                  type="radio"
                                  name={q.id}
                                  checked={answers[q.id] === optIdx}
                                  onChange={() => setAnswers((prev) => ({ ...prev, [q.id]: optIdx }))}
                                />
                                <span>{opt}</span>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <Input
                            placeholder="Type your answer..."
                            value={String(answers[q.id] || "")}
                            onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                          />
                        )}
                        {fb && (
                          <div
                            className={`rounded-lg p-2.5 text-xs ${
                              fb.is_correct ? "bg-emerald-500/15 text-emerald-200" : "bg-rose-500/15 text-rose-200"
                            }`}
                          >
                            <p className="font-semibold">
                              {fb.is_correct ? "Correct!" : `Correct answer: ${fb.correct_answer}`}
                            </p>
                            <p className="mt-0.5 opacity-90">{fb.explanation}</p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                <Button loading={submitQuiz.isPending} onClick={() => submitQuiz.mutate()}>
                  <CheckCircle2 className="h-4 w-4" /> Submit & Grade Quiz
                </Button>
              </GlassCard>
            )}
          </div>
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Study Pack">
        <div className="space-y-3">
          <Input placeholder="Subject (e.g., Operating Systems)" value={subject} onChange={(e) => setSubject(e.target.value)} />
          <Input placeholder="Chapter / Lecture Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-cyan-500/40 bg-cyan-500/5 py-3 text-xs text-cyan-300">
            <Upload className="h-4 w-4" />
            {uploadedAssetId ? "PDF Uploaded & Ready!" : "Optional: Upload Lecture PDF / DOCX"}
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const fd = new FormData();
                fd.append("file", file);
                try {
                  const res = await apiFetch<{ file: { id: string } }>("/files/upload", { method: "POST", body: fd });
                  setUploadedAssetId(res.file.id);
                  toast.success("Lecture file extracted");
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : "Upload failed");
                }
              }}
            />
          </label>
          <Textarea
            rows={5}
            placeholder="Paste lecture notes or textbook excerpts..."
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              disabled={subject.trim().length < 2 || title.trim().length < 2}
              loading={createMaterial.isPending}
              onClick={() => createMaterial.mutate()}
            >
              Generate Notes, Flashcards & Quiz
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
