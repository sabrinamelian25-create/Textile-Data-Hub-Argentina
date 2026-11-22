"""Initial Textile Data Hub Argentina schemas (raw, staging, core) and tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")
    op.execute("CREATE SCHEMA IF NOT EXISTS core")

    op.create_table(
        "official_sources",
        sa.Column("official_source_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("official_domain", sa.String(length=255), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("official_source_id"),
        sa.UniqueConstraint("source_code"),
        schema="core",
    )
    op.create_index("ix_core_official_sources_source_code", "official_sources", ["source_code"], schema="core")

    op.create_table(
        "datasets",
        sa.Column("dataset_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_code", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("official_url", sa.Text(), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=False),
        sa.Column("methodology_url", sa.Text(), nullable=True),
        sa.Column("update_frequency", sa.String(length=32), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["core.official_sources.official_source_id"]),
        sa.PrimaryKeyConstraint("dataset_id"),
        sa.UniqueConstraint("dataset_code"),
        schema="core",
    )
    op.create_index("ix_core_datasets_dataset_code", "datasets", ["dataset_code"], schema="core")

    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("connector_name", sa.String(length=120), nullable=False),
        sa.Column("dataset_code", sa.String(length=120), nullable=False),
        sa.Column("schedule_tier", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("records_downloaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
        schema="core",
    )
    op.create_index("ix_core_ingestion_runs_connector_name", "ingestion_runs", ["connector_name"], schema="core")

    op.create_table(
        "raw_extractions",
        sa.Column("raw_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("response_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["core.datasets.dataset_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["core.ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("raw_id"),
        schema="raw",
    )
    op.create_index("ix_raw_raw_extractions_run_id", "raw_extractions", ["run_id"], schema="raw")
    op.create_index("ix_raw_raw_extractions_dataset_id", "raw_extractions", ["dataset_id"], schema="raw")

    op.create_table(
        "staged_observations",
        sa.Column("staging_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("raw_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("series_code", sa.String(length=120), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=True),
        sa.Column("raw_value", sa.String(length=128), nullable=True),
        sa.Column("numeric_value", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("is_preliminary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_release_date", sa.Date(), nullable=True),
        sa.Column("audit_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("audit_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("staged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["raw_id"], ["raw.raw_extractions.raw_id"]),
        sa.ForeignKeyConstraint(["run_id"], ["core.ingestion_runs.run_id"]),
        sa.PrimaryKeyConstraint("staging_id"),
        schema="staging",
    )
    op.create_index("ix_staging_staged_observations_raw_id", "staged_observations", ["raw_id"], schema="staging")
    op.create_index("ix_staging_staged_observations_run_id", "staged_observations", ["run_id"], schema="staging")
    op.create_index("ix_staging_staged_observations_series_code", "staged_observations", ["series_code"], schema="staging")

    op.create_table(
        "series",
        sa.Column("series_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series_code", sa.String(length=120), nullable=False),
        sa.Column("series_name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("what_it_measures", sa.Text(), nullable=False),
        sa.Column("how_it_is_built", sa.Text(), nullable=False),
        sa.Column("economic_relevance", sa.Text(), nullable=False),
        sa.Column("methodology_summary", sa.Text(), nullable=False),
        sa.Column("interpretation_notes", sa.Text(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.Column("economic_sense_note", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=120), nullable=False),
        sa.Column("base_period", sa.String(length=120), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("subcategory", sa.String(length=120), nullable=False),
        sa.Column("is_context_variable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("geography", sa.String(length=120), nullable=False),
        sa.Column("textile_chain_level", sa.String(length=120), nullable=True),
        sa.Column("seasonal_adjustment", sa.String(length=160), nullable=False),
        sa.Column("price_type", sa.String(length=160), nullable=False),
        sa.Column("currency", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("source_series_code", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("methodology_url", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("last_observation_date", sa.Date(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("series_type", sa.String(length=32), nullable=False),
        sa.Column("audit_status", sa.String(length=32), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("quality_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_comparisons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["dataset_id"], ["core.datasets.dataset_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["core.official_sources.official_source_id"]),
        sa.PrimaryKeyConstraint("series_id"),
        sa.UniqueConstraint("series_code"),
        schema="core",
    )
    op.create_index("ix_core_series_series_code", "series", ["series_code"], schema="core")
    op.create_index("ix_core_series_category", "series", ["category"], schema="core")
    op.create_index("ix_core_series_audit_status", "series", ["audit_status"], schema="core")

    op.create_table(
        "derived_series_lineage",
        sa.Column("lineage_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("derived_series_id", sa.Integer(), nullable=False),
        sa.Column("source_series_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("deflator_series_code", sa.String(length=120), nullable=True),
        sa.Column("calculation_version", sa.String(length=32), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["derived_series_id"], ["core.series.series_id"]),
        sa.PrimaryKeyConstraint("lineage_id"),
        sa.UniqueConstraint("derived_series_id"),
        schema="core",
    )

    op.create_table(
        "observations",
        sa.Column("observation_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_preliminary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_outlier_flagged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("outlier_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_release_date", sa.Date(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("raw_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["raw_id"], ["raw.raw_extractions.raw_id"]),
        sa.ForeignKeyConstraint(["series_id"], ["core.series.series_id"]),
        sa.PrimaryKeyConstraint("observation_id"),
        sa.UniqueConstraint("series_id", "observation_date", "revision_number", name="uq_obs_series_date_rev"),
        schema="core",
    )
    op.create_index("ix_obs_series_date", "observations", ["series_id", "observation_date"], schema="core")
    op.create_index(
        "uq_obs_series_date_current",
        "observations",
        ["series_id", "observation_date"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("is_current = true"),
    )

    op.create_table(
        "trade_product_mapping",
        sa.Column("mapping_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nomenclature", sa.String(length=32), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("official_description", sa.Text(), nullable=False),
        sa.Column("textile_chain_level", sa.String(length=64), nullable=False),
        sa.Column("analytical_group", sa.String(length=120), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("mapping_id"),
        sa.UniqueConstraint("nomenclature", "product_code", name="uq_trade_nomenclature_code"),
        schema="core",
    )

    op.create_table(
        "audit_reports",
        sa.Column("report_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("audit_status", sa.String(length=32), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("quality_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revisions_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outliers_flagged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audited_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["core.ingestion_runs.run_id"]),
        sa.ForeignKeyConstraint(["series_id"], ["core.series.series_id"]),
        sa.PrimaryKeyConstraint("report_id"),
        schema="core",
    )
    op.create_index("ix_core_audit_reports_run_id", "audit_reports", ["run_id"], schema="core")
    op.create_index("ix_core_audit_reports_series_id", "audit_reports", ["series_id"], schema="core")

    op.create_table(
        "audit_findings",
        sa.Column("finding_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=False),
        sa.Column("check_category", sa.String(length=32), nullable=False),
        sa.Column("check_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["core.audit_reports.report_id"]),
        sa.ForeignKeyConstraint(["series_id"], ["core.series.series_id"]),
        sa.PrimaryKeyConstraint("finding_id"),
        schema="core",
    )
    op.create_index("ix_core_audit_findings_report_id", "audit_findings", ["report_id"], schema="core")
    op.create_index("ix_core_audit_findings_series_id", "audit_findings", ["series_id"], schema="core")

    op.create_table(
        "search_synonyms",
        sa.Column("synonym_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("term", sa.String(length=120), nullable=False),
        sa.Column("expanded_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_series_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("synonym_id"),
        sa.UniqueConstraint("term"),
        schema="core",
    )
    op.create_index("ix_core_search_synonyms_term", "search_synonyms", ["term"], schema="core")

    op.create_table(
        "glossary_terms",
        sa.Column("term_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("term_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("short_explanation", sa.Text(), nullable=False),
        sa.Column("academic_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("term_id"),
        sa.UniqueConstraint("term_key"),
        schema="core",
    )
    op.create_index("ix_core_glossary_terms_term_key", "glossary_terms", ["term_key"], schema="core")


def downgrade() -> None:
    op.drop_table("glossary_terms", schema="core")
    op.drop_table("search_synonyms", schema="core")
    op.drop_table("audit_findings", schema="core")
    op.drop_table("audit_reports", schema="core")
    op.drop_table("trade_product_mapping", schema="core")
    op.drop_table("observations", schema="core")
    op.drop_table("derived_series_lineage", schema="core")
    op.drop_table("series", schema="core")
    op.drop_table("staged_observations", schema="staging")
    op.drop_table("raw_extractions", schema="raw")
    op.drop_table("ingestion_runs", schema="core")
    op.drop_table("datasets", schema="core")
    op.drop_table("official_sources", schema="core")
    op.execute("DROP SCHEMA IF EXISTS staging CASCADE")
    op.execute("DROP SCHEMA IF EXISTS raw CASCADE")
    op.execute("DROP SCHEMA IF EXISTS core CASCADE")
