from __future__ import annotations

import csv
from datetime import date
import io
import json
from typing import Any

from app.auditor.engine import StagedInputRow
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult

SIPA_API_SERIES = [
    ("EMPLEO_PRIVADO_TOTAL", "152.1_TL_SIN_EST_2009_M_13"),
    ("EMPLEO_PRIVADO_INDUSTRIA", "152.1_ISTRIASEST_2009_M_33"),
    ("REMUNERACION_INDUSTRIA", "157.1_ISTRIASRAS_C_0_0_25"),
    ("RIPTE_NOMINAL", "158.1_REPTE_0_0_5"),
    ("INDICE_SALARIOS_PRIV_REG", "149.1_SOR_PRIADO_OCTU_0_25"),
]

CEP_PUESTOS_URL = "https://cdn.produccion.gob.ar/cdn-cep/datos-por-actividad/puestos/puestos_privados_mensual_por_clae2.csv"
CEP_SALARIOS_URL = "https://cdn.produccion.gob.ar/cdn-cep/datos-por-actividad/salarios/w-mean/w_mean_privado_mensual_por_clae2.csv"


class SipaLabourConnector(BaseConnector):
    connector_name = "sipa_labour"
    dataset_code = "SIPA_TRABAJO_SERIES"
    schedule_tier = "MONTHLY"

    def discover(self) -> list[dict[str, Any]]:
        ids = ",".join(src_id for _, src_id in SIPA_API_SERIES)
        return [
            {
                "kind": "datos_gob_api",
                "dataset_code": "SIPA_TRABAJO_SERIES",
                "url": f"https://apis.datos.gob.ar/series/api/series/?ids={ids}&start_date=2004-01-01&limit=1000&format=json",
                "filename": "sipa_datos_gob.json",
            },
            {
                "kind": "cep_csv",
                "dataset_code": "CEP_SIPA_PUESTOS_CLAE2",
                "url": CEP_PUESTOS_URL,
                "filename": "cep_puestos_clae2.csv",
                "value_col": "puestos",
                "mapping": {"13": "EMPLEO_PRIVADO_TEXTIL", "14": "EMPLEO_PRIVADO_INDUMENTARIA"},
            },
            {
                "kind": "cep_csv",
                "dataset_code": "CEP_SIPA_SALARIOS_CLAE2",
                "url": CEP_SALARIOS_URL,
                "filename": "cep_salarios_clae2.csv",
                "value_col": "w_mean",
                "mapping": {"13": "REMUNERACION_TEXTIL", "14": "REMUNERACION_INDUMENTARIA"},
            },
        ]

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        client = self._get_client()
        close_after = self.http_client is None
        try:
            resp = client.get(target["url"])
            resp.raise_for_status()
            file_path, sha = self.save_raw_file(target["filename"], resp.content)
            return RawDownloadResult(
                dataset_code=target["dataset_code"],
                source_url=target["url"],
                http_status=resp.status_code,
                content_type=resp.headers.get("content-type"),
                payload_bytes=resp.content,
                file_path=file_path,
                payload_sha256=sha,
                response_headers=dict(resp.headers),
            )
        finally:
            if close_after:
                client.close()

    def parse(self, raw_result: RawDownloadResult, target: dict[str, Any]) -> list[ParsedSeriesBatch]:
        if target["kind"] == "datos_gob_api":
            payload = json.loads(raw_result.payload_bytes.decode("utf-8"))
            meta = payload.get("meta", [])
            data = payload.get("data", [])
            col_by_id = {
                (m.get("field") or {}).get("id"): idx
                for idx, m in enumerate(meta)
                if idx > 0 and (m.get("field") or {}).get("id")
            }
            batches: list[ParsedSeriesBatch] = []
            for series_code, src_id in SIPA_API_SERIES:
                idx = col_by_id.get(src_id)
                if idx is None:
                    batches.append(
                        ParsedSeriesBatch(series_code=series_code, rows=[], structure_context={"columns_ok": False, "unit_ok": True, "frequency_ok": True})
                    )
                    continue
                rows: list[StagedInputRow] = []
                for entry in data:
                    if len(entry) <= idx or entry[idx] is None:
                        continue
                    try:
                        obs_d = date.fromisoformat(str(entry[0])[:10])
                    except ValueError:
                        obs_d = None
                    rows.append(StagedInputRow(observation_date=obs_d, raw_value=str(entry[idx])))
                batches.append(ParsedSeriesBatch(series_code=series_code, rows=rows))
            return batches

        # CEP XXI CLAE2 long CSV: fecha,clae2,<value_col>
        text = raw_result.payload_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
        val_col = target["value_col"]
        mapping: dict[str, str] = target["mapping"]
        cols_ok = "fecha" in fieldnames and "clae2" in fieldnames and val_col in fieldnames
        rows_by_code: dict[str, list[StagedInputRow]] = {code: [] for code in mapping.values()}

        if cols_ok:
            for row in reader:
                clae = (row.get("clae2") or "").strip()
                if clae not in mapping:
                    continue
                raw_v = (row.get(val_col) or "").strip()
                if raw_v == "":
                    continue
                try:
                    obs_d = date.fromisoformat((row.get("fecha") or "").strip()[:10])
                except ValueError:
                    obs_d = None
                rows_by_code[mapping[clae]].append(StagedInputRow(observation_date=obs_d, raw_value=raw_v))

        return [
            ParsedSeriesBatch(
                series_code=series_code,
                rows=rows_by_code[series_code],
                structure_context={"columns_ok": cols_ok, "unit_ok": True, "frequency_ok": True},
            )
            for series_code in mapping.values()
        ]
