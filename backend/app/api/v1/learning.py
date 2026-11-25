"""Module I — Learning Studio (PDF Summaries, Notes, Flashcards, Quizzes, Mock Exams & Revision Plans)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_project_access,
    get_current_user,
    get_default_workspace,
    log_audit,
)
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.entities import (
    Flashcard,
    MediaAsset,
    Quiz,
    QuizAttempt,
    StudyMaterial,
    User,
)
from app.services.learning_service import (
    build_revision_schedule,
    build_study_summary_and_notes,
    generate_flashcards_from_text,
    generate_quiz_questions_from_text,
    grade_quiz_submission,
)

router = APIRouter(prefix="/learning", tags=["Learning Studio"])


class StudyMaterialCreateRequest(BaseModel):
    subject: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=2, max_length=255)
    material_type: str = Field(default="lecture_notes", max_length=64)
    project_id: str | None = None
    source_asset_id: str | None = None
    source_text: str = ""
    exam_days_ahead: int = Field(default=14, ge=2, le=120)
    auto_generate_flashcards: bool = True
    auto_generate_quiz: bool = True


class FlashcardCreateRequest(BaseModel):
    front: str = Field(min_length=2)
    back: str = Field(min_length=2)
    hint: str | None = None


class FlashcardReviewRequest(BaseModel):
    confidence_level: int = Field(ge=1, le=5)


class QuizCreateRequest(BaseModel):
    study_material_id: str | None = None
    subject: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=2, max_length=255)
    quiz_type: str = Field(default="mcq", pattern="^(mcq|short_answer|mock_exam)$")
    time_limit_minutes: int | None = Field(default=15, ge=1, le=180)
    source_text: str | None = None
    question_count: int = Field(default=5, ge=1, le=30)
    questions_json: list[dict[str, Any]] | None = None


class QuizSubmitRequest(BaseModel):
    answers: dict[str, Any]


@router.get("/materials")
async def list_study_materials(
    subject: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(StudyMaterial).where(
        StudyMaterial.owner_id == user.id, StudyMaterial.deleted_at.is_(None)
    )
    if subject:
        stmt = stmt.where(StudyMaterial.subject.ilike(f"%{subject}%"))
    rows = (await db.execute(stmt.order_by(StudyMaterial.updated_at.desc()))).scalars().all()
    return {
        "materials": [
            {
                "id": m.id,
                "subject": m.subject,
                "title": m.title,
                "material_type": m.material_type,
                "summary": m.summary,
                "content_markdown": m.content_markdown,
                "revision_schedule": m.revision_schedule,
                "mastery_percent": m.mastery_percent,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
    }


@router.post("/materials", status_code=status.HTTP_201_CREATED)
async def create_study_material(
    body: StudyMaterialCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.project_id:
        proj = await ensure_project_access(db, body.project_id, user, require_write=True)
        ws_id = proj.workspace_id
    else:
        ws = await get_default_workspace(db, user)
        ws_id = ws.id

    text = body.source_text or ""
    if body.source_asset_id:
        asset = (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id == body.source_asset_id,
                    MediaAsset.owner_id == user.id,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if asset and asset.extracted_text:
            text = asset.extracted_text + ("\n\n" + text if text else "")

    summary, notes_md = build_study_summary_and_notes(body.title, text)
    schedule = build_revision_schedule(body.title, body.exam_days_ahead)

    mat = StudyMaterial(
        workspace_id=ws_id,
        project_id=body.project_id,
        owner_id=user.id,
        subject=body.subject.strip(),
        title=body.title.strip(),
        material_type=body.material_type,
        source_asset_id=body.source_asset_id,
        summary=summary,
        content_markdown=notes_md,
        revision_schedule=schedule,
    )
    db.add(mat)
    await db.flush()

    created_cards: list[Flashcard] = []
    if body.auto_generate_flashcards and text.strip():
        for c in generate_flashcards_from_text(text, count=6):
            fc = Flashcard(
                study_material_id=mat.id,
                owner_id=user.id,
                front=c["front"],
                back=c["back"],
                hint=c.get("hint"),
            )
            db.add(fc)
            created_cards.append(fc)

    created_quiz = None
    if body.auto_generate_quiz and text.strip():
        questions = generate_quiz_questions_from_text(text, quiz_type="mcq", count=5)
        if questions:
            created_quiz = Quiz(
                study_material_id=mat.id,
                owner_id=user.id,
                subject=mat.subject,
                title=f"{mat.title} — Practice Quiz",
                quiz_type="mcq",
                time_limit_minutes=15,
                questions_json=questions,
            )
            db.add(created_quiz)

    await db.flush()
    await log_audit(db, user.id, "learning.create_material", "study_material", mat.id)
    await db.commit()
    return {
        "material": {
            "id": mat.id,
            "subject": mat.subject,
            "title": mat.title,
            "summary": mat.summary,
            "content_markdown": mat.content_markdown,
            "revision_schedule": mat.revision_schedule,
            "mastery_percent": mat.mastery_percent,
        },
        "flashcards_created": len(created_cards),
        "quiz_id": created_quiz.id if created_quiz else None,
    }


@router.get("/materials/{material_id}/flashcards")
async def list_flashcards(
    material_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cards = (
        await db.execute(
            select(Flashcard).where(
                Flashcard.study_material_id == material_id, Flashcard.owner_id == user.id
            )
        )
    ).scalars().all()
    return {
        "flashcards": [
            {
                "id": c.id,
                "front": c.front,
                "back": c.back,
                "hint": c.hint,
                "confidence_level": c.confidence_level,
                "times_reviewed": c.times_reviewed,
                "next_review_at": c.next_review_at.isoformat() if c.next_review_at else None,
            }
            for c in cards
        ]
    }


@router.post("/materials/{material_id}/flashcards", status_code=status.HTTP_201_CREATED)
async def add_flashcard(
    material_id: str,
    body: FlashcardCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mat = (
        await db.execute(
            select(StudyMaterial).where(
                StudyMaterial.id == material_id,
                StudyMaterial.owner_id == user.id,
                StudyMaterial.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not mat:
        raise NotFoundError("Study material")
    fc = Flashcard(
        study_material_id=mat.id,
        owner_id=user.id,
        front=body.front.strip(),
        back=body.back.strip(),
        hint=body.hint,
    )
    db.add(fc)
    await db.commit()
    return {"flashcard": {"id": fc.id, "front": fc.front, "back": fc.back, "hint": fc.hint}}


@router.post("/flashcards/{flashcard_id}/review")
async def review_flashcard(
    flashcard_id: str,
    body: FlashcardReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fc = (
        await db.execute(
            select(Flashcard).where(Flashcard.id == flashcard_id, Flashcard.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if not fc:
        raise NotFoundError("Flashcard")
    fc.confidence_level = body.confidence_level
    fc.times_reviewed += 1
    interval_days = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}[body.confidence_level]
    fc.next_review_at = datetime.now(timezone.utc) + timedelta(days=interval_days)
    await db.commit()
    return {
        "flashcard": {
            "id": fc.id,
            "confidence_level": fc.confidence_level,
            "times_reviewed": fc.times_reviewed,
            "next_review_at": fc.next_review_at.isoformat(),
        }
    }


@router.get("/quizzes")
async def list_quizzes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quizzes = (
        await db.execute(
            select(Quiz)
            .where(Quiz.owner_id == user.id, Quiz.deleted_at.is_(None))
            .order_by(Quiz.created_at.desc())
        )
    ).scalars().all()
    attempts = (
        await db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user.id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    return {
        "quizzes": [
            {
                "id": q.id,
                "study_material_id": q.study_material_id,
                "subject": q.subject,
                "title": q.title,
                "quiz_type": q.quiz_type,
                "time_limit_minutes": q.time_limit_minutes,
                "question_count": len(q.questions_json or []),
                "questions_json": q.questions_json,
                "created_at": q.created_at.isoformat(),
            }
            for q in quizzes
        ],
        "recent_attempts": [
            {
                "id": a.id,
                "quiz_id": a.quiz_id,
                "score": a.score,
                "correct_count": a.correct_count,
                "total_questions": a.total_questions,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in attempts
        ],
    }


@router.post("/quizzes", status_code=status.HTTP_201_CREATED)
async def create_quiz(
    body: QuizCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    questions = body.questions_json
    if not questions:
        text = body.source_text or ""
        if not text and body.study_material_id:
            mat = (
                await db.execute(
                    select(StudyMaterial).where(
                        StudyMaterial.id == body.study_material_id, StudyMaterial.owner_id == user.id
                    )
                )
            ).scalar_one_or_none()
            if mat:
                text = mat.content_markdown
        questions = generate_quiz_questions_from_text(
            text or f"Academic concepts in {body.subject}. Key definitions and methodologies require analysis.",
            quiz_type="short_answer" if body.quiz_type == "short_answer" else "mcq",
            count=body.question_count,
        )

    quiz = Quiz(
        study_material_id=body.study_material_id,
        owner_id=user.id,
        subject=body.subject.strip(),
        title=body.title.strip(),
        quiz_type=body.quiz_type,
        time_limit_minutes=body.time_limit_minutes,
        questions_json=questions,
    )
    db.add(quiz)
    await db.commit()
    return {
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "subject": quiz.subject,
            "quiz_type": quiz.quiz_type,
            "questions_json": quiz.questions_json,
        }
    }


@router.post("/quizzes/{quiz_id}/attempt", status_code=status.HTTP_201_CREATED)
async def submit_quiz_attempt(
    quiz_id: str,
    body: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quiz = (
        await db.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.owner_id == user.id, Quiz.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if not quiz:
        raise NotFoundError("Quiz")

    score, correct, feedback = grade_quiz_submission(quiz.questions_json or [], body.answers)
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user.id,
        answers_json=body.answers,
        feedback_json=feedback,
        score=score,
        total_questions=len(quiz.questions_json or []),
        correct_count=correct,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    if quiz.study_material_id:
        mat = (
            await db.execute(select(StudyMaterial).where(StudyMaterial.id == quiz.study_material_id))
        ).scalar_one_or_none()
        if mat:
            mat.mastery_percent = max(mat.mastery_percent, int(round(score)))
    await db.commit()
    return {
        "attempt": {
            "id": attempt.id,
            "quiz_id": quiz.id,
            "score": score,
            "correct_count": correct,
            "total_questions": attempt.total_questions,
            "feedback": feedback,
        }
    }
