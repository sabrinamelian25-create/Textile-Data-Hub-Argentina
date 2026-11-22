from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
import io
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auditor.engine import _domain_matches
from app.db.models import (
    Company,
    CompanyChainPosition,
    CompanyClassificationHistory,
    OfficialSource,
    Series,
)

# ---------------------------------------------------------------------------
# CANONICAL INDEPENDENT DIMENSIONS TAXONOMY
# Never mix size, origin, production model, and chain position into one label.
# ---------------------------------------------------------------------------

DIMENSION_CODES = ("SIZE", "ORIGIN", "PRODUCTION_MODEL", "CHAIN_POSITION")

SIZE_OPTIONS: list[dict[str, str]] = [
    {"code": "MICRO", "label": "Micro", "description": "Categoría Micro según topes oficiales vigentes (Registro MiPyME / SEPyME)."},
    {"code": "SMALL", "label": "Pequeña", "description": "Categoría Pequeña según topes oficiales vigentes (Registro MiPyME / SEPyME)."},
    {"code": "MEDIUM", "label": "Mediana", "description": "Categoría Mediana (Tramo 1 o 2) según topes oficiales vigentes (Registro MiPyME / SEPyME)."},
    {"code": "LARGE", "label": "Grande", "description": "Firma que supera los topes oficiales MiPyME verificada por balances auditados (CNV/IGJ) o registros oficiales."},
    {"code": "UNKNOWN", "label": "No determinado", "description": "Sin evidencia oficial verificable suficiente para determinar tamaño empresarial."},
]

ORIGIN_OPTIONS: list[dict[str, str]] = [
    {"code": "NATIONAL", "label": "Nacional", "description": "Capital controlante verificado de origen argentino según registros societarios oficiales (IGJ/CNV/BORA)."},
    {"code": "FOREIGN", "label": "Extranjera", "description": "Capital controlante o sociedad matriz verificada de origen extranjero según registros oficiales (IGJ art. 118/123, CNV, BORA)."},
    {"code": "UNKNOWN", "label": "No determinado", "description": "Sin evidencia oficial verificable suficiente sobre la nacionalidad del capital controlante."},
]

PRODUCTION_MODEL_OPTIONS: list[dict[str, str]] = [
    {"code": "LOCAL_PRIMARY", "label": "Producción principalmente local", "description": "Manufactura predominantemente en territorio argentino verificada en memorias/balances CNV o registros industriales oficiales."},
    {"code": "LOCAL_IMPORTED_INPUTS", "label": "Producción local con insumos importados", "description": "Proceso productivo local con uso verificado de fibras, hilados o tejidos importados según documentación oficial."},
    {"code": "MIXED", "label": "Producción mixta", "description": "Combinación verificada de fabricación local e importación de bienes terminados en balances o registros oficiales."},
    {"code": "MAJORITY_IMPORTED_FINISHED", "label": "Importación mayoritaria de producto terminado", "description": "Predominio verificado de importación de prendas o textiles terminados sobre la producción propia."},
    {"code": "IMPORTED_FINISHED", "label": "Importación de producto terminado", "description": "Actividad centrada en importación y comercialización de producto terminado verificada en registros oficiales."},
    {"code": "UNKNOWN", "label": "No determinado", "description": "Sin evidencia oficial verificable suficiente para clasificar el modelo productivo."},
]

CHAIN_POSITION_OPTIONS: list[dict[str, str]] = [
    {"code": "FIBER", "label": "Fibra", "description": "Producción, desmotado, lavado o preparación de fibras textiles (naturales o sintéticas)."},
    {"code": "YARN", "label": "Hilado", "description": "Hilandería, retorcido o fabricación de hilados y filamentos."},
    {"code": "FABRIC", "label": "Tejido", "description": "Tejeduría plana o de punto, tintorería y acabado textil."},
    {"code": "APPAREL", "label": "Confección", "description": "Corte y confección de prendas de vestir o artículos textiles confeccionados."},
    {"code": "BRAND", "label": "Marca", "description": "Diseño, desarrollo y titularidad comercial de marca de indumentaria o textil."},
    {"code": "RETAIL", "label": "Retail", "description": "Comercialización minorista directa al consumidor final."},
    {"code": "INTEGRATED", "label": "Integrada", "description": "Integración vertical verificada a lo largo de múltiples eslabones industriales y comerciales."},
    {"code": "UNKNOWN", "label": "No determinado", "description": "Sin evidencia oficial verificable suficiente para determinar la posición en la cadena."},
]

PYME_SIZE_CODES = ("MICRO", "SMALL", "MEDIUM")

ALLOWED_VALUES_BY_DIMENSION: dict[str, set[str]] = {
    "SIZE": {o["code"] for o in SIZE_OPTIONS},
    "ORIGIN": {o["code"] for o in ORIGIN_OPTIONS},
    "PRODUCTION_MODEL": {o["code"] for o in PRODUCTION_MODEL_OPTIONS},
    "CHAIN_POSITION": {o["code"] for o in CHAIN_POSITION_OPTIONS},
}

LABELS_BY_DIMENSION: dict[str, dict[str, str]] = {
    "SIZE": {o["code"]: o["label"] for o in SIZE_OPTIONS},
    "ORIGIN": {o["code"]: o["label"] for o in ORIGIN_OPTIONS},
    "PRODUCTION_MODEL": {o["code"]: o["label"] for o in PRODUCTION_MODEL_OPTIONS},
    "CHAIN_POSITION": {o["code"]: o["label"] for o in CHAIN_POSITION_OPTIONS},
}

CLASSIFICATION_STATUS_LABELS: dict[str, str] = {
    "VERIFIED_COMPLETE": "Verificada completa (4/4 dimensiones)",
    "PARTIALLY_VERIFIED": "Verificada parcial (dimensiones restantes en UNKNOWN)",
    "UNKNOWN": "No determinada (UNKNOWN)",
    "PENDING_AUDIT": "Pendiente de auditoría",
    "REJECTED": "Evidencia rechazada",
}

