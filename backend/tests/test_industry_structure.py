from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import OfficialSource
from app.db.session import get_db
from app.main import app
from app.services.industry_structure import (
    CompanyClassificationAuditor,
    create_company,
    import_company_evidence_csv,
    query_companies,
)


def _source_id(db, code: str) -> int:
    src = db.scalar(select(OfficialSource).where(OfficialSource.source_code == code))
    assert src is not None, f"Expected official source {code}"
    return src.official_source_id


def test_company_defaults_to_unknown_and_rejects_forbidden_sources(db_session):
    c = create_company(db_session, legal_name="Firma Textil Experimental S.A.", brand_name="Marca Test")
    db_session.commit()

    assert c.company_size == "UNKNOWN"
    assert c.company_origin == "UNKNOWN"
    assert c.production_model == "UNKNOWN"
    assert c.classification_status == "UNKNOWN"
    assert [p.chain_position for p in c.chain_positions] == ["UNKNOWN"]

    auditor = CompanyClassificationAuditor(db_session)
    sepyme_id = _source_id(db_session, "SEPYME_MIPYME")
    bora_id = _source_id(db_session, "BOLETIN_OFICIAL")
    cnv_id = _source_id(db_session, "CNV_AIF")

    # 1. Wikipedia MUST be rejected
    r_wiki = auditor.audit_and_record(
        company_id=c.company_id,
        dimension="SIZE",
        classification="LARGE",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=sepyme_id,
        source_url="https://es.wikipedia.org/wiki/Empresa_ejemplo",
        evidence="Según artículo de Wikipedia es una empresa grande.",
    )
    assert r_wiki.audit_status == "REJECTED"
    assert r_wiki.promoted_to_company is False

    # 2. Social media MUST be rejected
    r_ig = auditor.audit_and_record(
        company_id=c.company_id,
        dimension="PRODUCTION_MODEL",
        classification="LOCAL_PRIMARY",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=cnv_id,
        source_url="https://www.instagram.com/marca_ejemplo",
        evidence="En Instagram muestran talleres propios en Buenos Aires.",
    )
    assert r_ig.audit_status == "REJECTED"

    # 3. News outlet MUST be rejected
    r_news = auditor.audit_and_record(
        company_id=c.company_id,
        dimension="ORIGIN",
        classification="NATIONAL",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=bora_id,
        source_url="https://www.infobae.com/economia/nota-textil",
        evidence="Nota periodística indica que es de capital argentino.",
    )
    assert r_news.audit_status == "REJECTED"

    # 4. Commercial brand site / mismatched domain MUST be rejected
    r_comm = auditor.audit_and_record(
        company_id=c.company_id,
        dimension="PRODUCTION_MODEL",
        classification="IMPORTED_FINISHED",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=cnv_id,
        source_url="https://www.marca-comercial.com.ar/nosotros",
        evidence="El sitio comercial declara origen de productos importados.",
    )
    assert r_comm.audit_status == "REJECTED"

    # 5. Model knowledge / brand perception even with an official URL MUST be rejected
    r_llm = auditor.audit_and_record(
        company_id=c.company_id,
        dimension="SIZE",
        classification="LARGE",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=sepyme_id,
        source_url="https://www.argentina.gob.ar/produccion/registrar-una-pyme",
        evidence="Inferido por percepción de marca y conocimiento del modelo como firma muy conocida.",
    )
    assert r_llm.audit_status == "REJECTED"

    # Company state MUST remain strictly UNKNOWN across all 4 dimensions!
    db_session.refresh(c)
    assert c.company_size == "UNKNOWN"
    assert c.company_origin == "UNKNOWN"
    assert c.production_model == "UNKNOWN"
    assert c.classification_status == "UNKNOWN"
    assert [p.chain_position for p in c.chain_positions] == ["UNKNOWN"]


