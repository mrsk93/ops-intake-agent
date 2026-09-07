from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("status in ('active', 'suspended')", name="ck_tenants_status"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (CheckConstraint("status in ('active', 'suspended')", name="ck_users_status"),)


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
        CheckConstraint("role in ('viewer', 'reviewer', 'admin')", name="ck_memberships_role"),
        CheckConstraint("status in ('active', 'suspended')", name="ck_memberships_status"),
    )


class SopDocument(Base):
    __tablename__ = "sop_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_name: Mapped[str] = mapped_column(String(240), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    effective_from: Mapped[datetime] = mapped_column(nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_sop_documents_id_tenant"),
        UniqueConstraint("tenant_id", "title", "version", name="uq_sop_documents_tenant_version"),
        CheckConstraint(
            "status in ('draft', 'approved', 'retired')", name="ck_sop_documents_status"
        ),
        Index("ix_sop_documents_tenant_effective", "tenant_id", "status", "effective_from"),
    )


class IntakeRun(Base):
    __tablename__ = "intake_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    demo_fixture: Mapped[str] = mapped_column(String(20), nullable=False, default="valid")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    graph_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_request_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_intake_runs_id_tenant"),
        UniqueConstraint("tenant_id", "graph_thread_id", name="uq_intake_runs_tenant_thread"),
        CheckConstraint(
            "source_channel in ('upload', 'email', 'webhook', 'demo')",
            name="ck_intake_runs_source_channel",
        ),
        CheckConstraint(
            "demo_fixture in ('valid', 'missing', 'conflict')",
            name="ck_intake_runs_demo_fixture",
        ),
        CheckConstraint(
            "status in ("
            "'received', 'processing', 'review_required', "
            "'review_received', 'failed', 'completed')",
            name="ck_intake_runs_status",
        ),
        Index("ix_intake_runs_tenant_status", "tenant_id", "status", "started_at"),
    )


class DraftVersion(Base):
    __tablename__ = "draft_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intake_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prior_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_draft_versions_intake_tenant",
        ),
        UniqueConstraint(
            "tenant_id", "intake_run_id", "version", name="uq_draft_versions_intake_version"
        ),
        CheckConstraint(
            "source in ('extraction', 'operator_edit', 'revalidation')",
            name="ck_draft_versions_source",
        ),
        Index("ix_draft_versions_tenant_intake", "tenant_id", "intake_run_id", "version"),
    )


class ValidationSnapshot(Base):
    __tablename__ = "validation_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intake_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["draft_version_id", "tenant_id"],
            ["draft_versions.id", "draft_versions.tenant_id"],
            ondelete="CASCADE",
            name="fk_validation_snapshots_draft_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_validation_snapshots_id_tenant"),
        Index(
            "ix_validation_snapshots_tenant_intake",
            "tenant_id",
            "intake_run_id",
            "created_at",
        ),
    )


class ValidationIssueRecord(Base):
    __tablename__ = "validation_issues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    field_paths_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    safe_message: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    rule_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["validation_snapshot_id", "tenant_id"],
            ["validation_snapshots.id", "validation_snapshots.tenant_id"],
            ondelete="CASCADE",
            name="fk_validation_issues_snapshot_tenant",
        ),
        CheckConstraint(
            "severity in ('blocking', 'warning', 'info')",
            name="ck_validation_issues_severity",
        ),
        Index("ix_validation_issues_tenant_snapshot", "tenant_id", "validation_snapshot_id"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intake_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    acknowledged_warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    current_draft_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    current_validation_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_reviews_intake_tenant",
        ),
        UniqueConstraint("tenant_id", "intake_run_id", name="uq_reviews_tenant_intake"),
        CheckConstraint(
            "status in ('open', 'submitted', 'approved', 'stale')",
            name="ck_reviews_status",
        ),
        Index("ix_reviews_tenant_updated", "tenant_id", "updated_at"),
    )


class ReviewEdit(Base):
    __tablename__ = "review_edits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    field_path: Mapped[str] = mapped_column(String(160), nullable=False)
    before_json: Mapped[str] = mapped_column(Text, nullable=False)
    after_json: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "tenant_id"],
            ["reviews.id", "reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_review_edits_review_tenant",
        ),
        Index("ix_review_edits_tenant_review", "tenant_id", "review_id", "created_at"),
    )


