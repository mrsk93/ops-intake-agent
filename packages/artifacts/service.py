from __future__ import annotations

import hashlib
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Artifact
from packages.db.repositories import ArtifactRepository
from packages.domain.artifacts import (
    ArtifactInspection,
    ArtifactLimits,
    ArtifactRole,
    ArtifactSafetyError,
    ArtifactStatus,
    inspect_content,
    sanitize_filename,
)
from packages.providers.ports import StoragePort


class ArtifactIngestionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ArtifactIngestionService:
    def __init__(
        self,
        storage: StoragePort,
        *,
        repository: ArtifactRepository | None = None,
        limits: ArtifactLimits | None = None,
        retention_days: int = 30,
    ) -> None:
        self.storage = storage
        self.repository = repository or ArtifactRepository()
        self.limits = limits or ArtifactLimits()
        self.retention_days = retention_days

    async def ingest_bytes(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        filename: str,
        content: bytes,
        declared_media_type: str | None = None,
        intake_id: str | None = None,
        external_request_reference: str | None = None,
        artifact_role: ArtifactRole = ArtifactRole.SOURCE,
    ) -> ArtifactIngestResult:
        async def chunks() -> AsyncIterable[bytes]:
            yield content

        return await self.ingest(
            session,
            tenant_id=tenant_id,
            filename=filename,
            chunks=chunks(),
            declared_media_type=declared_media_type,
            intake_id=intake_id,
            external_request_reference=external_request_reference,
            artifact_role=artifact_role,
        )

    async def ingest(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        filename: str,
        chunks: AsyncIterable[bytes],
        declared_media_type: str | None = None,
        intake_id: str | None = None,
        external_request_reference: str | None = None,
        artifact_role: ArtifactRole = ArtifactRole.SOURCE,
    ) -> ArtifactIngestResult:
        artifact_id = f"artifact-{uuid4().hex}"
        quarantine_key = f"quarantine/{artifact_id}"
        accepted_key = f"accepted/{artifact_id}"
        content, digest = await self._stream_to_quarantine(
            session,
            tenant_id=tenant_id,
            intake_id=intake_id,
            chunks=chunks,
            key=quarantine_key,
            content_type=declared_media_type or "application/octet-stream",
        )
        safe_filename = sanitize_filename(filename)

        try:
            inspection = inspect_content(
                filename=safe_filename,
                declared_media_type=declared_media_type,
                content=content,
            )
        except ArtifactSafetyError as exc:
            await self.storage.delete(tenant_id=tenant_id, key=quarantine_key)
            rejected = Artifact(
                id=artifact_id,
                tenant_id=tenant_id,
                intake_id=intake_id,
                artifact_role=artifact_role.value,
                original_filename=filename[:255],
                display_filename=safe_filename,
                declared_media_type=declared_media_type,
                detected_type="unknown",
                status=ArtifactStatus.REJECTED.value,
                content_sha256=digest,
                size_bytes=len(content),
                rejection_code=exc.code,
                rejection_reason=exc.message,
            )
            session.add(rejected)
            await session.commit()
            raise ArtifactIngestionError(exc.code, exc.message) from exc

        duplicate = await self.repository.find_by_hash(
            session,
            tenant_id=tenant_id,
            content_sha256=digest,
            artifact_role=artifact_role.value,
        )
        if duplicate is not None:
            await self.storage.delete(tenant_id=tenant_id, key=quarantine_key)
            return ArtifactIngestResult(
                artifact=duplicate,
                duplicate=True,
                duplicate_of_artifact_id=duplicate.id,
            )

        prior_reference = None
        if external_request_reference:
            prior_reference = await self.repository.find_by_external_reference(
                session,
                tenant_id=tenant_id,
                external_request_reference=external_request_reference,
            )

        now = datetime.now(UTC)
        artifact = Artifact(
            id=artifact_id,
            tenant_id=tenant_id,
            intake_id=intake_id,
            artifact_role=artifact_role.value,
            original_filename=filename[:255],
            display_filename=inspection.safe_filename,
            declared_media_type=declared_media_type,
            detected_type=inspection.artifact_type.value,
            status=ArtifactStatus.QUARANTINED.value,
            content_sha256=digest,
            size_bytes=len(content),
            storage_key=quarantine_key,
            external_request_reference=external_request_reference,
            amendment_of_artifact_id=prior_reference.id if prior_reference else None,
            review_required=prior_reference is not None,
            created_at=now,
            expires_at=now + timedelta(days=self.retention_days),
        )
        session.add(artifact)
        await session.commit()

        await self.storage.put(
            tenant_id=tenant_id,
            key=accepted_key,
            content=content,
            content_type=inspection.media_type,
        )
        await self.storage.delete(tenant_id=tenant_id, key=quarantine_key)
        artifact.status = ArtifactStatus.ACCEPTED.value
        artifact.storage_key = accepted_key
        artifact.accepted_at = datetime.now(UTC)
        await session.commit()
        return ArtifactIngestResult(artifact=artifact, inspection=inspection)

    async def _stream_to_quarantine(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_id: str | None,
        chunks: AsyncIterable[bytes],
        key: str,
        content_type: str,
    ) -> tuple[bytes, str]:
        if intake_id:
            count = await self.repository.count_for_intake(
                session, tenant_id=tenant_id, intake_id=intake_id
            )
            if count >= self.limits.max_artifacts_per_intake:
                raise ArtifactIngestionError(
                    "ARTIFACT_COUNT_LIMIT", "intake artifact limit exceeded"
                )
            existing_size = await self.repository.total_size_for_intake(
                session, tenant_id=tenant_id, intake_id=intake_id
            )
        else:
            existing_size = 0

        parts: list[bytes] = []
        size = 0
        digest = hashlib.sha256()

        async def bounded_chunks() -> AsyncIterable[bytes]:
            nonlocal size
            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ArtifactIngestionError(
                        "INVALID_UPLOAD_CHUNK", "upload chunks must be bytes"
                    )
                size += len(chunk)
                if size > self.limits.max_artifact_bytes:
                    raise ArtifactIngestionError(
                        "ARTIFACT_SIZE_LIMIT", "artifact size limit exceeded"
                    )
                if intake_id and existing_size + size > self.limits.max_total_intake_bytes:
                    raise ArtifactIngestionError("INTAKE_SIZE_LIMIT", "intake size limit exceeded")
                digest.update(chunk)
                parts.append(chunk)
                yield chunk

        try:
            await self.storage.put_stream(
                tenant_id=tenant_id,
                key=key,
                chunks=bounded_chunks(),
                content_type=content_type,
            )
        except Exception:
            await self.storage.delete(tenant_id=tenant_id, key=key)
            raise
        if size == 0:
            await self.storage.delete(tenant_id=tenant_id, key=key)
            raise ArtifactIngestionError("EMPTY_ARTIFACT", "empty artifacts are not accepted")
        return b"".join(parts), digest.hexdigest()

    async def expire_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, now: datetime | None = None
    ) -> int:
        expired = await self.repository.list_expired_for_tenant(
            session, tenant_id=tenant_id, now=now
        )
        for artifact in expired:
            if artifact.storage_key:
                await self.storage.delete(tenant_id=tenant_id, key=artifact.storage_key)
            artifact.storage_key = None
            artifact.status = ArtifactStatus.EXPIRED.value
        await session.commit()
        return len(expired)


class ArtifactIngestResult:
    def __init__(
        self,
        *,
        artifact: Artifact,
        inspection: ArtifactInspection | None = None,
        duplicate: bool = False,
        duplicate_of_artifact_id: str | None = None,
    ) -> None:
        self.artifact = artifact
        self.inspection = inspection
        self.duplicate = duplicate
        self.duplicate_of_artifact_id = duplicate_of_artifact_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.artifact.id,
            "tenant_id": self.artifact.tenant_id,
            "filename": self.artifact.display_filename,
            "detected_type": self.artifact.detected_type,
            "status": self.artifact.status,
            "content_sha256": self.artifact.content_sha256,
            "size_bytes": self.artifact.size_bytes,
            "review_required": self.artifact.review_required,
            "duplicate": self.duplicate,
            "duplicate_of_artifact_id": self.duplicate_of_artifact_id,
        }