def test_official_evidence_verification_multipositions_history_and_combinable_filters(db_session):
    sepyme_id = _source_id(db_session, "SEPYME_MIPYME")
    bora_id = _source_id(db_session, "BOLETIN_OFICIAL")
    cnv_id = _source_id(db_session, "CNV_AIF")
    arca_id = _source_id(db_session, "ARCA_AFIP")
    sic_id = _source_id(db_session, "SIC_RIN")

    auditor = CompanyClassificationAuditor(db_session)

    # Company 1: PyME (SMALL) + NATIONAL + LOCAL_PRIMARY + [APPAREL, BRAND]
    c1 = create_company(db_session, legal_name="Confecciones Sur S.R.L.", brand_name="Sur Indumentaria", cuit="30-70000001-1")
    r1 = auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="SIZE",
        classification="MICRO",
        valid_from=date(2024, 1, 1),
        valid_to=None,
        official_source_id=sepyme_id,
        source_url="https://www.argentina.gob.ar/economia/pymes-emprendedores-y-economia-del-conocimiento",
        evidence="Certificado MiPyME categoría Micro Industria vigente ejercicio 2024 (Res. SEPyME 220/2019).",
    )
    assert r1.audit_status == "VERIFIED"

    # Supersede SIZE from MICRO -> SMALL in 2026; history must preserve MICRO with valid_to=2026-01-01
    r1b = auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="SIZE",
        classification="SMALL",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=sepyme_id,
        source_url="https://www.argentina.gob.ar/economia/pymes-emprendedores-y-economia-del-conocimiento",
        evidence="Certificado MiPyME actualizado categoría Pequeña Industria (Res. SIC 1/2026).",
    )
    assert r1b.audit_status == "VERIFIED"

    auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="ORIGIN",
        classification="NATIONAL",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=bora_id,
        source_url="https://www.boletinoficial.gob.ar/detalleAviso/segunda/123456",
        evidence="Edicto de constitución y composición societaria 100% socios domiciliados en Argentina (BORA Sección Sociedades).",
    )
    auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="PRODUCTION_MODEL",
        classification="LOCAL_PRIMARY",
        valid_from=date(2025, 6, 1),
        valid_to=None,
        official_source_id=sic_id,
        source_url="https://datos.produccion.gob.ar/dataset/registro-mipyme",
        evidence="Inscripción oficial en Registro Industrial de la Nación con planta de confección activa en territorio nacional.",
    )
    # Multi-valued chain positions: APPAREL + BRAND
    auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="CHAIN_POSITION",
        classification="APPAREL",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=arca_id,
        source_url="https://www.afip.gob.ar/actividades/clae",
        evidence="Constancia oficial F.883 actividad principal CLAE 141199 Confección de prendas de vestir.",
    )
    auditor.audit_and_record(
        company_id=c1.company_id,
        dimension="CHAIN_POSITION",
        classification="BRAND",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=arca_id,
        source_url="https://www.afip.gob.ar/actividades/clae",
        evidence="Actividad secundaria registrada en padrón oficial vinculada a diseño y desarrollo de colección propia.",
    )

    # Company 2: LARGE + FOREIGN + IMPORTED_FINISHED + [RETAIL]
    c2 = create_company(db_session, legal_name="Importadora Global Textil S.A.", cuit="30-70000002-2")
    auditor.audit_and_record(
        company_id=c2.company_id,
        dimension="SIZE",
        classification="LARGE",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=cnv_id,
        source_url="https://www.cnv.gov.ar/SitioWeb/Empresas",
        evidence="Estados contables auditados CNV AIF 2025 superan topes máximos de facturación MiPyME vigentes.",
    )
    auditor.audit_and_record(
        company_id=c2.company_id,
        dimension="ORIGIN",
        classification="FOREIGN",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=cnv_id,
        source_url="https://www.cnv.gov.ar/SitioWeb/Empresas",
        evidence="Nota 12 de Estados Contables auditados CNV AIF declara sociedad controlante domiciliada en el exterior.",
    )
    auditor.audit_and_record(
        company_id=c2.company_id,
        dimension="PRODUCTION_MODEL",
        classification="IMPORTED_FINISHED",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=cnv_id,
        source_url="https://www.cnv.gov.ar/SitioWeb/Empresas",
        evidence="Memoria anual auditada CNV AIF informa actividad exclusiva de importación de prendas terminadas.",
    )
    auditor.audit_and_record(
        company_id=c2.company_id,
        dimension="CHAIN_POSITION",
        classification="RETAIL",
        valid_from=date(2025, 1, 1),
        valid_to=None,
        official_source_id=arca_id,
        source_url="https://www.afip.gob.ar/actividades/clae",
        evidence="Constancia oficial CLAE 477110 Venta al por menor de prendas y accesorios de vestir.",
    )

    # Company 3: Partially verified (only ORIGIN verified; SIZE, PRODUCTION_MODEL, CHAIN_POSITION remain UNKNOWN)
    c3 = create_company(db_session, legal_name="Hilados Parcial S.A.")
    auditor.audit_and_record(
        company_id=c3.company_id,
        dimension="ORIGIN",
        classification="NATIONAL",
        valid_from=date(2026, 1, 1),
        valid_to=None,
        official_source_id=bora_id,
        source_url="https://www.boletinoficial.gob.ar/detalleAviso/segunda/999999",
        evidence="Edicto societario oficial en Boletín Oficial acredita capital accionario nacional.",
    )
    db_session.commit()

    db_session.refresh(c1)
    db_session.refresh(c2)
    db_session.refresh(c3)
    assert c1.company_size == "SMALL"
    assert c1.classification_status == "VERIFIED_COMPLETE"
    assert sorted(p.chain_position for p in c1.chain_positions) == ["APPAREL", "BRAND"]
    assert c2.classification_status == "VERIFIED_COMPLETE"
    assert c3.classification_status == "PARTIALLY_VERIFIED"
    assert c3.company_size == "UNKNOWN"
    assert c3.production_model == "UNKNOWN"

    # Verify history closed the superseded MICRO record
    size_hist = [h for h in c1.classification_history if h.dimension == "SIZE"]
    assert len(size_hist) == 2
    micro_row = next(h for h in size_hist if h.classification == "MICRO")
    small_row = next(h for h in size_hist if h.classification == "SMALL")
    assert micro_row.valid_to == date(2026, 1, 1)
    assert small_row.valid_to is None

    # Combinable filter matching the prompt example: PyME + Nacional + Producción principalmente local + Confección
    matched = query_companies(
        db_session,
        sizes=["PYME"],
        origins=["NATIONAL"],
        production_models=["LOCAL_PRIMARY"],
        chain_positions=["APPAREL"],
    )
    assert c1.company_id in [c.company_id for c in matched]

    # Multi-position AND match
    matched_and = query_companies(db_session, chain_positions=["APPAREL", "BRAND"], chain_match="all")
    assert [c.company_id for c in matched_and] == [c1.company_id]
    assert query_companies(db_session, chain_positions=["APPAREL", "RETAIL"], chain_match="all") == []


