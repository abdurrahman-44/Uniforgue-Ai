"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  CheckCircle2,
  FileText,
  Film,
  GraduationCap,
  Image as ImageIcon,
  Network,
  Presentation,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { AcademicOrbitalCanvas } from "@/components/three/AcademicOrbitalCanvas";
import { Badge, Button, GlassCard } from "@/components/ui/primitives";
import { useAuthStore } from "@/stores/auth-store";

const STUDIOS = [
  {
    icon: FileText,
    title: "Academic Document Studio",
    desc: "APA 7, IEEE, Harvard, MLA & Chicago templates, Assignment Requirement Analyzer, version history, and genuine ReportLab PDF & python-docx exports.",
  },
  {
    icon: BookOpen,
    title: "Research & Citation Studio",
    desc: "Live OpenAlex, Crossref DOI verification & Semantic Scholar search with verified provenance tracking. Zero fabricated citations.",
  },
  {
    icon: Network,
    title: "Interactive Diagram Studio",
    desc: "Editable React Flow canvas + Mermaid & PlantUML for UML, ER, DFD, Mind Maps, and System Architecture with SVG, PNG & PDF export.",
  },
  {
    icon: Presentation,
    title: "Presentation Studio",
    desc: "Transform prompts, documents, PDFs, or research notes into native editable PowerPoint (.pptx) decks with charts & speaker notes.",
  },
  {
    icon: Boxes,
    title: "Project Dev & Unified Hub",
    desc: "Generate IEEE 830 SRS, database schemas, test cases, and connect documents, diagrams, tasks & isolated AI context in one workspace.",
  },
  {
    icon: GraduationCap,
    title: "Learning & Exam Studio",
    desc: "Extract lecture summaries from PDFs, build spaced-repetition flashcards, auto-graded MCQ & short-answer quizzes, and revision schedules.",
  },
  {
    icon: ImageIcon,
    title: "AI Image Studio",
    desc: "Academic Visual Mode, multi-provider adapter architecture, honest provider status, plus real local Pillow upscaling & background tools.",
  },
  {
    icon: Film,
    title: "AI Video & FFmpeg Studio",
    desc: "Plan scripts & storyboards, generate SRT subtitles, and render real MP4 explainers from scenes or slide decks via FFmpeg.",
  },
];

export default function HomePage() {
  const user = useAuthStore((s) => s.user);

  return (
    <div className="min-h-screen uniforge-ambient-bg">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 font-bold text-white shadow-lg shadow-violet-900/40">
            U
          </div>
          <div>
            <span className="text-base font-bold tracking-tight">UNIFORGE AI</span>
            <p className="text-[11px] text-cyan-400">One Platform. Every Academic Creation.</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <Link href="/dashboard">
              <Button>
                Open Workspace <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost">Sign In</Button>
              </Link>
              <Link href="/register">
                <Button>
                  Start Free <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 pb-20 pt-8">
        <div className="grid items-center gap-10 lg:grid-cols-12">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="lg:col-span-7"
          >
            <Badge tone="cyan" className="mb-4">
              <Sparkles className="h-3 w-3" /> 100% Free for University Students Worldwide • No Payment Required
            </Badge>
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl lg:text-6xl">
              From Academic Ideas to{" "}
              <span className="bg-gradient-to-r from-violet-400 via-indigo-300 to-cyan-300 bg-clip-text text-transparent">
                Submission-Ready Work.
              </span>
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--text-secondary)]">
              UNIFORGE AI unifies scholarly research discovery, academic writing, rubric analysis,
              editable technical diagrams, native PPTX decks, FFmpeg video assembly, and exam
              preparation inside a privacy-first ecosystem powered by modular GPT-6 Astra &amp; open-source
              providers.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href={user ? "/dashboard" : "/register"}>
                <Button size="lg">
                  {user ? "Launch Student Dashboard" : "Create Free Student Account"}{" "}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/login">
                <Button size="lg" variant="secondary">
                  Sign In to Existing Workspace
                </Button>
              </Link>
            </div>
            <div className="mt-6 flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" /> Real PDF, DOCX, PPTX &amp; MP4 Exports
              </span>
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-cyan-400" /> Verified DOIs &amp; Isolated Project Context
              </span>
            </div>
          </motion.div>

          <div className="flex justify-center lg:col-span-5">
            <GlassCard className="flex flex-col items-center p-6">
              <AcademicOrbitalCanvas />
              <div className="mt-2 grid w-full grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-xl bg-black/25 p-2.5">
                  <p className="font-bold text-violet-300">12</p>
                  <p className="text-[var(--text-muted)]">Studios</p>
                </div>
                <div className="rounded-xl bg-black/25 p-2.5">
                  <p className="font-bold text-cyan-300">GPT-6 Astra</p>
                  <p className="text-[var(--text-muted)]">+ Ollama Ready</p>
                </div>
                <div className="rounded-xl bg-black/25 p-2.5">
                  <p className="font-bold text-emerald-300">$0</p>
                  <p className="text-[var(--text-muted)]">Forever Free</p>
                </div>
              </div>
            </GlassCard>
          </div>
        </div>

        <section className="mt-16">
          <h2 className="mb-6 text-xl font-bold">Integrated Academic Studios</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STUDIOS.map((studio) => {
              const Icon = studio.icon;
              return (
                <GlassCard key={studio.title} hover>
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/15 text-cyan-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-semibold">{studio.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-muted)]">
                    {studio.desc}
                  </p>
                </GlassCard>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}
