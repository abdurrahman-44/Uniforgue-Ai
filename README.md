# UNIFORGE AI

**From Academic Ideas to Submission-Ready Work.**

UNIFORGE AI is a 100% free, privacy-first, modular full-stack academic productivity and creation ecosystem designed for university students worldwide.

## Architecture Overview

- **Frontend (`frontend/`)**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v4, Framer Motion, Lucide Icons, TanStack Query, Zustand, React Hook Form + Zod, React Flow (`@xyflow/react`), Mermaid, Three.js.
- **Backend (`backend/`)**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), Alembic migrations, Argon2id password hashing, JWT + HttpOnly cookies + CSRF protection, RBAC, WebSockets, Celery worker, PyMuPDF, python-docx, ReportLab, python-pptx, Pillow, FFmpeg (`imageio-ffmpeg` / system `ffmpeg`).
- **Infrastructure (`infrastructure/`, `docker-compose.yml`)**: PostgreSQL 16 + `pgvector`, Redis, MinIO (S3-compatible object storage), Celery Worker, Prometheus, GitHub Actions CI.

## Implemented Studios (Modules A–L)

| Module | Studio | Key Real Capabilities |
| :--- | :--- | :--- |
| **A** | Student Dashboard | Live DB metrics, global academic search, fair-use bars, task tracker, recent activity |
| **B** | AI Image Studio | Multi-provider adapter (`openai`, `huggingface`, self-hosted `comfyui`), Academic Visual Mode, honest unavailable state, plus real local Pillow upscale/enhance/BG tools |
| **C** | AI Video Studio | Storyboard planner, SRT subtitles, real FFmpeg storyboard & presentation-to-MP4 assembly, trim/merge, honest separation of assembled vs generative video |
| **D** | Academic Document Studio | 10 academic templates, APA 7/IEEE/Harvard/MLA/Chicago profiles, version history + optimistic concurrency, real ReportLab PDF & python-docx DOCX exports, Assignment Requirement Analyzer (PyMuPDF/DOCX extraction) |
| **E** | Presentation Studio | Prompt/Document/PDF/Research-to-deck, slide editor & reordering, native `python-pptx` PPTX (with charts & speaker notes) & PDF export |
| **F** | Research & Citation Studio | Live OpenAlex, Crossref DOI verification & Semantic Scholar search, traceable provenance (`discovered` → `retrieved` → `verified`), zero fabricated citations |
| **G** | Project Dev Studio | One-click IEEE 830 SRS, Database Schema, Architecture & Test Cases paired with linked editable diagrams |
| **H** | Diagram Studio | Interactive React Flow canvas + Mermaid/PlantUML import/edit, undo/redo, persistent graph JSON, SVG/PNG/PDF exports |
| **I** | Learning Studio | PDF/lecture summarization, spaced-repetition flashcards, auto-graded MCQ & short-answer quizzes with explanations, revision schedules |
| **J** | Unified Academic Hub | Workspaces, team collaboration, project hub, strictly isolated per-project AI context selection |
| **K** | Community | Private by default, explicit publishing with CC-BY-4.0/MIT/CC0 licensing, search, ratings, reporting |
| **L** | Administration Console | Strict Admin RBAC, user suspension/roles, Fernet-encrypted provider secrets, job/storage monitoring, moderation & audit trail |

## Quick Start (Local Development)

### 1. Backend
```bash
cd backend
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```
API docs: `http://localhost:8000/api/docs`

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Web app: `http://localhost:3000`

### 3. Production Deployment (Docker Compose)
```bash
cp .env.example .env
# Edit .env with strong SECRET_KEY, POSTGRES_PASSWORD, and optional provider keys
docker compose up --build -d
```
