from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.seed_catalog import (
    COMPANIES_OFFICIAL_SEED,
    DATASETS_SEED,
    GLOSSARY_TERMS_SEED,
    OFFICIAL_SOURCES_SEED,
    SEARCH_SYNONYMS_SEED,
    TRADE_PRODUCT_MAPPING_SEED,
)
from app.catalog.series_catalog import SERIES_CATALOG
from app.db.models import (
    Company,
    Dataset,
    GlossaryTerm,
    OfficialSource,
    SearchSynonym,
    Series,
    TradeProductMapping,
)
from app.services.industry_structure import CompanyClassificationAuditor, create_company


def seed_all(db: Session) -> dict[str, int]:
    """Idempotently upsert official_sources, datasets, series, trade_product_mapping, synonyms, glossary."""
    counts = {"sources": 0, "datasets": 0, "series": 0, "trade_mapping": 0, "synonyms": 0, "glossary": 0}

    source_map: dict[str, OfficialSource] = {}
    for item in OFFICIAL_SOURCES_SEED:
        obj = db.scalar(select(OfficialSource).where(OfficialSource.source_code == item["source_code"]))
        if obj is None:
            obj = OfficialSource(**item)
            db.add(obj)
            db.flush()
            counts["sources"] += 1
        else:
            for k, v in item.items():
                setattr(obj, k, v)
        source_map[item["source_code"]] = obj

    dataset_map: dict[str, Dataset] = {}
    for item in DATASETS_SEED:
        src = source_map[item["source_code"]]
        payload = {k: v for k, v in item.items() if k != "source_code"}
        payload["source_id"] = src.official_source_id
        obj = db.scalar(select(Dataset).where(Dataset.dataset_code == item["dataset_code"]))
        if obj is None:
            obj = Dataset(**payload)
            db.add(obj)
            db.flush()
            counts["datasets"] += 1
        else:
            for k, v in payload.items():
                setattr(obj, k, v)
        dataset_map[item["dataset_code"]] = obj

    for item in SERIES_CATALOG:
        src = source_map[item["source_code"]]
        ds = dataset_map[item["dataset_code"]]
        payload = {k: v for k, v in item.items() if k not in ("source_code", "dataset_code")}
        payload["source_id"] = src.official_source_id
        payload["dataset_id"] = ds.dataset_id
        obj = db.scalar(select(Series).where(Series.series_code == item["series_code"]))
        if obj is None:
            obj = Series(**payload, audit_status="PENDING", active=True)
            db.add(obj)
            counts["series"] += 1
        else:
            for k, v in payload.items():
                setattr(obj, k, v)

    for item in TRADE_PRODUCT_MAPPING_SEED:
        obj = db.scalar(
            select(TradeProductMapping).where(
                TradeProductMapping.nomenclature == item["nomenclature"],
                TradeProductMapping.product_code == item["product_code"],
            )
        )
        if obj is None:
            db.add(TradeProductMapping(**item))
            counts["trade_mapping"] += 1
        else:
            for k, v in item.items():
                setattr(obj, k, v)

    for item in SEARCH_SYNONYMS_SEED:
        obj = db.scalar(select(SearchSynonym).where(SearchSynonym.term == item["term"]))
        if obj is None:
            db.add(SearchSynonym(**item))
            counts["synonyms"] += 1
        else:
            obj.expanded_terms = item["expanded_terms"]
            obj.target_series_codes = item["target_series_codes"]

    for item in GLOSSARY_TERMS_SEED:
        obj = db.scalar(select(GlossaryTerm).where(GlossaryTerm.term_key == item["term_key"]))
        if obj is None:
            db.add(GlossaryTerm(**item))
            counts["glossary"] += 1
        else:
            for k, v in item.items():
                setattr(obj, k, v)

    counts["companies"] = 0
    auditor = CompanyClassificationAuditor(db)
    for c_item in COMPANIES_OFFICIAL_SEED:
        existing_c = db.scalar(select(Company).where(Company.legal_name == c_item["legal_name"]))
        if existing_c is None:
            comp = create_company(
                db,
                legal_name=c_item["legal_name"],
                brand_name=c_item.get("brand_name"),
                cuit=c_item.get("cuit"),
                notes=c_item.get("notes"),
            )
            for cls_row in c_item.get("classifications", []):
                src_code = cls_row.get("official_source_code")
                src_obj = source_map.get(src_code) if src_code else None
                auditor.audit_and_record(
                    company_id=comp.company_id,
                    dimension=cls_row["dimension"],
                    classification=cls_row["classification"],
                    valid_from=cls_row["valid_from"],
                    valid_to=cls_row.get("valid_to"),
                    official_source_id=src_obj.official_source_id if src_obj else None,
                    source_url=cls_row.get("source_url"),
                    evidence=cls_row["evidence"],
                )
            counts["companies"] += 1

    db.commit()
    return counts
