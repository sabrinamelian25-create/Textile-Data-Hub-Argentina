from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Company, CompanyClassificationHistory
from app.db.session import get_db
from app.services.industry_structure import (
    CompanyClassificationAuditor,
    DIMENSIONS_TAXONOMY,
    build_structural_research_frame,
    create_company,
    get_industry_structure_summary,
    list_structural_research_presets,
    query_companies,
    render_companies_csv,
    serialize_company,
)

router = APIRouter(prefix="/api/industry-structure", tags=["industry-structure"])


class CompanyCreateRequest(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=255, description="Razón social legal")
    brand_name: str | None = Field(None, max_length=255, description="Nombre comercial / marca (opcional)")
    cuit: str | None = Field(None, max_length=20, description="CUIT oficial (opcional)")
    notes: str | None = Field(None, description="Notas metodológicas (opcional)")


class ClassificationCreateRequest(BaseModel):
    dimension: str = Field(..., description="SIZE | ORIGIN | PRODUCTION_MODEL | CHAIN_POSITION")
    classification: str = Field(..., description="Valor canónico de la dimensión o UNKNOWN")
    valid_from: date = Field(..., description="Fecha de inicio de vigencia de la evidencia oficial")
    valid_to: date | None = Field(None, description="Fecha de fin de vigencia (NULL si vigente)")
    official_source_id: int | None = Field(None, description="ID en core.official_sources (obligatorio si != UNKNOWN)")
    source_url: str | None = Field(None, description="URL oficial perteneciente al dominio aprobado del organismo")
    evidence: str = Field(..., description="Referencia documental oficial verificable (resolución, balance CNV, edicto BORA, etc.)")


class ResearchBuilderRequest(BaseModel):
    preset_id: str | None = Field(None, description="ID de preset estructural (opcional)")
    sizes: list[str] = Field(default_factory=list)
    origins: list[str] = Field(default_factory=list)
    production_models: list[str] = Field(default_factory=list)
    chain_positions: list[str] = Field(default_factory=list)
    custom_focus: str | None = Field(None, max_length=300)


