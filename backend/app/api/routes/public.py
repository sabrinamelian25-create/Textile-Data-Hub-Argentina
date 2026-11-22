from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.catalog.series_catalog import CATEGORY_DEFINITIONS
from app.db.models import (
    AuditFinding,
    AuditReport,
    Dataset,
    DerivedSeriesLineage,
    GlossaryTerm,
    IngestionRun,
    Observation,
    OfficialSource,
    RawExtraction,
    Series,
    TradeProductMapping,
)
from app.db.session import get_db
from app.services.export import build_metadata_rows, render_csv, render_csv_bundle_zip, render_xlsx
from app.services.research import suggest_research_structure
from app.services.search import search_series
from app.services.transforms import (
    ObsPoint,
    aggregate_daily_to_monthly,
    build_comparison_warnings,
    compute_latest_summary,
    transform_series,
)

router = APIRouter(prefix="/api", tags=["public"])


def _to_obs_points(obs_rows: list[Observation]) -> list[ObsPoint]:
    return [
        ObsPoint(
            observation_date=o.observation_date,
            value=float(o.value),
            is_preliminary=o.is_preliminary,
            is_outlier_flagged=o.is_outlier_flagged,
            revision_number=o.revision_number,
        )
        for o in obs_rows
    ]


def _serialize_series_card(s: Series, summary: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "series_id": s.series_id,
        "series_code": s.series_code,
        "series_name": s.series_name,
        "short_name": s.short_name,
        "description": s.description,
        "unit": s.unit,
        "base_period": s.base_period,
        "frequency": s.frequency,
        "category": s.category,
        "subcategory": s.subcategory,
        "is_context_variable": s.is_context_variable,
        "geography": s.geography,
        "textile_chain_level": s.textile_chain_level,
        "seasonal_adjustment": s.seasonal_adjustment,
        "price_type": s.price_type,
        "currency": s.currency,
        "source_code": s.source.source_code if s.source else None,
        "source_institution": s.source.institution if s.source else None,
        "source_series_code": s.source_series_code,
        "source_url": s.source_url,
        "methodology_url": s.methodology_url,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
        "last_updated_at": s.last_updated_at.isoformat() if s.last_updated_at else None,
        "last_extracted_at": s.last_extracted_at.isoformat() if s.last_extracted_at else None,
        "series_type": s.series_type,
        "audit_status": s.audit_status,
        "quality_score": s.quality_score,
        "latest": summary,
    }


