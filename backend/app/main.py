from __future__ import annotations

from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api.routes.auditor import router as auditor_router
from app.api.routes.industry_structure import router as industry_structure_router
from app.api.routes.public import router as public_router
from app.core.config import get_settings
from app.db.models import Observation
from app.db.session import SessionLocal
from app.scheduler.runner import build_scheduler, run_tier

settings = get_settings()


def _background_initial_ingest() -> None:
    try:
        with SessionLocal() as db:
            obs_count = db.scalar(select(func.count()).select_from(Observation)) or 0
        if obs_count == 0:
            run_tier("ALL")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.auto_ingest_if_empty:
        threading.Thread(target=_background_initial_ingest, daemon=True).start()
    if settings.enable_scheduler:
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Plataforma académica de datos económicos oficiales sobre la industria textil, indumentaria, "
        "comercio exterior (NCM 50–63), empleo sectorial (SIPA/CLAE), precios y contexto macroeconómico de Argentina."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(auditor_router)
app.include_router(industry_structure_router)