DIMENSIONS_TAXONOMY: dict[str, Any] = {
    "module_status": "EXPERIMENTAL",
    "core_principle": (
        "No mezclar tamaño empresarial, nacionalidad (origen) y estructura productiva en una única clasificación. "
        "Cada atributo se modela como una dimensión independiente respaldada por evidencia oficial verificable."
    ),
    "source_rule": {
        "required": "Toda clasificación distinta de UNKNOWN debe citar una fuente oficial aprobada (official_sources), una URL perteneciente a su dominio oficial y evidencia documental verificable.",
        "fallback": "Si no existe evidencia oficial suficiente, la clasificación debe permanecer en UNKNOWN (No determinado). Nunca inventar ni inferir.",
        "forbidden_sources": [
            "Noticias y artículos periodísticos",
            "Redes sociales (Instagram, LinkedIn, X/Twitter, Facebook, TikTok, YouTube)",
            "Sitios web comerciales o institucionales de marca",
            "Wikipedia u otras enciclopedias colaborativas",
            "Conocimiento previo de modelos de lenguaje (LLM)",
            "Percepción subjetiva del tamaño o visibilidad de la marca",
        ],
    },
    "dimensions": [
        {
            "key": "SIZE",
            "letter": "A",
            "name": "Tamaño empresarial",
            "multi_valued": False,
            "official_criteria": (
                "Criterios normativos verificables de categorización MiPyME (Ley 24.467, Res. SEPyME 220/2019 y actualizaciones "
                "como Res. SIC 1/2026 de topes de facturación, personal ocupado y activos para Industria y Comercio), constancia "
                "MiPyME ARCA/AFIP y estados contables auditados presentados ante CNV o IGJ."
            ),
            "composite_presets": [
                {"code": "PYME", "label": "PyME (Micro + Pequeña + Mediana)", "includes": list(PYME_SIZE_CODES)}
            ],
            "options": SIZE_OPTIONS,
        },
        {
            "key": "ORIGIN",
            "letter": "B",
            "name": "Origen del capital",
            "multi_valued": False,
            "official_criteria": (
                "Registros societarios oficiales: Inspección General de Justicia (IGJ, incluyendo art. 118/123 LGS), "
                "Registros Públicos provinciales, Boletín Oficial de la República Argentina (Sección Sociedades) y "
                "notas de control societario en estados contables auditados ante la CNV (AIF)."
            ),
            "composite_presets": [],
            "options": ORIGIN_OPTIONS,
        },
        {
            "key": "PRODUCTION_MODEL",
            "letter": "C",
            "name": "Modelo productivo",
            "multi_valued": False,
            "official_criteria": (
                "Memorias anuales y estados contables auditados ante CNV (AIF) con desglose industrial/comercial, "
                "Registro Industrial de la Nación (RIN / Secretaría de Industria y Comercio), habilitaciones industriales "
                "oficiales y registros aduaneros oficiales (DGA/ARCA). No se infiere desde webs comerciales ni marketing."
            ),
            "composite_presets": [],
            "options": PRODUCTION_MODEL_OPTIONS,
        },
        {
            "key": "CHAIN_POSITION",
            "letter": "D",
            "name": "Posición en la cadena",
            "multi_valued": True,
            "official_criteria": (
                "Códigos de actividad principal y secundaria CLAE (AFIP/ARCA F.883, divisiones 13, 14 y 46/47), "
                "Registro Industrial de la Nación, objeto social en Boletín Oficial y memorias auditadas CNV. "
                "Una misma firma puede ocupar simultáneamente más de una posición."
            ),
            "composite_presets": [],
            "options": CHAIN_POSITION_OPTIONS,
        },
    ],
}

# Strict blocklist enforcing the "Regla de fuentes"
FORBIDDEN_SOURCE_DOMAINS: tuple[str, ...] = (
    "wikipedia.org",
    "wikimedia.org",
    "instagram.com",
    "facebook.com",
    "fb.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "infobae.com",
    "clarin.com",
    "lanacion.com.ar",
    "ambito.com",
    "cronista.com",
    "iprofesional.com",
    "pagina12.com.ar",
    "perfil.com",
    "baenegocios.com",
    "bloomberg.com",
    "reuters.com",
    "forbesargentina.com",
    "forbes.com",
    "mercadolibre.com.ar",
)

FORBIDDEN_EVIDENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bwikipedia\b", "Referencia a Wikipedia prohibida por regla de fuentes."),
    (r"\b(instagram|facebook|tiktok|linkedin|twitter|red(?:es)?\s+social(?:es)?)\b", "Referencia a redes sociales prohibida por regla de fuentes."),
    (r"\b(web\s+comercial|sitio\s+comercial|tienda\s+online|e-?commerce\s+propio)\b", "Referencia a web comercial prohibida por regla de fuentes."),
    (r"\b(noticia|nota\s+period[ií]stica|art[ií]culo\s+period[ií]stico|diario\s+|prensa)\b", "Referencia a noticias o prensa prohibida por regla de fuentes."),
    (r"\b(conocimiento\s+del\s+modelo|conocimiento\s+general|es\s+p[uú]blico\s+conocimiento|percepci[oó]n\s+de\s+(?:la\s+)?marca|marca\s+muy\s+conocida|inferido|estimado\s+sin\s+fuente)\b", "Inferencia basada en conocimiento del modelo o percepción de marca prohibida."),
)


def _normalize_cuit(cuit: str | None) -> str | None:
    if not cuit:
        return None
    digits = re.sub(r"\D+", "", cuit)
    return digits or None


def _host_matches_forbidden(url: str) -> str | None:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    for forbidden in FORBIDDEN_SOURCE_DOMAINS:
        if host == forbidden or host.endswith("." + forbidden):
            return forbidden
    return None


@dataclass
class ClassificationAuditResult:
    history_id: int
    company_id: int
    dimension: str
    classification: str
    audit_status: str
    audit_notes: str
    promoted_to_company: bool


