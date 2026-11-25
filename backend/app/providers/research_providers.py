"""Legitimate Academic Research Discovery APIs (Crossref, OpenAlex, Semantic Scholar).

Academic integrity guarantee:
- Queries real public scholarly registries only.
- Preserves DOIs, source URLs, external IDs, and provenance (`discovered` -> `retrieved` -> `verified`).
- NEVER fabricates citations, authors, publication years, or DOI records.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return None
    return " ".join(words[i] for i in sorted(words.keys()))


async def search_openalex(query: str, limit: int = 8) -> list[dict[str, Any]]:
    params = {
        "search": query,
        "per-page": min(limit, 20),
        "mailto": settings.openalex_mailto,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get("https://api.openalex.org/works", params=params)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        raw_doi = item.get("doi") or ""
        doi = raw_doi.replace("https://doi.org/", "").strip() or None
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in item.get("authorships", [])
            if a.get("author", {}).get("display_name")
        ]
        venue = (item.get("primary_location") or {}).get("source", {}) or {}
        results.append(
            {
                "title": item.get("display_name") or "Untitled Work",
                "authors": authors,
                "year": item.get("publication_year"),
                "venue": venue.get("display_name"),
                "doi": doi,
                "url": raw_doi or item.get("id"),
                "abstract": _reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
                "source_provider": "openalex",
                "external_id": item.get("id"),
                "citation_count": item.get("cited_by_count"),
                "provenance_status": "discovered",
            }
        )
    return results


async def search_crossref(query: str, limit: int = 8) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "rows": min(limit, 20),
        "mailto": settings.crossref_mailto,
    }
    headers = {"User-Agent": f"UNIFORGE-AI/1.0 (mailto:{settings.crossref_mailto})"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get("https://api.crossref.org/works", params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, Any]] = []
    for item in data.get("message", {}).get("items", []):
        titles = item.get("title") or []
        title = titles[0] if titles else "Untitled Work"
        authors = []
        for a in item.get("author", []):
            name = " ".join(p for p in [a.get("given"), a.get("family")] if p)
            if name:
                authors.append(name)
        date_parts = (
            item.get("published-print", {}).get("date-parts")
            or item.get("published-online", {}).get("date-parts")
            or item.get("issued", {}).get("date-parts")
            or [[None]]
        )
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        containers = item.get("container-title") or []
        doi = item.get("DOI")
        results.append(
            {
                "title": title,
                "authors": authors,
                "year": year,
                "venue": containers[0] if containers else None,
                "doi": doi,
                "url": item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
                "abstract": item.get("abstract"),
                "source_provider": "crossref",
                "external_id": doi,
                "citation_count": item.get("is-referenced-by-count"),
                "provenance_status": "discovered",
            }
        )
    return results


async def verify_doi_crossref(doi: str) -> dict[str, Any] | None:
    """Validate a DOI directly against Crossref's authoritative registry."""
    clean_doi = doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
    if not clean_doi:
        return None
    headers = {"User-Agent": f"UNIFORGE-AI/1.0 (mailto:{settings.crossref_mailto})"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"https://api.crossref.org/works/{clean_doi}", headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        item = resp.json().get("message", {})

    titles = item.get("title") or []
    authors = [
        " ".join(p for p in [a.get("given"), a.get("family")] if p)
        for a in item.get("author", [])
    ]
    date_parts = (
        item.get("issued", {}).get("date-parts")
        or item.get("created", {}).get("date-parts")
        or [[None]]
    )
    containers = item.get("container-title") or []
    return {
        "verified": True,
        "doi": item.get("DOI", clean_doi),
        "title": titles[0] if titles else None,
        "authors": [a for a in authors if a],
        "year": date_parts[0][0] if date_parts and date_parts[0] else None,
        "venue": containers[0] if containers else None,
        "url": item.get("URL") or f"https://doi.org/{clean_doi}",
        "citation_count": item.get("is-referenced-by-count"),
        "provenance_status": "verified",
    }


async def search_semantic_scholar(query: str, limit: int = 8) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "limit": min(limit, 20),
        "fields": "title,authors,year,venue,externalIds,url,abstract,citationCount",
    }
    headers: dict[str, str] = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, Any]] = []
    for item in data.get("data", []):
        ext = item.get("externalIds") or {}
        doi = ext.get("DOI")
        results.append(
            {
                "title": item.get("title") or "Untitled Work",
                "authors": [a.get("name", "") for a in item.get("authors", []) if a.get("name")],
                "year": item.get("year"),
                "venue": item.get("venue") or None,
                "doi": doi,
                "url": item.get("url") or (f"https://doi.org/{doi}" if doi else None),
                "abstract": item.get("abstract"),
                "source_provider": "semantic_scholar",
                "external_id": item.get("paperId"),
                "citation_count": item.get("citationCount"),
                "provenance_status": "discovered",
            }
        )
    return results


def format_citation(
    title: str,
    authors: list[str],
    year: int | None,
    venue: str | None,
    doi: str | None,
    url: str | None,
    style: str = "APA 7",
    page_range: str | None = None,
) -> tuple[str, str]:
    """Deterministically format inline and bibliography entries in APA 7, IEEE, Harvard, MLA, Chicago."""
    yr = str(year) if year else "n.d."
    first_surname = (authors[0].split()[-1] if authors else "Unknown")
    if len(authors) > 2:
        author_short = f"{first_surname} et al."
    elif len(authors) == 2:
        second_surname = authors[1].split()[-1]
        author_short = f"{first_surname} & {second_surname}"
    else:
        author_short = first_surname

    authors_full = ", ".join(authors) if authors else "Unknown Author"
    doi_str = f"https://doi.org/{doi}" if doi else (url or "")
    page_suffix = f", p. {page_range}" if page_range else ""
    venue_part = f" {venue}." if venue else ""

    norm_style = style.upper()
    if "IEEE" in norm_style:
        inline = f"[{first_surname}, {yr}]"
        bib = f'{authors_full}, "{title},"{venue_part} {yr}. {doi_str}'.strip()
    elif "MLA" in norm_style:
        inline = f"({author_short}{(' ' + page_range) if page_range else ''})"
        bib = f'{authors_full}. "{title}."{venue_part} {yr}. {doi_str}'.strip()
    elif "HARVARD" in norm_style:
        inline = f"({author_short}, {yr}{page_suffix})"
        bib = f"{authors_full} ({yr}) '{title}',{venue_part} Available at: {doi_str}".strip()
    elif "CHICAGO" in norm_style:
        inline = f"({author_short} {yr}{page_suffix})"
        bib = f'{authors_full}. {yr}. "{title}."{venue_part} {doi_str}'.strip()
    else:  # APA 7 default
        inline = f"({author_short}, {yr}{page_suffix})"
        bib = f"{authors_full} ({yr}). {title}.{venue_part} {doi_str}".strip()
    return inline, bib
