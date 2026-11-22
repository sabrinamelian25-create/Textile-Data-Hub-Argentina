from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
from typing import Any

from sqlalchemy import select

from app.auditor.engine import StagedInputRow
from app.catalog.series_catalog import NCM_EXPO_COLUMNS_50_63, NCM_IMPO_COLUMNS_50_63
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult
from app.db.models import DerivedSeriesLineage, Series

IMPO_NCM_URL = "https://infra.datos.gob.ar/catalog/sspm/dataset/163/distribution/163.3/download/importaciones-clasificadas-nomenclador-comun-mercosur-ncm-2-digitos.csv"
EXPO_NCM_URL = "https://infra.datos.gob.ar/catalog/sspm/dataset/162/distribution/162.3/download/exportaciones-clasificadas-nomenclador-comun-mercosur-ncm-2-digitos-mensual.csv"

IMPO_SERIES_MAP = {
    "IMPO_NCM_52_ALGODON": "m_algodon",
    "IMPO_NCM_54_FILAMENTOS_SINT": "m_filamentos_sinteticos_artificiales",
    "IMPO_NCM_60_TEJIDOS_PUNTO": "m_tejido_punto",
    "IMPO_NCM_61_PRENDAS_PUNTO": "m_prendas_complementos_accesorios_vestir_punto",
    "IMPO_NCM_62_PRENDAS_PLANO": "m_prendas_complementos_accesorios_vestir_emcepto_punto",
    "IMPO_NCM_63_CONFECCIONES_HOGAR": "m_demas_articulos_textiles_confeccionados",
}

EXPO_SERIES_MAP = {
    "EXPO_NCM_51_LANA": "x_lana_pelo_fino_ordinario_hilados_tejidos_crin",
    "EXPO_NCM_52_ALGODON": "x_algodon",
}


class NcmTradeConnector(BaseConnector):
    connector_name = "ncm_trade"
    dataset_code = "SSPM_NCM_IMPO_M"
    schedule_tier = "MONTHLY"

    def discover(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": "impo",
                "dataset_code": "SSPM_NCM_IMPO_M",
                "url": IMPO_NCM_URL,
                "filename": "sspm_ncm_impo_m.csv",
                "series_map": IMPO_SERIES_MAP,
                "chain_cols": NCM_IMPO_COLUMNS_50_63,
                "total_series_code": "IMPO_CADENA_TEXTIL_TOTAL",
            },
            {
                "kind": "expo",
                "dataset_code": "SSPM_NCM_EXPO_M",
                "url": EXPO_NCM_URL,
                "filename": "sspm_ncm_expo_m.csv",
                "series_map": EXPO_SERIES_MAP,
                "chain_cols": NCM_EXPO_COLUMNS_50_63,
                "total_series_code": "EXPO_CADENA_TEXTIL_TOTAL",
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

    def _upsert_chain_lineage(self, target: dict[str, Any]) -> None:
        total_code = target["total_series_code"]
        s = self.db.scalar(select(Series).where(Series.series_code == total_code))
        if s is None:
            return
        cols = [col for _, col in target["chain_cols"]]
        formula = " + ".join(cols)
        lin = self.db.scalar(select(DerivedSeriesLineage).where(DerivedSeriesLineage.derived_series_id == s.series_id))
        now_utc = datetime.now(timezone.utc)
        if lin is None:
            lin = DerivedSeriesLineage(
                derived_series_id=s.series_id,
                source_series_ids=[target["dataset_code"]] + cols,
                formula=formula,
                deflator_series_code=None,
                calculation_version="1.0.0",
                calculated_at=now_utc,
                notes=(
                    "Suma homogénea de los capítulos NCM 50–63 (Sección XI) expresados en millones de USD. "
                    "Cuando SSPM deja en blanco capítulos sin despachos en el mes (p. ej. cap. 50 seda), se suman los capítulos informados siguiendo exactamente la convención oficial de x_total/m_total."
                ),
            )
            self.db.add(lin)
        else:
            lin.source_series_ids = [target["dataset_code"]] + cols
            lin.formula = formula
            lin.calculated_at = now_utc
        self.db.flush()

    def parse(self, raw_result: RawDownloadResult, target: dict[str, Any]) -> list[ParsedSeriesBatch]:
        self._upsert_chain_lineage(target)

        text = raw_result.payload_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        fieldnames = reader.fieldnames or []
        series_map: dict[str, str] = target["series_map"]
        chain_cols = [col for _, col in target["chain_cols"]]
        total_code = target["total_series_code"]

        rows_by_code: dict[str, list[StagedInputRow]] = {code: [] for code in series_map}
        rows_by_code[total_code] = []

        all_chain_cols_present = "indice_tiempo" in fieldnames and all(c in fieldnames for c in chain_cols)

        for row in reader:
            dt_str = (row.get("indice_tiempo") or "").strip()[:10]
            try:
                obs_d = date.fromisoformat(dt_str)
            except ValueError:
                obs_d = None

            for code, col in series_map.items():
                if col not in fieldnames:
                    continue
                val = (row.get(col) or "").strip()
                if val == "":
                    continue
                rows_by_code[code].append(StagedInputRow(observation_date=obs_d, raw_value=val))

            if all_chain_cols_present:
                # Sum all reported NCM 50-63 chapter values in the row (SSPM leaves chapters with no monthly customs flow blank, matching x_total/m_total).
                chapter_vals: list[Decimal] = []
                malformed_cell = False
                for col in chain_cols:
                    cell = (row.get(col) or "").strip()
                    if cell == "":
                        continue
                    try:
                        chapter_vals.append(Decimal(cell))
                    except Exception:
                        malformed_cell = True
                        break
                if not malformed_cell and len(chapter_vals) > 0:
                    total_sum = sum(chapter_vals, Decimal("0"))
                    rows_by_code[total_code].append(StagedInputRow(observation_date=obs_d, raw_value=str(total_sum)))

        batches: list[ParsedSeriesBatch] = []
        for code, col in series_map.items():
            cols_ok = "indice_tiempo" in fieldnames and col in fieldnames
            batches.append(
                ParsedSeriesBatch(
                    series_code=code,
                    rows=rows_by_code[code],
                    structure_context={"columns_ok": cols_ok, "unit_ok": True, "frequency_ok": True},
                )
            )
        batches.append(
            ParsedSeriesBatch(
                series_code=total_code,
                rows=rows_by_code[total_code],
                structure_context={"columns_ok": all_chain_cols_present, "unit_ok": True, "frequency_ok": True},
            )
        )
        return batches
