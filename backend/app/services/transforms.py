from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass
class ObsPoint:
    observation_date: date
    value: float
    is_preliminary: bool = False
    is_outlier_flagged: bool = False
    revision_number: int = 1


def _month_step(d: date, months_back: int) -> date:
    y = d.year
    m = d.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def aggregate_daily_to_monthly(points: list[ObsPoint], method: str = "avg") -> list[ObsPoint]:
    """Aggregate daily observations to monthly (YYYY-MM-01) using average or end-of-period."""
    buckets: dict[date, list[ObsPoint]] = defaultdict(list)
    for p in points:
        m_date = date(p.observation_date.year, p.observation_date.month, 1)
        buckets[m_date].append(p)

    out: list[ObsPoint] = []
    for m_date in sorted(buckets):
        pts = sorted(buckets[m_date], key=lambda x: x.observation_date)
        if method == "eop":
            chosen = pts[-1]
            val = chosen.value
        else:
            val = sum(p.value for p in pts) / len(pts)
        out.append(
            ObsPoint(
                observation_date=m_date,
                value=round(val, 6),
                is_preliminary=any(p.is_preliminary for p in pts),
                is_outlier_flagged=any(p.is_outlier_flagged for p in pts),
                revision_number=max(p.revision_number for p in pts),
            )
        )
    return out


