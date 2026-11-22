from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import statistics
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditFinding,
    AuditReport,
    Dataset,
    DerivedSeriesLineage,
    Observation,
    OfficialSource,
    RawExtraction,
    Series,
    StagedObservation,
)


@dataclass
class StagedInputRow:
    observation_date: date | None
    raw_value: str | None
    is_preliminary: bool = False
    source_release_date: date | None = None


@dataclass
class AuditOutcome:
    report_id: int
    series_code: str
    audit_status: str
    quality_score: float
    quality_breakdown: dict[str, Any]
    total_checked: int
    passed_count: int
    warning_count: int
    error_count: int
    revisions_detected: int
    outliers_flagged: int
    records_inserted: int
    records_updated: int
    records_rejected: int


def _domain_matches(url: str, official_domain: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    dom = official_domain.lower().strip()
    return host == dom or host.endswith("." + dom)


def _month_diff(d1: date, d2: date) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


class DataAuditor:
    """Central mandatory audit gate between RAW/STAGING and CORE."""

    def __init__(self, db: Session):
        self.db = db

    def audit_and_publish(
        self,
        *,
        run_id: int,
        raw_id: int,
        series_code: str,
        rows: list[StagedInputRow],
        structure_context: dict[str, Any] | None = None,
        reference_date: date | None = None,
    ) -> AuditOutcome:
        ref_today = reference_date or datetime.now(timezone.utc).date()
        structure_context = structure_context or {"columns_ok": True, "unit_ok": True, "frequency_ok": True}

        series = self.db.scalar(select(Series).where(Series.series_code == series_code))
        if series is None:
            raise ValueError(f"Series {series_code} not registered in core.series")

        raw_ext = self.db.scalar(select(RawExtraction).where(RawExtraction.raw_id == raw_id))
        source = self.db.scalar(select(OfficialSource).where(OfficialSource.official_source_id == series.source_id))
        dataset = self.db.scalar(select(Dataset).where(Dataset.dataset_id == series.dataset_id))

        findings: list[dict[str, Any]] = []
        severe_errors = 0
        warning_count = 0

        # ------------------------------------------------------------------
        # 1. PROVENANCE CHECKS
        # ------------------------------------------------------------------
        provenance_ok = True
        if source is None or not source.is_approved:
            provenance_ok = False
            severe_errors += 1
            findings.append({
                "check_category": "PROVENANCE",
                "check_code": "UNAPPROVED_SOURCE",
                "severity": "ERROR",
                "message": "El organismo fuente no existe o no está aprobado en official_sources.",
                "details": {"source_id": series.source_id},
            })
        if dataset is None or raw_ext is None or not series.source_series_code or not series.source_url:
            provenance_ok = False
            severe_errors += 1
            findings.append({
                "check_category": "PROVENANCE",
                "check_code": "BROKEN_LINEAGE_CHAIN",
                "severity": "ERROR",
                "message": "Cadena de trazabilidad incompleta entre raw_extractions, dataset, source y series.",
                "details": {"raw_id": raw_id, "dataset_id": series.dataset_id},
            })
        elif source is not None:
            if series.series_type == "OFFICIAL":
                if source.source_code == "TDH_DERIVED" or not _domain_matches(raw_ext.source_url, source.official_domain):
                    provenance_ok = False
                    severe_errors += 1
                    findings.append({
                        "check_category": "PROVENANCE",
                        "check_code": "DOMAIN_MISMATCH",
                        "severity": "ERROR",
                        "message": f"La URL de extracción ({raw_ext.source_url}) no coincide con el dominio oficial aprobado ({source.official_domain}).",
                        "details": {"source_url": raw_ext.source_url, "expected_domain": source.official_domain},
                    })
            elif series.series_type == "DERIVED":
                lineage = self.db.scalar(
                    select(DerivedSeriesLineage).where(DerivedSeriesLineage.derived_series_id == series.series_id)
                )
                if lineage is None or not lineage.formula or not lineage.source_series_ids:
                    provenance_ok = False
                    severe_errors += 1
                    findings.append({
                        "check_category": "PROVENANCE",
                        "check_code": "MISSING_DERIVED_LINEAGE",
                        "severity": "ERROR",
                        "message": "Serie DERIVED sin registro de fórmula y series origen en derived_series_lineage.",
                        "details": None,
                    })

        # ------------------------------------------------------------------
        # 2. STRUCTURAL CHECKS
        # ------------------------------------------------------------------
        if not rows:
            severe_errors += 1
            findings.append({
                "check_category": "STRUCTURE",
                "check_code": "EMPTY_EXTRACTION",
                "severity": "ERROR",
                "message": "La extracción no devolvió observaciones para esta serie.",
                "details": None,
            })

        if not structure_context.get("columns_ok", True):
            severe_errors += 1
            findings.append({
                "check_category": "STRUCTURE",
                "check_code": "SCHEMA_DRIFT",
                "severity": "ERROR",
                "message": "Se detectó un cambio inesperado de columnas o estructura en el archivo oficial.",
                "details": structure_context,
            })

        if not structure_context.get("unit_ok", True) or not structure_context.get("frequency_ok", True):
            warning_count += 1
            findings.append({
                "check_category": "STRUCTURE",
                "check_code": "UNIT_OR_FREQUENCY_DRIFT",
                "severity": "WARNING",
                "message": "Cambio potencial en unidad o frecuencia declarada por el organismo.",
                "details": structure_context,
            })

        # ------------------------------------------------------------------
        # 3. INTEGRITY CHECKS (Stage every row explicitly; never invent/fill)
        # ------------------------------------------------------------------
        parsed_by_date: dict[date, tuple[Decimal, StagedInputRow, StagedObservation]] = {}
        staged_records: list[StagedObservation] = []
        malformed_count = 0
        duplicate_conflict_count = 0
        duplicate_exact_count = 0

        for r in rows:
            flags: list[str] = []
            num_val: Decimal | None = None
            row_status = "PENDING"

            if r.observation_date is None:
                flags.append("INVALID_DATE")
            if r.raw_value is None or str(r.raw_value).strip() == "" or str(r.raw_value).strip().lower() in {"nan", "null", "none", "n/a", "-", "..", "..."}:
                flags.append("NULL_VALUE")
            else:
                cleaned = str(r.raw_value).strip()
                try:
                    d_val = Decimal(cleaned)
                    if not d_val.is_finite():
                        flags.append("NON_FINITE_VALUE")
                    else:
                        num_val = d_val.quantize(Decimal("0.000001"))
                except (InvalidOperation, ValueError):
                    flags.append("NON_NUMERIC_VALUE")

            if flags:
                row_status = "REJECTED"
                malformed_count += 1
                staged = StagedObservation(
                    raw_id=raw_id,
                    run_id=run_id,
                    series_code=series_code,
                    observation_date=r.observation_date,
                    raw_value=r.raw_value,
                    numeric_value=None,
                    is_preliminary=r.is_preliminary,
                    source_release_date=r.source_release_date,
                    audit_status=row_status,
                    audit_flags={"flags": flags},
                )
                staged_records.append(staged)
                continue

            assert r.observation_date is not None and num_val is not None
            if r.observation_date in parsed_by_date:
                existing_val, _, _ = parsed_by_date[r.observation_date]
                if abs(existing_val - num_val) > Decimal("0.000001"):
                    duplicate_conflict_count += 1
                    flags.append("DUPLICATE_DATE_CONFLICT")
                    row_status = "REJECTED"
                else:
                    duplicate_exact_count += 1
                    flags.append("DUPLICATE_DATE_EXACT")
                    row_status = "WARNING"
                staged = StagedObservation(
                    raw_id=raw_id,
                    run_id=run_id,
                    series_code=series_code,
                    observation_date=r.observation_date,
                    raw_value=str(r.raw_value),
                    numeric_value=num_val,
                    is_preliminary=r.is_preliminary,
                    source_release_date=r.source_release_date,
                    audit_status=row_status,
                    audit_flags={"flags": flags},
                )
                staged_records.append(staged)
                continue

            staged = StagedObservation(
                raw_id=raw_id,
                run_id=run_id,
                series_code=series_code,
                observation_date=r.observation_date,
                raw_value=str(r.raw_value),
                numeric_value=num_val,
                is_preliminary=r.is_preliminary,
                source_release_date=r.source_release_date,
                audit_status="VERIFIED",
                audit_flags={"flags": []},
            )
            staged_records.append(staged)
            parsed_by_date[r.observation_date] = (num_val, r, staged)

        if duplicate_conflict_count > 0:
            severe_errors += 1
            findings.append({
                "check_category": "INTEGRITY",
                "check_code": "DUPLICATE_DATE_CONFLICT",
                "severity": "ERROR",
                "message": f"Se detectaron {duplicate_conflict_count} fechas duplicadas con valores contradictorios en la misma extracción.",
                "details": {"count": duplicate_conflict_count},
            })

        if duplicate_exact_count > 0:
            warning_count += 1
            findings.append({
                "check_category": "INTEGRITY",
                "check_code": "DUPLICATE_DATE_EXACT",
                "severity": "WARNING",
                "message": f"Se deduplicaron {duplicate_exact_count} registros repetidos idénticos.",
                "details": {"count": duplicate_exact_count},
            })

        total_rows = len(rows)
        if malformed_count > 0:
            malformed_ratio = malformed_count / max(total_rows, 1)
            if malformed_ratio > 0.50 or len(parsed_by_date) == 0:
                severe_errors += 1
                findings.append({
                    "check_category": "INTEGRITY",
                    "check_code": "HIGH_MALFORMED_RATE",
                    "severity": "ERROR",
                    "message": f"{malformed_count} de {total_rows} filas inválidas o vacías superan el umbral permitido.",
                    "details": {"malformed_count": malformed_count, "total": total_rows},
                })
            elif malformed_ratio > 0.05:
                warning_count += 1
                findings.append({
                    "check_category": "INTEGRITY",
                    "check_code": "PARTIAL_MALFORMED_ROWS",
                    "severity": "WARNING",
                    "message": f"Se rechazaron {malformed_count} filas no numéricas o nulas sin interpolar.",
                    "details": {"malformed_count": malformed_count, "total": total_rows},
                })
            else:
                findings.append({
                    "check_category": "INTEGRITY",
                    "check_code": "NULL_OR_MALFORMED_SKIPPED",
                    "severity": "INFO",
                    "message": f"Se omitieron {malformed_count} filas vacías o no numéricas manteniendo integridad estricta.",
                    "details": {"malformed_count": malformed_count, "total": total_rows},
                })

        # Gap analysis on sorted valid dates
        sorted_dates = sorted(parsed_by_date.keys())
        gap_details: list[dict[str, Any]] = []
        max_consecutive_missing = 0
        expected_periods = max(len(sorted_dates), 1)
        if len(sorted_dates) >= 2:
            if series.frequency == "MONTHLY":
                expected_periods = _month_diff(sorted_dates[0], sorted_dates[-1]) + 1
                for prev_d, curr_d in zip(sorted_dates, sorted_dates[1:]):
                    diff = _month_diff(prev_d, curr_d)
                    if diff > 1:
                        missing = diff - 1
                        max_consecutive_missing = max(max_consecutive_missing, missing)
                        gap_details.append({"from": prev_d.isoformat(), "to": curr_d.isoformat(), "missing_periods": missing})
            elif series.frequency == "QUARTERLY":
                expected_periods = (_month_diff(sorted_dates[0], sorted_dates[-1]) // 3) + 1
                for prev_d, curr_d in zip(sorted_dates, sorted_dates[1:]):
                    diff_q = _month_diff(prev_d, curr_d) // 3
                    if diff_q > 1:
                        missing = diff_q - 1
                        max_consecutive_missing = max(max_consecutive_missing, missing)
                        gap_details.append({"from": prev_d.isoformat(), "to": curr_d.isoformat(), "missing_periods": missing})
            elif series.frequency == "DAILY":
                # Business days (~5/7 calendar days)
                expected_periods = max(int((sorted_dates[-1] - sorted_dates[0]).days * 5 / 7), len(sorted_dates))
                for prev_d, curr_d in zip(sorted_dates, sorted_dates[1:]):
                    cal_gap = (curr_d - prev_d).days
                    if cal_gap > 10:
                        max_consecutive_missing = max(max_consecutive_missing, cal_gap)
                        gap_details.append({"from": prev_d.isoformat(), "to": curr_d.isoformat(), "calendar_days": cal_gap})

        if gap_details:
            is_warn_gap = (
                (series.frequency in ("MONTHLY", "QUARTERLY") and max_consecutive_missing > 2)
                or (series.frequency == "DAILY" and max_consecutive_missing > 30)
            )
            if is_warn_gap:
                warning_count += 1
            findings.append({
                "check_category": "INTEGRITY",
                "check_code": "DATE_GAP",
                "severity": "WARNING" if is_warn_gap else "INFO",
                "message": f"Se detectaron {len(gap_details)} discontinuidades temporales (máx. {max_consecutive_missing} períodos/días). No se interpoló ni rellenó con cero.",
                "details": {"gaps": gap_details[:10]},
            })

        # ------------------------------------------------------------------
        # 4. STATISTICAL OUTLIER DETECTION (MAD on % changes; NEVER delete)
        # ------------------------------------------------------------------
        outliers_by_date: dict[date, dict[str, Any]] = {}
        if len(sorted_dates) >= 8:
            pct_changes: list[tuple[date, float]] = []
            for prev_d, curr_d in zip(sorted_dates, sorted_dates[1:]):
                prev_v = float(parsed_by_date[prev_d][0])
                curr_v = float(parsed_by_date[curr_d][0])
                if abs(prev_v) > 1e-6:
                    pct = ((curr_v - prev_v) / abs(prev_v)) * 100.0
                    if math.isfinite(pct):
                        pct_changes.append((curr_d, pct))
            if len(pct_changes) >= 6:
                vals = [p for _, p in pct_changes]
                med = statistics.median(vals)
                abs_devs = [abs(v - med) for v in vals]
                mad = statistics.median(abs_devs) or 1e-6
                for d_obs, pct in pct_changes:
                    robust_z = 0.6745 * (pct - med) / mad
                    if abs(robust_z) > 6.5 and abs(pct) > 35.0:
                        outliers_by_date[d_obs] = {
                            "pct_change": round(pct, 2),
                            "robust_z": round(robust_z, 2),
                            "median_pct": round(med, 2),
                        }

        if outliers_by_date:
            for d_obs, odet in outliers_by_date.items():
                staged_obj = parsed_by_date[d_obs][2]
                staged_obj.audit_flags = {"flags": ["STATISTICAL_OUTLIER"], "outlier": odet}
            findings.append({
                "check_category": "STATISTICAL",
                "check_code": "EXTREME_JUMP_OUTLIER",
                "severity": "INFO",
                "message": f"Se marcaron {len(outliers_by_date)} observaciones con saltos estadísticamente atípicos para inspección (no eliminadas).",
                "details": {"samples": {d.isoformat(): v for d, v in list(outliers_by_date.items())[:8]}},
            })

        # ------------------------------------------------------------------
        # 5. REVISION DETECTION against current core.observations
        # ------------------------------------------------------------------
        current_obs_rows = self.db.scalars(
            select(Observation).where(Observation.series_id == series.series_id, Observation.is_current.is_(True))
        ).all()
        current_by_date = {o.observation_date: o for o in current_obs_rows}
        revision_samples: list[dict[str, Any]] = []
        revisions_detected = 0
        for obs_d, (new_val, _, _) in parsed_by_date.items():
            existing = current_by_date.get(obs_d)
            if existing is not None:
                old_val = Decimal(str(existing.value)).quantize(Decimal("0.000001"))
                if abs(new_val - old_val) > Decimal("0.000001"):
                    revisions_detected += 1
                    if len(revision_samples) < 10:
                        revision_samples.append({
                            "date": obs_d.isoformat(),
                            "old_value": float(old_val),
                            "new_value": float(new_val),
                            "new_revision_number": existing.revision_number + 1,
                        })

        if revisions_detected > 0:
            findings.append({
                "check_category": "STATISTICAL",
                "check_code": "HISTORICAL_REVISION",
                "severity": "INFO",
                "message": f"Se detectaron {revisions_detected} revisiones de datos históricos publicadas por la fuente; se conservará el historial completo.",
                "details": {"samples": revision_samples},
            })

        # ------------------------------------------------------------------
        # 6. FRESHNESS CHECK & QUALITY SCORE (0-100)
        # ------------------------------------------------------------------
        last_obs_date = sorted_dates[-1] if sorted_dates else None
        freshness_pts = 0.0
        if last_obs_date is not None:
            lag_days = (ref_today - last_obs_date).days
            if series.frequency == "DAILY":
                freshness_pts = 15.0 if lag_days <= 10 else (10.0 if lag_days <= 45 else 4.0)
                lag_warn_days = 45
            elif series.frequency == "QUARTERLY":
                freshness_pts = 15.0 if lag_days <= 240 else (10.0 if lag_days <= 365 else 4.0)
                lag_warn_days = 300
            else:  # MONTHLY
                freshness_pts = 15.0 if lag_days <= 110 else (10.0 if lag_days <= 240 else (6.0 if lag_days <= 500 else 3.0))
                lag_warn_days = 150
            if lag_days > lag_warn_days:
                findings.append({
                    "check_category": "FRESHNESS",
                    "check_code": "OFFICIAL_PUBLICATION_LAG",
                    "severity": "INFO",
                    "message": f"Último dato oficial disponible corresponde a {last_obs_date.isoformat()} ({lag_days} días respecto de hoy). Refleja rezago de publicación del organismo.",
                    "details": {"last_observation_date": last_obs_date.isoformat(), "lag_days": lag_days},
                })

        # Determine final audit_status (VERIFIED / WARNING / REJECTED)
        if severe_errors > 0 or not provenance_ok or len(parsed_by_date) == 0:
            final_status = "REJECTED"
        elif warning_count > 0:
            final_status = "WARNING"
        else:
            final_status = "VERIFIED"

        # Compute Quality Score breakdown (never alters values!)
        source_pts = 25.0 if provenance_ok else 0.0
        meta_fields = [
            series.description,
            series.what_it_measures,
            series.how_it_is_built,
            series.economic_relevance,
            series.methodology_summary,
            series.interpretation_notes,
            series.limitations,
            series.unit,
            series.frequency,
        ]
        meta_pts = round(20.0 * sum(1 for m in meta_fields if m and len(str(m).strip()) > 10) / len(meta_fields), 1)
        completeness_ratio = min(1.0, len(parsed_by_date) / max(expected_periods, 1)) if sorted_dates else 0.0
        temporal_pts = round(15.0 * completeness_ratio, 1)
        consistency_pts = 15.0 if (severe_errors == 0 and warning_count == 0) else (11.0 if severe_errors == 0 else 0.0)
        revision_pts = 10.0 if raw_ext is not None else 0.0
        quality_score = round(source_pts + meta_pts + temporal_pts + consistency_pts + freshness_pts + revision_pts, 1)
        quality_breakdown = {
            "source_validation": {"score": source_pts, "max": 25.0},
            "metadata_completeness": {"score": meta_pts, "max": 20.0},
            "temporal_completeness": {"score": temporal_pts, "max": 15.0},
            "structural_statistical_consistency": {"score": consistency_pts, "max": 15.0},
            "freshness": {"score": freshness_pts, "max": 15.0},
            "revision_lineage_tracking": {"score": revision_pts, "max": 10.0},
            "total": quality_score,
        }

        # Persist staged rows
        self.db.add_all(staged_records)
        self.db.flush()

        # Persist AuditReport + AuditFindings
        report = AuditReport(
            run_id=run_id,
            series_id=series.series_id,
            audit_status=final_status,
            quality_score=quality_score,
            quality_breakdown=quality_breakdown,
            total_checked=total_rows,
            passed_count=len(parsed_by_date),
            warning_count=warning_count,
            error_count=severe_errors,
            revisions_detected=revisions_detected,
            outliers_flagged=len(outliers_by_date),
        )
        self.db.add(report)
        self.db.flush()

        for f in findings:
            self.db.add(
                AuditFinding(
                    report_id=report.report_id,
                    series_id=series.series_id,
                    check_category=f["check_category"],
                    check_code=f["check_code"],
                    severity=f["severity"],
                    message=f["message"],
                    details=f["details"],
                )
            )

        # Promote to core.observations ONLY if not REJECTED
        now_utc = datetime.now(timezone.utc)
        records_inserted = 0
        records_updated = 0

        if final_status in ("VERIFIED", "WARNING"):
            for obs_d in sorted_dates:
                new_val, row_meta, _ = parsed_by_date[obs_d]
                outlier_det = outliers_by_date.get(obs_d)
                existing = current_by_date.get(obs_d)
                if existing is None:
                    self.db.add(
                        Observation(
                            series_id=series.series_id,
                            observation_date=obs_d,
                            value=new_val,
                            status=final_status,
                            revision_number=1,
                            is_current=True,
                            is_preliminary=row_meta.is_preliminary,
                            is_outlier_flagged=outlier_det is not None,
                            outlier_details=outlier_det,
                            source_release_date=row_meta.source_release_date,
                            extracted_at=raw_ext.extracted_at if raw_ext else now_utc,
                            retrieved_at=now_utc,
                            raw_id=raw_id,
                        )
                    )
                    records_inserted += 1
                else:
                    old_val = Decimal(str(existing.value)).quantize(Decimal("0.000001"))
                    if abs(new_val - old_val) > Decimal("0.000001"):
                        existing.is_current = False
                        self.db.flush()
                        self.db.add(
                            Observation(
                                series_id=series.series_id,
                                observation_date=obs_d,
                                value=new_val,
                                status=final_status,
                                revision_number=existing.revision_number + 1,
                                is_current=True,
                                is_preliminary=row_meta.is_preliminary,
                                is_outlier_flagged=outlier_det is not None,
                                outlier_details=outlier_det,
                                source_release_date=row_meta.source_release_date,
                                extracted_at=raw_ext.extracted_at if raw_ext else now_utc,
                                retrieved_at=now_utc,
                                raw_id=raw_id,
                            )
                        )
                        records_updated += 1

            series.start_date = sorted_dates[0]
            series.end_date = sorted_dates[-1]
            series.last_observation_date = sorted_dates[-1]
            series.last_extracted_at = raw_ext.extracted_at if raw_ext else now_utc
            if records_inserted > 0 or records_updated > 0 or series.last_updated_at is None:
                series.last_updated_at = now_utc
            series.audit_status = final_status
            series.quality_score = quality_score
            series.quality_breakdown = quality_breakdown
        else:
            # Never erase previously VERIFIED observations on rejection; only update audit metadata if series had no verified data yet.
            series.last_extracted_at = raw_ext.extracted_at if raw_ext else now_utc
            series.quality_score = quality_score
            series.quality_breakdown = quality_breakdown
            if not current_by_date:
                series.audit_status = final_status

        self.db.flush()
        return AuditOutcome(
            report_id=report.report_id,
            series_code=series_code,
            audit_status=final_status,
            quality_score=quality_score,
            quality_breakdown=quality_breakdown,
            total_checked=total_rows,
            passed_count=len(parsed_by_date),
            warning_count=warning_count,
            error_count=severe_errors,
            revisions_detected=revisions_detected,
            outliers_flagged=len(outliers_by_date),
            records_inserted=records_inserted,
            records_updated=records_updated,
            records_rejected=malformed_count + duplicate_conflict_count,
        )