def _split_multi(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for item in values:
        for part in item.split(","):
            clean = part.strip()
            if clean:
                out.append(clean)
    return out


@router.get("/taxonomy", summary="Taxonomía oficial de las 4 dimensiones independientes y regla de fuentes")
def get_taxonomy() -> dict[str, Any]:
    return DIMENSIONS_TAXONOMY


@router.get("/summary", summary="Resumen cuantitativo por dimensiones independientes y estado de auditoría")
def get_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    return get_industry_structure_summary(db)


@router.get("/companies", summary="Listar y filtrar empresas combinando Tamaño, Origen, Modelo productivo y Posición en la cadena")
def list_companies(
    size: list[str] | None = Query(None, description="MICRO, SMALL, MEDIUM, LARGE, UNKNOWN o preset PYME"),
    origin: list[str] | None = Query(None, description="NATIONAL, FOREIGN, UNKNOWN"),
    production_model: list[str] | None = Query(
        None,
        description="LOCAL_PRIMARY, LOCAL_IMPORTED_INPUTS, MIXED, MAJORITY_IMPORTED_FINISHED, IMPORTED_FINISHED, UNKNOWN",
    ),
    chain_position: list[str] | None = Query(
        None,
        description="FIBER, YARN, FABRIC, APPAREL, BRAND, RETAIL, INTEGRATED, UNKNOWN",
    ),
    chain_match: str = Query("any", pattern="^(any|all)$", description="Coincidir con cualquiera (any) o todas (all) las posiciones"),
    classification_status: str | None = Query(None),
    q: str | None = Query(None, description="Búsqueda por razón social, marca o CUIT"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    companies = query_companies(
        db,
        sizes=_split_multi(size),
        origins=_split_multi(origin),
        production_models=_split_multi(production_model),
        chain_positions=_split_multi(chain_position),
        chain_match=chain_match,
        classification_status=classification_status,
        q=q,
    )
    return {
        "count": len(companies),
        "filters_applied": {
            "size": _split_multi(size),
            "origin": _split_multi(origin),
            "production_model": _split_multi(production_model),
            "chain_position": _split_multi(chain_position),
            "chain_match": chain_match,
            "classification_status": classification_status,
            "q": q,
        },
        "items": [serialize_company(c, include_history=False) for c in companies],
    }


@router.post("/companies", status_code=201, summary="Registrar firma en estado inicial UNKNOWN en todas las dimensiones")
def register_company(payload: CompanyCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        company = create_company(
            db,
            legal_name=payload.legal_name,
            brand_name=payload.brand_name,
            cuit=payload.cuit,
            notes=payload.notes,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    loaded = db.scalar(
        select(Company)
        .options(
            joinedload(Company.chain_positions),
            joinedload(Company.classification_history).joinedload(CompanyClassificationHistory.official_source),
        )
        .where(Company.company_id == company.company_id)
    )
    assert loaded is not None
    return serialize_company(loaded, include_history=True)


@router.get("/companies/{company_id}", summary="Detalle de empresa e historial completo de clasificaciones auditadas")
def get_company_detail(company_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    company = db.scalar(
        select(Company)
        .options(
            joinedload(Company.chain_positions),
            joinedload(Company.classification_history).joinedload(CompanyClassificationHistory.official_source),
        )
        .where(Company.company_id == company_id)
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Empresa company_id={company_id} no encontrada.")
    return serialize_company(company, include_history=True)


@router.post(
    "/companies/{company_id}/classifications",
    status_code=201,
    summary="Registrar clasificación para una dimensión independiente con auditoría de fuente oficial",
)
def add_company_classification(
    company_id: int,
    payload: ClassificationCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    auditor = CompanyClassificationAuditor(db)
    try:
        result = auditor.audit_and_record(
            company_id=company_id,
            dimension=payload.dimension,
            classification=payload.classification,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            official_source_id=payload.official_source_id,
            source_url=payload.source_url,
            evidence=payload.evidence,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    company = db.scalar(
        select(Company)
        .options(
            joinedload(Company.chain_positions),
            joinedload(Company.classification_history).joinedload(CompanyClassificationHistory.official_source),
        )
        .where(Company.company_id == company_id)
    )
    assert company is not None
    return {
        "audit_result": {
            "history_id": result.history_id,
            "dimension": result.dimension,
            "classification": result.classification,
            "audit_status": result.audit_status,
            "audit_notes": result.audit_notes,
            "promoted_to_company": result.promoted_to_company,
        },
        "company": serialize_company(company, include_history=True),
    }


@router.get("/research-presets", summary="Ejes de investigación estructurados por dimensiones empresariales")
def get_research_presets(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return list_structural_research_presets(db)


@router.post("/research-builder", summary="Construir marco exploratorio no causal combinando dimensiones de estructura empresarial")
def run_research_builder(payload: ResearchBuilderRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return build_structural_research_frame(
            db,
            preset_id=payload.preset_id,
            sizes=payload.sizes,
            origins=payload.origins,
            production_models=payload.production_models,
            chain_positions=payload.chain_positions,
            custom_focus=payload.custom_focus,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/export", summary="Exportar empresas filtradas con dimensiones independientes (CSV o JSON)")
def export_companies(
    format: str = Query("csv", pattern="^(csv|json)$"),
    size: list[str] | None = Query(None),
    origin: list[str] | None = Query(None),
    production_model: list[str] | None = Query(None),
    chain_position: list[str] | None = Query(None),
    chain_match: str = Query("any", pattern="^(any|all)$"),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    companies = query_companies(
        db,
        sizes=_split_multi(size),
        origins=_split_multi(origin),
        production_models=_split_multi(production_model),
        chain_positions=_split_multi(chain_position),
        chain_match=chain_match,
        q=q,
    )
    if format == "json":
        return {
            "module": "industry_structure_experimental",
            "count": len(companies),
            "items": [serialize_company(c, include_history=False) for c in companies],
        }
    payload = render_companies_csv(companies)
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="estructura_industria_textil.csv"'},
    )