class CompanyClassificationAuditor:
    """Mandatory audit gate enforcing official verifiable evidence for every corporate dimension."""

    def __init__(self, db: Session):
        self.db = db

    def audit_and_record(
        self,
        *,
        company_id: int,
        dimension: str,
        classification: str,
        valid_from: date,
        valid_to: date | None,
        official_source_id: int | None,
        source_url: str | None,
        evidence: str,
    ) -> ClassificationAuditResult:
        dim = dimension.strip().upper()
        cls = classification.strip().upper()

        if dim not in ALLOWED_VALUES_BY_DIMENSION:
            raise ValueError(f"Dimensión inválida '{dimension}'. Permitidas: {', '.join(DIMENSION_CODES)}.")
        if cls not in ALLOWED_VALUES_BY_DIMENSION[dim]:
            allowed = ", ".join(sorted(ALLOWED_VALUES_BY_DIMENSION[dim]))
            raise ValueError(f"Clasificación '{classification}' inválida para dimensión '{dim}'. Permitidas: {allowed}.")
        if valid_to is not None and valid_to < valid_from:
            raise ValueError("valid_to no puede ser anterior a valid_from.")

        company = self.db.get(Company, company_id)
        if company is None:
            raise ValueError(f"Empresa company_id={company_id} no encontrada.")

        clean_url = (source_url or "").strip() or None
        clean_evidence = (evidence or "").strip()

        # Case 1: Explicit UNKNOWN (verified lack of sufficient official evidence)
        if cls == "UNKNOWN":
            eff_evidence = clean_evidence or (
                "Sin evidencia oficial verificable suficiente para esta dimensión; se registra UNKNOWN sin inferencia."
            )
            audit_status = "VERIFIED"
            audit_notes = (
                "Clasificación UNKNOWN aceptada explícitamente conforme a la regla de fuentes "
                "(no se infiere ante falta de evidencia oficial)."
            )
            # Close previous open verified entries for this dimension if superseded
            self._close_open_verified_rows(company_id=company_id, dimension=dim, close_date=valid_from, match_all_for_chain=True)
            row = CompanyClassificationHistory(
                company_id=company_id,
                dimension=dim,
                classification="UNKNOWN",
                valid_from=valid_from,
                valid_to=valid_to,
                official_source_id=official_source_id,
                source_url=clean_url,
                evidence=eff_evidence,
                audit_status=audit_status,
                audit_notes=audit_notes,
            )
            self.db.add(row)
            self.db.flush()
            self.sync_company_current_state(company_id)
            return ClassificationAuditResult(
                history_id=row.history_id,
                company_id=company_id,
                dimension=dim,
                classification=cls,
                audit_status=audit_status,
                audit_notes=audit_notes,
                promoted_to_company=True,
            )

        # Case 2: Non-UNKNOWN classification -> strict official verifiable evidence checks
        rejection_reasons: list[str] = []

        source: OfficialSource | None = None
        if official_source_id is None:
            rejection_reasons.append("Falta official_source_id: toda clasificación distinta de UNKNOWN exige un organismo oficial aprobado.")
        else:
            source = self.db.get(OfficialSource, official_source_id)
            if source is None or not source.is_approved:
                rejection_reasons.append("La fuente indicada no existe o no está aprobada en core.official_sources.")
            elif source.source_code == "TDH_DERIVED":
                rejection_reasons.append("TDH_DERIVED no puede utilizarse como evidencia primaria de clasificación empresarial.")

        if not clean_url:
            rejection_reasons.append("Falta source_url: se requiere URL oficial verificable del documento o registro.")
        else:
            parsed = urlparse(clean_url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                rejection_reasons.append("source_url debe ser una URL http(s) válida.")
            else:
                forbidden_hit = _host_matches_forbidden(clean_url)
                if forbidden_hit:
                    rejection_reasons.append(
                        f"Dominio prohibido por regla de fuentes ('{forbidden_hit}'): no se permiten noticias, redes sociales, webs comerciales ni Wikipedia."
                    )
                elif source is not None and not _domain_matches(clean_url, source.official_domain):
                    rejection_reasons.append(
                        f"El host de source_url ('{parsed.hostname}') no coincide con el dominio oficial aprobado '{source.official_domain}' de {source.source_code}."
                    )

        if len(clean_evidence) < 20:
            rejection_reasons.append(
                "Evidencia insuficiente: debe citar explícitamente el documento, resolución, registro, balance o expediente oficial (mín. 20 caracteres)."
            )
        else:
            low_ev = clean_evidence.lower()
            for pattern, reason in FORBIDDEN_EVIDENCE_PATTERNS:
                if re.search(pattern, low_ev):
                    rejection_reasons.append(reason)

        if rejection_reasons:
            audit_status = "REJECTED"
            audit_notes = " | ".join(rejection_reasons)
            row = CompanyClassificationHistory(
                company_id=company_id,
                dimension=dim,
                classification=cls,
                valid_from=valid_from,
                valid_to=valid_to,
                official_source_id=source.official_source_id if source is not None else None,
                source_url=clean_url,
                evidence=clean_evidence or "(sin evidencia aportada)",
                audit_status=audit_status,
                audit_notes=audit_notes,
            )
            self.db.add(row)
            self.db.flush()
            # Re-sync without promoting rejected row; unverified dimensions remain UNKNOWN
            self.sync_company_current_state(company_id)
            return ClassificationAuditResult(
                history_id=row.history_id,
                company_id=company_id,
                dimension=dim,
                classification=cls,
                audit_status=audit_status,
                audit_notes=audit_notes,
                promoted_to_company=False,
            )

        # Approved VERIFIED classification!
        assert source is not None
        if dim != "CHAIN_POSITION":
            if valid_to is None:
                self._close_open_verified_rows(company_id=company_id, dimension=dim, close_date=valid_from, match_all_for_chain=False)
        else:
            # Multi-valued dimension: close any open UNKNOWN placeholder, and close duplicate open same-position entry
            open_chain_rows = self.db.scalars(
                select(CompanyClassificationHistory).where(
                    CompanyClassificationHistory.company_id == company_id,
                    CompanyClassificationHistory.dimension == "CHAIN_POSITION",
                    CompanyClassificationHistory.audit_status == "VERIFIED",
                    CompanyClassificationHistory.valid_to.is_(None),
                )
            ).all()
            for prev in open_chain_rows:
                if prev.classification in ("UNKNOWN", cls) and valid_to is None:
                    prev.valid_to = valid_from if valid_from >= prev.valid_from else prev.valid_from

        audit_status = "VERIFIED"
        audit_notes = (
            f"Evidencia oficial verificada contra {source.source_code} ({source.official_domain}). "
            "Clasificación aprobada y promovida sin mezclar dimensiones independientes."
        )
        row = CompanyClassificationHistory(
            company_id=company_id,
            dimension=dim,
            classification=cls,
            valid_from=valid_from,
            valid_to=valid_to,
            official_source_id=source.official_source_id,
            source_url=clean_url,
            evidence=clean_evidence,
            audit_status=audit_status,
            audit_notes=audit_notes,
        )
        self.db.add(row)
        self.db.flush()
        self.sync_company_current_state(company_id)

        return ClassificationAuditResult(
            history_id=row.history_id,
            company_id=company_id,
            dimension=dim,
            classification=cls,
            audit_status=audit_status,
            audit_notes=audit_notes,
            promoted_to_company=valid_to is None,
        )

    def _close_open_verified_rows(
        self,
        *,
        company_id: int,
        dimension: str,
        close_date: date,
        match_all_for_chain: bool,
    ) -> None:
        if dimension == "CHAIN_POSITION" and not match_all_for_chain:
            return
        open_rows = self.db.scalars(
            select(CompanyClassificationHistory).where(
                CompanyClassificationHistory.company_id == company_id,
                CompanyClassificationHistory.dimension == dimension,
                CompanyClassificationHistory.audit_status == "VERIFIED",
                CompanyClassificationHistory.valid_to.is_(None),
            )
        ).all()
        for prev in open_rows:
            prev.valid_to = close_date if close_date >= prev.valid_from else prev.valid_from

    def sync_company_current_state(self, company_id: int) -> Company:
        """Deterministically materialize current VERIFIED classifications onto core.companies."""
        company = self.db.get(Company, company_id)
        if company is None:
            raise ValueError(f"Empresa company_id={company_id} no encontrada.")

        current_verified = self.db.scalars(
            select(CompanyClassificationHistory)
            .where(
                CompanyClassificationHistory.company_id == company_id,
                CompanyClassificationHistory.audit_status == "VERIFIED",
                CompanyClassificationHistory.valid_to.is_(None),
            )
            .order_by(CompanyClassificationHistory.valid_from.desc(), CompanyClassificationHistory.history_id.desc())
        ).all()

        size_val = "UNKNOWN"
        origin_val = "UNKNOWN"
        model_val = "UNKNOWN"
        chain_vals: list[str] = []

        for h in current_verified:
            if h.dimension == "SIZE" and size_val == "UNKNOWN":
                size_val = h.classification
            elif h.dimension == "ORIGIN" and origin_val == "UNKNOWN":
                origin_val = h.classification
            elif h.dimension == "PRODUCTION_MODEL" and model_val == "UNKNOWN":
                model_val = h.classification
            elif h.dimension == "CHAIN_POSITION":
                if h.classification != "UNKNOWN" and h.classification not in chain_vals:
                    chain_vals.append(h.classification)

        if not chain_vals:
            chain_vals = ["UNKNOWN"]

        company.company_size = size_val
        company.company_origin = origin_val
        company.production_model = model_val

        # Sync core.company_chain_positions
        existing_pos = self.db.scalars(
            select(CompanyChainPosition).where(CompanyChainPosition.company_id == company_id)
        ).all()
        existing_set = {p.chain_position for p in existing_pos}
        target_set = set(chain_vals)

        for p in existing_pos:
            if p.chain_position not in target_set:
                self.db.delete(p)
        for pos in sorted(target_set - existing_set):
            self.db.add(CompanyChainPosition(company_id=company_id, chain_position=pos))

        # Compute overall classification_status
        verified_dims = sum(
            1
            for v in (size_val, origin_val, model_val)
            if v != "UNKNOWN"
        ) + (1 if any(c != "UNKNOWN" for c in chain_vals) else 0)

        if verified_dims == 4:
            company.classification_status = "VERIFIED_COMPLETE"
        elif verified_dims > 0:
            company.classification_status = "PARTIALLY_VERIFIED"
        else:
            company.classification_status = "UNKNOWN"

        company.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return company


# ---------------------------------------------------------------------------
# COMPANY CRUD, COMBINABLE FILTERING & SUMMARY
# ---------------------------------------------------------------------------

def create_company(
    db: Session,
    *,
    legal_name: str,
    brand_name: str | None = None,
    cuit: str | None = None,
    notes: str | None = None,
) -> Company:
    """Register a company starting with UNKNOWN across all 4 independent dimensions."""
    clean_legal = legal_name.strip()
    if len(clean_legal) < 2:
        raise ValueError("legal_name es obligatorio (mínimo 2 caracteres).")
    norm_cuit = _normalize_cuit(cuit)
    if norm_cuit:
        existing = db.scalar(select(Company).where(Company.cuit == norm_cuit))
        if existing is not None:
            raise ValueError(f"Ya existe una empresa registrada con CUIT {norm_cuit}.")

    company = Company(
        legal_name=clean_legal,
        brand_name=(brand_name or "").strip() or None,
        cuit=norm_cuit,
        company_size="UNKNOWN",
        company_origin="UNKNOWN",
        production_model="UNKNOWN",
        classification_status="UNKNOWN",
        notes=(notes or "").strip() or None,
    )
    db.add(company)
    db.flush()
    db.add(CompanyChainPosition(company_id=company.company_id, chain_position="UNKNOWN"))
    db.flush()
    return company


def serialize_company(company: Company, include_history: bool = False) -> dict[str, Any]:
    positions = sorted({p.chain_position for p in company.chain_positions}) or ["UNKNOWN"]
    payload: dict[str, Any] = {
        "company_id": company.company_id,
        "legal_name": company.legal_name,
        "brand_name": company.brand_name,
        "cuit": company.cuit,
        "company_size": company.company_size,
        "company_size_label": LABELS_BY_DIMENSION["SIZE"].get(company.company_size, company.company_size),
        "company_origin": company.company_origin,
        "company_origin_label": LABELS_BY_DIMENSION["ORIGIN"].get(company.company_origin, company.company_origin),
        "production_model": company.production_model,
        "production_model_label": LABELS_BY_DIMENSION["PRODUCTION_MODEL"].get(
            company.production_model, company.production_model
        ),
        "chain_positions": positions,
        "chain_position_labels": [LABELS_BY_DIMENSION["CHAIN_POSITION"].get(c, c) for c in positions],
        "classification_status": company.classification_status,
        "classification_status_label": CLASSIFICATION_STATUS_LABELS.get(
            company.classification_status, company.classification_status
        ),
        "notes": company.notes,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }
    if include_history:
        sorted_hist = sorted(
            company.classification_history,
            key=lambda h: (h.valid_from, h.history_id),
            reverse=True,
        )
        payload["classification_history"] = [
            {
                "history_id": h.history_id,
                "company_id": h.company_id,
                "dimension": h.dimension,
                "classification": h.classification,
                "classification_label": LABELS_BY_DIMENSION.get(h.dimension, {}).get(
                    h.classification, h.classification
                ),
                "valid_from": h.valid_from.isoformat(),
                "valid_to": h.valid_to.isoformat() if h.valid_to else None,
                "official_source_id": h.official_source_id,
                "official_source_code": h.official_source.source_code if h.official_source else None,
                "official_source_institution": h.official_source.institution if h.official_source else None,
                "source_url": h.source_url,
                "evidence": h.evidence,
                "audit_status": h.audit_status,
                "audit_notes": h.audit_notes,
                "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
            }
            for h in sorted_hist
        ]
    return payload


def _expand_size_filters(sizes: list[str] | None) -> list[str]:
    if not sizes:
        return []
    expanded: list[str] = []
    for raw in sizes:
        code = raw.strip().upper()
        if not code:
            continue
        if code == "PYME":
            for c in PYME_SIZE_CODES:
                if c not in expanded:
                    expanded.append(c)
        elif code in ALLOWED_VALUES_BY_DIMENSION["SIZE"]:
            if code not in expanded:
                expanded.append(code)
    return expanded


def query_companies(
    db: Session,
    *,
    sizes: list[str] | None = None,
    origins: list[str] | None = None,
    production_models: list[str] | None = None,
    chain_positions: list[str] | None = None,
    chain_match: str = "any",
    classification_status: str | None = None,
    q: str | None = None,
) -> list[Company]:
    stmt = (
        select(Company)
        .options(joinedload(Company.chain_positions))
        .order_by(Company.legal_name.asc(), Company.company_id.asc())
    )

    exp_sizes = _expand_size_filters(sizes)
    if exp_sizes:
        stmt = stmt.where(Company.company_size.in_(exp_sizes))

    clean_origins = [o.strip().upper() for o in (origins or []) if o.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["ORIGIN"]]
    if clean_origins:
        stmt = stmt.where(Company.company_origin.in_(clean_origins))

    clean_models = [
        m.strip().upper()
        for m in (production_models or [])
        if m.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["PRODUCTION_MODEL"]
    ]
    if clean_models:
        stmt = stmt.where(Company.production_model.in_(clean_models))

    clean_chains = [
        c.strip().upper()
        for c in (chain_positions or [])
        if c.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["CHAIN_POSITION"]
    ]
    if clean_chains:
        if chain_match == "all":
            for pos in clean_chains:
                stmt = stmt.where(
                    Company.chain_positions.any(CompanyChainPosition.chain_position == pos)
                )
        else:
            stmt = stmt.where(
                Company.chain_positions.any(CompanyChainPosition.chain_position.in_(clean_chains))
            )

    if classification_status:
        stmt = stmt.where(Company.classification_status == classification_status.strip().upper())

    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Company.legal_name.ilike(like),
                Company.brand_name.ilike(like),
                Company.cuit.ilike(like),
            )
        )

    return db.scalars(stmt).unique().all()


