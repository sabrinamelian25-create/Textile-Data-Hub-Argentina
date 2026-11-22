from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditor.engine import DataAuditor, StagedInputRow
from app.db.models import (
    Dataset,
    DerivedSeriesLineage,
    IngestionRun,
    Observation,
    RawExtraction,
    Series,
)


class DerivedSeriesCalculator:
    """Computes DERIVED series strictly from VERIFIED official core.observations and audits them."""

    connector_name = "derived_calculator"
    dataset_code = "TDH_DERIVED_PIPELINE"
    schedule_tier = "MONTHLY"

    def __init__(self, db: Session):
        self.db = db

    def _get_verified_obs_map(self, series_code: str) -> tuple[Series, dict[date, Decimal]]:
        s = self.db.scalar(select(Series).where(Series.series_code == series_code))
        if s is None or s.audit_status not in ("VERIFIED", "WARNING"):
            raise ValueError(f"Source series {series_code} is not available in VERIFIED/WARNING state")
        obs = self.db.scalars(
            select(Observation)
            .where(Observation.series_id == s.series_id, Observation.is_current.is_(True))
            .order_by(Observation.observation_date.asc())
        ).all()
        return s, {o.observation_date: Decimal(str(o.value)) for o in obs}

    def _upsert_lineage(
        self,
        derived_code: str,
        source_codes: list[str],
        formula: str,
        deflator_code: str | None = None,
        notes: str | None = None,
    ) -> None:
        ds = self.db.scalar(select(Series).where(Series.series_code == derived_code))
        if ds is None:
            return
        lin = self.db.scalar(select(DerivedSeriesLineage).where(DerivedSeriesLineage.derived_series_id == ds.series_id))
        now_utc = datetime.now(timezone.utc)
        if lin is None:
            lin = DerivedSeriesLineage(
                derived_series_id=ds.series_id,
                source_series_ids=source_codes,
                formula=formula,
                deflator_series_code=deflator_code,
                calculation_version="1.0.0",
                calculated_at=now_utc,
                notes=notes,
            )
            self.db.add(lin)
        else:
            lin.source_series_ids = source_codes
            lin.formula = formula
            lin.deflator_series_code = deflator_code
            lin.calculated_at = now_utc
            lin.notes = notes
        self.db.flush()

    def run(self) -> dict[str, Any]:
        run = IngestionRun(
            connector_name=self.connector_name,
            dataset_code=self.dataset_code,
            schedule_tier=self.schedule_tier,
            status="RUNNING",
        )
        self.db.add(run)
        self.db.commit()
        run_id = run.run_id

        try:
            ds = self.db.scalar(select(Dataset).where(Dataset.dataset_code == self.dataset_code))
            assert ds is not None

            # Prepare derived specs
            specs: list[tuple[str, list[str], str, str | None, str, list[StagedInputRow]]] = []

            # 1. PRECIO_RELATIVO_INDUMENTARIA = (IPC_PRENDAS_CALZADO / IPC_NIVEL_GENERAL) * 100
            _, ipc_prendas = self._get_verified_obs_map("IPC_PRENDAS_CALZADO")
            _, ipc_gral = self._get_verified_obs_map("IPC_NIVEL_GENERAL")
            common_ipc = sorted(set(ipc_prendas) & set(ipc_gral))
            rel_rows = [
                StagedInputRow(
                    observation_date=d,
                    raw_value=str(((ipc_prendas[d] / ipc_gral[d]) * Decimal("100")).quantize(Decimal("0.000001"))),
                )
                for d in common_ipc
                if ipc_gral[d] != 0
            ]
            specs.append((
                "PRECIO_RELATIVO_INDUMENTARIA",
                ["IPC_PRENDAS_CALZADO", "IPC_NIVEL_GENERAL"],
                "(IPC_PRENDAS_CALZADO / IPC_NIVEL_GENERAL) * 100",
                "IPC_NIVEL_GENERAL",
                "Ambas series comparten base diciembre 2016 = 100.",
                rel_rows,
            ))

            # 2. IMPO_PRENDAS_TERMINADAS_TOTAL = IMPO_NCM_61_PRENDAS_PUNTO + IMPO_NCM_62_PRENDAS_PLANO
            _, impo_61 = self._get_verified_obs_map("IMPO_NCM_61_PRENDAS_PUNTO")
            _, impo_62 = self._get_verified_obs_map("IMPO_NCM_62_PRENDAS_PLANO")
            common_prendas = sorted(set(impo_61) & set(impo_62))
            prendas_rows = [
                StagedInputRow(
                    observation_date=d,
                    raw_value=str((impo_61[d] + impo_62[d]).quantize(Decimal("0.000001"))),
                )
                for d in common_prendas
            ]
            specs.append((
                "IMPO_PRENDAS_TERMINADAS_TOTAL",
                ["IMPO_NCM_61_PRENDAS_PUNTO", "IMPO_NCM_62_PRENDAS_PLANO"],
                "IMPO_NCM_61_PRENDAS_PUNTO + IMPO_NCM_62_PRENDAS_PLANO",
                None,
                "Suma homogénea de importaciones CIF en millones de USD (NCM 61 + NCM 62).",
                prendas_rows,
            ))

            # 3. SALDO_COMERCIAL_TEXTIL = EXPO_CADENA_TEXTIL_TOTAL - IMPO_CADENA_TEXTIL_TOTAL
            _, expo_tot = self._get_verified_obs_map("EXPO_CADENA_TEXTIL_TOTAL")
            _, impo_tot = self._get_verified_obs_map("IMPO_CADENA_TEXTIL_TOTAL")
            common_trade = sorted(set(expo_tot) & set(impo_tot))
            saldo_rows = [
                StagedInputRow(
                    observation_date=d,
                    raw_value=str((expo_tot[d] - impo_tot[d]).quantize(Decimal("0.000001"))),
                )
                for d in common_trade
            ]
            specs.append((
                "SALDO_COMERCIAL_TEXTIL",
                ["EXPO_CADENA_TEXTIL_TOTAL", "IMPO_CADENA_TEXTIL_TOTAL"],
                "EXPO_CADENA_TEXTIL_TOTAL (FOB) - IMPO_CADENA_TEXTIL_TOTAL (CIF)",
                None,
                "Sigue la convención oficial del INDEC (Exportaciones FOB menos Importaciones CIF).",
                saldo_rows,
            ))

            # 4. SALARIO_REAL_RIPTE normalized to 2016-12-01 = 100
            _, ripte = self._get_verified_obs_map("RIPTE_NOMINAL")
            base_d = date(2016, 12, 1)
            common_ripte = sorted(set(ripte) & set(ipc_gral))
            if base_d not in ripte or base_d not in ipc_gral or ipc_gral[base_d] == 0:
                raise ValueError("Missing base date 2016-12-01 for SALARIO_REAL_RIPTE")
            base_ratio_ripte = ripte[base_d] / ipc_gral[base_d]
            ripte_real_rows = [
                StagedInputRow(
                    observation_date=d,
                    raw_value=str((((ripte[d] / ipc_gral[d]) / base_ratio_ripte) * Decimal("100")).quantize(Decimal("0.000001"))),
                )
                for d in common_ripte
                if ipc_gral[d] != 0
            ]
            specs.append((
                "SALARIO_REAL_RIPTE",
                ["RIPTE_NOMINAL", "IPC_NIVEL_GENERAL"],
                "((RIPTE_NOMINAL_t / IPC_NIVEL_GENERAL_t) / (RIPTE_NOMINAL_2016_12 / IPC_NIVEL_GENERAL_2016_12)) * 100",
                "IPC_NIVEL_GENERAL",
                "Deflactado por IPC Nivel General Nacional (base dic 2016 = 100).",
                ripte_real_rows,
            ))

            # 5. SALARIO_REAL_INDUSTRIA normalized to 2016-12-01 = 100
            _, remun_ind = self._get_verified_obs_map("REMUNERACION_INDUSTRIA")
            common_remun = sorted(set(remun_ind) & set(ipc_gral))
            if base_d not in remun_ind or ipc_gral[base_d] == 0:
                raise ValueError("Missing base date 2016-12-01 for SALARIO_REAL_INDUSTRIA")
            base_ratio_remun = remun_ind[base_d] / ipc_gral[base_d]
            remun_real_rows = [
                StagedInputRow(
                    observation_date=d,
                    raw_value=str((((remun_ind[d] / ipc_gral[d]) / base_ratio_remun) * Decimal("100")).quantize(Decimal("0.000001"))),
                )
                for d in common_remun
                if ipc_gral[d] != 0
            ]
            specs.append((
                "SALARIO_REAL_INDUSTRIA",
                ["REMUNERACION_INDUSTRIA", "IPC_NIVEL_GENERAL"],
                "((REMUNERACION_INDUSTRIA_t / IPC_NIVEL_GENERAL_t) / (REMUNERACION_INDUSTRIA_2016_12 / IPC_NIVEL_GENERAL_2016_12)) * 100",
                "IPC_NIVEL_GENERAL",
                "Conserva el pico semestral de aguinaldo (SAC) en junio y diciembre.",
                remun_real_rows,
            ))

            # Create a deterministic raw extraction audit artifact for the derived computation
            from app.connectors.base import BaseConnector
            helper = BaseConnector(self.db)
            summary_payload = {
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "series": [
                    {"code": c, "sources": src, "formula": f, "rows": len(r)}
                    for c, src, f, _, _, r in specs
                ],
            }
            raw_bytes = json.dumps(summary_payload, ensure_ascii=False, indent=2).encode("utf-8")
            file_path, sha = helper.save_raw_file("derived_calculation.json", raw_bytes)
            raw_rec = RawExtraction(
                run_id=run_id,
                dataset_id=ds.dataset_id,
                source_url="https://internal.textiledatahub.local/derived",
                http_status=200,
                content_type="application/json",
                payload_sha256=sha,
                file_path=file_path,
                byte_size=len(raw_bytes),
                response_headers={"calculator_version": "1.0.0"},
            )
            self.db.add(raw_rec)
            self.db.flush()

            auditor = DataAuditor(self.db)
            downloaded = 0
            inserted = 0
            updated = 0
            rejected = 0
            outcomes = []

            for code, src_codes, formula, defl, notes, rows in specs:
                self._upsert_lineage(code, src_codes, formula, defl, notes)
                downloaded += len(rows)
                o = auditor.audit_and_publish(
                    run_id=run_id,
                    raw_id=raw_rec.raw_id,
                    series_code=code,
                    rows=rows,
                )
                inserted += o.records_inserted
                updated += o.records_updated
                rejected += o.records_rejected
                outcomes.append(o)

            run.finished_at = datetime.now(timezone.utc)
            run.status = "SUCCESS"
            run.records_downloaded = downloaded
            run.records_inserted = inserted
            run.records_updated = updated
            run.records_rejected = rejected
            self.db.commit()
            return {
                "run_id": run_id,
                "connector": self.connector_name,
                "status": run.status,
                "downloaded": downloaded,
                "inserted": inserted,
                "updated": updated,
                "rejected": rejected,
                "series_audited": [
                    {"series_code": o.series_code, "audit_status": o.audit_status, "quality_score": o.quality_score}
                    for o in outcomes
                ],
            }
        except Exception as exc:
            self.db.rollback()
            failed_run = self.db.get(IngestionRun, run_id)
            if failed_run is not None:
                failed_run.finished_at = datetime.now(timezone.utc)
                failed_run.status = "FAILED"
                failed_run.error_message = str(exc)[:2000]
                self.db.commit()
            raise
