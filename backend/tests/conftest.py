from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.catalog.seeder import seed_all
from app.core.config import get_settings
from app.db.session import Base
from app.db import models  # noqa: F401


@pytest.fixture(scope="session")
def test_engine():
    settings = get_settings()
    test_url = os.environ.get("TEST_DATABASE_URL", settings.test_database_url)
    eng = create_engine(test_url, pool_pre_ping=True, future=True)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS staging CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS raw CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS core CASCADE"))
        conn.execute(text("CREATE SCHEMA raw"))
        conn.execute(text("CREATE SCHEMA staging"))
        conn.execute(text("CREATE SCHEMA core"))
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    with TestingSession() as db:
        # Clean tables cleanly between tests and re-seed catalog
        for tbl in [
            "core.company_classification_history",
            "core.company_chain_positions",
            "core.companies",
            "core.audit_findings",
            "core.audit_reports",
            "core.observations",
            "core.derived_series_lineage",
            "staging.staged_observations",
            "raw.raw_extractions",
            "core.ingestion_runs",
            "core.series",
            "core.datasets",
            "core.official_sources",
            "core.trade_product_mapping",
            "core.search_synonyms",
            "core.glossary_terms",
        ]:
            db.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))
        db.commit()
        seed_all(db)
        yield db
        db.rollback()
