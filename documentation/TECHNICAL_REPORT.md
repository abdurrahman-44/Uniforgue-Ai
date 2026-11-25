# UNIFORGE AI — Technical Architecture & Final Acceptance Report

## 1. GPT-6 Astra Integration Verification
- **Confirmed Model Identifiers**: `gpt-6-astra` (standard), `gpt-6.2-astra` (latest flagship).
- **Endpoints**: `https://api.openai.com/v1/chat/completions` and `https://api.openai.com/v1/responses`.
- **Capabilities**: 1,050,000-token context window, 128,000 max output tokens, text+image multimodal inputs, SSE streaming, strict JSON schema structured outputs (`response_format`), and configurable `reasoning_effort` (`low`, `medium`, `high`, `xhigh`, `max`).
- **Fallbacks & Honesty**: Automatic fallback chain (`openai_astra` -> `custom_openai` -> local free `ollama`), plus transparent `503 PROVIDER_UNAVAILABLE` states whenever unconfigured.

## 2. Database Architecture (31 Normalized Tables)
Managed via SQLAlchemy 2.0 Async ORM (`backend/app/models/entities.py`) and Alembic migration `0ce79050c4d2_initial_uniforge_schema.py`:
- **Identity & Security**: `users`, `user_profiles`, `user_settings`, `user_sessions`, `auth_tokens`
- **Workspaces & Projects**: `workspaces`, `workspace_members`, `academic_projects`, `project_context`, `tasks`
- **Documents**: `documents`, `document_versions`
- **Media & Async Jobs**: `media_assets`, `generation_jobs`, `generation_events`
- **Presentations**: `presentations`, `presentation_slides`
- **Diagrams**: `diagrams`
- **Research & Citations**: `research_sources`, `citations`
- **Learning**: `study_materials`, `flashcards`, `quizzes`, `quiz_attempts`
- **Community & Governance**: `templates`, `community_posts`, `reports`, `notifications`, `provider_configs`, `usage_records`, `audit_logs`

## 3. Production Hardening & Security Controls
- **Argon2id** password hashing (`time_cost=3, memory_cost=65536, parallelism=4`).
- **JWT + HttpOnly Cookies + Enforced CSRF Protection**: Cookie-authenticated state-changing requests require a valid HMAC-signed `X-CSRF-Token` header; password resets revoke all existing sessions.
- **Full Auth UI Flows**: `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, plus SMTP TLS email delivery (`backend/app/services/email_service.py`).
- **RBAC & Semantic Project Context Isolation**: Strict `admin` guards on `/api/v1/admin/*`, workspace membership verification, and TF-IDF cosine-similarity ranking scoped exclusively to user-enabled `ProjectContext` entries (`backend/app/services/retrieval_service.py`).
- **Redis Sliding-Window Rate Limiter & Fair-Use Quotas**: Redis sorted-set rate limiting in multi-node production with seamless in-memory fallback (`backend/app/core/rate_limit.py`).
- **Async Job Queue & Polling**: Celery worker tasks (`backend/app/workers/celery_app.py`) and `/api/v1/jobs` status/events/retry endpoints (`backend/app/api/v1/jobs.py`).
- **Rich Document Exports with Embedded Figures**: Live split-pane Markdown/academic preview, debounced autosave, university formatting profiles, and native embedded images + Figure captions in both ReportLab PDF and `python-docx` DOCX exports.
- **Video Studio Production Workflow**: Storyboard planning, scene background images, uploaded MP3/WAV voiceover muxing or optional OpenAI TTS synthesis, SRT subtitles, presentation-to-video, FFmpeg trimming & multi-clip merging, plus Replicate/Runway generative video HTTP adapters.
- **Upload Security**: Extension whitelist, magic-byte validation, SVG XSS sanitization, storage quotas, and HMAC signed download URLs.
- **Encrypted Provider Secrets**: Fernet-encrypted server-side storage in `provider_configs`, masked in Admin API responses, never sent to browsers.

## 4. Features Requiring External Provider Credentials
- **GPT-6 Astra / Cloud LLM**: `OPENAI_API_KEY` (or free local Ollama server / custom OpenAI-compatible key).
- **Generative AI Image Creation**: `IMAGE_PROVIDER` (`huggingface` via `https://router.huggingface.co/hf-inference/models`, `openai`, or self-hosted `comfyui`). Local Pillow upscale/enhance/BG tools work with zero keys.
- **Neural Generative Video**: `VIDEO_PROVIDER` (`replicate` or `runway`) + `VIDEO_API_KEY`. Local FFmpeg storyboard/deck MP4 assembly, audio muxing, trim, merge, and SRT export work with zero keys.
- **SMTP Email**: Optional `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` for live email delivery.
- **Academic Paper Discovery & DOI Verification**: Free public OpenAlex & Crossref APIs require no keys.
