from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath


class ArtifactType(StrEnum):
    CSV = "csv"
    EMAIL = "email"
    IMAGE = "image"
    PDF = "pdf"
    XLSX = "xlsx"


class ArtifactRole(StrEnum):
    SOURCE = "source"
    DERIVED_TEXT = "derived_text"
    PARSED = "parsed"


class ArtifactStatus(StrEnum):
    QUARANTINED = "quarantined"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ArtifactSafetyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ArtifactLimits:
    max_artifacts_per_intake: int = 10
    max_artifact_bytes: int = 15 * 1024 * 1024
    max_total_intake_bytes: int = 40 * 1024 * 1024
    max_pdf_pages: int = 100
    max_workbook_sheets: int = 10
    max_table_rows: int = 10_000
    max_extracted_text_chars: int = 1_000_000


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    artifact_type: ArtifactType
    extension: str
    safe_filename: str
    media_type: str


_CONTROL_OR_UNSAFE_FILENAME = re.compile(r"[\x00-\x1f\x7f<>:\"/\\|?*]+")
_EXTENSIONS = {
    ".csv": (ArtifactType.CSV, "text/csv"),
    ".eml": (ArtifactType.EMAIL, "message/rfc822"),
    ".jpeg": (ArtifactType.IMAGE, "image/jpeg"),
    ".jpg": (ArtifactType.IMAGE, "image/jpeg"),
    ".pdf": (ArtifactType.PDF, "application/pdf"),
    ".png": (ArtifactType.IMAGE, "image/png"),
    ".xlsx": (
        ArtifactType.XLSX,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}
_MEDIA_TYPES = {
    "text/csv": ArtifactType.CSV,
    "message/rfc822": ArtifactType.EMAIL,
    "application/pdf": ArtifactType.PDF,
    "image/jpeg": ArtifactType.IMAGE,
    "image/png": ArtifactType.IMAGE,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ArtifactType.XLSX,
}


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sanitize_filename(filename: str) -> str:
    basename = PurePath(filename or "unnamed").name
    sanitized = _CONTROL_OR_UNSAFE_FILENAME.sub("_", basename).strip(" .")
    return (sanitized or "unnamed")[:255]


def inspect_content(
    *, filename: str, content: bytes, declared_media_type: str | None = None
) -> ArtifactInspection:
    safe_filename = sanitize_filename(filename)
    extension = PurePath(safe_filename).suffix.lower()
    if extension in {".xlsm", ".xltm", ".docm", ".dotm", ".pptm", ".potm"}:
        raise ArtifactSafetyError(
            "MACRO_ENABLED_DOCUMENT", "macro-enabled Office files are not accepted"
        )
    if extension not in _EXTENSIONS:
        raise ArtifactSafetyError("UNSUPPORTED_EXTENSION", "file extension is not accepted")

    artifact_type, expected_media_type = _EXTENSIONS[extension]
    detected_type = _detect_type(content, extension)
    if detected_type is not artifact_type:
        raise ArtifactSafetyError("CONTENT_TYPE_MISMATCH", "file bytes do not match its extension")

    normalized_declared = (declared_media_type or "").split(";", 1)[0].strip().lower()
    if normalized_declared and normalized_declared not in {
        expected_media_type,
        "application/octet-stream",
    }:
        declared_type = _MEDIA_TYPES.get(normalized_declared)
        if declared_type is not artifact_type:
            raise ArtifactSafetyError("MIME_TYPE_MISMATCH", "declared media type is inconsistent")

    if artifact_type is ArtifactType.PDF and b"/Encrypt" in content[:2_000_000]:
        raise ArtifactSafetyError("ENCRYPTED_DOCUMENT", "encrypted PDFs are not accepted")
    if artifact_type is ArtifactType.XLSX:
        _validate_xlsx_container(content)
    return ArtifactInspection(artifact_type, extension, safe_filename, expected_media_type)


def _detect_type(content: bytes, extension: str) -> ArtifactType:
    if extension == ".pdf" and content.startswith(b"%PDF-"):
        return ArtifactType.PDF
    if extension == ".csv":
        try:
            text = content[:64_000].decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ArtifactSafetyError("INVALID_TEXT", "CSV content is not valid UTF-8") from exc
        if "\n" in text or "," in text or "\t" in text:
            return ArtifactType.CSV
    if extension == ".eml":
        try:
            content[:64_000].decode("utf-8", errors="replace")
        except Exception as exc:
            raise ArtifactSafetyError(
                "INVALID_EMAIL", "email content could not be decoded"
            ) from exc
        return ArtifactType.EMAIL
    if extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff"):
        return ArtifactType.IMAGE
    if extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ArtifactType.IMAGE
    if extension == ".xlsx" and content.startswith(b"PK\x03\x04"):
        return ArtifactType.XLSX
    raise ArtifactSafetyError("INVALID_FILE_SIGNATURE", "file signature is not accepted")


def _contains_macro(content: bytes) -> bool:
    lowered = content.lower()
    return b"vbaproject.bin" in lowered or b"vba/" in lowered


def _validate_xlsx_container(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise ArtifactSafetyError("INVALID_FILE_SIGNATURE", "XLSX container is not valid") from exc
    if _contains_macro(content):
        raise ArtifactSafetyError(
            "MACRO_ENABLED_DOCUMENT", "macro-enabled Office files are not accepted"
        )
    if "EncryptionInfo" in names or "EncryptedPackage" in names:
        raise ArtifactSafetyError("ENCRYPTED_DOCUMENT", "encrypted Office files are not accepted")
    if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
        raise ArtifactSafetyError("INVALID_FILE_SIGNATURE", "XLSX container is not valid")
