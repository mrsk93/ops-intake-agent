"""Persist immutable action previews before any approval or execution.

Revision ID: 0006_proposed_actions
Revises: 0005_review_versioning
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0006_proposed_actions"
down_revision = "0005_review_versioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposed_actions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("intake_run_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("draft_version_id", sa.String(length=64), nullable=False),
        sa.Column("validation_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("action_version", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="ready"),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_proposed_actions_intake_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "tenant_id"],
            ["reviews.id", "reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_proposed_actions_review_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_proposed_actions_idempotency"),
        sa.CheckConstraint(
            "status in ('ready', 'claimed', 'executing', 'uncertain', 'verified', 'failed', 'cancelled', 'manual_exception')",
            name="ck_proposed_actions_status",
        ),
    )
    op.create_index(
        "ix_proposed_actions_tenant_intake",
        "proposed_actions",
        ["tenant_id", "intake_run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposed_actions_tenant_intake", table_name="proposed_actions")
    op.drop_table("proposed_actions")
