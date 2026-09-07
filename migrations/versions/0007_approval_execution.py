"""Add explicit approvals, execution recovery records and audit events.

Revision ID: 0007_approval_execution
Revises: 0006_proposed_actions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0007_approval_execution"
down_revision = "0006_proposed_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("proposed_actions", recreate="always") as batch:
            batch.create_unique_constraint("uq_proposed_actions_id_tenant", ["id", "tenant_id"])
    else:
        op.create_unique_constraint(
            "uq_proposed_actions_id_tenant", "proposed_actions", ["id", "tenant_id"]
        )
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("proposed_action_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("preview_payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_approvals_action_tenant",
        ),
        sa.CheckConstraint(
            "status in ('active', 'stale', 'consumed', 'revoked')",
            name="ck_approvals_status",
        ),
    )
    op.create_index("ix_approvals_tenant_action", "approvals", ["tenant_id", "proposed_action_id"])
    op.create_table(
        "execution_attempts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("proposed_action_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_execution_attempts_action_tenant",
        ),
        sa.CheckConstraint(
            "status in ('executing', 'uncertain', 'verified', 'failed', 'manual_exception')",
            name="ck_execution_attempts_status",
        ),
        sa.UniqueConstraint(
            "tenant_id", "proposed_action_id", "attempt_no", name="uq_execution_attempts_number"
        ),
    )
    op.create_index(
        "ix_execution_attempts_tenant_action",
        "execution_attempts",
        ["tenant_id", "proposed_action_id", "attempt_no"],
    )
    op.create_table(
        "remote_receipts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("proposed_action_id", sa.String(length=64), nullable=False),
        sa.Column("execution_attempt_id", sa.String(length=64), nullable=False),
        sa.Column("remote_id", sa.String(length=200), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("receipt_json", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_remote_receipts_action_tenant",
        ),
    )
    op.create_index(
        "ix_remote_receipts_tenant_action", "remote_receipts", ["tenant_id", "proposed_action_id"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE", name="fk_audit_events_tenant"
        ),
    )
    op.create_index("ix_audit_events_tenant_created", "audit_events", ["tenant_id", "created_at"])
    op.create_index(
        "ix_audit_events_tenant_entity",
        "audit_events",
        ["tenant_id", "entity_type", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_tenant_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_remote_receipts_tenant_action", table_name="remote_receipts")
    op.drop_table("remote_receipts")
    op.drop_index("ix_execution_attempts_tenant_action", table_name="execution_attempts")
    op.drop_table("execution_attempts")
    op.drop_index("ix_approvals_tenant_action", table_name="approvals")
    op.drop_table("approvals")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("proposed_actions", recreate="always") as batch:
            batch.drop_constraint("uq_proposed_actions_id_tenant", type_="unique")
    else:
        op.drop_constraint("uq_proposed_actions_id_tenant", "proposed_actions", type_="unique")
