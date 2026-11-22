from __future__ import annotations

import csv
from datetime import date
import io
from typing import Any

from app.auditor.engine import StagedInputRow
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult

UCII_URL = "https://infra.datos.gob.ar/catalog/sspm/dataset/31/distribution/31.3/download/utilizacion-capacidad-instalada-industria-valores-mensuales-base-2004.csv"


class UciiCsvConnector(BaseConnector):
    connector_name = "ucii_csv"
    dataset_code = "INDEC_UCII_2004"
    schedule_tier = "MONTHLY"

    def discover(self) -> list[dict[str, Any]]:
        return [{"dataset_code": self.dataset_code, "url": UCII_URL}]

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        client = self._get_client()
        close_after = self.http_client is None
        try:
            resp = client.get(target["url"])
            resp.raise_for_status()
            file_path, sha = self.save_raw_file("ucii_31_3.csv", resp.content)
            return RawDownloadResult(
                dataset_code=self.dataset_code,
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
        text = raw_result.payload_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []

        col_map = {
            "UCII_TEXTILES": "ucii_productos_textiles",
            "UCII_NIVEL_GENERAL": "ucii_nivel_general",
        }
        rows_by_code: dict[str, list[StagedInputRow]] = {k: [] for k in col_map}

        for row in reader:
            dt_str = (row.get("indice_tiempo") or "").strip()[:10]
            try:
                obs_d = date.fromisoformat(dt_str)
            except ValueError:
                obs_d = None
            for series_code, col_name in col_map.items():
                if col_name not in fieldnames:
                    continue
                val = (row.get(col_name) or "").strip()
                if val == "":
                    continue
                rows_by_code[series_code].append(StagedInputRow(observation_date=obs_d, raw_value=val))

        batches: list[ParsedSeriesBatch] = []
        for series_code, col_name in col_map.items():
            cols_ok = "indice_tiempo" in fieldnames and col_name in fieldnames
            batches.append(
                ParsedSeriesBatch(
                    series_code=series_code,
                    rows=rows_by_code[series_code],
                    structure_context={"columns_ok": cols_ok, "unit_ok": True, "frequency_ok": True},
                )
            )
        return batches