def get_industry_structure_summary(db: Session) -> dict[str, Any]:
    total_companies = db.scalar(select(func.count()).select_from(Company)) or 0

    def _counts_for(column, options: list[dict[str, str]]) -> list[dict[str, Any]]:
        raw_map = dict(db.execute(select(column, func.count()).group_by(column)).all())
        return [
            {
                "code": opt["code"],
                "label": opt["label"],
                "count": int(raw_map.get(opt["code"], 0)),
            }
            for opt in options
        ]

    chain_raw = dict(
        db.execute(
            select(CompanyChainPosition.chain_position, func.count(func.distinct(CompanyChainPosition.company_id)))
            .group_by(CompanyChainPosition.chain_position)
        ).all()
    )
    chain_counts = [
        {
            "code": opt["code"],
            "label": opt["label"],
            "count": int(chain_raw.get(opt["code"], 0)),
        }
        for opt in CHAIN_POSITION_OPTIONS
    ]

    status_raw = dict(
        db.execute(select(Company.classification_status, func.count()).group_by(Company.classification_status)).all()
    )
    hist_raw = dict(
        db.execute(
            select(CompanyClassificationHistory.audit_status, func.count()).group_by(
                CompanyClassificationHistory.audit_status
            )
        ).all()
    )

    corporate_sources = db.scalars(
        select(OfficialSource)
        .where(OfficialSource.is_approved.is_(True), OfficialSource.source_code != "TDH_DERIVED")
        .order_by(OfficialSource.official_source_id.asc())
    ).all()

    return {
        "module_status": "EXPERIMENTAL",
        "total_companies": int(total_companies),
        "classification_status_counts": {
            "VERIFIED_COMPLETE": int(status_raw.get("VERIFIED_COMPLETE", 0)),
            "PARTIALLY_VERIFIED": int(status_raw.get("PARTIALLY_VERIFIED", 0)),
            "UNKNOWN": int(status_raw.get("UNKNOWN", 0)),
        },
        "audit_history_counts": {
            "VERIFIED": int(hist_raw.get("VERIFIED", 0)),
            "REJECTED": int(hist_raw.get("REJECTED", 0)),
            "PENDING": int(hist_raw.get("PENDING", 0)),
            "WARNING": int(hist_raw.get("WARNING", 0)),
        },
        "dimensions": {
            "SIZE": _counts_for(Company.company_size, SIZE_OPTIONS),
            "ORIGIN": _counts_for(Company.company_origin, ORIGIN_OPTIONS),
            "PRODUCTION_MODEL": _counts_for(Company.production_model, PRODUCTION_MODEL_OPTIONS),
            "CHAIN_POSITION": chain_counts,
        },
        "approved_official_sources": [
            {
                "official_source_id": s.official_source_id,
                "source_code": s.source_code,
                "institution": s.institution,
                "official_domain": s.official_domain,
                "notes": s.notes,
            }
            for s in corporate_sources
        ],
    }


