"""Complete normalized database schema for UNIFORGE AI (31 tables)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# ==============================================================================
# 1. AUTHENTICATION, IDENTITY, PROFILES, SETTINGS & SESSIONS
# ==============================================================================


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="student", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspension_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    university: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    academic_level: Mapped[str] = mapped_column(String(64), default="undergraduate", nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    theme: Mapped[str] = mapped_column(String(32), default="dark", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_citation_style: Mapped[str] = mapped_column(String(32), default="APA 7", nullable=False)
    ai_context_opt_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    storage_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=524288000, nullable=False)
    university_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped["User"] = relationship(back_populates="settings")


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuthToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "auth_tokens"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_type: Mapped[str] = mapped_column(String(32), nullable=False)  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ==============================================================================
# 2. WORKSPACES, ACADEMIC PROJECTS, CONTEXT & TASKS
# ==============================================================================


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "workspaces"

    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), default="private", nullable=False)
    is_personal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    projects: Mapped[list["AcademicProject"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class WorkspaceMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),)

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="owner", nullable=False)  # owner | editor | viewer

    workspace: Mapped["Workspace"] = relationship(back_populates="members")


class AcademicProject(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "academic_projects"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str] = mapped_column(String(64), default="research", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    citation_style: Mapped[str] = mapped_column(String(32), default="APA 7", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    context_items: Mapped[list["ProjectContext"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectContext(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_context"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)  # document | file | note | research
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    include_in_ai_context: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped["AcademicProject"] = relationship(back_populates="context_items")


class Task(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tasks"

    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="todo", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    project: Mapped["AcademicProject | None"] = relationship(back_populates="tasks")


# ==============================================================================
# 3. DOCUMENTS & VERSIONS (MODULE D)
# ==============================================================================


class Document(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), default="assignment", nullable=False)
    citation_style: Mapped[str] = mapped_column(String(32), default="APA 7", nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sections_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    formatting_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    cover_page: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assignment_requirements: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    sections_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="versions")


# ==============================================================================
# 4. MEDIA ASSETS & ASYNC GENERATION JOBS (MODULES B, C, FILE STORAGE)
# ==============================================================================


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "media_assets"

    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # file | image | video | export | audio
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class GenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_jobs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # ai_text | image | video_gen | video_assemble | export
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["GenerationEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class GenerationEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_events"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    job: Mapped["GenerationJob"] = relationship(back_populates="events")


# ==============================================================================
# 5. PRESENTATIONS & SLIDES (MODULE E)
# ==============================================================================


class Presentation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "presentations"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    theme: Mapped[str] = mapped_column(String(64), default="academic_navy", nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9", nullable=False)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    slides: Mapped[list["PresentationSlide"]] = relationship(
        back_populates="presentation",
        cascade="all, delete-orphan",
        order_by="PresentationSlide.order_index",
    )


class PresentationSlide(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "presentation_slides"

    presentation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("presentations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    layout: Mapped[str] = mapped_column(String(64), default="title_and_bullets", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bullets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    speaker_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    image_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    chart_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    elements_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    presentation: Mapped["Presentation"] = relationship(back_populates="slides")


# ==============================================================================
# 6. DIAGRAMS (MODULES G & H)
# ==============================================================================


class Diagram(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "diagrams"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    diagram_type: Mapped[str] = mapped_column(String(64), default="flowchart", nullable=False)
    engine: Mapped[str] = mapped_column(String(32), default="reactflow", nullable=False)  # reactflow | mermaid | plantuml
    nodes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    edges_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    mermaid_code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    plantuml_code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    viewport_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


# ==============================================================================
# 7. RESEARCH SOURCES & CITATIONS (MODULE F)
# ==============================================================================


class ResearchSource(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "research_sources"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_provider: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)  # crossref | openalex | semantic_scholar | manual
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provenance_status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)  # discovered | retrieved | verified
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    citations: Mapped[list["Citation"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Citation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "citations"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_range: Mapped[str | None] = mapped_column(String(64), nullable=True)
    citation_style: Mapped[str] = mapped_column(String(32), default="APA 7", nullable=False)
    formatted_inline: Mapped[str] = mapped_column(String(255), nullable=False)
    formatted_bibliography: Mapped[str] = mapped_column(Text, nullable=False)

    source: Mapped["ResearchSource"] = relationship(back_populates="citations")


# ==============================================================================
# 8. LEARNING & ASSESSMENT (MODULE I)
# ==============================================================================


class StudyMaterial(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "study_materials"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[str] = mapped_column(String(64), default="lecture_notes", nullable=False)
    source_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    revision_schedule: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    mastery_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="study_material", cascade="all, delete-orphan"
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="study_material", cascade="all, delete-orphan"
    )


class Flashcard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flashcards"

    study_material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0..5
    times_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    study_material: Mapped["StudyMaterial"] = relationship(back_populates="flashcards")


class Quiz(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "quizzes"

    study_material_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_materials.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    quiz_type: Mapped[str] = mapped_column(String(32), default="mcq", nullable=False)  # mcq | short_answer | mock_exam
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    questions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    study_material: Mapped["StudyMaterial | None"] = relationship(back_populates="quizzes")
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quiz_attempts"

    quiz_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answers_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    feedback_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")


# ==============================================================================
# 9. TEMPLATES, COMMUNITY, REPORTS & NOTIFICATIONS (MODULES K & L)
# ==============================================================================


class Template(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "templates"

    author_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # document | diagram | presentation | project
    citation_style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    structure_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    license_name: Mapped[str] = mapped_column(String(64), default="CC-BY-4.0", nullable=False)


class CommunityPost(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "community_posts"

    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # template | resource | diagram | study_material | showcase
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    license_name: Mapped[str] = mapped_column(String(64), default="CC-BY-4.0", nullable=False)
    source_resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    moderation_status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)  # approved | flagged | hidden
    rating_sum: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ratings_by_user: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)  # community_post | user | template
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)  # open | resolved | dismissed
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


# ==============================================================================
# 10. ADMINISTRATION, PROVIDER CONFIGS, USAGE & AUDIT LOGS
# ==============================================================================


class ProviderConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_configs"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # ai | image | video | research
    endpoint_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class UsageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_records"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


Index("ix_usage_user_type_created", UsageRecord.user_id, UsageRecord.resource_type, UsageRecord.created_at)
Index("ix_documents_owner_project", Document.owner_id, Document.project_id)
Index("ix_media_owner_type", MediaAsset.owner_id, MediaAsset.asset_type)
