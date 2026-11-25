"""AI Image Generation provider adapters + deterministic local image processing."""

from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from PIL import Image, ImageEnhance, ImageFilter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProviderUnavailableError
from app.core.security import decrypt_secret
from app.models.entities import ProviderConfig


@dataclass
class ImageGenerationRequest:
    prompt: str
    style: str = "academic_illustration"
    aspect_ratio: str = "1:1"
    resolution: str = "1024x1024"
    academic_visual_mode: bool = False
    reference_image_bytes: bytes | None = None
    operation: str = "text_to_image"  # text_to_image | image_to_image | variation


@dataclass
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    provider: str
    model: str
    width: int
    height: int
    enhanced_prompt: str


ACADEMIC_STYLE_PROMPTS: dict[str, str] = {
    "academic_illustration": "clean peer-reviewed textbook illustration, crisp vector lines, high contrast labels",
    "poster": "university research conference poster graphic, structured hierarchy, modern minimalist typography layout",
    "infographic": "educational schematic infographic diagram, balanced whitespace, color-blind safe palette",
    "technical_visual": "technical engineering cutaway schematic, precise proportions, dark navy & cyan studio lighting",
    "photorealistic": "high-resolution realistic editorial photography, natural lighting",
    "3d_render": "clean scientific 3D visualization, subtle studio lighting, neutral background",
}

ASPECT_TO_SIZE: dict[str, str] = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3": "1024x1024",
}


def enhance_academic_prompt(prompt: str, style: str, academic_visual_mode: bool) -> str:
    style_hint = ACADEMIC_STYLE_PROMPTS.get(style, "")
    parts = [prompt.strip()]
    if academic_visual_mode:
        parts.append(
            "Academic educational visualization: accurate proportions, uncluttered background, clear visual hierarchy"
        )
    if style_hint:
        parts.append(style_hint)
    return ". ".join(p for p in parts if p)


class BaseImageProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    async def generate(self, req: ImageGenerationRequest) -> ImageGenerationResult:
        ...

    @abstractmethod
    async def status(self) -> dict[str, Any]:
        ...


class OpenAIImageProvider(BaseImageProvider):
    name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-image-1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, req: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.is_configured():
            raise ProviderUnavailableError(self.name, "OpenAI Image API key is not configured.")
        prompt = enhance_academic_prompt(req.prompt, req.style, req.academic_visual_mode)
        size = ASPECT_TO_SIZE.get(req.aspect_ratio, "1024x1024")
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if req.reference_image_bytes and req.operation in {"image_to_image", "variation"}:
                    files = {"image": ("reference.png", req.reference_image_bytes, "image/png")}
                    data = {"model": self.model, "prompt": prompt, "size": size}
                    resp = await client.post(
                        f"{self.base_url}/images/edits", headers=headers, files=files, data=data
                    )
                else:
                    payload = {
                        "model": self.model,
                        "prompt": prompt,
                        "size": size,
                        "response_format": "b64_json",
                    }
                    resp = await client.post(
                        f"{self.base_url}/images/generations", headers=headers, json=payload
                    )
            resp.raise_for_status()
            item = resp.json()["data"][0]
            if "b64_json" in item:
                img_bytes = base64.b64decode(item["b64_json"])
            elif "url" in item:
                async with httpx.AsyncClient(timeout=60.0) as dl:
                    img_bytes = (await dl.get(item["url"])).content
            else:
                raise ProviderUnavailableError(self.name, "Image provider returned an unexpected payload.")
            img = Image.open(io.BytesIO(img_bytes))
            return ImageGenerationResult(
                image_bytes=img_bytes,
                mime_type="image/png",
                provider=self.name,
                model=self.model,
                width=img.width,
                height=img.height,
                enhanced_prompt=prompt,
            )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(self.name, f"OpenAI image request failed: {type(exc).__name__}")

    async def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "configured": self.is_configured(),
            "supports": ["text_to_image", "image_to_image", "variation"],
        }