# ---------------------------------------------------------------------------
# STRUCTURAL RESEARCH INTEGRATION (NON-CAUSAL EXPLORATORY BUILDER)
# ---------------------------------------------------------------------------

NON_CAUSALITY_WARNING = (
    "Advertencia metodológica estricta: no interpretar asociaciones entre la estructura empresarial "
    "(tamaño, origen, modelo productivo o posición en la cadena) y la evolución de series económicas agregadas "
    "como relaciones de causalidad. Asimismo, evitar la falacia ecológica al vincular agregados macro/sectoriales "
    "con segmentos de firmas sin microdatos longitudinales e identificación econométrica."
)

STRUCTURAL_RESEARCH_PRESETS: list[dict[str, Any]] = [
    {
        "preset_id": "local_vs_imports",
        "title": "Producción local vs importaciones",
        "short_label": "Producción local vs importaciones",
        "dimensions_involved": ["PRODUCTION_MODEL", "CHAIN_POSITION"],
        "segment_a": {
            "label": "Firmas con producción local (principalmente local / con insumos importados)",
            "filters": {"production_models": ["LOCAL_PRIMARY", "LOCAL_IMPORTED_INPUTS"]},
        },
        "segment_b": {
            "label": "Firmas importadoras (importación mayoritaria o total de producto terminado)",
            "filters": {"production_models": ["MAJORITY_IMPORTED_FINISHED", "IMPORTED_FINISHED"]},
        },
        "recommended_series": [
            "IPI_TEXTILES",
            "IPI_PRENDAS_VESTIR",
            "IMPO_CADENA_TEXTIL_TOTAL",
            "TC_MAYORISTA_BCRA",
        ],
        "exploratory_questions": [
            "¿Cómo coexistieron las trayectorias del IPI textil y de prendas de vestir con los cambios en el volumen monetario de importaciones textiles (NCM 50–63)?",
            "¿Qué proporción de las firmas con evidencia oficial verificada se concentra en producción principalmente local frente a modelos importadores?",
            "¿Cómo se diferencian los eslabones de hilado/tejido frente a confección/marca en términos de modelo productivo verificado?",
        ],
    },
    {
        "preset_id": "pyme_vs_large",
        "title": "PyMEs vs grandes empresas",
        "short_label": "PyMEs vs grandes empresas",
        "dimensions_involved": ["SIZE", "CHAIN_POSITION"],
        "segment_a": {
            "label": "PyMEs verificadas (Micro + Pequeña + Mediana, criterio oficial SEPyME)",
            "filters": {"sizes": ["MICRO", "SMALL", "MEDIUM"]},
        },
        "segment_b": {
            "label": "Grandes empresas verificadas",
            "filters": {"sizes": ["LARGE"]},
        },
        "recommended_series": [
            "EMPLEO_PRIVADO_TEXTIL",
            "EMPLEO_PRIVADO_INDUMENTARIA",
            "UCII_TEXTILES",
            "PRESTAMOS_SECTOR_PRIVADO",
        ],
        "exploratory_questions": [
            "¿En qué eslabones de la cadena (hilado, tejido, confección, marca, retail) se observa mayor presencia verificada de PyMEs frente a grandes empresas?",
            "¿Cómo evolucionaron el empleo registrado en textiles (CLAE 13) y confección (CLAE 14) junto con el crédito al sector privado y las tasas BADLAR?",
            "¿Existen diferencias de modelo productivo entre firmas PyME y grandes firmas dentro de un mismo eslabón de la cadena (sin asumir causalidad por tamaño)?",
        ],
    },
    {
        "preset_id": "national_vs_foreign",
        "title": "Firmas nacionales vs extranjeras",
        "short_label": "Firmas nacionales vs extranjeras",
        "dimensions_involved": ["ORIGIN", "PRODUCTION_MODEL"],
        "segment_a": {
            "label": "Firmas de capital nacional verificado",
            "filters": {"origins": ["NATIONAL"]},
        },
        "segment_b": {
            "label": "Firmas de capital extranjero verificado",
            "filters": {"origins": ["FOREIGN"]},
        },
        "recommended_series": [
            "IPI_TEXTILES",
            "IMPO_PRENDAS_TERMINADAS_TOTAL",
            "EXPO_CADENA_TEXTIL_TOTAL",
            "TC_MAYORISTA_BCRA",
        ],
        "exploratory_questions": [
            "¿Qué distribución de modelos productivos (local, mixto o importador) se observa separadamente dentro de firmas nacionales y dentro de firmas extranjeras?",
            "¿Qué posiciones de la cadena ocupan las firmas nacionales frente a las firmas de capital extranjero con evidencia societaria oficial?",
            "¿Cómo evitar confundir origen del capital con modelo productivo al analizar la evolución del saldo comercial textil?",
        ],
    },
    {
        "preset_id": "local_vs_imported_finished",
        "title": "Producción local vs producto terminado importado",
        "short_label": "Producción local vs producto terminado importado",
        "dimensions_involved": ["PRODUCTION_MODEL", "CHAIN_POSITION"],
        "segment_a": {
            "label": "Producción principalmente local",
            "filters": {"production_models": ["LOCAL_PRIMARY"]},
        },
        "segment_b": {
            "label": "Importación mayoritaria o total de producto terminado",
            "filters": {"production_models": ["MAJORITY_IMPORTED_FINISHED", "IMPORTED_FINISHED"]},
        },
        "recommended_series": [
            "IPI_PRENDAS_VESTIR",
            "IMPO_PRENDAS_TERMINADAS_TOTAL",
            "IPC_PRENDAS_CALZADO",
            "PRECIO_RELATIVO_INDUMENTARIA",
        ],
        "exploratory_questions": [
            "¿Cómo evolucionaron las importaciones de prendas terminadas (NCM 61+62) en comparación con el IPI de prendas de vestir y el precio relativo de la indumentaria?",
            "¿En qué medida las firmas clasificadas en Confección, Marca y Retail presentan modelos de producción principalmente local frente a importación de producto terminado?",
            "¿Qué parte del universo relevado permanece en UNKNOWN por falta de desglose oficial entre producción propia y mercadería importada?",
        ],
    },
    {
        "preset_id": "import_dependency_by_segment",
        "title": "Dependencia importadora por segmento",
        "short_label": "Dependencia importadora por segmento",
        "dimensions_involved": ["PRODUCTION_MODEL", "CHAIN_POSITION", "SIZE"],
        "segment_a": {
            "label": "Producción local con insumos importados o mixta",
            "filters": {"production_models": ["LOCAL_IMPORTED_INPUTS", "MIXED"]},
        },
        "segment_b": {
            "label": "Importación mayoritaria o total de producto terminado",
            "filters": {"production_models": ["MAJORITY_IMPORTED_FINISHED", "IMPORTED_FINISHED"]},
        },
        "recommended_series": [
            "IMPO_NCM_54_FILAMENTOS_SINT",
            "IMPO_NCM_60_TEJIDOS_PUNTO",
            "IMPO_PRENDAS_TERMINADAS_TOTAL",
            "IPI_TEJIDOS_ACABADO",
        ],
        "exploratory_questions": [
            "¿Qué peso relativo tienen en las importaciones textiles los insumos intermedios (filamentos sintéticos NCM 54, tejidos de punto NCM 60) frente a prendas terminadas (NCM 61+62)?",
            "¿Qué eslabones de la cadena (Hilado, Tejido, Confección, Marca, Retail, Integrada) muestran mayor exposición a insumos importados vs. producto terminado importado?",
            "¿Cómo varía la sensibilidad sectorial frente a movimientos del tipo de cambio real o mayorista según el eslabón de la cadena analizado?",
        ],
    },
]


