"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Clapperboard,
  Combine,
  Download,
  Film,
  Mic,
  Plus,
  Scissors,
  Sparkles,
  Subtitles,
  Trash2,
} from "lucide-react";
import { API_ORIGIN, apiDownloadBlob, apiFetch, ApiError } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  InfoCallout,
  Input,
  PageHeader,
  ProviderBanner,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { MediaAssetItem, PresentationItem } from "@/types/api";

interface SceneDraft {
  title: string;
  narration: string;
  visual_notes: string;
  duration_seconds: number;
  background_color: string;
  image_asset_id?: string | null;
}

export default function VideoStudioPage() {
  const qc = useQueryClient();
  const [topic, setTopic] = useState("");
  const [videoTitle, setVideoTitle] = useState("Academic Concept Explainer");
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [voiceoverAssetId, setVoiceoverAssetId] = useState<string | null>(null);
  const [autoTts, setAutoTts] = useState(false);
  const [scenes, setScenes] = useState<SceneDraft[]>([
    {
      title: "1. Introduction",
      narration: "Welcome to this concise university concept briefing.",
      visual_notes: "Title slide with key learning objective",
      duration_seconds: 3,
      background_color: "#0A1024",
    },
    {
      title: "2. Core Mechanism",
      narration: "Break down the underlying methodology step by step.",
      visual_notes: "Structured schematic overlay",
      duration_seconds: 4,
      background_color: "#111936",
    },
  ]);
  const [selectedPresentationId, setSelectedPresentationId] = useState("");
  const [trimAssetId, setTrimAssetId] = useState("");
  const [trimStart, setTrimStart] = useState("0");
  const [trimEnd, setTrimEnd] = useState("3");
  const [mergeIds, setMergeIds] = useState<string[]>([]);

  const { data: statusData } = useQuery({
    queryKey: ["video-status"],
    queryFn: () =>
      apiFetch<{
        generative_video_available: boolean;
        local_ffmpeg_assembly_available: boolean;
        ffmpeg_binary_detected: boolean;
      }>("/videos/status"),
  });

  const { data: libData, refetch: refetchLib } = useQuery({
    queryKey: ["video-library"],
    queryFn: () =>
      apiFetch<{
        videos: MediaAssetItem[];
        jobs: { id: string; job_type: string; status: string; provider: string }[];
      }>("/videos/library"),
  });

  const { data: decksData } = useQuery({
    queryKey: ["presentations"],
    queryFn: () => apiFetch<{ presentations: PresentationItem[] }>("/presentations"),
  });

  const { data: imgData } = useQuery({
    queryKey: ["image-gallery"],
    queryFn: () => apiFetch<{ images: MediaAssetItem[] }>("/images/gallery"),
  });

  const planStoryboard = useMutation({
    mutationFn: () =>
      apiFetch<{ scenes: SceneDraft[] }>("/videos/plan-storyboard", {
        method: "POST",
        body: JSON.stringify({ topic, target_duration_seconds: 25, scene_count: 5 }),
      }),
    onSuccess: (res) => {
      setScenes(res.scenes);
      setVideoTitle(`${topic} — Explainer`);
      toast.success("Storyboard & narration scenes planned!");
    },
  });

  const assembleVideo = useMutation({
    mutationFn: () =>
      apiFetch("/videos/assemble", {
        method: "POST",
        body: JSON.stringify({
          title: videoTitle,
          aspect_ratio: aspectRatio,
          voiceover_asset_id: voiceoverAssetId,
          auto_tts_voiceover: autoTts,
          scenes,
        }),
      }),
    onSuccess: () => {
      toast.success("Real MP4 video rendered via FFmpeg!");
      refetchLib();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deckToVideo = useMutation({
    mutationFn: () =>
      apiFetch("/videos/from-presentation", {
        method: "POST",
        body: JSON.stringify({
          presentation_id: selectedPresentationId,
          seconds_per_slide: 3.5,
          aspect_ratio: aspectRatio,
        }),
      }),
    onSuccess: () => {
      toast.success("Presentation rendered into MP4 video!");
      refetchLib();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const trimVideo = useMutation({
    mutationFn: () =>
      apiFetch("/videos/trim", {
        method: "POST",
        body: JSON.stringify({
          asset_id: trimAssetId,
          start_seconds: Number(trimStart),
          end_seconds: Number(trimEnd),
        }),
      }),
    onSuccess: () => {
      toast.success("Trimmed MP4 clip created with FFmpeg");
      refetchLib();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const mergeClips = useMutation({
    mutationFn: () =>
      apiFetch("/videos/merge", {
        method: "POST",
        body: JSON.stringify({ asset_ids: mergeIds, title: `${videoTitle} Merged` }),
      }),
    onSuccess: () => {
      toast.success("Selected MP4 clips merged with FFmpeg!");
      setMergeIds([]);
      refetchLib();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleVoiceoverUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiFetch<{ file: { id: string } }>("/files/upload", { method: "POST", body: fd });
      setVoiceoverAssetId(res.file.id);
      toast.success(`Voiceover "${file.name}" attached to storyboard render`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Audio upload failed");
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Video & Storyboard Studio"
        subtitle="Plan academic scripts & storyboards, attach voiceover audio or TTS, generate SRT subtitles, convert slides to MP4, and trim/merge clips via FFmpeg."
        badge="Module C • FFmpeg"
      />

      {statusData && (
        <ProviderBanner
          available={statusData.local_ffmpeg_assembly_available}
          title={
            statusData.local_ffmpeg_assembly_available
              ? "FFmpeg Storyboard & Presentation Video Assembly: Ready"
              : "FFmpeg Not Detected on Server"
          }
          message={
            statusData.generative_video_available
              ? "Both local FFmpeg assembly and external generative video adapters are active."
              : "Local FFmpeg storyboard-to-MP4 assembly, voiceover audio muxing, presentation-to-video, trimming & merging are fully active. External neural video adapters (Replicate/Runway) activate automatically when configured."
          }
        />
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-7 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              className="flex-1 min-w-[200px]"
              placeholder="Topic to auto-plan storyboard (e.g., How Neural Backpropagation Works)"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
            <Button
              size="sm"
              variant="secondary"
              disabled={topic.trim().length < 3}
              loading={planStoryboard.isPending}
              onClick={() => planStoryboard.mutate()}
            >
              <Sparkles className="h-3.5 w-3.5" /> Plan Storyboard
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Input
              className="sm:col-span-2"
              placeholder="Video Export Title"
              value={videoTitle}
              onChange={(e) => setVideoTitle(e.target.value)}
            />
            <Select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
              <option value="16:9">16:9 Widescreen</option>
              <option value="9:16">9:16 Vertical</option>
              <option value="1:1">1:1 Square</option>
              <option value="4:3">4:3 Lecture</option>
            </Select>
          </div>

          {/* Voiceover Integration Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border-subtle)] bg-black/20 px-3.5 py-2.5 text-xs">
            <label className="inline-flex cursor-pointer items-center gap-1.5 text-cyan-300 hover:underline">
              <Mic className="h-3.5 w-3.5" />
              {voiceoverAssetId ? "Voiceover Audio Attached ✓" : "Upload Voiceover Track (MP3/WAV)"}
              <input type="file" accept=".mp3,.wav" className="hidden" onChange={handleVoiceoverUpload} />
            </label>
            <label className="flex items-center gap-1.5 text-[var(--text-secondary)]">
              <input type="checkbox" checked={autoTts} onChange={(e) => setAutoTts(e.target.checked)} />
              Auto-synthesize TTS voiceover (when OpenAI key configured)
            </label>
          </div>

          <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
            {scenes.map((sc, idx) => (
              <div key={idx} className="rounded-xl border border-[var(--border-subtle)] bg-black/25 p-3 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Input
                    value={sc.title}
                    onChange={(e) =>
                      setScenes((prev) =>
                        prev.map((item, i) => (i === idx ? { ...item, title: e.target.value } : item))
                      )
                    }
                    className="flex-1 font-semibold"
                  />
                  <Input
                    type="number"
                    min={1}
                    max={30}
                    step={0.5}
                    value={sc.duration_seconds}
                    onChange={(e) =>
                      setScenes((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, duration_seconds: Number(e.target.value) || 2 } : item
                        )
                      )
                    }
                    className="w-20"
                  />
                  <span className="text-xs text-[var(--text-muted)]">sec</span>
                  <button
                    type="button"
                    onClick={() => setScenes((prev) => prev.filter((_, i) => i !== idx))}
                    className="rounded p-1.5 text-rose-400 hover:bg-rose-500/15"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                <Textarea
                  rows={2}
                  value={sc.narration}
                  onChange={(e) =>
                    setScenes((prev) =>
                      prev.map((item, i) => (i === idx ? { ...item, narration: e.target.value } : item))
                    )
                  }
                  placeholder="Scene narration & subtitle text..."
                />
                {(imgData?.images || []).length > 0 && (
                  <Select
                    value={sc.image_asset_id || ""}
                    onChange={(e) =>
                      setScenes((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, image_asset_id: e.target.value || null } : item
                        )
                      )
                    }
                  >
                    <option value="">Default dark navy academic backdrop</option>
                    {imgData?.images.map((im) => (
                      <option key={im.id} value={im.id}>
                        Scene Image: {im.filename}
                      </option>
                    ))}
                  </Select>
                )}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                setScenes((prev) => [
                  ...prev,
                  {
                    title: `${prev.length + 1}. New Scene`,
                    narration: "Explain the next academic milestone.",
                    visual_notes: "",
                    duration_seconds: 3,
                    background_color: "#0A1024",
                  },
                ])
              }
            >
              <Plus className="h-3.5 w-3.5" /> Add Scene
            </Button>
            <Button
              size="sm"
              variant="cyan"
              disabled={scenes.length === 0}
              loading={assembleVideo.isPending}
              onClick={() => assembleVideo.mutate()}
            >
              <Clapperboard className="h-3.5 w-3.5" /> Render Storyboard MP4 (FFmpeg)
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={async () => {
                try {
                  await apiDownloadBlob("/videos/subtitles/srt", "subtitles.srt", {
                    method: "POST",
                    body: JSON.stringify(scenes),
                  });
                } catch (err) {
                  toast.error(err instanceof ApiError ? err.message : "SRT export failed");
                }
              }}
            >
              <Subtitles className="h-3.5 w-3.5" /> Download SRT
            </Button>
          </div>

          {(decksData?.presentations || []).length > 0 && (
            <div className="border-t border-[var(--border-subtle)] pt-4 flex flex-wrap items-center gap-2">
              <Select
                className="flex-1"
                value={selectedPresentationId}
                onChange={(e) => setSelectedPresentationId(e.target.value)}
              >
                <option value="">Convert a Presentation Deck to MP4...</option>
                {decksData?.presentations.map((d) => (
                  <option key={d.id} value={d.id}>
                    Deck: {d.title}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                variant="secondary"
                disabled={!selectedPresentationId}
                loading={deckToVideo.isPending}
                onClick={() => deckToVideo.mutate()}
              >
                Render Deck Video
              </Button>
            </div>
          )}
        </GlassCard>

        <GlassCard className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-base font-semibold">Rendered Videos ({libData?.videos?.length || 0})</h2>
            {mergeIds.length >= 2 && (
              <Button size="sm" loading={mergeClips.isPending} onClick={() => mergeClips.mutate()}>
                <Combine className="h-3.5 w-3.5" /> Merge {mergeIds.length} Clips
              </Button>
            )}
          </div>
          <InfoCallout text="All locally rendered videos are transparently labeled `storyboard_assembled` (FFmpeg). Check 2+ clips below to merge them sequentially." />

          {(libData?.videos || []).length === 0 ? (
            <EmptyState
              icon={<Film className="h-6 w-6" />}
              title="No rendered videos yet"
              description="Click 'Render Storyboard MP4' on the left to assemble a real H.264 MP4 video with FFmpeg."
            />
          ) : (
            <div className="space-y-4">
              {libData?.videos.map((v) => {
                const checked = mergeIds.includes(v.id);
                return (
                  <div key={v.id} className="rounded-xl border border-[var(--border-subtle)] bg-black/25 p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <label className="flex items-center gap-2 truncate text-xs font-semibold cursor-pointer">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) =>
                            setMergeIds((prev) =>
                              e.target.checked ? [...prev, v.id] : prev.filter((id) => id !== v.id)
                            )
                          }
                        />
                        <span className="truncate">{v.filename}</span>
                      </label>
                      <Badge tone="cyan">{String(v.metadata?.video_mode || "video")}</Badge>
                    </div>
                    <video
                      controls
                      className="w-full rounded-lg bg-black"
                      src={`${API_ORIGIN}${v.download_url}`}
                    />
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-[var(--text-muted)]">
                        {(v.size_bytes / 1024).toFixed(1)} KB
                      </span>
                      <div className="flex gap-2">
                        <Button size="sm" variant="ghost" onClick={() => setTrimAssetId(v.id)}>
                          <Scissors className="h-3.5 w-3.5" /> Trim
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => apiDownloadBlob(v.download_url, v.filename)}>
                          <Download className="h-3.5 w-3.5" /> MP4
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={async () => {
                            await apiFetch(`/files/${v.id}`, { method: "DELETE" });
                            qc.invalidateQueries({ queryKey: ["video-library"] });
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {trimAssetId && (
            <div className="rounded-xl border border-violet-500/35 bg-violet-500/10 p-3 space-y-2 text-xs">
              <p className="font-semibold">FFmpeg Trim Selected Clip</p>
              <div className="flex items-center gap-2">
                <Input type="number" value={trimStart} onChange={(e) => setTrimStart(e.target.value)} placeholder="Start (s)" />
                <span>to</span>
                <Input type="number" value={trimEnd} onChange={(e) => setTrimEnd(e.target.value)} placeholder="End (s)" />
                <Button size="sm" loading={trimVideo.isPending} onClick={() => trimVideo.mutate()}>
                  Trim
                </Button>
              </div>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
