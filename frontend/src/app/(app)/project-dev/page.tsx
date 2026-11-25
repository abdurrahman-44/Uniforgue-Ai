"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Boxes, CheckCircle2, FileText, Network } from "lucide-react";
import { apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  GlassCard,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { AcademicProject } from "@/types/api";

const ARTIFACT_TYPES = [
  { id: "proposal", label: "Project Proposal" },
  { id: "srs", label: "IEEE 830 SRS Document" },
  { id: "functional_requirements", label: "Functional Requirements Spec" },
  { id: "non_functional_requirements", label: "Non-Functional Requirements" },
  { id: "system_architecture", label: "System Architecture Blueprint" },
  { id: "database_schema", label: "Normalized Database Schema (3NF)" },
  { id: "test_cases", label: "Testing Documentation & Test Cases" },
  { id: "implementation_report", label: "Implementation Report" },
  { id: "user_manual", label: "End-User Manual" },
  { id: "final_documentation", label: "Final-Year Project Documentation" },
];

export default function ProjectDevStudioPage() {
  const { data: projData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<{ projects: AcademicProject[] }>("/projects"),
  });

  const [projectId, setProjectId] = useState("");
  const [artifactType, setArtifactType] = useState("srs");
  const [domainSummary, setDomainSummary] = useState("");
  const [createDiagrams, setCreateDiagrams] = useState(true);
  const [result, setResult] = useState<{
    document: { id: string; title: string; word_count: number };
    diagrams: { id: string; title: string; diagram_type: string }[];
  } | null>(null);

  const selectedProjectId = projectId || projData?.projects?.[0]?.id || "";

  const generate = useMutation({
    mutationFn: () =>
      apiFetch<{
        document: { id: string; title: string; word_count: number };
        diagrams: { id: string; title: string; diagram_type: string }[];
      }>(`/projects/${selectedProjectId}/generate-artifact`, {
        method: "POST",
        body: JSON.stringify({
          artifact_type: artifactType,
          domain_summary: domainSummary,
          create_diagrams: createDiagrams,
        }),
      }),
    onSuccess: (res) => {
      setResult(res);
      toast.success("Engineering artifact & editable diagram saved to project workspace!");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Project Development Studio"
        subtitle="Generate structured university software engineering documentation (SRS, Database Schema, Architecture, Test Cases) paired with editable UML/ER diagrams."
        badge="Module G"
      />

      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-7 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
              Target Academic Project
            </label>
            {(projData?.projects || []).length === 0 ? (
              <p className="text-xs text-amber-300">
                Create an Academic Project in <Link href="/projects" className="underline">Academic Hub</Link> first.
              </p>
            ) : (
              <Select value={selectedProjectId} onChange={(e) => setProjectId(e.target.value)}>
                {projData?.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} {p.course_code ? `(${p.course_code})` : ""}
                  </option>
                ))}
              </Select>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
              Engineering Deliverable Type
            </label>
            <div className="grid grid-cols-2 gap-2">
              {ARTIFACT_TYPES.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setArtifactType(a.id)}
                  className={`rounded-xl border px-3 py-2 text-left text-xs font-medium transition ${
                    artifactType === a.id
                      ? "border-violet-500 bg-violet-600/20 text-white"
                      : "border-[var(--border-subtle)] bg-black/20 text-[var(--text-secondary)] hover:border-violet-500/40"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
              System Description & Domain Requirements
            </label>
            <Textarea
              rows={5}
              placeholder="Describe your university system (e.g., Smart Bus Booking System with real-time GPS tracking, student seat reservation, QR boarding passes, and admin route scheduling)..."
              value={domainSummary}
              onChange={(e) => setDomainSummary(e.target.value)}
            />
          </div>

          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <input
              type="checkbox"
              checked={createDiagrams}
              onChange={(e) => setCreateDiagrams(e.target.checked)}
            />
            Also create a linked editable diagram (ER / UML Class / Architecture / Flowchart) in Diagram Studio
          </label>

          <Button
            size="lg"
            disabled={!selectedProjectId || domainSummary.trim().length < 5}
            loading={generate.isPending}
            onClick={() => generate.mutate()}
          >
            <Boxes className="h-4 w-4" /> Generate & Save to Project Workspace
          </Button>
        </GlassCard>

        <GlassCard className="lg:col-span-5 space-y-4">
          <h2 className="text-base font-semibold">Generated Deliverables</h2>
          {!result ? (
            <p className="text-xs text-[var(--text-muted)]">
              Generated SRS documents, schemas, test matrices, and linked editable diagrams will appear here and persist inside your project workspace.
            </p>
          ) : (
            <div className="space-y-3">
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                <div className="flex items-center gap-2 text-emerald-300 text-xs font-semibold">
                  <CheckCircle2 className="h-4 w-4" /> Document Saved to Workspace
                </div>
                <p className="mt-1 text-sm font-semibold">{result.document.title}</p>
                <p className="text-xs text-[var(--text-muted)]">{result.document.word_count} words</p>
                <Link href="/documents" className="mt-3 inline-block">
                  <Button size="sm" variant="secondary">
                    <FileText className="h-3.5 w-3.5" /> Edit & Export in Document Studio
                  </Button>
                </Link>
              </div>

              {result.diagrams.map((d) => (
                <div key={d.id} className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4">
                  <Badge tone="cyan">{d.diagram_type}</Badge>
                  <p className="mt-1 text-sm font-semibold">{d.title}</p>
                  <Link href="/diagrams" className="mt-3 inline-block">
                    <Button size="sm" variant="cyan">
                      <Network className="h-3.5 w-3.5" /> Open in Interactive Diagram Studio
                    </Button>
                  </Link>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
