from __future__ import annotations

from datetime import date
import json
from typing import Any

from app.auditor.engine import StagedInputRow
from app.connectors.base import BaseConnector, ParsedSeriesBatch, RawDownloadResult

# Series served via official Datos Argentina Series API (apis.datos.gob.ar/series/api/series)
DATOS_GOB_GROUPS = [
    {
        "dataset_code": "INDEC_IPI_MANUF",
        "filename": "datos_gob_ipi.json",
        "series": [
            ("IPI_TEXTILES", "453.2_PRODUCTOS_LES_0_0_18_32"),
            ("IPI_FIBRAS_TEXTILES", "453.2_PREPARACIOTIL_0_0_29_69"),
            ("IPI_HILADOS_ALGODON", "453.2_HILADOS_ALDON_0_0_15_97"),
            ("IPI_TEJIDOS_ACABADO", "453.2_TEJIDOS_ACLES_0_0_34_1"),
            ("IPI_OTROS_TEXTILES", "453.2_OTROS_PRODLES_0_0_24_67"),
            ("IPI_PRENDAS_VESTIR", "453.2_PRENDAS_VETIR_0_0_14_10"),
            ("IPI_NIVEL_GENERAL_ORIG", "453.1_SERIE_ORIGNAL_0_0_14_46"),
        ],
    },
    {
        "dataset_code": "INDEC_IPC_NACIONAL",
        "filename": "datos_gob_ipc.json",
        "series": [
            ("IPC_PRENDAS_CALZADO", "146.3_IPRENDANAL_DICI_M_35"),
            ("IPC_VIVIENDA_ENERGIA", "146.3_IVIVIENNAL_DICI_M_52"),
            ("IPC_NIVEL_GENERAL", "148.3_INIVELNAL_DICI_M_26"),
        ],
    },
    {
        "dataset_code": "INDEC_EMAE_PIB",
        "filename": "datos_gob_emae.json",
        "series": [
            ("EMAE_INDUSTRIA", "11.3_VMASD_2004_M_23"),
            ("EMAE_NIVEL_GENERAL_DESEST", "143.3_NO_PR_2004_A_31"),
        ],
    },
    {
        "dataset_code": "INDEC_EMAE_PIB",
        "filename": "datos_gob_pib.json",
        "series": [
            ("PIB_PRECIOS_CONSTANTES", "9.2_PP2_2004_T_16"),
        ],
    },
    {
        "dataset_code": "INDEC_ICA_MENSUAL",
        "filename": "datos_gob_ica.json",
        "series": [
            ("EXPO_TOTALES_ARG", "75.3_IETG_0_M_31"),
            ("IMPO_TOTALES_ARG", "76.3_ITG_0_M_17"),
        ],
    },
]


class DatosGobSeriesConnector(BaseConnector):
    connector_name = "datos_gob_series"
    dataset_code = "INDEC_IPI_MANUF"
    schedule_tier = "MONTHLY"

    def __init__(self, db, http_client=None, dataset_filter: str | None = None):
        super().__init__(db, http_client=http_client)
        self.dataset_filter = dataset_filter

    def discover(self) -> list[dict[str, Any]]:
        if self.dataset_filter:
            return [g for g in DATOS_GOB_GROUPS if g["dataset_code"] == self.dataset_filter]
        return list(DATOS_GOB_GROUPS)

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        ids = ",".join(src_id for _, src_id in target["series"])
        url = f"https://apis.datos.gob.ar/series/api/series/?ids={ids}&start_date=2004-01-01&limit=1000&format=json"
        client = self._get_client()
        close_after = self.http_client is None
        try:
            resp = client.get(url)
            resp.raise_for_status()
            raw_bytes = resp.content
            file_path, sha = self.save_raw_file(target["filename"], raw_bytes)
            return RawDownloadResult(
                dataset_code=target["dataset_code"],
                source_url=url,
                http_status=resp.status_code,
                content_type=resp.headers.get("content-type"),
                payload_bytes=raw_bytes,
                file_path=file_path,
                payload_sha256=sha,
                response_headers=dict(resp.headers),
            )
        finally:
            if close_after:
                client.close()

    def parse(self, raw_result: RawDownloadResult, target: dict[str, Any]) -> list[ParsedSeriesBatch]:
        payload = json.loads(raw_result.payload_bytes.decode("utf-8"))
        meta = payload.get("meta", [])
        data = payload.get("data", [])

        # Build column index mapping by meta[i]["field"]["id"] (never rely purely on positional order)
        col_index_by_src_id: dict[str, int] = {}
        for idx, m in enumerate(meta):
            if idx == 0:
                continue
            field_info = m.get("field") or {}
            sid = field_info.get("id")
            if sid:
                col_index_by_src_id[sid] = idx

        batches: list[ParsedSeriesBatch] = []
        for series_code, src_id in target["series"]:
            col_idx = col_index_by_src_id.get(src_id)
            if col_idx is None:
                batches.append(
                    ParsedSeriesBatch(
                        series_code=series_code,
                        rows=[],
                        structure_context={"columns_ok": False, "missing_id": src_id, "unit_ok": True, "frequency_ok": True},
                    )
                )
                continue

            rows: list[StagedInputRow] = []
            for entry in data:
                if not entry or len(entry) <= col_idx:
                    continue
                val = entry[col_idx]
                if val is None:
                    # Different start dates across series inside same API call yield null for unstarted periods; skip rather than fabricate.
                    continue
                dt_str = str(entry[0])[:10]
                try:
                    obs_d = date.fromisoformat(dt_str)
                except ValueError:
                    obs_d = None
                rows.append(StagedInputRow(observation_date=obs_d, raw_value=str(val), is_preliminary=False))

            batches.append(ParsedSeriesBatch(series_code=series_code, rows=rows))
        return batches
