"""AI Video Studio: Generative provider adapters + Real FFmpeg local video assembly.

Clearly distinguishes:
- `storyboard_assembled`: Real MP4 rendered locally using FFmpeg from scenes, slides, subtitles, and images.
- `generative_video`: External generative video model provider (e.g., Runway/Replicate) when configured.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError


def resolve_ffmpeg_binary() -> str | None:
    """Locate system ffmpeg or bundled imageio-ffmpeg binary."""
    if settings.ffmpeg_binary and shutil.which(settings.ffmpeg_binary):
        return shutil.which(settings.ffmpeg_binary)
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def generate_srt_subtitles(scenes: list[dict[str, Any]]) -> str:
    """Build valid SubRip (.srt) subtitle content from storyboard scenes."""
    def _fmt(sec: float) -> str:
        ms = int(round((sec - int(sec)) * 1000))
        total = int(sec)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: list[str] = []
    cursor = 0.0
    for idx, scene in enumerate(scenes, start=1):
        duration = max(1.0, float(scene.get("duration_seconds", 4)))
        caption = (scene.get("narration") or scene.get("title") or f"Scene {idx}").strip()
        lines.append(str(idx))
        lines.append(f"{_fmt(cursor)} --> {_fmt(cursor + duration)}")
        lines.append(caption)
        lines.append("")
        cursor += duration
    return "\n".join(lines)


def _render_scene_frame(
    scene: dict[str, Any],
    scene_index: int,
    total_scenes: int,
    width: int,
    height: int,
    background_image_bytes: bytes | None = None,
) -> bytes:
    """Render a crisp 1080p/720p academic slide/storyboard frame via Pillow."""
    bg_hex = scene.get("background_color") or "#0A1024"
    img = Image.new("RGB", (width, height), color=bg_hex)
    if background_image_bytes:
        try:
            bg = Image.open(io.BytesIO(background_image_bytes)).convert("RGB")
            bg = bg.resize((width, height), Image.Resampling.LANCZOS)
            overlay = Image.new("RGBA", (width, height), (5, 8, 22, 165))
            img = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
        except Exception:
            pass

    draw = ImageDraw.Draw(img)
    # Accent bar
    draw.rectangle([0, 0, width, 10], fill="#7C3AED")
    draw.rectangle([0, height - 6, width, height], fill="#06B6D4")

    try:
        font_title = ImageFont.truetype("arial.ttf", max(28, width // 28))
        font_body = ImageFont.truetype("arial.ttf", max(18, width // 46))
        font_meta = ImageFont.truetype("arial.ttf", max(14, width // 64))
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_meta = ImageFont.load_default()

    margin_x = int(width * 0.08)
    draw.text(
        (margin_x, int(height * 0.08)),
        f"UNIFORGE AI  |  SCENE {scene_index} OF {total_scenes}",
        fill="#22D3EE",
        font=font_meta,
    )

    title = str(scene.get("title") or f"Scene {scene_index}")
    wrapped_title = textwrap.wrap(title, width=38)
    y = int(height * 0.17)
    for line in wrapped_title[:3]:
        draw.text((margin_x, y), line, fill="#F8FAFC", font=font_title)
        y += int(height * 0.08)

    narration = str(scene.get("narration") or scene.get("visual_notes") or "")
    wrapped_body = textwrap.wrap(narration, width=62)
    y = max(y + 24, int(height * 0.42))
    for line in wrapped_body[:8]:
        draw.text((margin_x, y), line, fill="#CBD5E1", font=font_body)
        y += int(height * 0.055)

    # Subtitle strip at bottom
    if narration:
        sub_text = narration[:120] + ("..." if len(narration) > 120 else "")
        bar_y = int(height * 0.85)
        draw.rectangle([margin_x - 16, bar_y - 10, width - margin_x + 16, bar_y + 44], fill="#0F172A")
        draw.text((margin_x, bar_y + 4), sub_text, fill="#E2E8F0", font=font_meta)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


ASPECT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "1:1": (720, 720),
    "4:3": (960, 720),
}


def assemble_storyboard_video_mp4(
    scenes: list[dict[str, Any]],
    aspect_ratio: str = "16:9",
    scene_images: dict[int, bytes] | None = None,
    voiceover_audio_bytes: bytes | None = None,
    voiceover_ext: str = ".mp3",
) -> bytes:
    """Assemble a genuine H.264 + AAC MP4 video from scenes using FFmpeg, optionally muxing voiceover audio."""
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        raise ProviderUnavailableError(
            "local_ffmpeg",
            "FFmpeg binary is not installed on this server. Install ffmpeg or imageio-ffmpeg to render MP4 videos.",
        )
    if not scenes:
        raise ValueError("At least one storyboard scene is required to assemble a video.")

    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1280, 720))
    scene_images = scene_images or {}

    with tempfile.TemporaryDirectory(prefix="uniforge_video_") as tmpdir:
        tmp = Path(tmpdir)
        concat_entries: list[str] = []
        for idx, scene in enumerate(scenes):
            duration = max(1.0, min(float(scene.get("duration_seconds", 3.0)), 30.0))
            frame_bytes = _render_scene_frame(
                scene=scene,
                scene_index=idx + 1,
                total_scenes=len(scenes),
                width=width,
                height=height,
                background_image_bytes=scene_images.get(idx),
            )
            frame_path = tmp / f"scene_{idx:03d}.png"
            frame_path.write_bytes(frame_bytes)
            seg_path = tmp / f"seg_{idx:03d}.mp4"
            cmd = [
                ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                str(frame_path),
                "-t",
                f"{duration:.2f}",
                "-vf",
                f"scale={width}:{height},format=yuv420p",
                "-c:v",
                "libx264",
                "-r",
                "24",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(seg_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg scene render failed: {proc.stderr[-300:]}")
            concat_entries.append(f"file '{seg_path.as_posix()}'")

        concat_file = tmp / "concat.txt"
        concat_file.write_text("\n".join(concat_entries), encoding="utf-8")
        video_only = tmp / "video_only.mp4"
        merge_cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(video_only),
        ]
        proc = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not video_only.exists():
            raise RuntimeError(f"FFmpeg merge failed: {proc.stderr[-300:]}")

        if voiceover_audio_bytes:
            audio_path = tmp / f"voiceover{voiceover_ext}"
            audio_path.write_bytes(voiceover_audio_bytes)
            output_mp4 = tmp / "output_voiced.mp4"
            mux_cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(video_only),
                "-i",
                str(audio_path),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_mp4),
            ]
            mux_proc = subprocess.run(mux_cmd, capture_output=True, text=True, timeout=120)
            if mux_proc.returncode == 0 and output_mp4.exists():
                return output_mp4.read_bytes()

        return video_only.read_bytes()


async def synthesize_openai_tts_voiceover(narration_text: str) -> bytes | None:
    """Optionally synthesize spoken voiceover MP3 via OpenAI TTS when OPENAI_API_KEY is configured."""
    if not settings.openai_api_key or not narration_text.strip():
        return None
    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/audio/speech",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": "gpt-4o-mini-tts", "voice": "alloy", "input": narration_text[:4000]},
            )
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


async def submit_external_generative_video(prompt: str, aspect_ratio: str = "16:9") -> dict[str, Any]:
    """Real adapter for Replicate or Runway external generative video APIs when configured."""
    import httpx

    provider = settings.video_provider
    api_key = settings.video_api_key
    if provider not in {"replicate", "runway"} or not api_key:
        raise ProviderUnavailableError(
            "generative_video",
            "External generative video provider is not configured. Set VIDEO_PROVIDER (runway or replicate) and VIDEO_API_KEY, "
            "or use the FFmpeg Storyboard Assembly workflow which produces real MP4 videos locally.",
        )

    if provider == "replicate":
        base = (settings.video_base_url or "https://api.replicate.com/v1").rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base}/predictions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"input": {"prompt": prompt, "aspect_ratio": aspect_ratio}},
            )
            resp.raise_for_status()
            data = resp.json()
            return {"provider": "replicate", "external_job_id": data.get("id"), "status": data.get("status", "queued")}

    # Runway Gen-3 / Gen-4 API boundary
    base = (settings.video_base_url or "https://api.dev.runwayml.com/v1").rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base}/text_to_video",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Runway-Version": "2024-11-06",
                "Content-Type": "application/json",
            },
            json={"promptText": prompt, "ratio": "1280:720" if aspect_ratio == "16:9" else "720:1280"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {"provider": "runway", "external_job_id": data.get("id"), "status": "queued"}


def trim_video_mp4(video_bytes: bytes, start_seconds: float, end_seconds: float) -> bytes:
    """Trim an existing MP4 video using FFmpeg."""
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        raise ProviderUnavailableError("local_ffmpeg", "FFmpeg binary is not available for video trimming.")
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds.")

    with tempfile.TemporaryDirectory(prefix="uniforge_trim_") as tmpdir:
        tmp = Path(tmpdir)
        in_path = tmp / "in.mp4"
        out_path = tmp / "trimmed.mp4"
        in_path.write_bytes(video_bytes)
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{max(0.0, start_seconds):.2f}",
            "-to",
            f"{end_seconds:.2f}",
            "-i",
            str(in_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"FFmpeg trim failed: {proc.stderr[-300:]}")
        return out_path.read_bytes()


def merge_videos_mp4(video_blobs: list[bytes]) -> bytes:
    """Merge multiple MP4 clips sequentially using FFmpeg."""
    ffmpeg = resolve_ffmpeg_binary()
    if not ffmpeg:
        raise ProviderUnavailableError("local_ffmpeg", "FFmpeg binary is not available for video merging.")
    if len(video_blobs) < 2:
        raise ValueError("At least two video clips are required to merge.")

    with tempfile.TemporaryDirectory(prefix="uniforge_merge_") as tmpdir:
        tmp = Path(tmpdir)
        entries: list[str] = []
        for idx, blob in enumerate(video_blobs):
            raw_path = tmp / f"raw_{idx}.mp4"
            norm_path = tmp / f"norm_{idx}.mp4"
            raw_path.write_bytes(blob)
            norm_cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(raw_path),
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-c:v",
                "libx264",
                "-r",
                "24",
                str(norm_path),
            ]
            proc = subprocess.run(norm_cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg normalization failed: {proc.stderr[-300:]}")
            entries.append(f"file '{norm_path.as_posix()}'")

        concat_file = tmp / "concat.txt"
        concat_file.write_text("\n".join(entries), encoding="utf-8")
        out_path = tmp / "merged.mp4"
        proc = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(out_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"FFmpeg merge failed: {proc.stderr[-300:]}")
        return out_path.read_bytes()


def video_provider_status() -> dict[str, Any]:
    ffmpeg_path = resolve_ffmpeg_binary()
    gen_configured = bool(
        settings.video_provider in {"runway", "replicate"} and settings.video_api_key
    )
    return {
        "generative_video_available": gen_configured,
        "generative_provider": settings.video_provider if gen_configured else None,
        "local_ffmpeg_assembly_available": ffmpeg_path is not None,
        "ffmpeg_binary_detected": bool(ffmpeg_path),
        "mode_distinction": {
            "storyboard_assembled": "Deterministic FFmpeg slide/storyboard MP4 rendering, trimming, merging, and SRT subtitles.",
            "generative_video": "External neural text-to-video / image-to-video API (requires provider API credentials).",
        },
    }
