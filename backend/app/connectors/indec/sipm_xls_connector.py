from __future__ import annotations

from datetime import date
from typing import Any

import xlrd

from app.auditor.engine import StagedInputRow
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult

SIPM_XLS_URL = "https://www.indec.gob.ar/ftp/cuadros/economia/series_sipm_dic2015.xls"

SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "set": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

# Dynamic matching by official SIPM code & description substring (never hardcoded cell rows)
SIPM_SERIES_TARGETS = [
    {"series_code": "IPIM_NIVEL_GENERAL", "code": "NG", "desc_contains": "nivel general"},
    {"series_code": "IPIM_PRODUCTOS_MANUFACTURADOS", "code": "D", "desc_contains": "productos manufacturados"},
    {"series_code": "IPIM_PRODUCTOS_TEXTILES", "code": "17", "desc_contains": "productos textiles"},
    {"series_code": "IPIM_PRENDAS_VESTIR", "code": "18", "desc_contains": "prendas de materiales textiles"},
    {"series_code": "IPIM_ENERGIA_ELECTRICA", "code": "E", "desc_contains": "energía eléctrica"},
]


def _norm_code(val: Any) -> str:
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


class SipmXlsConnector(BaseConnector):
    connector_name = "sipm_xls"
    dataset_code = "INDEC_SIPM_IPIM"
    schedule_tier = "MONTHLY"

    def discover(self) -> list[dict[str, Any]]:
        return [{"dataset_code": self.dataset_code, "url": SIPM_XLS_URL}]

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        client = self._get_client()
        close_after = self.http_client is None
        try:
            resp = client.get(target["url"])
            resp.raise_for_status()
            file_path, sha = self.save_raw_file("series_sipm_dic2015.xls", resp.content)
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
        wb = xlrd.open_workbook(file_contents=raw_result.payload_bytes)
        if "IPIM" not in wb.sheet_names():
            return [
                ParsedSeriesBatch(
                    series_code=t["series_code"],
                    rows=[],
                    structure_context={"columns_ok": False, "reason": "Missing IPIM sheet", "unit_ok": True, "frequency_ok": True},
                )
                for t in SIPM_SERIES_TARGETS
            ]

        sh = wb.sheet_by_name("IPIM")

        # Locate header row dynamically where 'Código' and 'Descripción' appear
        year_row_idx: int | None = None
        month_row_idx: int | None = None
        for r in range(min(15, sh.nrows)):
            c0 = str(sh.cell_value(r, 0)).strip().lower()
            c1 = str(sh.cell_value(r, 1)).strip().lower()
            if "código" in c0 and "descripción" in c1:
                year_row_idx = r
                month_row_idx = r + 1
                break

        if year_row_idx is None or month_row_idx is None:
            return [
                ParsedSeriesBatch(
                    series_code=t["series_code"],
                    rows=[],
                    structure_context={"columns_ok": False, "reason": "Header row not found", "unit_ok": True, "frequency_ok": True},
                )
                for t in SIPM_SERIES_TARGETS
            ]

        # Build column -> (date, is_preliminary) map by forward-filling year headers across months
        col_dates: dict[int, tuple[date, bool]] = {}
        current_year: int | None = None
        for c in range(2, sh.ncols):
            raw_y = sh.cell_value(year_row_idx, c)
            if isinstance(raw_y, (int, float)) and raw_y > 1990:
                current_year = int(raw_y)
            elif isinstance(raw_y, str) and raw_y.strip().isdigit():
                current_year = int(raw_y.strip())

            raw_m = str(sh.cell_value(month_row_idx, c)).strip()
            is_preliminary = "*" in raw_m
            m_clean = raw_m.replace("*", "").strip().lower()
            month_num = SPANISH_MONTHS.get(m_clean)
            if current_year is not None and month_num is not None:
                col_dates[c] = (date(current_year, month_num, 1), is_preliminary)

        # Match rows dynamically by official code + description
        row_by_series: dict[str, int] = {}
        for r in range(month_row_idx + 1, sh.nrows):
            code_val = _norm_code(sh.cell_value(r, 0))
            desc_val = str(sh.cell_value(r, 1)).strip().lower()
            for t in SIPM_SERIES_TARGETS:
                if t["series_code"] in row_by_series:
                    continue
                if code_val == t["code"] and t["desc_contains"] in desc_val:
                    row_by_series[t["series_code"]] = r

        batches: list[ParsedSeriesBatch] = []
        for t in SIPM_SERIES_TARGETS:
            sc = t["series_code"]
            r_idx = row_by_series.get(sc)
            if r_idx is None or not col_dates:
                batches.append(
                    ParsedSeriesBatch(
                        series_code=sc,
                        rows=[],
                        structure_context={"columns_ok": False, "missing_row": t["code"], "unit_ok": True, "frequency_ok": True},
                    )
                )
                continue

            rows: list[StagedInputRow] = []
            for c, (obs_d, is_prelim) in sorted(col_dates.items()):
                cell = sh.cell_value(r_idx, c)
                if cell == "" or cell is None:
                    continue
                rows.append(
                    StagedInputRow(
                        observation_date=obs_d,
                        raw_value=str(cell),
                        is_preliminary=is_prelim,
                    )
                )
            batches.append(ParsedSeriesBatch(series_code=sc, rows=rows))
        return batches
