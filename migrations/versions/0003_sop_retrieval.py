"""Create versioned tenant-scoped SOP retrieval records.

Revision ID: 0003_sop_retrieval
Revises: 0002_artifact_ingestion
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0003_sop_retrieval"
down_revision = "0002_artifact_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sop_documents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_name", sa.String(length=240), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_sop_documents_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id", "title", "version", name="uq_sop_documents_tenant_version"
        ),
        sa.CheckConstraint(
            "status in ('draft', 'approved', 'retired')", name="ck_sop_documents_status"
        ),
    )
    op.create_index(
        "ix_sop_documents_tenant_effective",
        "sop_documents",
        ["tenant_id", "status", "effective_from"],
    )
    op.create_table(
        "sop_chunks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("sop_document_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=80), nullable=False),
        sa.Column("customer_account_code", sa.String(length=64), nullable=True),
        sa.Column("location_code", sa.String(length=64), nullable=True),
        sa.Column("service_level", sa.String(length=64), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sop_document_id", "tenant_id"],
            ["sop_documents.id", "sop_documents.tenant_id"],
            ondelete="CASCADE",
            name="fk_sop_chunks_document_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id", "sop_document_id", "ordinal", name="uq_sop_chunks_ordinal"
        ),
    )
    op.create_index(
        "ix_sop_chunks_tenant_metadata",
        "sop_chunks",
        [
            "tenant_id",
            "customer_account_code",
            "location_code",
            "service_level",
            "rule_type",
        ],
    )
    op.create_table(
        "retrieval_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column("filter_json", sa.Text(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=120), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_retrieval_runs_tenant_created", "retrieval_runs", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_retrieval_runs_tenant_query", "retrieval_runs", ["tenant_id", "query_sha256"]
    )
    op.create_table(
        "retrieval_hits",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("retrieval_run_id", sa.String(length=64), nullable=False),
        sa.Column("sop_chunk_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("lexical_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["retrieval_run_id", "tenant_id"],
            ["retrieval_runs.id", "retrieval_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_retrieval_hits_run_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["sop_chunk_id", "tenant_id"],
            ["sop_chunks.id", "sop_chunks.tenant_id"],
            ondelete="CASCADE",
            name="fk_retrieval_hits_chunk_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id", "retrieval_run_id", "sop_chunk_id", name="uq_retrieval_hit"
        ),
    )
    op.create_index(
        "ix_retrieval_hits_tenant_run", "retrieval_hits", ["tenant_id", "retrieval_run_id", "rank"]
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_hits_tenant_run", table_name="retrieval_hits")
    op.drop_table("retrieval_hits")
    op.drop_index("ix_retrieval_runs_tenant_query", table_name="retrieval_runs")
    op.drop_index("ix_retrieval_runs_tenant_created", table_name="retrieval_runs")
    op.drop_table("retrieval_runs")
    op.drop_index("ix_sop_chunks_tenant_metadata", table_name="sop_chunks")
    op.drop_table("sop_chunks")
    op.drop_index("ix_sop_documents_tenant_effective", table_name="sop_documents")
    op.drop_table("sop_documents")
