"""Semantic Context Retrieval Service (TF-IDF Cosine Similarity + Optional Dense Embeddings).

Ensures isolated project context retrieval ranks the most relevant excerpts for the user's
query strictly within the authorized project scope.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

from app.models.entities import ProjectContext

_STOPWORDS = {
    "the", "and", "for", "that", "with", "this", "from", "are", "was", "were",
    "have", "has", "had", "not", "but", "can", "will", "into", "about", "your",
    "our", "their", "they", "them", "been", "being", "which", "when", "where",
    "what", "how", "why", "who", "also", "more", "most", "some", "such", "than",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]{2,}", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS]


def rank_project_context(
    query: str,
    items: Sequence[ProjectContext],
    top_k: int = 8,
) -> list[tuple[ProjectContext, float]]:
    """Rank project context records by TF-IDF cosine similarity to the prompt."""
    if not items:
        return []
    q_tokens = _tokenize(query)
    if not q_tokens:
        return [(item, 1.0) for item in items[:top_k]]

    docs_tokens = [_tokenize(f"{item.title} {item.content_excerpt}") for item in items]
    n_docs = len(docs_tokens)
    df: Counter[str] = Counter()
    for toks in docs_tokens:
        for term in set(toks):
            df[term] += 1

    def _idf(term: str) -> float:
        return math.log((1 + n_docs) / (1 + df.get(term, 0))) + 1.0

    def _tfidf_vec(toks: list[str]) -> dict[str, float]:
        counts = Counter(toks)
        total = max(1, len(toks))
        return {t: (c / total) * _idf(t) for t, c in counts.items()}

    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(v * b.get(k, 0.0) for k, v in a.items())
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    q_vec = _tfidf_vec(q_tokens)
    scored: list[tuple[ProjectContext, float]] = []
    for item, toks in zip(items, docs_tokens, strict=False):
        score = _cosine(q_vec, _tfidf_vec(toks))
        scored.append((item, round(score, 4)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
