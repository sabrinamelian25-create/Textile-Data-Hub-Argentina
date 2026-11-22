from __future__ import annotations

from datetime import date
import json
import time
from typing import Any

from app.auditor.engine import StagedInputRow
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult

BCRA_SERIES_SPECS = [
    {"series_code": "TC_MAYORISTA_BCRA", "id_variable": 5, "desde": "2016-01-01"},
    {"series_code": "TASA_BADLAR_PRIVADOS", "id_variable": 7, "desde": "2016-01-01"},
    {"series_code": "PRESTAMOS_SECTOR_PRIVADO", "id_variable": 26, "desde": "2016-01-01"},
]


class BcraMonetariasConnector(BaseConnector):
    connector_name = "bcra_monetarias"
    dataset_code = "BCRA_MONETARIAS_V4"
    schedule_tier = "DAILY"

    def discover(self) -> list[dict[str, Any]]:
        return list(BCRA_SERIES_SPECS)

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        vid = target["id_variable"]
        desde = target["desde"]
        base_url = f"https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{vid}"
        client = self._get_client()
        close_after = self.http_client is None

        all_detalle: list[dict[str, Any]] = []
        last_status = 200
        last_ct = "application/json"
        last_headers: dict[str, Any] = {}
        offset = 0
        limit = 3000

        try:
            while True:
                url = f"{base_url}?desde={desde}&limit={limit}&offset={offset}"
                resp = client.get(url)
                resp.raise_for_status()
                last_status = resp.status_code
                last_ct = resp.headers.get("content-type", "application/json")
                last_headers = dict(resp.headers)
                j = resp.json()
                results = j.get("results") or []
                if not results:
                    break
                det = results[0].get("detalle") or []
                all_detalle.extend(det)
                if len(det) < limit:
                    break
                offset += limit
                time.sleep(0.4)

            combined = {"idVariable": vid, "desde": desde, "count": len(all_detalle), "detalle": all_detalle}
            raw_bytes = json.dumps(combined, ensure_ascii=False).encode("utf-8")
            file_path, sha = self.save_raw_file(f"bcra_var_{vid}.json", raw_bytes)
            return RawDownloadResult(
                dataset_code=self.dataset_code,
                source_url=base_url,
                http_status=last_status,
                content_type=last_ct,
                payload_bytes=raw_bytes,
                file_path=file_path,
                payload_sha256=sha,
                response_headers=last_headers,
            )
        finally:
            if close_after:
                client.close()

    def parse(self, raw_result: RawDownloadResult, target: dict[str, Any]) -> list[ParsedSeriesBatch]:
        j = json.loads(raw_result.payload_bytes.decode("utf-8"))
        detalle = j.get("detalle") or []
        seen_dates: set[date] = set()
        rows: list[StagedInputRow] = []

        for item in detalle:
            dt_str = str(item.get("fecha") or "")[:10]
            val = item.get("valor")
            if val is None:
                continue
            try:
                obs_d = date.fromisoformat(dt_str)
            except ValueError:
                obs_d = None
            if obs_d is not None:
                if obs_d in seen_dates:
                    continue
                seen_dates.add(obs_d)
            rows.append(StagedInputRow(observation_date=obs_d, raw_value=str(val), is_preliminary=False))

        return [ParsedSeriesBatch(series_code=target["series_code"], rows=rows)]