@router.get("/health", summary="Healthcheck del servicio y conexión a PostgreSQL")
def health(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        verified_count = db.scalar(
            select(func.count()).select_from(Series).where(Series.audit_status == "VERIFIED", Series.active.is_(True))
        )
        obs_count = db.scalar(select(func.count()).select_from(Observation).where(Observation.is_current.is_(True)))
        return {
            "status": "ok",
            "database": "connected",
            "verified_series_count": verified_count or 0,
            "current_observations_count": obs_count or 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}")


@router.get("/categories", summary="Listar las 5 dimensiones sectoriales con conteo de series verificadas")
def list_categories(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    counts = dict(
        db.execute(
            select(Series.category, func.count())
            .where(Series.audit_status == "VERIFIED", Series.active.is_(True))
            .group_by(Series.category)
        ).all()
    )
    out = []
    for cat in sorted(CATEGORY_DEFINITIONS, key=lambda c: c["order"]):
        out.append({
            **cat,
            "verified_series_count": counts.get(cat["code"], 0),
        })
    return out


@router.get("/series", summary="Listar series económicas (por defecto exclusivamente audit_status=VERIFIED)")
def list_series(
    category: str | None = Query(None),
    chain_level: str | None = Query(None),
    series_type: str | None = Query(None, description="OFFICIAL o DERIVED"),
    include_non_verified: bool = Query(False, description="Solo para inspección administrativa; por defecto False"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(Series)
        .options(joinedload(Series.source), joinedload(Series.dataset))
        .where(Series.active.is_(True))
    )
    if not include_non_verified:
        stmt = stmt.where(Series.audit_status == "VERIFIED")
    if category:
        stmt = stmt.where(Series.category == category)
    if chain_level:
        stmt = stmt.where(Series.textile_chain_level == chain_level)
    if series_type:
        stmt = stmt.where(Series.series_type == series_type.upper())

    stmt = stmt.order_by(Series.is_context_variable.asc(), Series.category.asc(), Series.series_name.asc())
    series_rows = db.scalars(stmt).all()

    out = []
    for s in series_rows:
        # Fetch recent 24 observations for quick summary stats
        recent_obs = db.scalars(
            select(Observation)
            .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
            .order_by(Observation.observation_date.desc())
            .limit(400)
        ).all()
        summary = compute_latest_summary(_to_obs_points(recent_obs), s.frequency)
        out.append(_serialize_series_card(s, summary))
    return out


@router.get("/series/{series_code}", summary="Detalle completo de un indicador (Nivel 1 + Nivel 2 educativo)")
def get_series_detail(series_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = db.scalar(
        select(Series)
        .options(joinedload(Series.source), joinedload(Series.dataset), joinedload(Series.derived_lineage))
        .where(Series.series_code == series_code, Series.active.is_(True))
    )
    if s is None:
        raise HTTPException(status_code=404, detail=f"Serie '{series_code}' no encontrada.")

    obs_rows = db.scalars(
        select(Observation)
        .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
        .order_by(Observation.observation_date.asc())
    ).all()
    summary = compute_latest_summary(_to_obs_points(obs_rows), s.frequency)

    # Resolve suggested comparison cards
    suggested_cards = []
    if s.suggested_comparisons:
        comp_rows = db.scalars(
            select(Series).where(
                Series.series_code.in_(s.suggested_comparisons),
                Series.audit_status == "VERIFIED",
                Series.active.is_(True),
            )
        ).all()
        comp_map = {c.series_code: c for c in comp_rows}
        for code in s.suggested_comparisons:
            if code in comp_map:
                c = comp_map[code]
                suggested_cards.append({
                    "series_code": c.series_code,
                    "short_name": c.short_name,
                    "series_name": c.series_name,
                    "unit": c.unit,
                    "frequency": c.frequency,
                    "category": c.category,
                    "is_context_variable": c.is_context_variable,
                })

    latest_report = db.scalar(
        select(AuditReport).where(AuditReport.series_id == s.series_id).order_by(AuditReport.audited_at.desc()).limit(1)
    )
    findings = []
    if latest_report:
        findings = [
            {
                "check_category": f.check_category,
                "check_code": f.check_code,
                "severity": f.severity,
                "message": f.message,
                "details": f.details,
            }
            for f in db.scalars(select(AuditFinding).where(AuditFinding.report_id == latest_report.report_id)).all()
        ]

    derived_info = None
    if s.derived_lineage:
        derived_info = {
            "source_series_ids": s.derived_lineage.source_series_ids,
            "formula": s.derived_lineage.formula,
            "deflator_series_code": s.derived_lineage.deflator_series_code,
            "calculation_version": s.derived_lineage.calculation_version,
            "calculated_at": s.derived_lineage.calculated_at.isoformat(),
            "notes": s.derived_lineage.notes,
        }

    return {
        **_serialize_series_card(s, summary),
        "observations_count": len(obs_rows),
        "educational": {
            "what_it_measures": s.what_it_measures,
            "how_it_is_built": s.how_it_is_built,
            "economic_relevance": s.economic_relevance,
            "methodology_summary": s.methodology_summary,
            "interpretation_notes": s.interpretation_notes,
            "limitations": s.limitations,
            "economic_sense_note": s.economic_sense_note,
        },
        "dataset": {
            "dataset_code": s.dataset.dataset_code if s.dataset else None,
            "title": s.dataset.title if s.dataset else None,
            "official_url": s.dataset.official_url if s.dataset else None,
        },
        "derived_lineage": derived_info,
        "suggested_comparisons": suggested_cards,
        "research_questions": s.research_questions or [],
        "quality_breakdown": s.quality_breakdown,
        "audit_findings": findings,
    }


@router.get("/series/{series_code}/observations", summary="Observaciones de una serie con transformación opcional")
def get_series_observations(
    series_code: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    transform: str = Query("level", pattern="^(level|mom_pct|yoy_pct|base_100)$"),
    base_date: date | None = Query(None),
    include_revisions: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    s = db.scalar(select(Series).where(Series.series_code == series_code, Series.active.is_(True)))
    if s is None:
        raise HTTPException(status_code=404, detail=f"Serie '{series_code}' no encontrada.")
    if s.audit_status not in ("VERIFIED", "WARNING"):
        raise HTTPException(status_code=403, detail=f"Serie '{series_code}' no está aprobada (estado={s.audit_status}).")

    # Fetch full history first so yoy_pct / mom_pct / base_100 have lookback context, then slice to [start_date, end_date]
    obs_rows = db.scalars(
        select(Observation)
        .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
        .order_by(Observation.observation_date.asc())
    ).all()
    pts = _to_obs_points(obs_rows)

    if transform == "base_100" and base_date is None and start_date is not None:
        # Use start of selected window as Base 100 reference unless base_date explicitly passed
        window_pts = [p for p in pts if p.observation_date >= start_date and (end_date is None or p.observation_date <= end_date)]
        if window_pts:
            base_date = window_pts[0].observation_date

    transformed, tmeta = transform_series(pts, frequency=s.frequency, transform=transform, base_date=base_date)

    if start_date:
        sd_iso = start_date.isoformat()
        transformed = [r for r in transformed if r["date"] >= sd_iso]
    if end_date:
        ed_iso = end_date.isoformat()
        transformed = [r for r in transformed if r["date"] <= ed_iso]

    revisions_history = []
    if include_revisions:
        rev_rows = db.scalars(
            select(Observation)
            .where(Observation.series_id == s.series_id, Observation.revision_number > 1)
            .order_by(Observation.observation_date.desc(), Observation.revision_number.desc())
            .limit(50)
        ).all()
        for r in rev_rows:
            revisions_history.append({
                "observation_date": r.observation_date.isoformat(),
                "value": float(r.value),
                "revision_number": r.revision_number,
                "is_current": r.is_current,
                "retrieved_at": r.retrieved_at.isoformat(),
            })

    return {
        "series_code": s.series_code,
        "series_name": s.series_name,
        "unit": s.unit,
        "frequency": s.frequency,
        "transform": transform,
        "meta": tmeta,
        "count": len(transformed),
        "observations": transformed,
        "revisions_history": revisions_history,
    }


@router.get("/series/{series_code}/metadata", summary="Ficha metodológica completa de una serie")
def get_series_metadata(series_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    detail = get_series_detail(series_code, db)
    return detail


@router.get("/series/{series_code}/traceability", summary="Trazabilidad completa desde el organismo hasta el gráfico")
def get_series_traceability(series_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = db.scalar(
        select(Series)
        .options(joinedload(Series.source), joinedload(Series.dataset), joinedload(Series.derived_lineage))
        .where(Series.series_code == series_code)
    )
    if s is None:
        raise HTTPException(status_code=404, detail=f"Serie '{series_code}' no encontrada.")

    latest_obs = db.scalar(
        select(Observation)
        .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
        .order_by(Observation.observation_date.desc())
        .limit(1)
    )
    raw_ext = db.get(RawExtraction, latest_obs.raw_id) if latest_obs else None
    run = db.get(IngestionRun, raw_ext.run_id) if raw_ext else None
    report = db.scalar(
        select(AuditReport).where(AuditReport.series_id == s.series_id).order_by(AuditReport.audited_at.desc()).limit(1)
    )
    rev_count = db.scalar(
        select(func.count()).select_from(Observation).where(Observation.series_id == s.series_id, Observation.revision_number > 1)
    )
    outlier_count = db.scalar(
        select(func.count()).select_from(Observation).where(Observation.series_id == s.series_id, Observation.is_outlier_flagged.is_(True), Observation.is_current.is_(True))
    )

    steps = [
        {
            "step": 1,
            "stage": "ORGANISMO",
            "label": s.source.institution if s.source else "Desconocido",
            "detail": f"Dominio oficial verificado: {s.source.official_domain if s.source else '-'} ({s.source.jurisdiction if s.source else '-'})",
        },
        {
            "step": 2,
            "stage": "DATASET",
            "label": s.dataset.title if s.dataset else s.source_series_code,
            "detail": f"Dataset ID: {s.dataset.dataset_code if s.dataset else '-'} | Código fuente: {s.source_series_code}",
        },
        {
            "step": 3,
            "stage": "ARCHIVO / API OFICIAL",
            "label": s.source_url,
            "detail": f"Formato: {s.dataset.format if s.dataset else '-'} | Frecuencia: {s.frequency}",
        },
        {
            "step": 4,
            "stage": "RAW (Inmutable)",
            "label": f"SHA-256: {raw_ext.payload_sha256[:20]}..." if raw_ext else "Sin extracción",
            "detail": f"raw_id={raw_ext.raw_id} | bytes={raw_ext.byte_size} | HTTP {raw_ext.http_status}" if raw_ext else "-",
        },
        {
            "step": 5,
            "stage": "EXTRACCIÓN",
            "label": f"Run #{run.run_id} ({run.connector_name})" if run else "Pendiente",
            "detail": f"Extraído el {raw_ext.extracted_at.isoformat()}" if raw_ext else "-",
        },
        {
            "step": 6,
            "stage": "DATA AUDITOR",
            "label": f"Estado: {s.audit_status} (Score: {s.quality_score}/100)",
            "detail": f"Report #{report.report_id if report else '-'} | Revisiones detectadas: {rev_count or 0} | Outliers marcados: {outlier_count or 0}",
        },
        {
            "step": 7,
            "stage": "TRANSFORMACIÓN",
            "label": f"Tipo de serie: {s.series_type}",
            "detail": s.derived_lineage.formula if s.derived_lineage else "Valores oficiales publicados sin alteración de nivel",
        },
        {
            "step": 8,
            "stage": "OBSERVACIÓN CORE",
            "label": f"Último dato: {s.last_observation_date.isoformat() if s.last_observation_date else '-'}",
            "detail": f"Valor vigente={float(latest_obs.value) if latest_obs else '-'} ({s.unit}) | Rev. #{latest_obs.revision_number if latest_obs else '-'}",
        },
        {
            "step": 9,
            "stage": "API & GRÁFICO",
            "label": f"/api/series/{s.series_code}/observations",
            "detail": "Disponible para visualización, comparación y exportación CSV/XLSX/JSON reproducible.",
        },
    ]

    return {
        "series_code": s.series_code,
        "series_name": s.series_name,
        "audit_status": s.audit_status,
        "series_type": s.series_type,
        "steps": steps,
        "raw_snapshot": {
            "raw_id": raw_ext.raw_id if raw_ext else None,
            "payload_sha256": raw_ext.payload_sha256 if raw_ext else None,
            "extracted_at": raw_ext.extracted_at.isoformat() if raw_ext else None,
        },
    }


@router.get("/search", summary="Buscador inteligente tolerante a tildes, plurales y sinónimos económicos")
def search(
    q: str = Query(..., min_length=1, description="Consulta económica en lenguaje natural"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return search_series(db, q, include_warning=False)


@router.get("/compare", summary="Comparador multi-serie (2 a 4 series) con alertas metodológicas")
def compare_series(
    series: str = Query(..., description="Lista separada por comas de 2 a 4 series_code"),
    mode: str = Query("base_100", pattern="^(original|pct_change|yoy_pct|base_100)$"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    base_date: date | None = Query(None),
    align_monthly: str | None = Query("avg", pattern="^(avg|eop|none)$"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    codes = [c.strip() for c in series.split(",") if c.strip()]
    codes = list(dict.fromkeys(codes))
    if len(codes) < 2 or len(codes) > 4:
        raise HTTPException(status_code=400, detail="Debe seleccionar entre 2 y 4 series para comparar.")

    series_objs = db.scalars(
        select(Series)
        .options(joinedload(Series.source))
        .where(Series.series_code.in_(codes), Series.active.is_(True), Series.audit_status == "VERIFIED")
    ).all()
    by_code = {s.series_code: s for s in series_objs}
    missing = [c for c in codes if c not in by_code]
    if missing:
        raise HTTPException(status_code=404, detail=f"Series no encontradas o no verificadas: {', '.join(missing)}")

    ordered_series = [by_code[c] for c in codes]
    has_daily = any(s.frequency == "DAILY" for s in ordered_series)
    has_lower_freq = any(s.frequency in ("MONTHLY", "QUARTERLY") for s in ordered_series)
    effective_align = align_monthly if (has_daily and has_lower_freq and align_monthly != "none") else None

    warnings = build_comparison_warnings(ordered_series, mode, effective_align)

    # Fetch observations for each series
    raw_points_map: dict[str, tuple[str, list[ObsPoint]]] = {}
    for s in ordered_series:
        obs_rows = db.scalars(
            select(Observation)
            .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
            .order_by(Observation.observation_date.asc())
        ).all()
        pts = _to_obs_points(obs_rows)
        eff_freq = s.frequency
        if s.frequency == "DAILY" and effective_align:
            pts = aggregate_daily_to_monthly(pts, method=effective_align)
            eff_freq = "MONTHLY"
        raw_points_map[s.series_code] = (eff_freq, pts)

    # Determine common base_date for base_100 mode
    effective_base_date = base_date
    if mode == "base_100" and effective_base_date is None:
        window_starts = []
        for s in ordered_series:
            _, pts = raw_points_map[s.series_code]
            cand = [p.observation_date for p in pts if (start_date is None or p.observation_date >= start_date) and (end_date is None or p.observation_date <= end_date)]
            if cand:
                window_starts.append(cand[0])
        if window_starts:
            effective_base_date = max(window_starts)

    series_payload = []
    for s in ordered_series:
        eff_freq, pts = raw_points_map[s.series_code]
        t_mode = "level" if mode == "original" else mode
        t_rows, tmeta = transform_series(pts, frequency=eff_freq, transform=t_mode, base_date=effective_base_date)
        if start_date:
            sd_iso = start_date.isoformat()
            t_rows = [r for r in t_rows if r["date"] >= sd_iso]
        if end_date:
            ed_iso = end_date.isoformat()
            t_rows = [r for r in t_rows if r["date"] <= ed_iso]
        if tmeta.get("warnings"):
            for w_msg in tmeta["warnings"]:
                warnings.append({"code": f"TRANSFORM_{s.series_code}", "severity": "warning", "message": f"{s.short_name}: {w_msg}"})
        series_payload.append({
            "series_code": s.series_code,
            "series_name": s.series_name,
            "short_name": s.short_name,
            "unit": s.unit,
            "frequency": s.frequency,
            "effective_frequency": eff_freq,
            "series_type": s.series_type,
            "is_context_variable": s.is_context_variable,
            "seasonal_adjustment": s.seasonal_adjustment,
            "price_type": s.price_type,
            "source_institution": s.source.institution if s.source else None,
            "meta": tmeta,
            "observations": t_rows,
        })

    return {
        "mode": mode,
        "base_date": effective_base_date.isoformat() if effective_base_date else None,
        "align_monthly": effective_align,
        "warnings": warnings,
        "correlation_caution": (
            "Advertencia metodológica: la coincidencia visual o correlación estadística entre estas series "
            "no implica causalidad. Utilice esta visualización para formular hipótesis exploratorias y contrastarlas económicamente."
        ),
        "series": series_payload,
    }


@router.get("/export", summary="Exportación lista para research (Excel, Python, R, Stata, EViews) en CSV, ZIP, XLSX o JSON")
def export_dataset(
    series: str = Query(..., description="Uno o varios series_code separados por coma"),
    format: str = Query("csv", pattern="^(csv|csv_bundle|xlsx|json)$"),
    mode: str = Query("original", pattern="^(original|pct_change|yoy_pct|base_100)$"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    base_date: date | None = Query(None),
    align_monthly: str | None = Query("avg", pattern="^(avg|eop|none)$"),
    db: Session = Depends(get_db),
):
    codes = [c.strip() for c in series.split(",") if c.strip()]
    codes = list(dict.fromkeys(codes))
    if not codes or len(codes) > 6:
        raise HTTPException(status_code=400, detail="Indique entre 1 y 6 series para exportar.")

    series_objs = db.scalars(
        select(Series)
        .options(joinedload(Series.source))
        .where(Series.series_code.in_(codes), Series.active.is_(True), Series.audit_status == "VERIFIED")
    ).all()
    by_code = {s.series_code: s for s in series_objs}
    missing = [c for c in codes if c not in by_code]
    if missing:
        raise HTTPException(status_code=404, detail=f"Series no disponibles: {', '.join(missing)}")

    ordered = [by_code[c] for c in codes]
    has_daily = any(s.frequency == "DAILY" for s in ordered)
    has_lower = any(s.frequency in ("MONTHLY", "QUARTERLY") for s in ordered)
    effective_align = align_monthly if (len(ordered) > 1 and has_daily and has_lower and align_monthly != "none") else None

    date_values: dict[str, dict[str, Any]] = {}
    t_mode = "level" if mode == "original" else mode
    effective_base = base_date
    if mode == "base_100" and effective_base is None and start_date is not None:
        effective_base = start_date

    for s in ordered:
        obs_rows = db.scalars(
            select(Observation)
            .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
            .order_by(Observation.observation_date.asc())
        ).all()
        pts = _to_obs_points(obs_rows)
        eff_freq = s.frequency
        if s.frequency == "DAILY" and effective_align:
            pts = aggregate_daily_to_monthly(pts, method=effective_align)
            eff_freq = "MONTHLY"
        t_rows, _ = transform_series(pts, frequency=eff_freq, transform=t_mode, base_date=effective_base)
        for r in t_rows:
            d_iso = r["date"]
            if start_date and d_iso < start_date.isoformat():
                continue
            if end_date and d_iso > end_date.isoformat():
                continue
            date_values.setdefault(d_iso, {})[s.series_code] = r["value"]

    sorted_dates = sorted(date_values.keys())
    if len(ordered) == 1:
        headers = ["fecha", "valor"]
        c0 = ordered[0].series_code
        data_rows = [[d_iso, date_values[d_iso].get(c0, "")] for d_iso in sorted_dates]
    else:
        headers = ["fecha"] + [s.series_code.lower() for s in ordered]
        data_rows = [[d_iso] + [date_values[d_iso].get(s.series_code, "") for s in ordered] for d_iso in sorted_dates]

    metadata_rows = build_metadata_rows(ordered)
    slug = ordered[0].series_code.lower() if len(ordered) == 1 else "textile_data_hub_comparacion"

    if format == "json":
        return {
            "headers": headers,
            "data": [dict(zip(headers, row)) for row in data_rows],
            "metadata": metadata_rows,
        }
    if format == "csv":
        payload = render_csv(headers, data_rows)
        return Response(
            content=payload,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{slug}.csv"'},
        )
    if format == "csv_bundle":
        payload = render_csv_bundle_zip(headers, data_rows, metadata_rows)
        return Response(
            content=payload,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{slug}_bundle.zip"'},
        )
    payload = render_xlsx(headers, data_rows, metadata_rows)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{slug}.xlsx"'},
    )


@router.get("/research/suggest", summary="Asistente exploratorio para estructurar un research")
def research_suggest(q: str = Query(..., min_length=2), db: Session = Depends(get_db)) -> dict[str, Any]:
    return suggest_research_structure(db, q)


@router.get("/trade/chain", summary="Mapeo oficial NCM 50–63 organizado por eslabón de la cadena productiva textil")
def get_trade_chain(db: Session = Depends(get_db)) -> dict[str, Any]:
    mappings = db.scalars(
        select(TradeProductMapping).order_by(TradeProductMapping.product_code.asc())
    ).all()
    trade_series = db.scalars(
        select(Series)
        .where(Series.category == "comercio_exterior", Series.audit_status == "VERIFIED", Series.active.is_(True))
        .order_by(Series.series_code.asc())
    ).all()

    chain_order = [
        ("MATERIAS_PRIMAS_FIBRAS", "1. Materias primas / Fibras"),
        ("HILADOS", "2. Hilados y filamentos"),
        ("TEJIDOS", "3. Tejidos y acabados"),
        ("MANUFACTURAS_TEXTILES", "4. Manufacturas textiles"),
        ("PRENDAS_TERMINADAS", "5. Prendas terminadas"),
    ]
    stages = []
    for key, label in chain_order:
        chap_items = [
            {
                "nomenclature": m.nomenclature,
                "product_code": m.product_code,
                "official_description": m.official_description,
                "analytical_group": m.analytical_group,
                "notes": m.notes,
            }
            for m in mappings
            if m.textile_chain_level == key
        ]
        linked_series = [
            {
                "series_code": s.series_code,
                "short_name": s.short_name,
                "unit": s.unit,
                "series_type": s.series_type,
                "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
            }
            for s in trade_series
            if s.textile_chain_level == key
        ]
        stages.append({
            "stage_key": key,
            "stage_label": label,
            "ncm_chapters": chap_items,
            "linked_series": linked_series,
        })

    return {
        "stages": stages,
        "methodological_note": (
            "Las series NCM a 2 dígitos provienen de SSPM / INDEC (millones de USD CIF para importaciones y FOB para exportaciones). "
            "No se suman categorías con valuación heterogénea sin documentarlo explícitamente."
        ),
    }


@router.get("/glossary", summary="Glosario académico contextual para tooltips educativos")
def get_glossary(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    terms = db.scalars(select(GlossaryTerm).order_by(GlossaryTerm.term_id.asc())).all()
    return [
        {
            "term_key": t.term_key,
            "title": t.title,
            "short_explanation": t.short_explanation,
            "academic_note": t.academic_note,
        }
        for t in terms
    ]


@router.get("/sources", summary="Listado de organismos públicos aprobados (official_sources) y datasets")
def get_sources(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    sources = db.scalars(
        select(OfficialSource).options(joinedload(OfficialSource.datasets)).order_by(OfficialSource.official_source_id.asc())
    ).unique().all()
    return [
        {
            "official_source_id": src.official_source_id,
            "source_code": src.source_code,
            "institution": src.institution,
            "official_domain": src.official_domain,
            "jurisdiction": src.jurisdiction,
            "is_approved": src.is_approved,
            "verified_at": src.verified_at.isoformat() if src.verified_at else None,
            "notes": src.notes,
            "datasets": [
                {
                    "dataset_code": ds.dataset_code,
                    "title": ds.title,
                    "official_url": ds.official_url,
                    "update_frequency": ds.update_frequency,
                    "format": ds.format,
                }
                for ds in src.datasets
            ],
        }
        for src in sources
    ]


@router.get("/updates", summary="Historial de corridas de extracción y actualización automática")
def get_updates(limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    runs = db.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    ).all()
    return [
        {
            "run_id": r.run_id,
            "connector_name": r.connector_name,
            "dataset_code": r.dataset_code,
            "schedule_tier": r.schedule_tier,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "records_downloaded": r.records_downloaded,
            "records_inserted": r.records_inserted,
            "records_updated": r.records_updated,
            "records_rejected": r.records_rejected,
            "error_message": r.error_message,
        }
        for r in runs
    ]
