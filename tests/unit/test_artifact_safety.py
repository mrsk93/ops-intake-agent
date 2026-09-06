import asyncio
import io
import zipfile

import pytest

from packages.artifacts.service import ArtifactIngestionError, ArtifactIngestionService
from packages.domain.artifacts import (
    ArtifactLimits,
    ArtifactSafetyError,
    inspect_content,
    sanitize_filename,
)
from packages.testkit.fakes import FakeStorage


def test_filename_is_sanitized_and_signature_is_checked() -> None:
    inspection = inspect_content(
        filename="../../unsafe<>name.csv",
        declared_media_type="text/csv; charset=utf-8",
        content=b"sku,quantity\nABC,2\n",
    )
    assert inspection.safe_filename == "unsafe_name.csv"
    assert inspection.artifact_type.value == "csv"

    with pytest.raises(ArtifactSafetyError, match="signature"):
        inspect_content(
            filename="request.pdf", declared_media_type="application/pdf", content=b"no"
        )


def test_encrypted_and_macro_like_documents_are_rejected() -> None:
    with pytest.raises(ArtifactSafetyError, match="encrypted"):
        inspect_content(filename="request.pdf", content=b"%PDF-1.7\n/Encrypt 12 0 R")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"synthetic macro")
    with pytest.raises(ArtifactSafetyError, match="macro"):
        inspect_content(filename="request.xlsx", content=buffer.getvalue())


@pytest.mark.asyncio
async def test_upload_chunk_limit_is_enforced_before_storage(db_session_factory) -> None:
    service = ArtifactIngestionService(
        FakeStorage(),
        limits=ArtifactLimits(max_artifact_bytes=4),
    )

    async def chunks():
        yield b"ab"
        await asyncio.sleep(0)
        yield b"cde"

    async with db_session_factory() as session:
        with pytest.raises(ArtifactIngestionError, match="size limit"):
            await service.ingest(
                session,
                tenant_id="tenant-a",
                filename="request.csv",
                chunks=chunks(),
            )


def test_empty_filename_has_safe_fallback() -> None:
    assert sanitize_filename("") == "unnamed"
