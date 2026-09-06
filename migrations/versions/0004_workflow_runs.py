"""Create tenant-scoped intake run records for workflow threads.

Revision ID: 0004_workflow_runs
Revises: 0003_sop_retrieval
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0004_workflow_runs"
down_revision = "0003_sop_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intake_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=64),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("graph_thread_id", sa.String(length=255), nullable=False),
        sa.Column("external_request_reference", sa.String(length=200), nullable=True),
        sa.Column("review_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "graph_thread_id", name="uq_intake_runs_tenant_thread"),
        sa.CheckConstraint(
            "source_channel in ('upload', 'email', 'webhook', 'demo')",
            name="ck_intake_runs_source_channel",
        ),
        sa.CheckConstraint(
            "status in ('received', 'processing', 'review_required', 'review_received', 'failed', 'completed')",
            name="ck_intake_runs_status",
        ),
    )
    op.create_index(
        "ix_intake_runs_tenant_status",
        "intake_runs",
        ["tenant_id", "status", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_intake_runs_tenant_status", table_name="intake_runs")
    op.drop_table("intake_runs")
