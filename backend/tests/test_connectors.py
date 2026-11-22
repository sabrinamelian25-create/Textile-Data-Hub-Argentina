from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from app.connectors.base import RawDownloadResult
from app.connectors.bcra.bcra_monetarias_connector import BcraMonetariasConnector
from app.connectors.foreign_trade.ncm_trade_connector import NcmTradeConnector
from app.connectors.indec.datos_gob_series_connector import DatosGobSeriesConnector
from app.connectors.indec.sipm_xls_connector import SipmXlsConnector
from app.connectors.indec.ucii_csv_connector import UciiCsvConnector
from app.connectors.labour.sipa_labour_connector import SipaLabourConnector


def test_sipm_xls_connector_parses_real_indec_snapshot(db_session):
    xls_path = Path(__file__).resolve().parents[1] / "data" / "raw" / "series_sipm_dic2015.xls"
    assert xls_path.exists(), "Expected downloaded INDEC SIPM .xls snapshot"
    payload = xls_path.read_bytes()

    conn = SipmXlsConnector(db_session)
    raw_res = RawDownloadResult(
        dataset_code="INDEC_SIPM_IPIM",
        source_url="https://www.indec.gob.ar/ftp/cuadros/economia/series_sipm_dic2015.xls",
        http_status=200,
        content_type="application/vnd.ms-excel",
        payload_bytes=payload,
        file_path=str(xls_path),
        payload_sha256="abc",
    )
    batches = conn.parse(raw_res, conn.discover()[0])
    assert len(batches) == 5
    by_code = {b.series_code: b for b in batches}
    for code in [
        "IPIM_NIVEL_GENERAL",
        "IPIM_PRODUCTOS_MANUFACTURADOS",
        "IPIM_PRODUCTOS_TEXTILES",
        "IPIM_PRENDAS_VESTIR",
        "IPIM_ENERGIA_ELECTRICA",
    ]:
        rows = by_code[code].rows
        assert len(rows) > 100
        assert rows[0].observation_date == date(2015, 12, 1)
        assert float(rows[0].raw_value) == 100.0
        assert rows[-1].is_preliminary is True


def test_datos_gob_series_connector_parse(db_session):
    conn = DatosGobSeriesConnector(db_session, dataset_filter="INDEC_IPC_NACIONAL")
    target = conn.discover()[0]
    sample = {
        "meta": [
            {"frequency": "month"},
            {"field": {"id": "146.3_IPRENDANAL_DICI_M_35"}},
            {"field": {"id": "146.3_IVIVIENNAL_DICI_M_52"}},
            {"field": {"id": "148.3_INIVELNAL_DICI_M_26"}},
        ],
        "data": [
            ["2016-12-01", 100.0, 100.0, 100.0],
            ["2017-01-01", 99.1, None, 101.6],
        ],
    }
    raw_res = RawDownloadResult(
        dataset_code="INDEC_IPC_NACIONAL",
        source_url="https://apis.datos.gob.ar/series/api/series/?ids=test",
        http_status=200,
        content_type="application/json",
        payload_bytes=json.dumps(sample).encode(),
        file_path="x.json",
        payload_sha256="x",
    )
    batches = conn.parse(raw_res, target)
    by_code = {b.series_code: b for b in batches}
    assert len(by_code["IPC_PRENDAS_CALZADO"].rows) == 2
    assert len(by_code["IPC_VIVIENDA_ENERGIA"].rows) == 1  # null skipped, never filled with 0!


def test_ucii_and_bcra_and_sipa_parsers(db_session):
    ucii = UciiCsvConnector(db_session)
    csv_bytes = b"indice_tiempo,ucii_nivel_general,ucii_productos_textiles\n2026-08-01,60.1,44.6\n"
    ub = ucii.parse(
        RawDownloadResult("INDEC_UCII_2004", "https://infra.datos.gob.ar/test.csv", 200, "text/csv", csv_bytes, "x.csv", "h"),
        ucii.discover()[0],
    )
    assert ub[0].rows[0].raw_value == "44.6"

    bcra = BcraMonetariasConnector(db_session)
    b_json = json.dumps({"detalle": [{"fecha": "2026-11-20", "valor": 1575.95}]}).encode()
    bb = bcra.parse(
        RawDownloadResult("BCRA_MONETARIAS_V4", "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/5", 200, "application/json", b_json, "b.json", "h"),
        bcra.discover()[0],
    )
    assert bb[0].series_code == "TC_MAYORISTA_BCRA"
    assert bb[0].rows[0].raw_value == "1575.95"

    sipa = SipaLabourConnector(db_session)
    cep_target = sipa.discover()[1]
    cep_csv = b"fecha,clae2,puestos\n2023-11-01,13,42100\n2023-11-01,14,45200\n2023-11-01,99,1000\n"
    sb = sipa.parse(
        RawDownloadResult("CEP_SIPA_PUESTOS_CLAE2", "https://cdn.produccion.gob.ar/test.csv", 200, "text/csv", cep_csv, "s.csv", "h"),
        cep_target,
    )
    assert {b.series_code: b.rows[0].raw_value for b in sb} == {
        "EMPLEO_PRIVADO_TEXTIL": "42100",
        "EMPLEO_PRIVADO_INDUMENTARIA": "45200",
    }


def test_ncm_trade_connector_computes_14_chapter_sum(db_session):
    ncm = NcmTradeConnector(db_session)
    impo_target = ncm.discover()[0]
    cols = ["indice_tiempo"] + [col for _, col in impo_target["chain_cols"]]
    vals_full = ["2025-01-01"] + ["1.5"] * 14
    vals_no_silk = ["2025-02-01", ""] + ["2.0"] * 13
    csv_bytes = (",".join(cols) + "\n" + ",".join(vals_full) + "\n" + ",".join(vals_no_silk) + "\n").encode()

    batches = ncm.parse(
        RawDownloadResult("SSPM_NCM_IMPO_M", "https://infra.datos.gob.ar/test.csv", 200, "text/csv", csv_bytes, "n.csv", "h"),
        impo_target,
    )
    by_code = {b.series_code: b for b in batches}
    assert by_code["IMPO_NCM_62_PRENDAS_PLANO"].rows[0].raw_value == "1.5"
    assert float(by_code["IMPO_CADENA_TEXTIL_TOTAL"].rows[0].raw_value) == 21.0
    assert float(by_code["IMPO_CADENA_TEXTIL_TOTAL"].rows[1].raw_value) == 26.0