class ProposedAction(Base):
    __tablename__ = "proposed_actions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    intake_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ready")
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["intake_run_id", "tenant_id"],
            ["intake_runs.id", "intake_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_proposed_actions_intake_tenant",
        ),
        ForeignKeyConstraint(
            ["review_id", "tenant_id"],
            ["reviews.id", "reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_proposed_actions_review_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_proposed_actions_id_tenant"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_proposed_actions_idempotency"),
        CheckConstraint(
            "status in ("
            "'ready', 'claimed', 'executing', 'uncertain', 'verified', 'failed', "
            "'cancelled', 'manual_exception')",
            name="ck_proposed_actions_status",
        ),
        Index("ix_proposed_actions_tenant_intake", "tenant_id", "intake_run_id", "created_at"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_approvals_action_tenant",
        ),
        CheckConstraint(
            "status in ('active', 'stale', 'consumed', 'revoked')",
            name="ck_approvals_status",
        ),
        Index("ix_approvals_tenant_action", "tenant_id", "proposed_action_id"),
    )


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_execution_attempts_action_tenant",
        ),
        CheckConstraint(
            "status in ('executing', 'uncertain', 'verified', 'failed', 'manual_exception')",
            name="ck_execution_attempts_status",
        ),
        UniqueConstraint(
            "tenant_id", "proposed_action_id", "attempt_no", name="uq_execution_attempts_number"
        ),
        Index(
            "ix_execution_attempts_tenant_action",
            "tenant_id",
            "proposed_action_id",
            "attempt_no",
        ),
    )


class RemoteReceipt(Base):
    __tablename__ = "remote_receipts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_json: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["proposed_action_id", "tenant_id"],
            ["proposed_actions.id", "proposed_actions.tenant_id"],
            ondelete="CASCADE",
            name="fk_remote_receipts_action_tenant",
        ),
        Index("ix_remote_receipts_tenant_action", "tenant_id", "proposed_action_id"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE", name="fk_audit_events_tenant"
        ),
        Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_events_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )


class SopChunk(Base):
    __tablename__ = "sop_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sop_document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(80), nullable=False)
    customer_account_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["sop_document_id", "tenant_id"],
            ["sop_documents.id", "sop_documents.tenant_id"],
            ondelete="CASCADE",
            name="fk_sop_chunks_document_tenant",
        ),
        UniqueConstraint("tenant_id", "sop_document_id", "ordinal", name="uq_sop_chunks_ordinal"),
        Index(
            "ix_sop_chunks_tenant_metadata",
            "tenant_id",
            "customer_account_code",
            "location_code",
            "service_level",
            "rule_type",
        ),
    )


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filter_json: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(120), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_retrieval_runs_tenant_created", "tenant_id", "created_at"),
        Index("ix_retrieval_runs_tenant_query", "tenant_id", "query_sha256"),
    )


class RetrievalHit(Base):
    __tablename__ = "retrieval_hits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sop_chunk_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    lexical_score: Mapped[float] = mapped_column(nullable=False)
    semantic_score: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["retrieval_run_id", "tenant_id"],
            ["retrieval_runs.id", "retrieval_runs.tenant_id"],
            ondelete="CASCADE",
            name="fk_retrieval_hits_run_tenant",
        ),
        ForeignKeyConstraint(
            ["sop_chunk_id", "tenant_id"],
            ["sop_chunks.id", "sop_chunks.tenant_id"],
            ondelete="CASCADE",
            name="fk_retrieval_hits_chunk_tenant",
        ),
        UniqueConstraint("tenant_id", "retrieval_run_id", "sop_chunk_id", name="uq_retrieval_hit"),
        Index("ix_retrieval_hits_tenant_run", "tenant_id", "retrieval_run_id", "rank"),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    intake_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_role: Mapped[str] = mapped_column(String(32), nullable=False, default="source")
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_media_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detected_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="quarantined")
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_request_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    amendment_of_artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "content_sha256",
            "artifact_role",
            name="uq_artifacts_tenant_hash_role",
        ),
        CheckConstraint(
            "artifact_role in ('source', 'derived_text', 'parsed')",
            name="ck_artifacts_role",
        ),
        CheckConstraint(
            "status in ('quarantined', 'accepted', 'rejected', 'expired')",
            name="ck_artifacts_status",
        ),
        Index("ix_artifacts_tenant_created", "tenant_id", "created_at"),
        Index("ix_artifacts_tenant_intake", "tenant_id", "intake_id"),
        Index("ix_artifacts_tenant_reference", "tenant_id", "external_request_reference"),
    )