def transform_series(
    points: list[ObsPoint],
    *,
    frequency: str,
    transform: str = "level",
    base_date: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply rigorous time-series transformation without ever fabricating or zero-filling gaps."""
    pts = sorted(points, key=lambda p: p.observation_date)
    by_date = {p.observation_date: p for p in pts}
    meta: dict[str, Any] = {"transform": transform, "warnings": []}

    if not pts:
        return [], meta

    if transform == "level":
        out = [
            {
                "date": p.observation_date.isoformat(),
                "value": round(p.value, 6),
                "is_preliminary": p.is_preliminary,
                "is_outlier_flagged": p.is_outlier_flagged,
                "revision_number": p.revision_number,
            }
            for p in pts
        ]
        return out, meta

    if transform in ("mom_pct", "pct_change"):
        out = []
        for idx, p in enumerate(pts):
            prev_val: float | None = None
            if frequency == "MONTHLY":
                prev_p = by_date.get(_month_step(p.observation_date, 1))
                prev_val = prev_p.value if prev_p else None
            elif frequency == "QUARTERLY":
                prev_p = by_date.get(_month_step(p.observation_date, 3))
                prev_val = prev_p.value if prev_p else None
            else:
                if idx > 0 and (p.observation_date - pts[idx - 1].observation_date).days <= 7:
                    prev_val = pts[idx - 1].value

            if prev_val is None or abs(prev_val) < 1e-9:
                continue
            pct = ((p.value - prev_val) / abs(prev_val)) * 100.0
            out.append(
                {
                    "date": p.observation_date.isoformat(),
                    "value": round(pct, 4),
                    "raw_value": round(p.value, 6),
                    "is_preliminary": p.is_preliminary,
                    "is_outlier_flagged": p.is_outlier_flagged,
                    "revision_number": p.revision_number,
                }
            )
        return out, meta

    if transform == "yoy_pct":
        out = []
        for p in pts:
            prev_p: ObsPoint | None = None
            if frequency == "MONTHLY":
                prev_p = by_date.get(_month_step(p.observation_date, 12))
            elif frequency == "QUARTERLY":
                prev_p = by_date.get(_month_step(p.observation_date, 12))
            else:
                # Daily: find exact 1-year-ago or closest business day within +-5 days
                try:
                    target_d = date(p.observation_date.year - 1, p.observation_date.month, p.observation_date.day)
                except ValueError:
                    target_d = date(p.observation_date.year - 1, p.observation_date.month, 28)
                for offset in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5):
                    cand = by_date.get(target_d + timedelta(days=offset))
                    if cand is not None:
                        prev_p = cand
                        break

            if prev_p is None or abs(prev_p.value) < 1e-9:
                continue
            pct = ((p.value - prev_p.value) / abs(prev_p.value)) * 100.0
            out.append(
                {
                    "date": p.observation_date.isoformat(),
                    "value": round(pct, 4),
                    "raw_value": round(p.value, 6),
                    "is_preliminary": p.is_preliminary,
                    "is_outlier_flagged": p.is_outlier_flagged,
                    "revision_number": p.revision_number,
                }
            )
        return out, meta

    if transform == "base_100":
        has_non_positive = any(p.value <= 0 for p in pts)
        if has_non_positive:
            meta["warnings"].append(
                "La serie contiene valores menores o iguales a cero (por ejemplo, déficit comercial); la normalización Base 100 no es interpretable cuando el valor base o la serie cruza cero."
            )
        base_point: ObsPoint | None = None
        if base_date is not None:
            if base_date in by_date:
                base_point = by_date[base_date]
            else:
                # Closest observation on or after base_date
                after = [p for p in pts if p.observation_date >= base_date]
                base_point = after[0] if after else pts[0]
        else:
            positive_pts = [p for p in pts if abs(p.value) > 1e-9]
            base_point = positive_pts[0] if positive_pts else pts[0]

        if base_point is None or abs(base_point.value) < 1e-9:
            meta["warnings"].append("No existe valor base distinto de cero para calcular Base 100.")
            return [], meta

        base_val = base_point.value
        meta["base_date_used"] = base_point.observation_date.isoformat()
        meta["base_value_used"] = round(base_val, 6)
        out = [
            {
                "date": p.observation_date.isoformat(),
                "value": round((p.value / base_val) * 100.0, 4),
                "raw_value": round(p.value, 6),
                "is_preliminary": p.is_preliminary,
                "is_outlier_flagged": p.is_outlier_flagged,
                "revision_number": p.revision_number,
            }
            for p in pts
        ]
        return out, meta

    raise ValueError(f"Unsupported transform: {transform}")


def compute_latest_summary(points: list[ObsPoint], frequency: str) -> dict[str, Any]:
    """Compute latest value, MoM/QoQ change, and YoY change strictly from official observations."""
    pts = sorted(points, key=lambda p: p.observation_date)
    if not pts:
        return {
            "latest_date": None,
            "latest_value": None,
            "mom_pct": None,
            "yoy_pct": None,
            "is_preliminary": False,
        }
    latest = pts[-1]
    by_date = {p.observation_date: p for p in pts}

    mom_pct: float | None = None
    yoy_pct: float | None = None

    if frequency == "MONTHLY":
        prev = by_date.get(_month_step(latest.observation_date, 1))
        yoy = by_date.get(_month_step(latest.observation_date, 12))
    elif frequency == "QUARTERLY":
        prev = by_date.get(_month_step(latest.observation_date, 3))
        yoy = by_date.get(_month_step(latest.observation_date, 12))
    else:
        prev = pts[-2] if len(pts) >= 2 else None
        try:
            td = date(latest.observation_date.year - 1, latest.observation_date.month, latest.observation_date.day)
        except ValueError:
            td = date(latest.observation_date.year - 1, latest.observation_date.month, 28)
        yoy = None
        for offset in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5):
            if (td + timedelta(days=offset)) in by_date:
                yoy = by_date[td + timedelta(days=offset)]
                break

    if prev is not None and abs(prev.value) > 1e-9:
        mom_pct = round(((latest.value - prev.value) / abs(prev.value)) * 100.0, 2)
    if yoy is not None and abs(yoy.value) > 1e-9:
        yoy_pct = round(((latest.value - yoy.value) / abs(yoy.value)) * 100.0, 2)

    return {
        "latest_date": latest.observation_date.isoformat(),
        "latest_value": round(latest.value, 4),
        "mom_pct": mom_pct,
        "yoy_pct": yoy_pct,
        "is_preliminary": latest.is_preliminary,
    }


def build_comparison_warnings(series_objects: list[Any], mode: str, align_monthly: str | None) -> list[dict[str, str]]:
    """Generate explicit methodological warnings when comparing heterogeneous series."""
    warnings: list[dict[str, str]] = []
    if len(series_objects) < 2:
        return warnings

    units = {s.unit for s in series_objects}
    if len(units) > 1 and mode == "original":
        warnings.append({
            "code": "DIFFERENT_UNITS",
            "severity": "warning",
            "message": f"Las series seleccionadas tienen unidades distintas ({', '.join(sorted(units))}). En modo Valores Originales no comparten escala común; considere activar el modo Base 100 o Variación Interanual.",
        })

    freqs = {s.frequency for s in series_objects}
    if len(freqs) > 1:
        msg = f"Frecuencias heterogéneas ({', '.join(sorted(freqs))}). "
        if align_monthly:
            msg += f"Las series diarias se agregaron mensualmente ({'promedio mensual' if align_monthly == 'avg' else 'fin de período'})."
        else:
            msg += "Considere activar la alineación mensual para comparar puntos coincidentes en el tiempo."
        warnings.append({"code": "DIFFERENT_FREQUENCIES", "severity": "warning", "message": msg})

    seasonal_flags = {s.seasonal_adjustment for s in series_objects}
    has_desest = any("Desestacionalizada" in f for f in seasonal_flags)
    has_orig = any("Desestacionalizada" not in f for f in seasonal_flags)
    if has_desest and has_orig:
        warnings.append({
            "code": "MIXED_SEASONAL_ADJUSTMENT",
            "severity": "info",
            "message": "Se combinan series con ajuste estacional y series originales sin ajuste estacional. Los picos estacionales observados pueden pertenecer únicamente a la serie original.",
        })

    price_types = {s.price_type for s in series_objects}
    has_nominal = any("Nominal" in p or "corrientes" in p.lower() for p in price_types)
    has_real = any("Real" in p or "constantes" in p.lower() or "Volumen" in p for p in price_types)
    if has_nominal and has_real:
        warnings.append({
            "code": "NOMINAL_VS_REAL_MIX",
            "severity": "warning",
            "message": "Atención: está comparando magnitudes nominales (en pesos o dólares corrientes) con variables reales o de volumen físico. En economías con alta inflación, la trayectoria nominal refleja principalmente variaciones de precios.",
        })

    starts = [s.start_date for s in series_objects if s.start_date is not None]
    ends = [s.end_date for s in series_objects if s.end_date is not None]
    if starts and ends:
        overlap_start = max(starts)
        overlap_end = min(ends)
        if min(starts) < overlap_start or max(ends) > overlap_end:
            warnings.append({
                "code": "DIFFERENT_COVERAGE",
                "severity": "info",
                "message": f"La cobertura temporal difiere entre series. El período común superpuesto abarca desde {overlap_start.isoformat()} hasta {overlap_end.isoformat()}.",
            })

    if any(s.series_type == "DERIVED" for s in series_objects):
        derived_names = [s.short_name for s in series_objects if s.series_type == "DERIVED"]
        warnings.append({
            "code": "INCLUDES_DERIVED_SERIES",
            "severity": "info",
            "message": f"La comparación incluye serie(s) DERIVED calculadas por Textile Data Hub ({', '.join(derived_names)}) a partir de fuentes oficiales.",
        })

    return warnings