def _resolve_verified_series(db: Session, codes: list[str]) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Series).where(
            Series.series_code.in_(codes),
            Series.audit_status == "VERIFIED",
            Series.active.is_(True),
        )
    ).all()
    by_code = {s.series_code: s for s in rows}
    out = []
    for code in codes:
        if code in by_code:
            s = by_code[code]
            out.append({
                "series_code": s.series_code,
                "series_name": s.series_name,
                "short_name": s.short_name,
                "unit": s.unit,
                "frequency": s.frequency,
                "category": s.category,
                "is_context_variable": s.is_context_variable,
                "series_type": s.series_type,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else None,
            })
    return out


def list_structural_research_presets(db: Session) -> list[dict[str, Any]]:
    results = []
    for p in STRUCTURAL_RESEARCH_PRESETS:
        seg_a_count = len(query_companies(db, **p["segment_a"]["filters"]))
        seg_b_count = len(query_companies(db, **p["segment_b"]["filters"]))
        results.append({
            **p,
            "segment_a_company_count": seg_a_count,
            "segment_b_company_count": seg_b_count,
            "recommended_series_details": _resolve_verified_series(db, p["recommended_series"]),
            "non_causality_warning": NON_CAUSALITY_WARNING,
        })
    return results


def build_structural_research_frame(
    db: Session,
    *,
    preset_id: str | None = None,
    sizes: list[str] | None = None,
    origins: list[str] | None = None,
    production_models: list[str] | None = None,
    chain_positions: list[str] | None = None,
    custom_focus: str | None = None,
) -> dict[str, Any]:
    if preset_id:
        matched = next((p for p in STRUCTURAL_RESEARCH_PRESETS if p["preset_id"] == preset_id), None)
        if matched is None:
            raise ValueError(f"Preset de research '{preset_id}' no encontrado.")
        seg_a = query_companies(db, **matched["segment_a"]["filters"])
        seg_b = query_companies(db, **matched["segment_b"]["filters"])
        unknown_total = db.scalar(
            select(func.count()).select_from(Company).where(Company.classification_status == "UNKNOWN")
        ) or 0
        return {
            "mode": "preset",
            "preset_id": matched["preset_id"],
            "title": matched["title"],
            "dimensions_involved": matched["dimensions_involved"],
            "segment_comparison": {
                "segment_a": {
                    "label": matched["segment_a"]["label"],
                    "filters": matched["segment_a"]["filters"],
                    "verified_company_count": len(seg_a),
                },
                "segment_b": {
                    "label": matched["segment_b"]["label"],
                    "filters": matched["segment_b"]["filters"],
                    "verified_company_count": len(seg_b),
                },
                "companies_with_unknown_status": int(unknown_total),
            },
            "exploratory_questions": matched["exploratory_questions"],
            "recommended_series": _resolve_verified_series(db, matched["recommended_series"]),
            "non_causality_warning": NON_CAUSALITY_WARNING,
            "data_coverage_note": (
                "Los conteos de firmas reflejan únicamente registros cargados con evidencia oficial verificable. "
                "Las dimensiones sin respaldo documental oficial se mantienen explícitamente en UNKNOWN."
            ),
        }

    # Custom multi-dimension combination
    exp_sizes = _expand_size_filters(sizes)
    clean_origins = [o.strip().upper() for o in (origins or []) if o.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["ORIGIN"]]
    clean_models = [
        m.strip().upper()
        for m in (production_models or [])
        if m.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["PRODUCTION_MODEL"]
    ]
    clean_chains = [
        c.strip().upper()
        for c in (chain_positions or [])
        if c.strip().upper() in ALLOWED_VALUES_BY_DIMENSION["CHAIN_POSITION"]
    ]

    matched_companies = query_companies(
        db,
        sizes=exp_sizes,
        origins=clean_origins,
        production_models=clean_models,
        chain_positions=clean_chains,
    )
    total_companies = db.scalar(select(func.count()).select_from(Company)) or 0

    dim_labels: list[str] = []
    dims_used: list[str] = []
    if exp_sizes:
        dims_used.append("SIZE")
        dim_labels.append("Tamaño: " + ", ".join(LABELS_BY_DIMENSION["SIZE"][c] for c in exp_sizes))
    if clean_origins:
        dims_used.append("ORIGIN")
        dim_labels.append("Origen: " + ", ".join(LABELS_BY_DIMENSION["ORIGIN"][c] for c in clean_origins))
    if clean_models:
        dims_used.append("PRODUCTION_MODEL")
        dim_labels.append("Modelo productivo: " + ", ".join(LABELS_BY_DIMENSION["PRODUCTION_MODEL"][c] for c in clean_models))
    if clean_chains:
        dims_used.append("CHAIN_POSITION")
        dim_labels.append("Cadena: " + ", ".join(LABELS_BY_DIMENSION["CHAIN_POSITION"][c] for c in clean_chains))

    segment_desc = " + ".join(dim_labels) if dim_labels else "Universo completo (sin filtro de dimensión)"

    # Pick relevant verified aggregate series based on selected dimensions
    rec_codes: list[str] = []
    if "APPAREL" in clean_chains or "BRAND" in clean_chains or "RETAIL" in clean_chains:
        rec_codes.extend(["IPI_PRENDAS_VESTIR", "EMPLEO_PRIVADO_INDUMENTARIA", "IPC_PRENDAS_CALZADO"])
    if any(c in clean_chains for c in ("FIBER", "YARN", "FABRIC", "INTEGRATED")):
        rec_codes.extend(["IPI_TEXTILES", "IPI_TEJIDOS_ACABADO", "UCII_TEXTILES", "EMPLEO_PRIVADO_TEXTIL"])
    if any(m in clean_models for m in ("MAJORITY_IMPORTED_FINISHED", "IMPORTED_FINISHED")):
        rec_codes.extend(["IMPO_PRENDAS_TERMINADAS_TOTAL", "TC_MAYORISTA_BCRA"])
    if any(m in clean_models for m in ("LOCAL_IMPORTED_INPUTS", "MIXED")):
        rec_codes.extend(["IMPO_NCM_54_FILAMENTOS_SINT", "IMPO_NCM_60_TEJIDOS_PUNTO", "TC_MAYORISTA_BCRA"])
    if not rec_codes:
        rec_codes = ["IPI_TEXTILES", "IMPO_CADENA_TEXTIL_TOTAL", "EMPLEO_PRIVADO_TEXTIL", "TC_MAYORISTA_BCRA"]
    # Deduplicate preserving order, max 4
    dedup_codes = list(dict.fromkeys(rec_codes))[:4]

    questions = [
        f"¿Qué evolución muestran las series sectoriales oficiales en los eslabones vinculados al segmento [{segment_desc}]?",
        f"¿Cómo se distribuyen las demás dimensiones independientes dentro del subconjunto [{segment_desc}] sin asumir homogeneidad interna?",
        "¿Qué proporción de firmas relevantes en este segmento cuenta con evidencia oficial verificable frente a registros aún clasificados como UNKNOWN?",
    ]
    if custom_focus and custom_focus.strip():
        questions.insert(0, f"Pregunta exploratoria formulada: {custom_focus.strip()} (analizar asociación descriptiva sin inferir causalidad).")

    return {
        "mode": "custom",
        "preset_id": None,
        "title": f"Exploración estructural: {segment_desc}",
        "dimensions_involved": dims_used or list(DIMENSION_CODES),
        "segment_profile": {
            "description": segment_desc,
            "filters": {
                "sizes": exp_sizes,
                "origins": clean_origins,
                "production_models": clean_models,
                "chain_positions": clean_chains,
            },
            "matching_companies_count": len(matched_companies),
            "total_registered_companies": int(total_companies),
        },
        "exploratory_questions": questions,
        "recommended_series": _resolve_verified_series(db, dedup_codes),
        "non_causality_warning": NON_CAUSALITY_WARNING,
        "data_coverage_note": (
            "Las cuatro dimensiones (Tamaño, Origen, Modelo productivo y Posición en la cadena) se mantienen independientes. "
            "Ninguna clasificación se infiere sin respaldo oficial verificable."
        ),
    }


