from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditor.engine import AuditOutcome, DataAuditor, StagedInputRow
from app.core.config import get_settings
from app.db.models import Dataset, IngestionRun, RawExtraction


@dataclass
class RawDownloadResult:
    dataset_code: str
    source_url: str
    http_status: int | None
    content_type: str | None
    payload_bytes: bytes
    file_path: str
    payload_sha256: str
    response_headers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedSeriesBatch:
    series_code: str
    rows: list[StagedInputRow]
    structure_context: dict[str, Any] = field(default_factory=lambda: {"columns_ok": True, "unit_ok": True, "frequency_ok": True})


class BaseConnector:
    """Modular official-source connector implementing discover->download->validate->parse->normalize->load->audit->publish."""

    connector_name: str = "base"
    dataset_code: str = "UNKNOWN"
    schedule_tier: str = "MONTHLY"

    def __init__(self, db: Session, http_client: httpx.Client | None = None):
        self.db = db
        self.settings = get_settings()
        self.http_client = http_client

    def _get_client(self) -> httpx.Client:
        if self.http_client is not None:
            return self.http_client
        return httpx.Client(
            timeout=self.settings.http_timeout_seconds,
            headers={"User-Agent": "TextileDataHubArgentina/0.1 (Academic Research MVP)"},
            follow_redirects=True,
        )

    def save_raw_file(self, filename: str, content: bytes) -> tuple[str, str]:
        raw_dir = Path(self.settings.raw_data_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        sha256 = hashlib.sha256(content).hexdigest()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = f"{ts}_{sha256[:12]}_{filename}"
        out_path = raw_dir / safe_name
        out_path.write_bytes(content)
        return str(out_path), sha256

    def discover(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def download(self, target: dict[str, Any]) -> RawDownloadResult:
        raise NotImplementedError

    def validate(self, raw_result: RawDownloadResult) -> bool:
        return len(raw_result.payload_bytes) > 0

    def parse(self, raw_result: RawDownloadResult, target: dict[str, Any]) -> list[ParsedSeriesBatch]:
        raise NotImplementedError

    def normalize(self, batches: list[ParsedSeriesBatch]) -> list[ParsedSeriesBatch]:
        for batch in batches:
            batch.rows.sort(key=lambda r: r.observation_date or date.min)
        return batches

    def _record_raw_extraction(self, run_id: int, raw_res: RawDownloadResult) -> RawExtraction:
        ds = self.db.scalar(select(Dataset).where(Dataset.dataset_code == raw_res.dataset_code))
        if ds is None:
            raise ValueError(f"Dataset {raw_res.dataset_code} not found in core.datasets")
        rec = RawExtraction(
            run_id=run_id,
            dataset_id=ds.dataset_id,
            source_url=raw_res.source_url,
            http_status=raw_res.http_status,
            content_type=raw_res.content_type,
            payload_sha256=raw_res.payload_sha256,
            file_path=raw_res.file_path,
            byte_size=len(raw_res.payload_bytes),
            response_headers=raw_res.response_headers,
        )
        self.db.add(rec)
        self.db.flush()
        return rec

    def audit_and_publish(self, run_id: int, raw_id: int, batches: list[ParsedSeriesBatch]) -> list[AuditOutcome]:
        auditor = DataAuditor(self.db)
        outcomes: list[AuditOutcome] = []
        for batch in batches:
            outcome = auditor.audit_and_publish(
                run_id=run_id,
                raw_id=raw_id,
                series_code=batch.series_code,
                rows=batch.rows,
                structure_context=batch.structure_context,
            )
            outcomes.append(outcome)
        return outcomes

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

        downloaded = 0
        inserted = 0
        updated = 0
        rejected = 0
        outcomes: list[AuditOutcome] = []

        try:
            targets = self.discover()
            for target in targets:
                raw_res = self.download(target)
                if not self.validate(raw_res):
                    raise ValueError(f"Validation failed for {raw_res.source_url}")
                raw_rec = self._record_raw_extraction(run_id, raw_res)
                batches = self.parse(raw_res, target)
                batches = self.normalize(batches)
                for b in batches:
                    downloaded += len(b.rows)
                batch_outcomes = self.audit_and_publish(run_id, raw_rec.raw_id, batches)
                for o in batch_outcomes:
                    inserted += o.records_inserted
                    updated += o.records_updated
                    rejected += o.records_rejected
                outcomes.extend(batch_outcomes)

            run.finished_at = datetime.now(timezone.utc)
            run.status = "SUCCESS" if all(o.audit_status in ("VERIFIED", "WARNING") for o in outcomes) else "PARTIAL_WARNING"
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
                failed_run.records_downloaded = downloaded
                failed_run.records_inserted = inserted
                failed_run.records_updated = updated
                failed_run.records_rejected = rejected
                failed_run.error_message = str(exc)[:2000]
                self.db.commit()
            raise
