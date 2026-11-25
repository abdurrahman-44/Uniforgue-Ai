"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BookOpen,
  BookmarkPlus,
  CheckCircle2,
  Copy,
  ExternalLink,
  Search,
  ShieldCheck,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  InfoCallout,
  Input,
  PageHeader,
  Select,
} from "@/components/ui/primitives";
import type { ResearchSource } from "@/types/api";

export default function ResearchStudioPage() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("all");
  const [doiInput, setDoiInput] = useState("");
  const [citationStyle, setCitationStyle] = useState("APA 7");
  const [discovered, setDiscovered] = useState<ResearchSource[]>([]);
  const [doiResult, setDoiResult] = useState<Record<string, unknown> | null>(null);

  const { data: libraryData } = useQuery({
    queryKey: ["research-sources"],
    queryFn: () => apiFetch<{ sources: ResearchSource[] }>("/research/sources"),
  });

  const { data: citationsData, refetch: refetchCitations } = useQuery({
    queryKey: ["citations", citationStyle],
    queryFn: () =>
      apiFetch<{
        citations: { id: string; claim_text: string; formatted_inline: string; formatted_bibliography: string }[];
        bibliography: string[];
      }>(`/citations?style=${encodeURIComponent(citationStyle)}`),
  });

  const discoverMutation = useMutation({
    mutationFn: () =>
      apiFetch<{ results: ResearchSource[]; provider_errors: Record<string, string> }>(
        `/research/discover?q=${encodeURIComponent(query)}&provider=${provider}`
      ),
    onSuccess: (res) => {
      setDiscovered(res.results);
      if (res.results.length === 0) {
        toast.info("No matching papers returned from public APIs.");
      } else {
        toast.success(`Discovered ${res.results.length} real scholarly records`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const verifyDoiMutation = useMutation({
    mutationFn: () =>
      apiFetch<Record<string, unknown>>(`/research/verify-doi?doi=${encodeURIComponent(doiInput)}`),
    onSuccess: (res) => {
      setDoiResult(res);
      if (res.verified) toast.success("DOI verified in Crossref registry!");
      else toast.warning("DOI was not found in Crossref.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveSource = useMutation({
    mutationFn: (src: ResearchSource) =>
      apiFetch("/research/sources", {
        method: "POST",
        body: JSON.stringify({ ...src, provenance_status: "retrieved" }),
      }),
    onSuccess: () => {
      toast.success("Saved source to your research library");
      qc.invalidateQueries({ queryKey: ["research-sources"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createCitation = useMutation({
    mutationFn: (src: ResearchSource) =>
      apiFetch("/citations", {
        method: "POST",
        body: JSON.stringify({
          source_id: src.id,
          claim_text: `Supporting reference: ${src.title}`,
          citation_style: citationStyle,
        }),
      }),
    onSuccess: () => {
      toast.success(`Citation formatted in ${citationStyle}`);
      refetchCitations();
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research & Citation Studio"
        subtitle="Discover real peer-reviewed literature via OpenAlex, Crossref & Semantic Scholar, validate DOIs, and generate traceable bibliographies."
        badge="Module F • Zero Fabricated Citations"
      />

      <InfoCallout text="Academic Integrity Policy: Every discovered paper comes directly from OpenAlex, Crossref, or Semantic Scholar APIs with explicit provenance tags (discovered → retrieved → verified)." />

      {/* Live Academic Search + DOI Validator */}
      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-8 space-y-4">
          <h2 className="text-base font-semibold">Live Academic Paper Discovery</h2>
          <div className="flex flex-wrap gap-2">
            <Input
              className="flex-1 min-w-[220px]"
              placeholder="Search topic (e.g., distributed consensus raft, federated learning healthcare)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && query.trim().length >= 2 && discoverMutation.mutate()}
            />
            <Select value={provider} onChange={(e) => setProvider(e.target.value)} className="w-40">
              <option value="all">All Free APIs</option>
              <option value="openalex">OpenAlex</option>
              <option value="crossref">Crossref</option>
              <option value="semantic_scholar">Semantic Scholar</option>
            </Select>
            <Button
              loading={discoverMutation.isPending}
              disabled={query.trim().length < 2}
              onClick={() => discoverMutation.mutate()}
            >
              <Search className="h-4 w-4" /> Search Papers
            </Button>
          </div>

          <div className="space-y-3">
            {discovered.map((paper, idx) => (
              <div
                key={`${paper.doi || paper.title}-${idx}`}
                className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="text-sm font-semibold">{paper.title}</p>
                    <p className="mt-0.5 text-xs text-[var(--text-muted)]">
                      {(paper.authors || []).slice(0, 4).join(", ") || "Unknown authors"} •{" "}
                      {paper.year || "n.d."} {paper.venue ? `• ${paper.venue}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge tone="cyan">{paper.source_provider}</Badge>
                    <Button size="sm" variant="secondary" onClick={() => saveSource.mutate(paper)}>
                      <BookmarkPlus className="h-3.5 w-3.5" /> Save
                    </Button>
                  </div>
                </div>
                {paper.abstract && (
                  <p className="mt-2 line-clamp-2 text-xs text-[var(--text-secondary)]">
                    {paper.abstract}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-cyan-400">
                  {paper.doi && <span>DOI: {paper.doi}</span>}
                  {paper.url && (
                    <a href={paper.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
                      Source Record <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Crossref DOI Validator */}
        <GlassCard className="lg:col-span-4 space-y-4">
          <h2 className="text-base font-semibold">Crossref DOI Verification</h2>
          <p className="text-xs text-[var(--text-muted)]">
            Validate any DOI directly against Crossref&apos;s authoritative scholarly registry.
          </p>
          <Input
            placeholder="10.1145/3292500.3330701"
            value={doiInput}
            onChange={(e) => setDoiInput(e.target.value)}
          />
          <Button
            className="w-full"
            variant="cyan"
            disabled={doiInput.trim().length < 5}
            loading={verifyDoiMutation.isPending}
            onClick={() => verifyDoiMutation.mutate()}
          >
            <ShieldCheck className="h-4 w-4" /> Verify DOI Record
          </Button>

          {doiResult && (
            <div className="rounded-xl border border-[var(--border-subtle)] bg-black/25 p-3 text-xs space-y-1">
              <Badge tone={doiResult.verified ? "emerald" : "rose"}>
                {doiResult.verified ? "Verified in Crossref" : "Not Found"}
              </Badge>
              {Boolean(doiResult.title) && <p className="font-semibold mt-1">{String(doiResult.title)}</p>}
              {Boolean(doiResult.venue) && <p className="text-[var(--text-muted)]">{String(doiResult.venue)} ({String(doiResult.year || "n.d.")})</p>}
            </div>
          )}
        </GlassCard>
      </div>

      {/* Saved Source Library & Bibliography */}
      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">
              Saved Research Library ({libraryData?.sources?.length || 0})
            </h2>
            <Select value={citationStyle} onChange={(e) => setCitationStyle(e.target.value)} className="w-32">
              <option value="APA 7">APA 7</option>
              <option value="IEEE">IEEE</option>
              <option value="Harvard">Harvard</option>
              <option value="MLA">MLA</option>
              <option value="Chicago">Chicago</option>
            </Select>
          </div>
          {(libraryData?.sources || []).length === 0 ? (
            <EmptyState
              icon={<BookOpen className="h-6 w-6" />}
              title="Your source library is empty"
              description="Search academic APIs above and save verified sources to generate formatted citations."
            />
          ) : (
            libraryData?.sources.map((s) => (
              <div key={s.id} className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-3.5 text-xs">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-sm">{s.title}</p>
                    <p className="text-[var(--text-muted)]">
                      {s.authors.join(", ")} ({s.year || "n.d."})
                    </p>
                  </div>
                  <Badge tone={s.provenance_status === "verified" ? "emerald" : "amber"}>
                    {s.provenance_status}
                  </Badge>
                </div>
                <div className="mt-2.5 flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" onClick={() => createCitation.mutate(s)}>
                    Generate {citationStyle} Citation
                  </Button>
                  {s.doi && s.provenance_status !== "verified" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await apiFetch(`/research/sources/${s.id}/verify`, { method: "POST" });
                        toast.success("Source DOI verified!");
                        qc.invalidateQueries({ queryKey: ["research-sources"] });
                      }}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Verify DOI
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </GlassCard>

        <GlassCard className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Formatted Bibliography ({citationStyle})</h2>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                navigator.clipboard?.writeText((citationsData?.bibliography || []).join("\n"));
                toast.success("Bibliography copied");
              }}
            >
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
          </div>
          {(citationsData?.citations || []).length === 0 ? (
            <p className="text-xs text-[var(--text-muted)]">
              Click &ldquo;Generate Citation&rdquo; on any saved source to build your bibliography.
            </p>
          ) : (
            <div className="space-y-2.5 text-xs">
              {citationsData?.citations.map((c) => (
                <div key={c.id} className="rounded-xl bg-black/25 p-3">
                  <Badge tone="violet" className="mb-1">{c.formatted_inline}</Badge>
                  <p className="text-[var(--text-secondary)]">{c.formatted_bibliography}</p>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
