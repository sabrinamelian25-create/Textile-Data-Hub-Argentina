"""Experimental Industry Structure module: companies, chain positions, and audited classification history.

Revision ID: 0002_company_structure_module
Revises: 0001_initial_schema
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_company_structure_module"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("cuit", sa.String(length=16), nullable=True),
        sa.Column("company_size", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("company_origin", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("production_model", sa.String(length=48), nullable=False, server_default="UNKNOWN"),
        sa.Column("classification_status", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("company_id"),
        sa.UniqueConstraint("cuit", name="uq_core_companies_cuit"),
        schema="core",
    )
    op.create_index("ix_core_companies_legal_name", "companies", ["legal_name"], schema="core")
    op.create_index("ix_core_companies_brand_name", "companies", ["brand_name"], schema="core")
    op.create_index("ix_core_companies_cuit", "companies", ["cuit"], schema="core")
    op.create_index("ix_core_companies_company_size", "companies", ["company_size"], schema="core")
    op.create_index("ix_core_companies_company_origin", "companies", ["company_origin"], schema="core")
    op.create_index("ix_core_companies_production_model", "companies", ["production_model"], schema="core")
    op.create_index("ix_core_companies_classification_status", "companies", ["classification_status"], schema="core")

    op.create_table(
        "company_chain_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("chain_position", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.company_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "chain_position", name="uq_company_chain_position"),
        schema="core",
    )
    op.create_index(
        "ix_core_company_chain_positions_company_id", "company_chain_positions", ["company_id"], schema="core"
    )
    op.create_index(
        "ix_core_company_chain_positions_chain_position", "company_chain_positions", ["chain_position"], schema="core"
    )

    op.create_table(
        "company_classification_history",
        sa.Column("history_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=48), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("official_source_id", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("audit_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("audit_notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["core.companies.company_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["official_source_id"], ["core.official_sources.official_source_id"]),
        sa.PrimaryKeyConstraint("history_id"),
        schema="core",
    )
    op.create_index(
        "ix_core_cch_company_id", "company_classification_history", ["company_id"], schema="core"
    )
    op.create_index(
        "ix_core_cch_dimension", "company_classification_history", ["dimension"], schema="core"
    )
    op.create_index(
        "ix_core_cch_classification", "company_classification_history", ["classification"], schema="core"
    )
    op.create_index(
        "ix_core_cch_official_source_id", "company_classification_history", ["official_source_id"], schema="core"
    )
    op.create_index(
        "ix_core_cch_audit_status", "company_classification_history", ["audit_status"], schema="core"
    )
    op.create_index(
        "ix_cch_company_dim_valid",
        "company_classification_history",
        ["company_id", "dimension", "valid_to"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("company_classification_history", schema="core")
    op.drop_table("company_chain_positions", schema="core")
    op.drop_table("companies", schema="core")
