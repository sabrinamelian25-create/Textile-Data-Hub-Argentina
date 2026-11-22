from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.auditor.engine import DataAuditor, StagedInputRow
from app.db.models import Dataset, IngestionRun, Observation, OfficialSource, RawExtraction, Series


def _setup_run_and_raw(db_session, dataset_code: str, source_url: str) -> tuple[IngestionRun, RawExtraction]:
    ds = db_session.scalar(select(Dataset).where(Dataset.dataset_code == dataset_code))
    assert ds is not None
    run = IngestionRun(
        connector_name="test_connector",
        dataset_code=dataset_code,
        schedule_tier="MONTHLY",
        status="RUNNING",
    )
    db_session.add(run)
    db_session.flush()
    raw = RawExtraction(
        run_id=run.run_id,
        dataset_id=ds.dataset_id,
        source_url=source_url,
        http_status=200,
        content_type="application/json",
        payload_sha256="a" * 64,
        file_path="test.json",
        byte_size=123,
    )
    db_session.add(raw)
    db_session.flush()
    return run, raw


def test_auditor_rejects_unapproved_domain(db_session):
    run, raw = _setup_run_and_raw(db_session, "INDEC_IPI_MANUF", "https://unofficial-blog.example.com/data.json")
    auditor = DataAuditor(db_session)
    rows = [StagedInputRow(observation_date=date(2025, 1, 1), raw_value="100.5")]
    out = auditor.audit_and_publish(run_id=run.run_id, raw_id=raw.raw_id, series_code="IPI_TEXTILES", rows=rows)
    assert out.audit_status == "REJECTED"
    assert out.records_inserted == 0
    obs = db_session.scalars(select(Observation)).all()
    assert len(obs) == 0


def test_auditor_rejects_duplicate_conflicting_dates(db_session):
    run, raw = _setup_run_and_raw(
        db_session,
        "INDEC_IPI_MANUF",
        "https://apis.datos.gob.ar/series/api/series/?ids=453.2_PRODUCTOS_LES_0_0_18_32",
    )
    auditor = DataAuditor(db_session)
    rows = [
        StagedInputRow(observation_date=date(2025, 1, 1), raw_value="75.0"),
        StagedInputRow(observation_date=date(2025, 1, 1), raw_value="99.0"),
    ]
    out = auditor.audit_and_publish(run_id=run.run_id, raw_id=raw.raw_id, series_code="IPI_TEXTILES", rows=rows)
    assert out.audit_status == "REJECTED"
    assert out.records_inserted == 0


def test_auditor_flags_outliers_without_deleting_and_detects_gaps(db_session):
    run, raw = _setup_run_and_raw(
        db_session,
        "INDEC_IPI_MANUF",
        "https://apis.datos.gob.ar/series/api/series/?ids=453.2_PRODUCTOS_LES_0_0_18_32",
    )
    auditor = DataAuditor(db_session)
    rows = [
        StagedInputRow(observation_date=date(2024, 1, 1), raw_value="100.0"),
        StagedInputRow(observation_date=date(2024, 2, 1), raw_value="101.0"),
        StagedInputRow(observation_date=date(2024, 3, 1), raw_value="102.0"),
        StagedInputRow(observation_date=date(2024, 4, 1), raw_value="101.5"),
        StagedInputRow(observation_date=date(2024, 5, 1), raw_value="102.5"),
        StagedInputRow(observation_date=date(2024, 6, 1), raw_value="103.0"),
        StagedInputRow(observation_date=date(2024, 7, 1), raw_value="102.8"),
        StagedInputRow(observation_date=date(2024, 8, 1), raw_value="103.2"),
        # Gap of 3 months (Sep, Oct, Nov missing) + extreme jump to 190
        StagedInputRow(observation_date=date(2024, 12, 1), raw_value="190.0"),
    ]
    out = auditor.audit_and_publish(
        run_id=run.run_id,
        raw_id=raw.raw_id,
        series_code="IPI_TEXTILES",
        rows=rows,
        reference_date=date(2025, 1, 15),
    )
    # Gap > 2 months marks WARNING, NOT REJECTED; outlier is flagged, NOT deleted
    assert out.audit_status == "WARNING"
    assert out.records_inserted == 9
    assert out.outliers_flagged >= 1
    flagged_obs = db_session.scalar(
        select(Observation).where(Observation.observation_date == date(2024, 12, 1))
    )
    assert flagged_obs is not None
    assert flagged_obs.is_outlier_flagged is True
    assert Decimal(str(flagged_obs.value)) == Decimal("190.000000")


def test_auditor_tracks_revisions_and_preserves_verified_on_failed_run(db_session):
    auditor = DataAuditor(db_session)
    url = "https://apis.datos.gob.ar/series/api/series/?ids=453.2_PRODUCTOS_LES_0_0_18_32"

    run1, raw1 = _setup_run_and_raw(db_session, "INDEC_IPI_MANUF", url)
    out1 = auditor.audit_and_publish(
        run_id=run1.run_id,
        raw_id=raw1.raw_id,
        series_code="IPI_TEXTILES",
        rows=[
            StagedInputRow(observation_date=date(2025, 1, 1), raw_value="70.0", is_preliminary=True),
            StagedInputRow(observation_date=date(2025, 2, 1), raw_value="72.0", is_preliminary=True),
        ],
        reference_date=date(2025, 3, 15),
    )
    db_session.commit()
    assert out1.audit_status == "VERIFIED"
    assert out1.records_inserted == 2

    # Second run revises 2025-02-01 from 72.0 -> 74.5
    run2, raw2 = _setup_run_and_raw(db_session, "INDEC_IPI_MANUF", url)
    out2 = auditor.audit_and_publish(
        run_id=run2.run_id,
        raw_id=raw2.raw_id,
        series_code="IPI_TEXTILES",
        rows=[
            StagedInputRow(observation_date=date(2025, 1, 1), raw_value="70.0", is_preliminary=False),
            StagedInputRow(observation_date=date(2025, 2, 1), raw_value="74.5", is_preliminary=False),
        ],
        reference_date=date(2025, 3, 20),
    )
    db_session.commit()
    assert out2.revisions_detected == 1
    assert out2.records_updated == 1
    assert out2.records_inserted == 0

    s = db_session.scalar(select(Series).where(Series.series_code == "IPI_TEXTILES"))
    revs = db_session.scalars(
        select(Observation)
        .where(Observation.series_id == s.series_id, Observation.observation_date == date(2025, 2, 1))
        .order_by(Observation.revision_number.asc())
    ).all()
    assert len(revs) == 2
    assert revs[0].is_current is False and float(revs[0].value) == 72.0
    assert revs[1].is_current is True and revs[1].revision_number == 2 and float(revs[1].value) == 74.5

    # Third run fails provenance -> must NOT destroy previously VERIFIED observations
    run3, raw3 = _setup_run_and_raw(db_session, "INDEC_IPI_MANUF", "https://bad-host.example/foo")
    out3 = auditor.audit_and_publish(
        run_id=run3.run_id,
        raw_id=raw3.raw_id,
        series_code="IPI_TEXTILES",
        rows=[StagedInputRow(observation_date=date(2025, 3, 1), raw_value="999.0")],
    )
    db_session.commit()
    assert out3.audit_status == "REJECTED"
    db_session.refresh(s)
    assert s.audit_status == "VERIFIED"
    current_count = len(
        db_session.scalars(
            select(Observation).where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
        ).all()
    )
    assert current_count == 2
