"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Send, Sparkles } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import {
  Badge,
  Button,
  GlassCard,
  InfoCallout,
  PageHeader,
  ProviderBanner,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { AcademicProject } from "@/types/api";

interface AIStatusResponse {
  primary_target: string;
  active_provider: string | null;
  available: boolean;
  providers: { provider: string; model: string; endpoint: string; configured: boolean }[];
  prompt_templates: string[];
}

export default function AIAssistantStudioPage() {
  const [prompt, setPrompt] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [projectId, setProjectId] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState("medium");
  const [response, setResponse] = useState<{
    content: string;
    provider: string;
    model: string;
    context_blocks_used: number;
    ai_assisted_notice: string;
  } | null>(null);

  const { data: statusData } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => apiFetch<AIStatusResponse>("/ai/status"),
  });

  const { data: projData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<{ projects: AcademicProject[] }>("/projects"),
  });

  const runAI = useMutation({
    mutationFn: () =>
      apiFetch<NonNullable<typeof response>>("/ai/generate", {
        method: "POST",
        body: JSON.stringify({
          prompt,
          template_name: templateName || null,
          project_id: projectId || null,
          reasoning_effort: reasoningEffort,
        }),
      }),
    onSuccess: (res) => {
      setResponse(res);
      toast.success(`Response generated via ${res.provider} (${res.model})`);
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : "AI provider unavailable");
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="GPT-6 Astra Orchestration Studio"
        subtitle="Project-aware academic reasoning powered by GPT-6 Astra primary adapter with custom OpenAI-compatible and free local Ollama fallbacks."
        badge={statusData?.primary_target || "gpt-6-astra"}
      />

      {statusData && (
        <ProviderBanner
          available={statusData.available}
          title={
            statusData.available
              ? `Active AI Provider: ${statusData.active_provider}`
              : "No External or Local AI Provider Currently Active"
          }
          message={
            statusData.available
              ? "Ready for isolated project-context academic reasoning, structured outlines, and synthesis."
              : "UNIFORGE AI never simulates fake AI outputs. Configure OPENAI_API_KEY (for gpt-6-astra), a custom OpenAI-compatible endpoint in Admin Console, or start local Ollama."
          }
        />
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-7 space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Isolated Project Context</label>
              <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">No project context</option>
                {(projData?.projects || []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Prompt Template</label>
              <Select value={templateName} onChange={(e) => setTemplateName(e.target.value)}>
                <option value="">Free-form Academic Prompt</option>
                {(statusData?.prompt_templates || []).map((tpl) => (
                  <option key={tpl} value={tpl}>
                    {tpl.replace(/_/g, " ")}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--text-secondary)]">Reasoning Effort</label>
              <Select value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="xhigh">Extra High</option>
              </Select>
            </div>
          </div>

          <Textarea
            rows={6}
            placeholder="Ask GPT-6 Astra to critique your methodology, draft an IEEE 830 requirement section, or synthesize ONLY your attached project notes..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />

          <Button
            size="lg"
            disabled={!prompt.trim()}
            loading={runAI.isPending}
            onClick={() => runAI.mutate()}
          >
            <Send className="h-4 w-4" /> Run Academic Orchestration
          </Button>

          {response && (
            <div className="rounded-xl border border-violet-500/35 bg-black/30 p-4 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="cyan">{response.provider} • {response.model}</Badge>
                <Badge tone="slate">{response.context_blocks_used} context blocks injected</Badge>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[var(--text-primary)]">
                {response.content}
              </pre>
              <InfoCallout text={response.ai_assisted_notice} />
            </div>
          )}
        </GlassCard>

        <GlassCard className="lg:col-span-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-cyan-400" />
            <h2 className="text-base font-semibold">Configured Provider Adapters</h2>
          </div>
          <div className="space-y-2.5">
            {(statusData?.providers || []).map((p) => (
              <div key={p.provider} className="rounded-xl border border-[var(--border-subtle)] bg-black/20 p-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{p.provider}</span>
                  <Badge tone={p.configured ? "emerald" : "slate"}>
                    {p.configured ? "Ready" : "Not Configured"}
                  </Badge>
                </div>
                <p className="mt-1 text-[var(--text-muted)]">Model: {p.model}</p>
                <p className="truncate font-mono text-[11px] text-[var(--text-muted)]">{p.endpoint}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