def test_industry_structure_api_and_research_integration(db_session):
    sepyme_id = _source_id(db_session, "SEPYME_MIPYME")
    bora_id = _source_id(db_session, "BOLETIN_OFICIAL")

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    try:
        # Taxonomy & summary
        r_tax = client.get("/api/industry-structure/taxonomy")
        assert r_tax.status_code == 200
        assert len(r_tax.json()["dimensions"]) == 4

        # Register company via API
        r_new = client.post(
            "/api/industry-structure/companies",
            json={"legal_name": "Tejeduría API S.A.", "brand_name": "TejeAPI"},
        )
        assert r_new.status_code == 201
        cid = r_new.json()["company_id"]
        assert r_new.json()["company_size"] == "UNKNOWN"
        assert r_new.json()["classification_status"] == "UNKNOWN"

        # Submit forbidden source -> stored as REJECTED, company stays UNKNOWN
        r_rej = client.post(
            f"/api/industry-structure/companies/{cid}/classifications",
            json={
                "dimension": "SIZE",
                "classification": "MEDIUM",
                "valid_from": "2026-01-01",
                "official_source_id": sepyme_id,
                "source_url": "https://es.wikipedia.org/wiki/Tejeduria",
                "evidence": "Tomado de Wikipedia sin fuente oficial.",
            },
        )
        assert r_rej.status_code == 201
        assert r_rej.json()["audit_result"]["audit_status"] == "REJECTED"
        assert r_rej.json()["company"]["company_size"] == "UNKNOWN"

        # Submit official verified evidence -> VERIFIED and promoted
        r_ok = client.post(
            f"/api/industry-structure/companies/{cid}/classifications",
            json={
                "dimension": "SIZE",
                "classification": "MEDIUM",
                "valid_from": "2026-01-01",
                "official_source_id": sepyme_id,
                "source_url": "https://www.argentina.gob.ar/produccion/registrar-una-pyme",
                "evidence": "Certificado MiPyME vigente categoría Mediana Tramo 1 Industria (Res. SIC 1/2026).",
            },
        )
        assert r_ok.status_code == 201
        assert r_ok.json()["audit_result"]["audit_status"] == "VERIFIED"
        assert r_ok.json()["company"]["company_size"] == "MEDIUM"

        # Submit ORIGIN verified
        r_orig = client.post(
            f"/api/industry-structure/companies/{cid}/classifications",
            json={
                "dimension": "ORIGIN",
                "classification": "NATIONAL",
                "valid_from": "2026-01-01",
                "official_source_id": bora_id,
                "source_url": "https://www.boletinoficial.gob.ar/detalleAviso/segunda/7777",
                "evidence": "Edicto societario oficial en Boletín Oficial acredita accionistas residentes argentinos.",
            },
        )
        assert r_orig.status_code == 201
        assert r_orig.json()["company"]["company_origin"] == "NATIONAL"

        # Filter via API combining PYME + NATIONAL
        r_list = client.get("/api/industry-structure/companies?size=PYME&origin=NATIONAL")
        assert r_list.status_code == 200
        assert r_list.json()["count"] >= 1
        assert cid in [item["company_id"] for item in r_list.json()["items"]]

        # Export CSV & JSON
        r_csv = client.get("/api/industry-structure/export?format=csv&size=PYME")
        assert r_csv.status_code == 200
        assert "Tejeduría API S.A." in r_csv.text

        r_json = client.get("/api/industry-structure/export?format=json&size=PYME")
        assert r_json.status_code == 200
        assert r_json.json()["count"] >= 1

        # Research presets & builder (non-causal!)
        r_presets = client.get("/api/industry-structure/research-presets")
        assert r_presets.status_code == 200
        preset_ids = {p["preset_id"] for p in r_presets.json()}
        assert {
            "local_vs_imports",
            "pyme_vs_large",
            "national_vs_foreign",
            "local_vs_imported_finished",
            "import_dependency_by_segment",
        }.issubset(preset_ids)

        r_build = client.post(
            "/api/industry-structure/research-builder",
            json={"preset_id": "pyme_vs_large"},
        )
        assert r_build.status_code == 200
        body = r_build.json()
        assert body["segment_comparison"]["segment_a"]["verified_company_count"] >= 1
        assert body["segment_comparison"]["segment_b"]["verified_company_count"] >= 1
        assert "causalidad" in body["non_causality_warning"].lower()

        r_custom = client.post(
            "/api/industry-structure/research-builder",
            json={
                "sizes": ["PYME"],
                "origins": ["NATIONAL"],
                "production_models": ["LOCAL_PRIMARY"],
                "chain_positions": ["APPAREL"],
            },
        )
        assert r_custom.status_code == 200
        assert "causalidad" in r_custom.json()["non_causality_warning"].lower()

        # Research suggest integrates structural_preset_id
        r_sug = client.get("/api/research/suggest?q=PyMEs+vs+grandes+empresas")
        assert r_sug.status_code == 200
        assert r_sug.json()["structural_preset_id"] == "pyme_vs_large"

        # Audited CSV importer test (1 verified + 1 rejected Wikipedia)
        csv_sample = (
            "legal_name,brand_name,cuit,dimension,classification,valid_from,valid_to,official_source_code,source_url,evidence\n"
            "CSV Valid S.A.,MarcaCSV,30-70000099-1,ORIGIN,NATIONAL,2026-01-01,,BOLETIN_OFICIAL,https://www.boletinoficial.gob.ar/aviso/1,Edicto oficial de constitución societaria publicado en Boletín Oficial.\n"
            "CSV Valid S.A.,MarcaCSV,30-70000099-1,SIZE,LARGE,2026-01-01,,SEPYME_MIPYME,https://es.wikipedia.org/wiki/Algo,Según Wikipedia es una gran empresa.\n"
        )
        stats = import_company_evidence_csv(db_session, csv_sample)
        assert stats["companies_created"] == 1
        assert stats["records_verified"] == 1
        assert stats["records_rejected"] == 1
    finally:
        app.dependency_overrides.clear()
