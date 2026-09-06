"""Create tenant-scoped artifact lifecycle storage.

Revision ID: 0002_artifact_ingestion
Revises: 0001_identity_tenancy
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0002_artifact_ingestion"
down_revision = "0001_identity_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intake_id", sa.String(length=64), nullable=True),
        sa.Column("artifact_role", sa.String(length=32), nullable=False, server_default="source"),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("display_filename", sa.String(length=255), nullable=False),
        sa.Column("declared_media_type", sa.String(length=200), nullable=True),
        sa.Column("detected_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="quarantined"),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("external_request_reference", sa.String(length=200), nullable=True),
        sa.Column("amendment_of_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rejection_code", sa.String(length=64), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "content_sha256",
            "artifact_role",
            name="uq_artifacts_tenant_hash_role",
        ),
        sa.CheckConstraint(
            "artifact_role in ('source', 'derived_text', 'parsed')",
            name="ck_artifacts_role",
        ),
        sa.CheckConstraint(
            "status in ('quarantined', 'accepted', 'rejected', 'expired')",
            name="ck_artifacts_status",
        ),
    )
    op.create_index("ix_artifacts_tenant_created", "artifacts", ["tenant_id", "created_at"])
    op.create_index("ix_artifacts_tenant_intake", "artifacts", ["tenant_id", "intake_id"])
    op.create_index(
        "ix_artifacts_tenant_reference",
        "artifacts",
        ["tenant_id", "external_request_reference"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifacts_tenant_reference", table_name="artifacts")
    op.drop_index("ix_artifacts_tenant_intake", table_name="artifacts")
    op.drop_index("ix_artifacts_tenant_created", table_name="artifacts")
    op.drop_table("artifacts")
