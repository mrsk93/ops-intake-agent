"""Add immutable drafts, validation snapshots and optimistic reviews.

Revision ID: 0005_review_versioning
Revises: 0004_workflow_runs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0005_review_versioning"
down_revision = "0004_workflow_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("intake_runs", recreate="always") as batch:
            batch.add_column(
                sa.Column(
                    "demo_fixture", sa.String(length=20), nullable=False, server_default="valid"
                )
            )
            batch.create_unique_constraint("uq_intake_runs_id_tenant", ["id", "tenant_id"])
            batch.create_check_constraint(
                "ck_intake_runs_demo_fixture",
                "demo_fixture in ('valid', 'missing', 'conflict')",
            )
    else:
        op.create_unique_constraint("uq_intake_runs_id_tenant", "intake_runs", ["id", "tenant_id"])
        op.add_column(
            "intake_runs",
            sa.Column("demo_fixture", sa.String(length=20), nullable=False, server_default="valid"),
        )
        op.create_check_constraint(
            "ck_intake_runs_demo_fixture",
            "intake_runs",
            "demo_fixture in ('valid', 'missing', 'conflict')",
        )
    op.create_table(
        "draft_versions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("intake_run_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("prior_version_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_draft_versions_intake_tenant",
        ),
        sa.UniqueConstraint(
            "tenant_id", "intake_run_id", "version", name="uq_draft_versions_intake_version"
        ),
        sa.CheckConstraint(
            "source in ('extraction', 'operator_edit', 'revalidation')",
            name="ck_draft_versions_source",
        ),
    )
    op.create_index(
        "ix_draft_versions_tenant_intake",
        "draft_versions",
        ["tenant_id", "intake_run_id", "version"],
    )
    op.create_table(
        "validation_snapshots",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("intake_run_id", sa.String(length=64), nullable=False),
        sa.Column("draft_version_id", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("rules_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["draft_version_id", "tenant_id"],
            ["draft_versions.id", "draft_versions.tenant_id"],
            ondelete="CASCADE",
            name="fk_validation_snapshots_draft_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_validation_snapshots_id_tenant"),
    )
    op.create_index(
        "ix_validation_snapshots_tenant_intake",
        "validation_snapshots",
        ["tenant_id", "intake_run_id", "created_at"],
    )
    op.create_table(
        "validation_issues",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("validation_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("field_paths_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("safe_message", sa.String(length=500), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("rule_refs_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["validation_snapshot_id", "tenant_id"],
            ["validation_snapshots.id", "validation_snapshots.tenant_id"],
            ondelete="CASCADE",
            name="fk_validation_issues_snapshot_tenant",
        ),
        sa.CheckConstraint(
            "severity in ('blocking', 'warning', 'info')",
            name="ck_validation_issues_severity",
        ),
    )
    op.create_index(
        "ix_validation_issues_tenant_snapshot",
        "validation_issues",
        ["tenant_id", "validation_snapshot_id"],
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("intake_run_id", sa.String(length=64), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("acknowledged_warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("current_draft_version_id", sa.String(length=64), nullable=False),
        sa.Column("current_validation_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_reviews_intake_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "intake_run_id", name="uq_reviews_tenant_intake"),
        sa.CheckConstraint(
            "status in ('open', 'submitted', 'approved', 'stale')",
            name="ck_reviews_status",
        ),
    )
    op.create_index("ix_reviews_tenant_updated", "reviews", ["tenant_id", "updated_at"])
    op.create_table(
        "review_edits",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("review_id", sa.String(length=64), nullable=False),
        sa.Column("draft_version_id", sa.String(length=64), nullable=False),
        sa.Column("field_path", sa.String(length=160), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=False),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id", "tenant_id"],
            ["reviews.id", "reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_review_edits_review_tenant",
        ),
    )
    op.create_index(
        "ix_review_edits_tenant_review",
        "review_edits",
        ["tenant_id", "review_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_edits_tenant_review", table_name="review_edits")
    op.drop_table("review_edits")
    op.drop_index("ix_reviews_tenant_updated", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_validation_issues_tenant_snapshot", table_name="validation_issues")
    op.drop_table("validation_issues")
    op.drop_index("ix_validation_snapshots_tenant_intake", table_name="validation_snapshots")
    op.drop_table("validation_snapshots")
    op.drop_index("ix_draft_versions_tenant_intake", table_name="draft_versions")
    op.drop_table("draft_versions")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("intake_runs", recreate="always") as batch:
            batch.drop_constraint("ck_intake_runs_demo_fixture", type_="check")
            batch.drop_column("demo_fixture")
            batch.drop_constraint("uq_intake_runs_id_tenant", type_="unique")
    else:
        op.drop_constraint("ck_intake_runs_demo_fixture", "intake_runs", type_="check")
        op.drop_column("intake_runs", "demo_fixture")
        op.drop_constraint("uq_intake_runs_id_tenant", "intake_runs", type_="unique")
