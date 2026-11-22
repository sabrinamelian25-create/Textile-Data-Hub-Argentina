from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.connectors.bcra.bcra_monetarias_connector import BcraMonetariasConnector
from app.connectors.derived.derived_calculator import DerivedSeriesCalculator
from app.connectors.foreign_trade.ncm_trade_connector import NcmTradeConnector
from app.connectors.indec.datos_gob_series_connector import DatosGobSeriesConnector
from app.connectors.indec.sipm_xls_connector import SipmXlsConnector
from app.connectors.indec.ucii_csv_connector import UciiCsvConnector
from app.connectors.labour.sipa_labour_connector import SipaLabourConnector
from app.db.session import SessionLocal

logger = logging.getLogger("textile_data_hub.scheduler")

CONNECTOR_REGISTRY = {
    "datos_gob_series": DatosGobSeriesConnector,
    "ucii_csv": UciiCsvConnector,
    "sipm_xls": SipmXlsConnector,
    "bcra_monetarias": BcraMonetariasConnector,
    "sipa_labour": SipaLabourConnector,
    "ncm_trade": NcmTradeConnector,
    "derived_calculator": DerivedSeriesCalculator,
}

# Ordered execution to guarantee OFFICIAL series exist before DERIVED calculations
EXECUTION_ORDER = [
    "datos_gob_series",
    "ucii_csv",
    "sipm_xls",
    "bcra_monetarias",
    "sipa_labour",
    "ncm_trade",
    "derived_calculator",
]


def run_connector_by_name(db: Session, connector_name: str) -> dict[str, Any]:
    if connector_name == "all":
        results = []
        for name in EXECUTION_ORDER:
            cls = CONNECTOR_REGISTRY[name]
            results.append(cls(db).run())
        return {"status": "completed", "runs": results}

    if connector_name not in CONNECTOR_REGISTRY:
        raise ValueError(f"Unknown connector: {connector_name}")
    cls = CONNECTOR_REGISTRY[connector_name]
    res = cls(db).run()
    # Recompute derived series whenever an upstream official connector runs
    if connector_name in ("datos_gob_series", "sipa_labour", "ncm_trade"):
        derived_res = DerivedSeriesCalculator(db).run()
        return {"primary_run": res, "derived_run": derived_res}
    return res


def run_tier(tier: str) -> list[dict[str, Any]]:
    tier_upper = tier.upper()
    results = []
    with SessionLocal() as db:
        if tier_upper == "DAILY":
            results.append(BcraMonetariasConnector(db).run())
        elif tier_upper == "MONTHLY":
            for name in ["datos_gob_series", "ucii_csv", "sipm_xls", "sipa_labour", "ncm_trade", "derived_calculator"]:
                try:
                    results.append(CONNECTOR_REGISTRY[name](db).run())
                except Exception as exc:
                    logger.exception("Monthly connector %s failed: %s", name, exc)
                    results.append({"connector": name, "status": "FAILED", "error": str(exc)})
        elif tier_upper == "QUARTERLY":
            results.append(DatosGobSeriesConnector(db, dataset_filter="INDEC_EMAE_PIB").run())
        elif tier_upper == "ALL":
            for name in EXECUTION_ORDER:
                try:
                    results.append(CONNECTOR_REGISTRY[name](db).run())
                except Exception as exc:
                    logger.exception("Connector %s failed: %s", name, exc)
                    results.append({"connector": name, "status": "FAILED", "error": str(exc)})
    return results


def build_scheduler() -> BackgroundScheduler:
    """Frequency-aware scheduler: DAILY for BCRA, MONTHLY for INDEC/SIPA/NCM, QUARTERLY for PIB."""
    scheduler = BackgroundScheduler(timezone=timezone.utc)
    # Daily BCRA update at 22:00 UTC (19:00 ART after market close) Mon-Fri
    scheduler.add_job(
        run_tier,
        trigger="cron",
        args=["DAILY"],
        day_of_week="mon-fri",
        hour=22,
        minute=0,
        id="tier_daily_bcra",
        replace_existing=True,
    )
    # Monthly INDEC/SIPA/NCM update on the 18th of each month (after CPI/IPI/SIPA release window)
    scheduler.add_job(
        run_tier,
        trigger="cron",
        args=["MONTHLY"],
        day=18,
        hour=14,
        minute=0,
        id="tier_monthly_official",
        replace_existing=True,
    )
    # Quarterly National Accounts check on days 25 of Mar, Jun, Sep, Dec
    scheduler.add_job(
        run_tier,
        trigger="cron",
        args=["QUARTERLY"],
        month="3,6,9,12",
        day=25,
        hour=15,
        minute=0,
        id="tier_quarterly_pib",
        replace_existing=True,
    )
    return scheduler


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sched = build_scheduler()
    sched.start()
    logger.info("Textile Data Hub Scheduler started at %s", datetime.now(timezone.utc).isoformat())
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
