"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Download,
  Image as ImageIcon,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from "lucide-react";
import { API_ORIGIN, apiDownloadBlob, apiFetch, ApiError } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  GlassCard,
  PageHeader,
  ProviderBanner,
  Select,
  Textarea,
} from "@/components/ui/primitives";
import type { MediaAssetItem } from "@/types/api";

export default function ImageStudioPage() {
  const qc = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("academic_illustration");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [academicMode, setAcademicMode] = useState(true);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [bgHex, setBgHex] = useState("#0A1024");

  const { data: statusData } = useQuery({
    queryKey: ["image-status"],
    queryFn: () =>
      apiFetch<{
        available: boolean;
        active_provider: string | null;
        message?: string;
        styles: string[];
      }>("/images/status"),
  });

  const { data: galleryData, refetch: refetchGallery } = useQuery({
    queryKey: ["image-gallery"],
    queryFn: () =>
      apiFetch<{
        images: MediaAssetItem[];
        jobs: { id: string; provider: string; status: string; error_message: string | null }[];
      }>("/images/gallery"),
  });

  const enhancePrompt = useMutation({
    mutationFn: () =>
      apiFetch<{ enhanced_prompt: string }>("/images/enhance-prompt", {
        method: "POST",
        body: JSON.stringify({ prompt, style, academic_visual_mode: academicMode }),
      }),
    onSuccess: (res) => {
      setPrompt(res.enhanced_prompt);
      toast.success("Prompt enhanced for Academic Visual Mode");
    },
  });

  const generateImg = useMutation({
    mutationFn: () =>
      apiFetch("/images/generate", {
        method: "POST",
        body: JSON.stringify({
          prompt,
          style,
          aspect_ratio: aspectRatio,
          academic_visual_mode: academicMode,
          reference_asset_id: selectedAssetId,
          operation: selectedAssetId ? "image_to_image" : "text_to_image",
        }),
      }),
    onSuccess: () => {
      toast.success("Image generated and stored in object storage");
      refetchGallery();
    },
    onError: (e) => {
      toast.error(e instanceof ApiError ? e.message : "Image provider unavailable");
      refetchGallery();
    },
  });

  const processLocal = useMutation({
    mutationFn: (op: string) =>
      apiFetch("/images/process-local", {
        method: "POST",
        body: JSON.stringify({
          asset_id: selectedAssetId,
          operation: op,
          scale_factor: 2.0,
          background_hex: op === "replace_background" ? bgHex : null,
        }),
      }),
    onSuccess: () => {
      toast.success("Local Pillow image processing completed");
      refetchGallery();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleUploadRef = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiFetch<{ file: MediaAssetItem }>("/files/upload", {
        method: "POST",
        body: fd,
      });
      setSelectedAssetId(res.file.id);
      toast.success("Reference image uploaded to gallery");
      refetchGallery();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
    e.target.value = "";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Image Studio"
        subtitle="Academic Visual Mode for educational illustrations, posters & schematics, plus real local Pillow upscaling, enhancement & background tools."
        badge="Module B"
        actions={
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-cyan-600/80 px-3.5 py-2 text-xs font-medium text-white hover:bg-cyan-500">
            <Upload className="h-4 w-4" /> Upload Reference Image
            <input type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden" onChange={handleUploadRef} />
          </label>
        }
      />

      {statusData && (
        <ProviderBanner
          available={statusData.available}
          title={
            statusData.available
              ? `Generative Image Provider Ready: ${statusData.active_provider}`
              : "Generative Image Provider Not Configured (Honest Status)"
          }
          message={
            statusData.message ||
            "Real image provider configured. Assets are stored in object storage and tracked via generation jobs."
          }
        />
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <GlassCard className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold">Generation & Prompt Studio</h2>
            <label className="flex items-center gap-1.5 text-xs text-cyan-300">
              <input
                type="checkbox"
                checked={academicMode}
                onChange={(e) => setAcademicMode(e.target.checked)}
              />
              Academic Visual Mode
            </label>
          </div>

          <Textarea
            rows={4}
            placeholder="Describe an educational illustration, scientific diagram, conference poster visual, or cutaway schematic..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select value={style} onChange={(e) => setStyle(e.target.value)}>
              <option value="academic_illustration">Academic Illustration</option>
              <option value="poster">Conference Poster</option>
              <option value="infographic">Educational Infographic</option>
              <option value="technical_visual">Technical Cutaway</option>
              <option value="3d_render">Scientific 3D Render</option>
              <option value="photorealistic">Editorial Photorealistic</option>
            </Select>
            <Select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
              <option value="1:1">1:1 Square</option>
              <option value="16:9">16:9 Widescreen</option>
              <option value="9:16">9:16 Vertical Poster</option>
              <option value="4:3">4:3 Presentation</option>
            </Select>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={prompt.trim().length < 2}
              loading={enhancePrompt.isPending}
              onClick={() => enhancePrompt.mutate()}
            >
              <Wand2 className="h-3.5 w-3.5" /> Enhance Prompt
            </Button>
            <Button
              size="sm"
              disabled={prompt.trim().length < 3}
              loading={generateImg.isPending}
              onClick={() => generateImg.mutate()}
            >
              <Sparkles className="h-3.5 w-3.5" /> Generate Image
            </Button>
          </div>

          {/* Local Deterministic Image Processing Toolkit */}
          <div className="border-t border-[var(--border-subtle)] pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-cyan-300">
                Local Image Toolkit (Always Free)
              </h3>
              {selectedAssetId && <Badge tone="emerald">Image Selected</Badge>}
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              Select any image from your gallery (or upload one above) to run real server-side Pillow operations:
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" disabled={!selectedAssetId} loading={processLocal.isPending} onClick={() => processLocal.mutate("upscale")}>
                2x Upscale
              </Button>
              <Button size="sm" variant="secondary" disabled={!selectedAssetId} loading={processLocal.isPending} onClick={() => processLocal.mutate("enhance")}>
                Enhance Clarity
              </Button>
              <Button size="sm" variant="secondary" disabled={!selectedAssetId} loading={processLocal.isPending} onClick={() => processLocal.mutate("remove_background")}>
                Remove BG
              </Button>
              <div className="flex items-center gap-1">
                <input type="color" value={bgHex} onChange={(e) => setBgHex(e.target.value)} className="h-7 w-7 rounded bg-transparent" />
                <Button size="sm" variant="secondary" disabled={!selectedAssetId} loading={processLocal.isPending} onClick={() => processLocal.mutate("replace_background")}>
                  Replace BG
                </Button>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Asset Gallery */}
        <GlassCard className="lg:col-span-7 space-y-4">
          <h2 className="text-base font-semibold">Image Asset Gallery ({galleryData?.images?.length || 0})</h2>
          {(galleryData?.images || []).length === 0 ? (
            <EmptyState
              icon={<ImageIcon className="h-6 w-6" />}
              title="No images in your gallery yet"
              description="Upload a reference diagram/photo to test local upscaling & background removal, or configure an image provider for generative visuals."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {galleryData?.images.map((img) => (
                <div
                  key={img.id}
                  onClick={() => setSelectedAssetId(img.id)}
                  className={`cursor-pointer overflow-hidden rounded-xl border transition ${
                    selectedAssetId === img.id
                      ? "border-cyan-400 ring-2 ring-cyan-500/30"
                      : "border-[var(--border-subtle)] bg-black/25"
                  }`}
                >
                  <img
                    src={`${API_ORIGIN}${img.download_url}`}
                    alt={img.filename}
                    className="h-36 w-full object-cover bg-black/40"
                  />
                  <div className="p-2.5 flex items-center justify-between gap-1 text-xs">
                    <span className="truncate">{img.filename}</span>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          apiDownloadBlob(img.download_url, img.filename);
                        }}
                        className="rounded p-1 hover:bg-white/10"
                        title="Download"
                      >
                        <Download className="h-3.5 w-3.5 text-cyan-300" />
                      </button>
                      <button
                        type="button"
                        onClick={async (e) => {
                          e.stopPropagation();
                          await apiFetch(`/files/${img.id}`, { method: "DELETE" });
                          if (selectedAssetId === img.id) setSelectedAssetId(null);
                          qc.invalidateQueries({ queryKey: ["image-gallery"] });
                        }}
                        className="rounded p-1 hover:bg-rose-500/20"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
