from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import func, select

from app.catalog.seeder import seed_all
from app.db.models import Observation, Series
from app.db.session import SessionLocal
from app.scheduler.runner import run_connector_by_name, run_tier
from app.services.industry_structure import import_company_evidence_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Textile Data Hub Argentina CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="Seed official_sources, datasets, series, NCM mapping, synonyms, glossary")

    ingest_p = sub.add_parser("ingest", help="Run official connectors and Data Auditor")
    group = ingest_p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Run all connectors in topological order")
    group.add_argument("--connector", type=str, help="Run a single connector by name")
    group.add_argument("--tier", type=str, choices=["daily", "monthly", "quarterly"], help="Run a schedule tier")

    sub.add_parser("audit-summary", help="Print current Data Auditor verification summary")

    imp_p = sub.add_parser(
        "import-company-evidence",
        help="Import official verifiable corporate evidence CSV through CompanyClassificationAuditor",
    )
    imp_p.add_argument("csv_path", type=str, help="Path to CSV file with official corporate evidence")

    args = parser.parse_args()

    if args.command == "seed":
        with SessionLocal() as db:
            counts = seed_all(db)
            print("Seed completed:", json.dumps(counts, ensure_ascii=False))
        return 0

    if args.command == "ingest":
        if args.all:
            results = run_tier("ALL")
            print(json.dumps(results, ensure_ascii=False, indent=2))
            failed = [r for r in results if r.get("status") == "FAILED"]
            return 1 if failed else 0
        if args.tier:
            results = run_tier(args.tier)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0
        if args.connector:
            with SessionLocal() as db:
                res = run_connector_by_name(db, args.connector)
                print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0

    if args.command == "audit-summary":
        with SessionLocal() as db:
            counts = dict(
                db.execute(select(Series.audit_status, func.count()).group_by(Series.audit_status)).all()
            )
            obs_total = db.scalar(select(func.count()).select_from(Observation).where(Observation.is_current.is_(True)))
            series_rows = db.scalars(select(Series).order_by(Series.series_code.asc())).all()
            print(f"Series counts: {counts} | Current observations: {obs_total}")
            for s in series_rows:
                print(
                    f"  {s.series_code:34s} | {s.series_type:8s} | {s.audit_status:8s} | "
                    f"score={s.quality_score or 0:5.1f} | {s.start_date}..{s.last_observation_date}"
                )
        return 0

    if args.command == "import-company-evidence":
        csv_file = Path(args.csv_path)
        if not csv_file.exists():
            print(f"File not found: {csv_file}", file=sys.stderr)
            return 1
        with SessionLocal() as db:
            stats = import_company_evidence_csv(db, csv_file.read_text(encoding="utf-8-sig"))
            print("Company evidence import completed:", json.dumps(stats, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
