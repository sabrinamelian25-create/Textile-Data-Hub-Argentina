from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import AuditFinding, AuditReport, IngestionRun, Series
from app.db.session import get_db
from app.scheduler.runner import CONNECTOR_REGISTRY, run_connector_by_name

router = APIRouter(prefix="/api/auditor", tags=["data-auditor"])


@router.get("/summary", summary="Resumen global del Data Auditor y metodología del Quality Score")
def auditor_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    counts_raw = dict(
        db.execute(
            select(Series.audit_status, func.count()).where(Series.active.is_(True)).group_by(Series.audit_status)
        ).all()
    )
    total = sum(counts_raw.values())
    avg_score = db.scalar(select(func.avg(Series.quality_score)).where(Series.active.is_(True), Series.quality_score.is_not(None)))
    recent_runs = db.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(12)).all()

    return {
        "total_series": total,
        "counts": {
            "VERIFIED": counts_raw.get("VERIFIED", 0),
            "WARNING": counts_raw.get("WARNING", 0),
            "PENDING": counts_raw.get("PENDING", 0),
            "REJECTED": counts_raw.get("REJECTED", 0),
        },
        "average_quality_score": round(float(avg_score), 1) if avg_score is not None else None,
        "quality_score_methodology": {
            "description": "Puntaje 0–100 meramente diagnóstico sobre calidad de procedencia, completitud y oportunidad. Nunca altera datos ni observaciones.",
            "weights": [
                {"dimension": "Validación de fuente oficial y dominio", "max_points": 25},
                {"dimension": "Completitud de metadata educativa y técnica", "max_points": 20},
                {"dimension": "Completitud temporal sin gaps", "max_points": 15},
                {"dimension": "Consistencia estructural y estadística", "max_points": 15},
                {"dimension": "Oportunidad (freshness respecto de la frecuencia)", "max_points": 15},
                {"dimension": "Trazabilidad SHA-256 y control de revisiones", "max_points": 10},
            ],
        },
        "available_connectors": list(CONNECTOR_REGISTRY.keys()),
        "recent_runs": [
            {
                "run_id": r.run_id,
                "connector_name": r.connector_name,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "records_downloaded": r.records_downloaded,
                "records_inserted": r.records_inserted,
                "records_updated": r.records_updated,
                "records_rejected": r.records_rejected,
                "error_message": r.error_message,
            }
            for r in recent_runs
        ],
    }


@router.get("/series", summary="Tabla completa de auditoría de todas las series (incluye WARNING/PENDING/REJECTED)")
def auditor_series_table(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    series_rows = db.scalars(
        select(Series)
        .options(joinedload(Series.source))
        .where(Series.active.is_(True))
        .order_by(Series.audit_status.asc(), Series.series_code.asc())
    ).all()

    out = []
    for s in series_rows:
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
                }
                for f in db.scalars(select(AuditFinding).where(AuditFinding.report_id == latest_report.report_id)).all()
            ]
        out.append({
            "series_code": s.series_code,
            "series_name": s.series_name,
            "short_name": s.short_name,
            "category": s.category,
            "series_type": s.series_type,
            "source_institution": s.source.institution if s.source else None,
            "frequency": s.frequency,
            "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
            "last_extracted_at": s.last_extracted_at.isoformat() if s.last_extracted_at else None,
            "audit_status": s.audit_status,
            "quality_score": s.quality_score,
            "quality_breakdown": s.quality_breakdown,
            "revisions_detected": latest_report.revisions_detected if latest_report else 0,
            "outliers_flagged": latest_report.outliers_flagged if latest_report else 0,
            "findings": findings,
        })
    return out


@router.get("/series/{series_code}/findings", summary="Detalle de hallazgos e historial de auditoría de una serie")
def auditor_series_findings(series_code: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    s = db.scalar(select(Series).where(Series.series_code == series_code))
    if s is None:
        raise HTTPException(status_code=404, detail=f"Serie '{series_code}' no encontrada.")
    reports = db.scalars(
        select(AuditReport).where(AuditReport.series_id == s.series_id).order_by(AuditReport.audited_at.desc()).limit(10)
    ).all()
    payload = []
    for rep in reports:
        f_list = db.scalars(select(AuditFinding).where(AuditFinding.report_id == rep.report_id)).all()
        payload.append({
            "report_id": rep.report_id,
            "run_id": rep.run_id,
            "audit_status": rep.audit_status,
            "quality_score": rep.quality_score,
            "audited_at": rep.audited_at.isoformat(),
            "total_checked": rep.total_checked,
            "passed_count": rep.passed_count,
            "warning_count": rep.warning_count,
            "error_count": rep.error_count,
            "revisions_detected": rep.revisions_detected,
            "outliers_flagged": rep.outliers_flagged,
            "findings": [
                {
                    "check_category": f.check_category,
                    "check_code": f.check_code,
                    "severity": f.severity,
                    "message": f.message,
                    "details": f.details,
                }
                for f in f_list
            ],
        })
    return {"series_code": s.series_code, "audit_status": s.audit_status, "reports": payload}


@router.post("/run/{connector_name}", summary="Disparar manualmente un conector oficial y ejecutar Data Auditor")
def trigger_connector(connector_name: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    if connector_name not in CONNECTOR_REGISTRY and connector_name != "all":
        raise HTTPException(status_code=404, detail=f"Conector '{connector_name}' no reconocido.")
    try:
        return run_connector_by_name(db, connector_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