class HuggingFaceImageProvider(BaseImageProvider):
    """Connects to Hugging Face Serverless Inference API for open-source image models (e.g. FLUX/SDXL)."""

    name = "huggingface"

    def __init__(
        self,
        api_key: str,
        model: str = "black-forest-labs/FLUX.1-schnell",
        base_url: str = "https://router.huggingface.co/hf-inference/models",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://router.huggingface.co/hf-inference/models").rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    async def generate(self, req: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.is_configured():
            raise ProviderUnavailableError(self.name, "Hugging Face API token is not configured.")
        prompt = enhance_academic_prompt(req.prompt, req.style, req.academic_visual_mode)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/{self.model}", headers=headers, json={"inputs": prompt}
                )
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            png_buf = io.BytesIO()
            img.save(png_buf, format="PNG")
            return ImageGenerationResult(
                image_bytes=png_buf.getvalue(),
                mime_type="image/png",
                provider=self.name,
                model=self.model,
                width=img.width,
                height=img.height,
                enhanced_prompt=prompt,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:220] if exc.response is not None else ""
            raise ProviderUnavailableError(
                self.name,
                f"Hugging Face API error (HTTP {exc.response.status_code}): {detail or 'Check your Hugging Face token and Inference Providers permission.'}",
            )
        except Exception as exc:
            raise ProviderUnavailableError(self.name, f"Hugging Face image generation failed: {type(exc).__name__}")

    async def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "configured": self.is_configured(),
            "supports": ["text_to_image"],
        }


class PollinationsImageProvider(BaseImageProvider):
    """Free open-access Pollinations.ai FLUX image generation adapter (optional API key for higher limits)."""

    name = "pollinations"

    def __init__(
        self,
        api_key: str = "",
        model: str = "flux",
        base_url: str = "https://image.pollinations.ai/prompt",
    ) -> None:
        self.api_key = api_key
        self.model = model or "flux"
        self.base_url = (base_url or "https://image.pollinations.ai/prompt").rstrip("/")

    def is_configured(self) -> bool:
        return True

    async def generate(self, req: ImageGenerationRequest) -> ImageGenerationResult:
        from urllib.parse import quote

        prompt = enhance_academic_prompt(req.prompt, req.style, req.academic_visual_mode)
        size = ASPECT_TO_SIZE.get(req.aspect_ratio, "1024x1024")
        w_str, h_str = size.split("x")
        encoded = quote(prompt[:900], safe="")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        params = {"model": self.model, "width": w_str, "height": h_str, "nologo": "true"}

        endpoints = [
            f"{self.base_url}/{encoded}",
            f"https://gen.pollinations.ai/image/{encoded}",
            f"https://image.pollinations.ai/prompt/{encoded}",
        ]
        seen: set[str] = set()
        last_err = "Request failed"
        for url in endpoints:
            if url in seen:
                continue
            seen.add(url)
            try:
                async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                img = Image.open(io.BytesIO(resp.content))
                png_buf = io.BytesIO()
                img.save(png_buf, format="PNG")
                return ImageGenerationResult(
                    image_bytes=png_buf.getvalue(),
                    mime_type="image/png",
                    provider=self.name,
                    model=self.model,
                    width=img.width,
                    height=img.height,
                    enhanced_prompt=prompt,
                )
            except Exception as exc:
                last_err = type(exc).__name__
        raise ProviderUnavailableError(
            self.name,
            f"Pollinations image service temporarily unreachable ({last_err}). Try again or configure Hugging Face / OpenAI in Admin Console.",
        )

    async def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "endpoint": self.base_url,
            "configured": True,
            "supports": ["text_to_image"],
        }


class LocalDiffusersWebhookProvider(BaseImageProvider):
    """Self-hosted open-source Automatic1111 / ComfyUI / Diffusers HTTP integration."""

    name = "comfyui"

    def __init__(self, base_url: str, model: str = "sdxl-local") -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def generate(self, req: ImageGenerationRequest) -> ImageGenerationResult:
        if not self.is_configured():
            raise ProviderUnavailableError(self.name, "Self-hosted image endpoint URL is not configured.")
        prompt = enhance_academic_prompt(req.prompt, req.style, req.academic_visual_mode)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img",
                    json={"prompt": prompt, "steps": 24, "width": 1024, "height": 1024},
                )
            resp.raise_for_status()
            b64 = resp.json()["images"][0]
            img_bytes = base64.b64decode(b64)
            img = Image.open(io.BytesIO(img_bytes))
            return ImageGenerationResult(
                image_bytes=img_bytes,
                mime_type="image/png",
                provider=self.name,
                model=self.model,
                width=img.width,
                height=img.height,
                enhanced_prompt=prompt,
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                self.name, f"Self-hosted image server unreachable at {self.base_url}: {type(exc).__name__}"
            )

    async def status(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "endpoint": self.base_url,
            "configured": self.is_configured(),
            "supports": ["text_to_image"],
        }


