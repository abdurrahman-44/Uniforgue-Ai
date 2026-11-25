"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Flag, Globe, Lock, Plus, Search, Star, Users } from "lucide-react";
import { apiFetch } from "@/lib/api";
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

interface CommunityPost {
  id: string;
  author_name: string;
  title: string;
  category: string;
  summary: string;
  content_markdown: string;
  tags: string[];
  license_name: string;
  is_published: boolean;
  average_rating: number;
  rating_count: number;
  created_at: string;
}

export default function CommunityPage() {
  const qc = useQueryClient();
  const [mineOnly, setMineOnly] = useState(false);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [reportTarget, setReportTarget] = useState<string | null>(null);
  const [reportReason, setReportReason] = useState("");

  const [title, setTitle] = useState("");
  const [postCat, setPostCat] = useState("template");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");
  const [license, setLicense] = useState("CC-BY-4.0");
  const [publishNow, setPublishNow] = useState(false);

  const { data } = useQuery({
    queryKey: ["community", mineOnly, category, q],
    queryFn: () => {
      const params = new URLSearchParams();
      if (mineOnly) params.set("mine_only", "true");
      if (category) params.set("category", category);
      if (q.trim()) params.set("q", q.trim());
      return apiFetch<{ posts: CommunityPost[] }>(`/community/posts?${params.toString()}`);
    },
  });

  const createPost = useMutation({
    mutationFn: () =>
      apiFetch("/community/posts", {
        method: "POST",
        body: JSON.stringify({
          title,
          category: postCat,
          summary,
          content_markdown: content,
          license_name: license,
          publish_now: publishNow,
        }),
      }),
    onSuccess: () => {
      toast.success(publishNow ? "Published to Community!" : "Saved as private draft");
      setCreateOpen(false);
      setTitle("");
      setSummary("");
      setContent("");
      setPublishNow(false);
      qc.invalidateQueries({ queryKey: ["community"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const ratePost = useMutation({
    mutationFn: ({ id, rating }: { id: string; rating: number }) =>
      apiFetch(`/community/posts/${id}/rate`, {
        method: "POST",
        body: JSON.stringify({ rating }),
      }),
    onSuccess: () => {
      toast.success("Rating recorded");
      qc.invalidateQueries({ queryKey: ["community"] });
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Academic Community & Templates"
        subtitle="Discover peer-shared templates, diagram blueprints, study guides, and university project showcases with clear open licensing."
        badge="Module K • Private by Default"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Share Template / Showcase
          </Button>
        }
      />

      <InfoCallout text="Privacy Guarantee: Your workspace files and drafts remain strictly private until you explicitly choose to publish them to the Community with a license." />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--text-muted)]" />
          <Input
            className="pl-9"
            placeholder="Search templates, diagram blueprints, study notes..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-44">
          <option value="">All Categories</option>
          <option value="template">Document Templates</option>
          <option value="diagram">Diagram Templates</option>
          <option value="study_material">Study Materials</option>
          <option value="resource">Academic Resources</option>
          <option value="showcase">Project Showcases</option>
        </Select>
        <Button size="sm" variant={mineOnly ? "primary" : "secondary"} onClick={() => setMineOnly((v) => !v)}>
          {mineOnly ? "Showing My Posts & Drafts" : "View My Drafts"}
        </Button>
      </div>

      {(data?.posts || []).length === 0 ? (
        <EmptyState
          icon={<Users className="h-6 w-6" />}
          title="No community resources match your filter"
          description="Be the first scholar to publish a reusable academic template, diagram blueprint, or project showcase."
          action={<Button size="sm" onClick={() => setCreateOpen(true)}>Create First Post</Button>}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data?.posts.map((p) => (
            <GlassCard key={p.id} hover className="flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Badge tone="cyan">{p.category.replace("_", " ")}</Badge>
                  <Badge tone={p.is_published ? "emerald" : "amber"}>
                    {p.is_published ? <Globe className="h-3 w-3" /> : <Lock className="h-3 w-3" />}
                    {p.is_published ? "Public" : "Private Draft"}
                  </Badge>
                </div>
                <h3 className="mt-2.5 text-base font-bold">{p.title}</h3>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{p.summary}</p>
                <p className="mt-2 text-[11px] text-[var(--text-muted)]">
                  By {p.author_name} • License: {p.license_name}
                </p>
              </div>

              <div className="flex items-center justify-between border-t border-[var(--border-subtle)] pt-3 text-xs">
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      disabled={!p.is_published}
                      onClick={() => ratePost.mutate({ id: p.id, rating: star })}
                      className="text-amber-400 hover:scale-110 transition disabled:opacity-30"
                      title={`Rate ${star}/5`}
                    >
                      <Star className={`h-3.5 w-3.5 ${star <= Math.round(p.average_rating) ? "fill-amber-400" : ""}`} />
                    </button>
                  ))}
                  <span className="ml-1 text-[var(--text-muted)]">
                    {p.average_rating.toFixed(1)} ({p.rating_count})
                  </span>
                </div>

                <div className="flex gap-1.5">
                  {mineOnly && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        await apiFetch(`/community/posts/${p.id}/publish?publish=${!p.is_published}`, {
                          method: "POST",
                        });
                        qc.invalidateQueries({ queryKey: ["community"] });
                        toast.success(p.is_published ? "Unpublished to private draft" : "Published publicly");
                      }}
                    >
                      {p.is_published ? "Unpublish" : "Publish"}
                    </Button>
                  )}
                  <button
                    onClick={() => setReportTarget(p.id)}
                    title="Report content"
                    className="rounded p-1.5 text-[var(--text-muted)] hover:bg-rose-500/15 hover:text-rose-400"
                  >
                    <Flag className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create Community Resource">
        <div className="space-y-3">
          <Input placeholder="Title (e.g., IEEE Final-Year Thesis Template)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <Select value={postCat} onChange={(e) => setPostCat(e.target.value)}>
              <option value="template">Document Template</option>
              <option value="diagram">Diagram Template</option>
              <option value="study_material">Study Material</option>
              <option value="resource">Academic Resource</option>
              <option value="showcase">Project Showcase</option>
            </Select>
            <Select value={license} onChange={(e) => setLicense(e.target.value)}>
              <option value="CC-BY-4.0">CC-BY-4.0 (Attribution)</option>
              <option value="CC0-1.0">CC0-1.0 (Public Domain)</option>
              <option value="MIT">MIT License</option>
              <option value="Apache-2.0">Apache-2.0</option>
              <option value="All-Rights-Reserved">All Rights Reserved</option>
            </Select>
          </div>
          <Textarea rows={2} placeholder="Brief summary..." value={summary} onChange={(e) => setSummary(e.target.value)} />
          <Textarea rows={4} placeholder="Markdown content / instructions..." value={content} onChange={(e) => setContent(e.target.value)} />
          <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <input type="checkbox" checked={publishNow} onChange={(e) => setPublishNow(e.target.checked)} />
            Explicitly publish publicly right now (leave unchecked to keep as a private draft)
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={title.trim().length < 3 || summary.trim().length < 10} loading={createPost.isPending} onClick={() => createPost.mutate()}>
              Save Resource
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(reportTarget)} onClose={() => setReportTarget(null)} title="Report Community Content">
        <div className="space-y-3">
          <Input placeholder="Reason (e.g., Plagiarism, Inappropriate content, Broken link)" value={reportReason} onChange={(e) => setReportReason(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setReportTarget(null)}>Cancel</Button>
            <Button
              variant="danger"
              disabled={reportReason.trim().length < 3}
              onClick={async () => {
                await apiFetch("/community/reports", {
                  method: "POST",
                  body: JSON.stringify({ target_type: "community_post", target_id: reportTarget, reason: reportReason }),
                });
                toast.success("Report submitted to moderation queue");
                setReportReason("");
                setReportTarget(null);
              }}
            >
              Submit Report
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
