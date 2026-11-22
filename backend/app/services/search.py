from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from unidecode import unidecode

from app.db.models import SearchSynonym, Series


SPANISH_STOPWORDS = {
    "de", "del", "la", "las", "el", "los", "en", "y", "o", "a", "al", "con", "por", "para", "un", "una", "que", "sobre", "se", "su",
}


def normalize_text(text: str) -> str:
    clean = unidecode(text or "").lower().strip()
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()


def _stem_es(token: str) -> str:
    if len(token) > 4 and token.endswith("es") and token[-3] not in "aeiou":
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def search_series(db: Session, query: str, include_warning: bool = False) -> dict[str, Any]:
    norm_q = normalize_text(query)
    allowed_statuses = ["VERIFIED", "WARNING"] if include_warning else ["VERIFIED"]

    series_list = db.scalars(
        select(Series)
        .options(joinedload(Series.source), joinedload(Series.dataset))
        .where(Series.active.is_(True), Series.audit_status.in_(allowed_statuses))
        .order_by(Series.series_code.asc())
    ).all()

    if not norm_q:
        return {
            "query": query,
            "normalized_query": norm_q,
            "expanded_terms": [],
            "results": [],
        }

    synonyms = db.scalars(select(SearchSynonym)).all()
    q_tokens = [t for t in norm_q.split(" ") if len(t) >= 2 and t not in SPANISH_STOPWORDS]
    if not q_tokens:
        q_tokens = [t for t in norm_q.split(" ") if len(t) >= 2]
    q_stems = [_stem_es(t) for t in q_tokens]

    expanded_terms: set[str] = set()
    boosted_codes: dict[str, list[str]] = {}

    for syn in synonyms:
        syn_norm = normalize_text(syn.term)
        syn_tokens = [t for t in syn_norm.split(" ") if t]
        syn_stems = [_stem_es(t) for t in syn_tokens]
        # Exact phrase match OR all tokens of synonym match
        if syn_norm in norm_q or norm_q == syn_norm or any(st in q_stems for st in syn_stems if len(syn_stems) == 1):
            for et in syn.expanded_terms or []:
                expanded_terms.add(normalize_text(et))
            for code in syn.target_series_codes or []:
                boosted_codes.setdefault(code, []).append(syn.term)

    all_search_tokens = set(q_tokens) | set(q_stems) | expanded_terms | {_stem_es(t) for t in expanded_terms}

    scored: list[tuple[float, Series, str]] = []
    for s in series_list:
        score = 0.0
        reasons: list[str] = []

        name_n = normalize_text(s.series_name)
        short_n = normalize_text(s.short_name)
        desc_n = normalize_text(s.description)
        what_n = normalize_text(s.what_it_measures)
        sub_n = normalize_text(s.subcategory)
        cat_n = normalize_text(s.category)
        code_n = normalize_text(s.series_code)

        if s.series_code in boosted_codes:
            syns_hit = ", ".join(sorted(set(boosted_codes[s.series_code])))
            score += 35.0
            reasons.append(f"Coincidencia conceptual por sinónimo ({syns_hit})")

        if norm_q in name_n or norm_q in short_n:
            score += 40.0
            reasons.append("Coincidencia directa en el nombre del indicador")
        elif norm_q in code_n:
            score += 35.0
            reasons.append("Coincidencia por código de serie")

        direct_hits = []
        for tok, stem in zip(q_tokens, q_stems):
            if tok in name_n or stem in name_n:
                score += 14.0
                direct_hits.append(tok)
            elif tok in desc_n or stem in desc_n or tok in what_n:
                score += 7.0
                direct_hits.append(tok)
            elif tok in sub_n or tok in cat_n:
                score += 5.0
                direct_hits.append(tok)

        if direct_hits:
            uniq = ", ".join(dict.fromkeys(direct_hits))
            reasons.append(f"Términos encontrados ({uniq}) en título, categoría o descripción")

        exp_hits = [t for t in expanded_terms if t in name_n or t in desc_n]
        if exp_hits and score > 0:
            score += min(12.0, 3.0 * len(exp_hits))

        # Slight preference for core textile indicators over macro context unless macro explicitly queried
        if score > 0 and not s.is_context_variable:
            score += 2.0

        if score > 0:
            if not reasons:
                reasons.append("Relación temática con tu consulta")
            scored.append((score, s, "; ".join(dict.fromkeys(reasons))))

    scored.sort(key=lambda x: (-x[0], x[1].series_name))

    return {
        "query": query,
        "normalized_query": norm_q,
        "expanded_terms": sorted(expanded_terms),
        "results": [
            {
                "series_code": s.series_code,
                "series_name": s.series_name,
                "short_name": s.short_name,
                "description": s.description,
                "category": s.category,
                "subcategory": s.subcategory,
                "is_context_variable": s.is_context_variable,
                "source_institution": s.source.institution if s.source else None,
                "unit": s.unit,
                "frequency": s.frequency,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
                "audit_status": s.audit_status,
                "series_type": s.series_type,
                "quality_score": s.quality_score,
                "match_reason": reason,
                "score": round(sc, 1),
            }
            for sc, s, reason in scored
        ],
    }
