from __future__ import annotations

from datetime import date
import io
import zipfile

from fastapi.testclient import TestClient
import openpyxl
from sqlalchemy import select

from app.auditor.engine import DataAuditor, StagedInputRow
from app.connectors.derived.derived_calculator import DerivedSeriesCalculator
from app.db.models import Dataset, IngestionRun, RawExtraction, Series
from app.db.session import get_db
from app.main import app


def _seed_sample_observations(db):
    def _load(ds_code: str, url: str, series_code: str, pts: list[tuple[date, str]]):
        ds = db.scalar(select(Dataset).where(Dataset.dataset_code == ds_code))
        run = IngestionRun(connector_name="api_test", dataset_code=ds_code, schedule_tier="MONTHLY", status="SUCCESS")
        db.add(run)
        db.flush()
        raw = RawExtraction(
            run_id=run.run_id,
            dataset_id=ds.dataset_id,
            source_url=url,
            http_status=200,
            content_type="application/json",
            payload_sha256="f" * 64,
            file_path="test.json",
            byte_size=10,
        )
        db.add(raw)
        db.flush()
        DataAuditor(db).audit_and_publish(
            run_id=run.run_id,
            raw_id=raw.raw_id,
            series_code=series_code,
            rows=[StagedInputRow(observation_date=d, raw_value=v) for d, v in pts],
            reference_date=date(2026, 11, 20),
        )

    _load(
        "INDEC_IPI_MANUF",
        "https://apis.datos.gob.ar/series/api/series/?ids=453.2_PRODUCTOS_LES_0_0_18_32",
        "IPI_TEXTILES",
        [(date(2026, 6, 1), "70.0"), (date(2026, 7, 1), "72.0"), (date(2026, 8, 1), "65.0"), (date(2026, 9, 1), "66.5")],
    )
    _load(
        "INDEC_IPI_MANUF",
        "https://apis.datos.gob.ar/series/api/series/?ids=453.1_SERIE_ORIGNAL_0_0_14_46",
        "IPI_NIVEL_GENERAL_ORIG",
        [(date(2026, 6, 1), "120.0"), (date(2026, 7, 1), "121.0"), (date(2026, 8, 1), "122.0"), (date(2026, 9, 1), "122.4")],
    )
    _load(
        "INDEC_IPC_NACIONAL",
        "https://apis.datos.gob.ar/series/api/series/?ids=146.3_IPRENDANAL_DICI_M_35",
        "IPC_PRENDAS_CALZADO",
        [(date(2026, 7, 1), "8000.0"), (date(2026, 8, 1), "8200.0"), (date(2026, 9, 1), "8513.0")],
    )
    _load(
        "INDEC_IPC_NACIONAL",
        "https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26",
        "IPC_NIVEL_GENERAL",
        [(date(2026, 7, 1), "12200.0"), (date(2026, 8, 1), "12500.0"), (date(2026, 9, 1), "12785.0")],
    )
    # Leave IPI_HILADOS_ALGODON as PENDING and mark IPI_FIBRAS_TEXTILES REJECTED to verify public visibility rules
    bad = db.scalar(select(Series).where(Series.series_code == "IPI_FIBRAS_TEXTILES"))
    bad.audit_status = "REJECTED"
    db.commit()


def test_api_end_to_end_endpoints(db_session):
    _seed_sample_observations(db_session)

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    try:
        # 1. Health & categories
        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        assert r_health.json()["verified_series_count"] == 4

        r_cats = client.get("/api/categories")
        assert r_cats.status_code == 200
        assert len(r_cats.json()) == 5

        # 2. Public series endpoint ONLY returns VERIFIED by default
        r_ser = client.get("/api/series")
        assert r_ser.status_code == 200
        codes = {s["series_code"] for s in r_ser.json()}
        assert "IPI_TEXTILES" in codes
        assert "IPI_FIBRAS_TEXTILES" not in codes
        assert "IPI_HILADOS_ALGODON" not in codes

        # 3. Search with synonyms & accents (stopwords ignored so unrelated series do not pollute)
        r_search = client.get("/api/search?q=precio%20de%20la%20ropa")
        assert r_search.status_code == 200
        s_codes = [x["series_code"] for x in r_search.json()["results"]]
        assert "IPC_PRENDAS_CALZADO" in s_codes
        assert "IPI_TEXTILES" not in s_codes
        assert r_search.json()["results"][0]["match_reason"]

        # 4. Detail, observations, metadata, traceability
        r_det = client.get("/api/series/IPI_TEXTILES")
        assert r_det.status_code == 200
        assert r_det.json()["educational"]["what_it_measures"]

        r_obs = client.get("/api/series/IPI_TEXTILES/observations?transform=base_100")
        assert r_obs.status_code == 200
        assert r_obs.json()["observations"][0]["value"] == 100.0

        r_meta = client.get("/api/series/IPI_TEXTILES/metadata")
        assert r_meta.status_code == 200

        r_trace = client.get("/api/series/IPI_TEXTILES/traceability")
        assert r_trace.status_code == 200
        assert len(r_trace.json()["steps"]) == 9

        # 5. Compare
        r_cmp = client.get("/api/compare?series=IPI_TEXTILES,IPI_NIVEL_GENERAL_ORIG&mode=base_100")
        assert r_cmp.status_code == 200
        assert "causalidad" in r_cmp.json()["correlation_caution"].lower()

        # 6. Export CSV, ZIP bundle, XLSX, JSON
        r_csv = client.get("/api/export?series=IPI_TEXTILES&format=csv")
        assert r_csv.status_code == 200
        assert "fecha,valor" in r_csv.text

        r_zip = client.get("/api/export?series=IPI_TEXTILES,IPI_NIVEL_GENERAL_ORIG&format=csv_bundle")
        assert r_zip.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r_zip.content)) as zf:
            assert set(zf.namelist()) == {"datos.csv", "metadatos.csv"}

        r_xlsx = client.get("/api/export?series=IPI_TEXTILES&format=xlsx")
        assert r_xlsx.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content))
        assert wb.sheetnames == ["datos", "metadatos"]

        # 7. Research, trade chain, glossary, sources, updates, auditor
        assert client.get("/api/research/suggest?q=importaciones+y+produccion").status_code == 200
        assert len(client.get("/api/trade/chain").json()["stages"]) == 5
        assert len(client.get("/api/glossary").json()) >= 10
        assert len(client.get("/api/sources").json()) >= 6
        assert client.get("/api/updates").status_code == 200
        assert client.get("/api/auditor/summary").json()["counts"]["REJECTED"] == 1
        assert len(client.get("/api/auditor/series").json()) == 49
    finally:
        app.dependency_overrides.clear()