def process_local_image_operation(
    image_bytes: bytes,
    operation: str,
    scale_factor: float = 2.0,
    background_hex: str | None = None,
) -> tuple[bytes, int, int]:
    """Deterministic Pillow image transformations (upscale, enhance, chroma-key bg removal/replace).

    Never pretends to perform generative AI; performs genuine pixel operations on user-owned images.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    if operation == "upscale":
        factor = max(1.25, min(scale_factor, 4.0))
        new_size = (min(int(img.width * factor), 4096), min(int(img.height * factor), 4096))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
    elif operation == "enhance":
        rgb = img.convert("RGB")
        rgb = ImageEnhance.Contrast(rgb).enhance(1.15)
        rgb = ImageEnhance.Sharpness(rgb).enhance(1.25)
        rgb = ImageEnhance.Color(rgb).enhance(1.1)
        img = rgb.convert("RGBA")
    elif operation in {"remove_background", "replace_background"}:
        # Border-color chroma threshold background extraction for diagrams/illustrations
        pixels = img.load()
        w, h = img.size
        corners = [pixels[0, 0], pixels[w - 1, 0], pixels[0, h - 1], pixels[w - 1, h - 1]]
        bg_r = sum(c[0] for c in corners) // 4
        bg_g = sum(c[1] for c in corners) // 4
        bg_b = sum(c[2] for c in corners) // 4
        replace_rgb = None
        if operation == "replace_background" and background_hex:
            hx = background_hex.lstrip("#")
            if len(hx) == 6:
                replace_rgb = (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), 255)
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                dist = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
                if dist < 55:
                    pixels[x, y] = replace_rgb if replace_rgb else (0, 0, 0, 0)
    else:
        raise ValueError(f"Unsupported local image operation: {operation}")

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue(), img.width, img.height


class ImageStudioProviderService:
    async def resolve_provider(self, db: AsyncSession | None = None) -> BaseImageProvider | None:
        if db is not None:
            res = await db.execute(
                select(ProviderConfig)
                .where(ProviderConfig.category == "image", ProviderConfig.is_enabled.is_(True))
                .order_by(ProviderConfig.is_primary.desc(), ProviderConfig.updated_at.desc())
            )
            for cfg in res.scalars().all():
                key = decrypt_secret(cfg.encrypted_api_key or "") if cfg.encrypted_api_key else ""
                if cfg.name == "pollinations":
                    return PollinationsImageProvider(
                        key,
                        cfg.model_identifier or "flux",
                        cfg.endpoint_url or "https://image.pollinations.ai/prompt",
                    )
                if cfg.name == "openai" and key:
                    return OpenAIImageProvider(
                        key, cfg.endpoint_url or "https://api.openai.com/v1", cfg.model_identifier or "gpt-image-1"
                    )
                if cfg.name == "huggingface" and key:
                    return HuggingFaceImageProvider(
                        key,
                        cfg.model_identifier or "black-forest-labs/FLUX.1-schnell",
                        cfg.endpoint_url or "https://router.huggingface.co/hf-inference/models",
                    )
                if cfg.name == "comfyui" and cfg.endpoint_url:
                    return LocalDiffusersWebhookProvider(cfg.endpoint_url, cfg.model_identifier or "sdxl-local")

        if settings.image_provider == "pollinations":
            return PollinationsImageProvider(
                settings.image_api_key,
                settings.image_model or "flux",
                settings.image_base_url or "https://image.pollinations.ai/prompt",
            )
        if settings.image_provider == "openai" and settings.image_api_key:
            return OpenAIImageProvider(
                settings.image_api_key,
                settings.image_base_url or "https://api.openai.com/v1",
                settings.image_model or "gpt-image-1",
            )
        if settings.image_provider == "huggingface" and settings.image_api_key:
            return HuggingFaceImageProvider(
                settings.image_api_key,
                settings.image_model or "black-forest-labs/FLUX.1-schnell",
                settings.image_base_url or "https://router.huggingface.co/hf-inference/models",
            )
        if settings.image_provider == "comfyui" and settings.image_base_url:
            return LocalDiffusersWebhookProvider(settings.image_base_url, settings.image_model or "sdxl-local")
        return None

    async def status(self, db: AsyncSession | None = None) -> dict[str, Any]:
        provider = await self.resolve_provider(db)
        if provider is None:
            return {
                "available": False,
                "active_provider": None,
                "local_edit_tools_available": True,
                "message": (
                    "No generative image provider is currently configured. "
                    "Configure IMAGE_PROVIDER (pollinations, huggingface, openai, or self-hosted comfyui) in .env or Admin Console. "
                    "Local deterministic image tools (upscale, enhance, background removal/replacement) remain available."
                ),
                "supported_providers": ["pollinations", "huggingface", "openai", "comfyui"],
            }
        st = await provider.status()
        return {
            "available": st["configured"],
            "active_provider": provider.name,
            "local_edit_tools_available": True,
            "details": st,
            "supported_providers": ["pollinations", "huggingface", "openai", "comfyui"],
        }


image_provider_service = ImageStudioProviderService()
