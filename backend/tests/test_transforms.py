from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.transforms import (
    ObsPoint,
    aggregate_daily_to_monthly,
    build_comparison_warnings,
    compute_latest_summary,
    transform_series,
)


def test_transforms_level_mom_yoy_base100_respect_gaps():
    pts = [
        ObsPoint(date(2024, 1, 1), 100.0),
        ObsPoint(date(2024, 2, 1), 110.0),
        # 2024-03 missing (gap!) -> 2024-04 must NOT compute a MoM vs Feb!
        ObsPoint(date(2024, 4, 1), 121.0),
        ObsPoint(date(2025, 1, 1), 150.0),
    ]

    mom, _ = transform_series(pts, frequency="MONTHLY", transform="mom_pct")
    assert [r["date"] for r in mom] == ["2024-02-01"]
    assert mom[0]["value"] == 10.0

    yoy, _ = transform_series(pts, frequency="MONTHLY", transform="yoy_pct")
    assert [r["date"] for r in yoy] == ["2025-01-01"]
    assert yoy[0]["value"] == 50.0

    b100, meta = transform_series(pts, frequency="MONTHLY", transform="base_100", base_date=date(2024, 2, 1))
    assert meta["base_date_used"] == "2024-02-01"
    assert b100[1]["value"] == 100.0
    assert b100[2]["value"] == 110.0


def test_base100_warns_on_negative_values():
    pts = [
        ObsPoint(date(2024, 1, 1), -50.0),
        ObsPoint(date(2024, 2, 1), -25.0),
    ]
    _, meta = transform_series(pts, frequency="MONTHLY", transform="base_100")
    assert len(meta["warnings"]) == 1


def test_aggregate_daily_to_monthly():
    pts = [
        ObsPoint(date(2025, 1, 2), 1000.0),
        ObsPoint(date(2025, 1, 3), 1020.0),
    ]
    avg_res = aggregate_daily_to_monthly(pts, method="avg")
    eop_res = aggregate_daily_to_monthly(pts, method="eop")
    assert avg_res[0].value == 1010.0
    assert eop_res[0].value == 1020.0


def test_comparison_warnings_detect_mixed_units_freq_seasonal_nominal():
    s1 = SimpleNamespace(
        short_name="IPI Textiles",
        unit="Índice 2004 = 100",
        frequency="MONTHLY",
        seasonal_adjustment="Sin ajuste estacional",
        price_type="Volumen físico",
        start_date=date(2016, 1, 1),
        end_date=date(2026, 9, 1),
        series_type="OFFICIAL",
    )
    s2 = SimpleNamespace(
        short_name="Tipo de cambio",
        unit="ARS / USD",
        frequency="DAILY",
        seasonal_adjustment="Desestacionalizada",
        price_type="Nominal (ARS por USD)",
        start_date=date(2016, 1, 1),
        end_date=date(2026, 11, 20),
        series_type="DERIVED",
    )
    warnings = build_comparison_warnings([s1, s2], mode="original", align_monthly="avg")
    codes = {w["code"] for w in warnings}
    assert "DIFFERENT_UNITS" in codes
    assert "DIFFERENT_FREQUENCIES" in codes
    assert "MIXED_SEASONAL_ADJUSTMENT" in codes
    assert "NOMINAL_VS_REAL_MIX" in codes
    assert "DIFFERENT_COVERAGE" in codes
    assert "INCLUDES_DERIVED_SERIES" in codes


def test_latest_summary():
    pts = [ObsPoint(date(2024, 1, 1), 100.0), ObsPoint(date(2024, 12, 1), 110.0), ObsPoint(date(2025, 1, 1), 121.0)]
    summary = compute_latest_summary(pts, "MONTHLY")
    assert summary["latest_value"] == 121.0
    assert summary["mom_pct"] == 10.0
    assert summary["yoy_pct"] == 21.0
