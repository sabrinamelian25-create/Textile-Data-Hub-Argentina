from datetime import date, datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class OfficialSource(Base):
    __tablename__ = "official_sources"
    __table_args__ = {"schema": "core"}

    official_source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    official_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(120), nullable=False, default="República Argentina (Nacional)")
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="source")
    series: Mapped[list["Series"]] = relationship(back_populates="source")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = {"schema": "core"}

    dataset_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("core.official_sources.official_source_id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    official_url: Mapped[str] = mapped_column(Text, nullable=False)
    download_url: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["OfficialSource"] = relationship(back_populates="datasets")
    series: Mapped[list["Series"]] = relationship(back_populates="dataset")
    raw_extractions: Mapped[list["RawExtraction"]] = relationship(back_populates="dataset")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = {"schema": "core"}

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dataset_code: Mapped[str] = mapped_column(String(120), nullable=False)
    schedule_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    records_downloaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RawExtraction(Base):
    __tablename__ = "raw_extractions"
    __table_args__ = {"schema": "raw"}

    raw_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("core.ingestion_runs.run_id"), nullable=False, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("core.datasets.dataset_id"), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    response_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="raw_extractions")


class StagedObservation(Base):
    __tablename__ = "staged_observations"
    __table_args__ = {"schema": "staging"}

    staging_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw.raw_extractions.raw_id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("core.ingestion_runs.run_id"), nullable=False, index=True)
    series_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    observation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raw_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    is_preliminary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    audit_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    audit_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    staged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Series(Base):
    __tablename__ = "series"
    __table_args__ = {"schema": "core"}

    series_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    series_name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    what_it_measures: Mapped[str] = mapped_column(Text, nullable=False)
    how_it_is_built: Mapped[str] = mapped_column(Text, nullable=False)
    economic_relevance: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_summary: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation_notes: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    economic_sense_note: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(120), nullable=False)
    base_period: Mapped[str | None] = mapped_column(String(120), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subcategory: Mapped[str] = mapped_column(String(120), nullable=False)
    is_context_variable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    geography: Mapped[str] = mapped_column(String(120), nullable=False, default="Argentina (Nacional)")
    textile_chain_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seasonal_adjustment: Mapped[str] = mapped_column(String(160), nullable=False, default="Sin ajuste estacional")
    price_type: Mapped[str] = mapped_column(String(160), nullable=False, default="No aplica")
    currency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("core.official_sources.official_source_id"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("core.datasets.dataset_id"), nullable=False)
    source_series_code: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_observation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    series_type: Mapped[str] = mapped_column(String(32), nullable=False, default="OFFICIAL")
    audit_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suggested_comparisons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    research_questions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    source: Mapped["OfficialSource"] = relationship(back_populates="series")
    dataset: Mapped["Dataset"] = relationship(back_populates="series")
    observations: Mapped[list["Observation"]] = relationship(back_populates="series")
    derived_lineage: Mapped["DerivedSeriesLineage | None"] = relationship(back_populates="derived_series", uselist=False)
    audit_reports: Mapped[list["AuditReport"]] = relationship(back_populates="series")


class DerivedSeriesLineage(Base):
    __tablename__ = "derived_series_lineage"
    __table_args__ = {"schema": "core"}

    lineage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    derived_series_id: Mapped[int] = mapped_column(ForeignKey("core.series.series_id"), unique=True, nullable=False)
    source_series_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    deflator_series_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    derived_series: Mapped["Series"] = relationship(back_populates="derived_lineage")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", "revision_number", name="uq_obs_series_date_rev"),
        Index(
            "uq_obs_series_date_current",
            "series_id",
            "observation_date",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index("ix_obs_series_date", "series_id", "observation_date"),
        {"schema": "core"},
    )

    observation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("core.series.series_id"), nullable=False)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="VERIFIED")
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_preliminary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_outlier_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outlier_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw.raw_extractions.raw_id"), nullable=False)

    series: Mapped["Series"] = relationship(back_populates="observations")


class TradeProductMapping(Base):
    __tablename__ = "trade_product_mapping"
    __table_args__ = (
        UniqueConstraint("nomenclature", "product_code", name="uq_trade_nomenclature_code"),
        {"schema": "core"},
    )

    mapping_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nomenclature: Mapped[str] = mapped_column(String(32), nullable=False, default="NCM")
    product_code: Mapped[str] = mapped_column(String(32), nullable=False)
    official_description: Mapped[str] = mapped_column(Text, nullable=False)
    textile_chain_level: Mapped[str] = mapped_column(String(64), nullable=False)
    analytical_group: Mapped[str] = mapped_column(String(120), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, default=date(1990, 1, 1))
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditReport(Base):
    __tablename__ = "audit_reports"
    __table_args__ = {"schema": "core"}

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("core.ingestion_runs.run_id"), nullable=False, index=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("core.series.series_id"), nullable=False, index=True)
    audit_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revisions_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outliers_flagged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    series: Mapped["Series"] = relationship(back_populates="audit_reports")
    findings: Mapped[list["AuditFinding"]] = relationship(back_populates="report")


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    __table_args__ = {"schema": "core"}

    finding_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("core.audit_reports.report_id"), nullable=False, index=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("core.series.series_id"), nullable=False, index=True)
    check_category: Mapped[str] = mapped_column(String(32), nullable=False)
    check_code: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report: Mapped["AuditReport"] = relationship(back_populates="findings")


class SearchSynonym(Base):
    __tablename__ = "search_synonyms"
    __table_args__ = {"schema": "core"}

    synonym_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    expanded_terms: Mapped[list] = mapped_column(JSONB, nullable=False)
    target_series_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = {"schema": "core"}

    term_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    term_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    short_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    academic_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Company(Base):
    """Experimental corporate structure entity with strictly independent dimensions."""

    __tablename__ = "companies"
    __table_args__ = {"schema": "core"}

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    cuit: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True, index=True)
    company_size: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN", index=True)
    company_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN", index=True)
    production_model: Mapped[str] = mapped_column(String(48), nullable=False, default="UNKNOWN", index=True)
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chain_positions: Mapped[list["CompanyChainPosition"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    classification_history: Mapped[list["CompanyClassificationHistory"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyChainPosition(Base):
    """Multi-valued Dimension D: verifiable positions occupied by a company in the textile chain."""

    __tablename__ = "company_chain_positions"
    __table_args__ = (
        UniqueConstraint("company_id", "chain_position", name="uq_company_chain_position"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("core.companies.company_id", ondelete="CASCADE"), nullable=False, index=True
    )
    chain_position: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    company: Mapped["Company"] = relationship(back_populates="chain_positions")


class CompanyClassificationHistory(Base):
    """Audited temporal history of official evidence for each independent company dimension."""

    __tablename__ = "company_classification_history"
    __table_args__ = (
        Index("ix_cch_company_dim_valid", "company_id", "dimension", "valid_to"),
        {"schema": "core"},
    )

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("core.companies.company_id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    classification: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    official_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("core.official_sources.official_source_id"), nullable=True, index=True
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    audit_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    audit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="classification_history")
    official_source: Mapped["OfficialSource | None"] = relationship()
