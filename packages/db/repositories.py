import json
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    Artifact,
    DraftVersion,
    IntakeRun,
    Membership,
    ProposedAction,
    RetrievalHit,
    RetrievalRun,
    Review,
    ReviewEdit,
    SopChunk,
    SopDocument,
    Tenant,
    User,
    ValidationIssueRecord,
    ValidationSnapshot,
)


class IdentityRepository:
    """Every tenant-facing read requires tenant_id in the SQL predicate."""

    async def get_user_by_email(self, session: AsyncSession, *, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, user_id: str
    ) -> tuple[User, Membership, Tenant] | None:
        result = await session.execute(
            select(User, Membership, Tenant)
            .join(Membership, Membership.user_id == User.id)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Tenant.id == tenant_id,
            )
        )
        return result.one_or_none()

    async def list_memberships(
        self, session: AsyncSession, *, tenant_id: str, user_id: str
    ) -> list[Membership]:
        result = await session.execute(
            select(Membership).where(
                Membership.tenant_id == tenant_id, Membership.user_id == user_id
            )
        )
        return list(result.scalars())


class ArtifactRepository:
    """Artifact reads always carry the caller's tenant predicate."""

    async def get(
        self, session: AsyncSession, *, tenant_id: str, artifact_id: str
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact).where(Artifact.tenant_id == tenant_id, Artifact.id == artifact_id)
        )
        return result.scalar_one_or_none()

    async def find_by_hash(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        content_sha256: str,
        artifact_role: str,
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact).where(
                Artifact.tenant_id == tenant_id,
                Artifact.content_sha256 == content_sha256,
                Artifact.artifact_role == artifact_role,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_external_reference(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        external_request_reference: str,
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact)
            .where(
                Artifact.tenant_id == tenant_id,
                Artifact.external_request_reference == external_request_reference,
                Artifact.status == "accepted",
            )
            .order_by(Artifact.created_at.desc())
        )
        return result.scalars().first()

    async def count_for_intake(
        self, session: AsyncSession, *, tenant_id: str, intake_id: str
    ) -> int:
        result = await session.execute(
            select(func.count(Artifact.id)).where(
                Artifact.tenant_id == tenant_id,
                Artifact.intake_id == intake_id,
                Artifact.status != "rejected",
            )
        )
        return int(result.scalar_one())

    async def total_size_for_intake(
        self, session: AsyncSession, *, tenant_id: str, intake_id: str
    ) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(Artifact.size_bytes), 0)).where(
                Artifact.tenant_id == tenant_id,
                Artifact.intake_id == intake_id,
                Artifact.status != "rejected",
            )
        )
        return int(result.scalar_one())

    async def list_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, limit: int = 100
    ) -> list[Artifact]:
        result = await session.execute(
            select(Artifact)
            .where(Artifact.tenant_id == tenant_id)
            .order_by(Artifact.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_expired_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, now: datetime | None = None
    ) -> list[Artifact]:
        cutoff = now or datetime.now(UTC)
        result = await session.execute(
            select(Artifact).where(
                Artifact.tenant_id == tenant_id,
                Artifact.status == "accepted",
                Artifact.expires_at.is_not(None),
                Artifact.expires_at <= cutoff,
            )
        )
        return list(result.scalars())


class SopRepository:
    """SOP reads put tenant, status and effective-date predicates in SQL."""

    async def list_effective_chunks(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        as_of: datetime,
        customer_account_code: str | None,
        location_code: str | None,
        service_level: str | None,
        rule_types: list[str],
    ) -> list[tuple[SopChunk, SopDocument]]:
        predicates = [
            SopChunk.tenant_id == tenant_id,
            SopDocument.tenant_id == tenant_id,
            SopDocument.status == "approved",
            SopDocument.effective_from <= as_of,
            or_(SopDocument.effective_to.is_(None), SopDocument.effective_to >= as_of),
            _metadata_scope(SopChunk.customer_account_code, customer_account_code),
            _metadata_scope(SopChunk.location_code, location_code),
            _metadata_scope(SopChunk.service_level, service_level),
        ]
        if rule_types:
            predicates.append(SopChunk.rule_type.in_(rule_types))
        result = await session.execute(
            select(SopChunk, SopDocument)
            .join(
                SopDocument,
                and_(
                    SopDocument.id == SopChunk.sop_document_id,
                    SopDocument.tenant_id == SopChunk.tenant_id,
                ),
            )
            .where(*predicates)
            .order_by(SopDocument.version.asc(), SopChunk.ordinal.asc(), SopChunk.id.asc())
        )
        return list(result.all())

    async def save_retrieval_run(
        self,
        session: AsyncSession,
        *,
        run: RetrievalRun,
        hits: list[RetrievalHit],
    ) -> None:
        session.add(run)
        session.add_all(hits)
        await session.commit()

    async def get_retrieval_run(
        self, session: AsyncSession, *, tenant_id: str, retrieval_run_id: str
    ) -> RetrievalRun | None:
        result = await session.execute(
            select(RetrievalRun).where(
                RetrievalRun.tenant_id == tenant_id,
                RetrievalRun.id == retrieval_run_id,
            )
        )
        return result.scalar_one_or_none()


class IntakeRunRepository:
    """Workflow run records are always loaded with the caller's tenant predicate."""

    async def get(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> IntakeRun | None:
        result = await session.execute(
            select(IntakeRun).where(
                IntakeRun.tenant_id == tenant_id,
                IntakeRun.id == intake_run_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, limit: int = 100
    ) -> list[IntakeRun]:
        result = await session.execute(
            select(IntakeRun)
            .where(IntakeRun.tenant_id == tenant_id)
            .order_by(IntakeRun.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def create(self, session: AsyncSession, *, intake_run: IntakeRun) -> IntakeRun:
        session.add(intake_run)
        await session.commit()
        await session.refresh(intake_run)
        return intake_run

    async def update_status(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        status: str,
    ) -> IntakeRun | None:
        intake_run = await self.get(session, tenant_id=tenant_id, intake_run_id=intake_run_id)
        if intake_run is None:
            return None
        intake_run.status = status
        await session.commit()
        await session.refresh(intake_run)
        return intake_run


class ReviewRepository:
    """Review records and immutable versions are always tenant-filtered."""

    async def get(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> Review | None:
        result = await session.execute(
            select(Review).where(
                Review.tenant_id == tenant_id,
                Review.intake_run_id == intake_run_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_draft(
        self, session: AsyncSession, *, tenant_id: str, draft_version_id: str
    ) -> DraftVersion | None:
        result = await session.execute(
            select(DraftVersion).where(
                DraftVersion.tenant_id == tenant_id,
                DraftVersion.id == draft_version_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_snapshot(
        self, session: AsyncSession, *, tenant_id: str, snapshot_id: str
    ) -> ValidationSnapshot | None:
        result = await session.execute(
            select(ValidationSnapshot).where(
                ValidationSnapshot.tenant_id == tenant_id,
                ValidationSnapshot.id == snapshot_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_action_for_draft(
        self, session: AsyncSession, *, tenant_id: str, draft_version_id: str
    ) -> ProposedAction | None:
        result = await session.execute(
            select(ProposedAction)
            .where(
                ProposedAction.tenant_id == tenant_id,
                ProposedAction.draft_version_id == draft_version_id,
                ProposedAction.status.not_in(("cancelled", "failed", "manual_exception")),
            )
            .order_by(ProposedAction.created_at.desc())
        )
        return result.scalars().first()

    async def get_action(
        self, session: AsyncSession, *, tenant_id: str, action_id: str
    ) -> ProposedAction | None:
        result = await session.execute(
            select(ProposedAction).where(
                ProposedAction.tenant_id == tenant_id,
                ProposedAction.id == action_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_action_by_idempotency(
        self, session: AsyncSession, *, tenant_id: str, idempotency_key: str
    ) -> ProposedAction | None:
        result = await session.execute(
            select(ProposedAction).where(
                ProposedAction.tenant_id == tenant_id,
                ProposedAction.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_issues(
        self, session: AsyncSession, *, tenant_id: str, snapshot_id: str
    ) -> list[ValidationIssueRecord]:
        result = await session.execute(
            select(ValidationIssueRecord)
            .where(
                ValidationIssueRecord.tenant_id == tenant_id,
                ValidationIssueRecord.validation_snapshot_id == snapshot_id,
            )
            .order_by(ValidationIssueRecord.id.asc())
        )
        return list(result.scalars())

    async def list_edits(
        self, session: AsyncSession, *, tenant_id: str, review_id: str
    ) -> list[ReviewEdit]:
        result = await session.execute(
            select(ReviewEdit)
            .where(ReviewEdit.tenant_id == tenant_id, ReviewEdit.review_id == review_id)
            .order_by(ReviewEdit.created_at.asc(), ReviewEdit.id.asc())
        )
        return list(result.scalars())

    async def next_draft_version(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> int:
        result = await session.execute(
            select(func.coalesce(func.max(DraftVersion.version), 0)).where(
                DraftVersion.tenant_id == tenant_id,
                DraftVersion.intake_run_id == intake_run_id,
            )
        )
        return int(result.scalar_one()) + 1

    async def save_review_bundle(
        self,
        session: AsyncSession,
        *,
        review: Review,
        draft: DraftVersion,
        snapshot: ValidationSnapshot,
        issues: list[ValidationIssueRecord],
        edits: list[ReviewEdit] | None = None,
    ) -> None:
        session.add(draft)
        session.add(snapshot)
        session.add_all(issues)
        if edits:
            session.add_all(edits)
        session.add(review)
        await session.commit()

    async def json_payload(self, draft: DraftVersion) -> dict:
        return json.loads(draft.payload_json)


def _metadata_scope(column, value: str | None):
    if value is None:
        return column.is_(None)
    return or_(column.is_(None), column == value)
