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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    graph_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_request_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "graph_thread_id", name="uq_intake_runs_tenant_thread"),
        CheckConstraint(
            "source_channel in ('upload', 'email', 'webhook', 'demo')",
            name="ck_intake_runs_source_channel",
        ),
        CheckConstraint(
            "status in ("
            "'received', 'processing', 'review_required', "
            "'review_received', 'failed', 'completed')",
            name="ck_intake_runs_status",
        ),
        Index("ix_intake_runs_tenant_status", "tenant_id", "status", "started_at"),
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
