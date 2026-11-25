"""Learning Studio Engine: Summaries, Flashcards, Quizzes, Mock Exams & Revision Schedules."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


def extract_key_sentences(text: str, max_sentences: int = 8) -> list[str]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if len(s.strip()) > 25]
    return sentences[:max_sentences]


def build_study_summary_and_notes(title: str, source_text: str) -> tuple[str, str]:
    sentences = extract_key_sentences(source_text, max_sentences=12)
    if not sentences:
        summary = f"Study overview for {title}. Add lecture text or upload a PDF to extract detailed notes."
        notes = f"# {title}\n\n## Key Takeaways\n- Upload a lecture PDF or paste notes to build structured chapters."
        return summary, notes

    summary = " ".join(sentences[:3])
    bullet_lines = "\n".join(f"- {s}" for s in sentences)
    notes = f"# {title} — Structured Lecture Notes\n\n## Executive Summary\n{summary}\n\n## Core Concepts & Details\n{bullet_lines}\n"
    return summary, notes


def generate_flashcards_from_text(source_text: str, count: int = 6) -> list[dict[str, str]]:
    sentences = extract_key_sentences(source_text, max_sentences=max(count * 2, 10))
    cards: list[dict[str, str]] = []
    for idx, sent in enumerate(sentences[:count]):
        # Prefer definition sentences ("X is Y", "X refers to Y")
        def_match = re.match(r"^([A-Za-z0-9\s-]{3,50})\s+(is|are|refers to|means|defines)\s+(.+)$", sent, re.I)
        if def_match:
            term = def_match.group(1).strip()
            cards.append(
                {
                    "front": f"Define / explain: {term}",
                    "back": sent,
                    "hint": f"Starts with '{def_match.group(2)}'",
                }
            )
        else:
            words = sent.split()
            topic = " ".join(words[:5]).rstrip(",;:")
            cards.append(
                {
                    "front": f"Concept Check #{idx + 1}: What is the key point regarding '{topic}...'?",
                    "back": sent,
                    "hint": f"Key sentence #{idx + 1} from study material",
                }
            )
    return cards


def generate_quiz_questions_from_text(
    source_text: str,
    quiz_type: str = "mcq",
    count: int = 5,
) -> list[dict[str, Any]]:
    sentences = extract_key_sentences(source_text, max_sentences=max(count * 2, 10))
    questions: list[dict[str, Any]] = []
    for idx, sent in enumerate(sentences[:count]):
        words = [w.strip(".,;:()\"'") for w in sent.split() if len(w.strip(".,;:()\"'")) > 5]
        target = words[min(len(words) - 1, 2)] if words else "concept"
        if quiz_type == "short_answer":
            questions.append(
                {
                    "id": f"q{idx + 1}",
                    "type": "short_answer",
                    "prompt": f"Explain the significance of '{target}' based on the study material.",
                    "expected_keywords": [target.lower()],
                    "sample_answer": sent,
                    "explanation": f"Reference statement from notes: {sent}",
                }
            )
        else:
            blanked = re.sub(rf"\b{re.escape(target)}\b", "_____", sent, count=1)
            distractors = [
                w for w in ["methodology", "algorithm", "hypothesis", "architecture", "framework", "variable", "protocol"]
                if w.lower() != target.lower()
            ][:3]
            options = [target] + distractors
            # Deterministic rotation so correct option isn't always index 0
            shift = idx % len(options)
            rotated = options[shift:] + options[:shift]
            correct_idx = rotated.index(target)
            questions.append(
                {
                    "id": f"q{idx + 1}",
                    "type": "mcq",
                    "prompt": f"Fill in the key term: {blanked}",
                    "options": rotated,
                    "correct_index": correct_idx,
                    "correct_answer": target,
                    "explanation": f"In the source material: \"{sent}\"",
                }
            )
    return questions


def grade_quiz_submission(
    questions: list[dict[str, Any]],
    answers: dict[str, Any],
) -> tuple[float, int, list[dict[str, Any]]]:
    total = len(questions)
    correct = 0
    feedback: list[dict[str, Any]] = []

    for q in questions:
        qid = str(q["id"])
        user_ans = answers.get(qid)
        qtype = q.get("type", "mcq")
        is_correct = False
        if qtype == "mcq":
            correct_idx = q.get("correct_index")
            correct_ans = str(q.get("correct_answer", "")).strip().lower()
            if isinstance(user_ans, int) and user_ans == correct_idx:
                is_correct = True
            elif isinstance(user_ans, str) and (
                user_ans.strip().lower() == correct_ans or user_ans.strip() == str(correct_idx)
            ):
                is_correct = True
        else:
            keywords = [k.lower() for k in q.get("expected_keywords", [])]
            ans_str = str(user_ans or "").lower()
            is_correct = bool(ans_str and any(k in ans_str for k in keywords)) if keywords else bool(ans_str.strip())

        if is_correct:
            correct += 1
        feedback.append(
            {
                "question_id": qid,
                "is_correct": is_correct,
                "submitted": user_ans,
                "correct_answer": q.get("correct_answer") or q.get("sample_answer"),
                "explanation": q.get("explanation", "Review the corresponding study material section."),
            }
        )

    score = round((correct / total) * 100.0, 1) if total > 0 else 0.0
    return score, correct, feedback


def build_revision_schedule(title: str, exam_days_ahead: int = 14) -> list[dict[str, Any]]:
    """Spaced-repetition study plan (Day 1, Day 3, Day 7, Day N-1)."""
    now = datetime.now(timezone.utc)
    offsets = sorted({1, 3, min(7, max(4, exam_days_ahead // 2)), max(2, exam_days_ahead - 1)})
    activities = [
        "Initial active recall & flashcard pass",
        "Practice MCQ quiz & review missed explanations",
        "Synthesize chapter mind map & short-answer drill",
        "Timed mock exam & final weak-spot review",
    ]
    schedule = []
    for idx, day_offset in enumerate(offsets):
        schedule.append(
            {
                "session": idx + 1,
                "scheduled_date": (now + timedelta(days=day_offset)).strftime("%Y-%m-%d"),
                "focus": f"{title}: {activities[idx % len(activities)]}",
                "completed": False,
            }
        )
    return schedule