# ---------------------------------------------------------------------------
# EXPORT & AUDITED BATCH CSV IMPORTER
# ---------------------------------------------------------------------------

def render_companies_csv(companies: list[Company]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "company_id",
        "legal_name",
        "brand_name",
        "cuit",
        "company_size",
        "company_origin",
        "production_model",
        "chain_positions",
        "classification_status",
    ])
    for c in companies:
        pos = "|".join(sorted({p.chain_position for p in c.chain_positions}) or ["UNKNOWN"])
        writer.writerow([
            c.company_id,
            c.legal_name,
            c.brand_name or "",
            c.cuit or "",
            c.company_size,
            c.company_origin,
            c.production_model,
            pos,
            c.classification_status,
        ])
    return buf.getvalue().encode("utf-8-sig")


def import_company_evidence_csv(db: Session, csv_text: str) -> dict[str, int]:
    """
    Import official corporate evidence CSV rows through CompanyClassificationAuditor.
    Expected CSV headers:
      legal_name, brand_name, cuit, dimension, classification, valid_from, valid_to,
      official_source_code, source_url, evidence
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    auditor = CompanyClassificationAuditor(db)
    sources_by_code = {
        s.source_code: s
        for s in db.scalars(select(OfficialSource)).all()
    }
    stats = {"companies_created": 0, "records_verified": 0, "records_rejected": 0, "rows_processed": 0}

    for row in reader:
        stats["rows_processed"] += 1
        legal_name = (row.get("legal_name") or "").strip()
        if not legal_name:
            stats["records_rejected"] += 1
            continue
        brand_name = (row.get("brand_name") or "").strip() or None
        norm_cuit = _normalize_cuit(row.get("cuit"))

        company = None
        if norm_cuit:
            company = db.scalar(select(Company).where(Company.cuit == norm_cuit))
        if company is None:
            company = db.scalar(select(Company).where(Company.legal_name == legal_name))
        if company is None:
            company = create_company(db, legal_name=legal_name, brand_name=brand_name, cuit=norm_cuit)
            stats["companies_created"] += 1

        dim = (row.get("dimension") or "").strip().upper()
        cls = (row.get("classification") or "UNKNOWN").strip().upper() or "UNKNOWN"
        valid_from_str = (row.get("valid_from") or "").strip()
        valid_to_str = (row.get("valid_to") or "").strip()
        valid_from = date.fromisoformat(valid_from_str) if valid_from_str else date.today()
        valid_to = date.fromisoformat(valid_to_str) if valid_to_str else None
        src_code = (row.get("official_source_code") or "").strip().upper()
        src_obj = sources_by_code.get(src_code)

        res = auditor.audit_and_record(
            company_id=company.company_id,
            dimension=dim,
            classification=cls,
            valid_from=valid_from,
            valid_to=valid_to,
            official_source_id=src_obj.official_source_id if src_obj else None,
            source_url=row.get("source_url"),
            evidence=row.get("evidence") or "",
        )
        if res.audit_status == "VERIFIED":
            stats["records_verified"] += 1
        else:
            stats["records_rejected"] += 1

    db.commit()
    return stats
