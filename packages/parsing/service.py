from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import re
import zipfile
from collections.abc import Mapping
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from typing import Any

from packages.domain.artifacts import ArtifactLimits, ArtifactType
from packages.domain.parsing import (
    EvidenceCoordinate,
    ParsedArtifact,
    ParsedCell,
    ParsedPage,
    ParsedTable,
    ParserFailure,
    ParserWarning,
)
from packages.providers.ports import OcrProvider

PARSER_VERSION = "m3.1"


async def parse_artifact(
    *,
    artifact_id: str,
    tenant_id: str,
    artifact_type: ArtifactType | str,
    content: bytes,
    limits: ArtifactLimits | None = None,
    ocr_provider: OcrProvider | None = None,
) -> ParsedArtifact:
    resolved_type = ArtifactType(artifact_type)
    resolved_limits = limits or ArtifactLimits()
    if resolved_type is ArtifactType.CSV:
        return _parse_csv(artifact_id, content, resolved_limits)
    if resolved_type is ArtifactType.XLSX:
        return _parse_xlsx(artifact_id, content, resolved_limits)
    if resolved_type is ArtifactType.EMAIL:
        return _parse_email(artifact_id, content, resolved_limits)
    if resolved_type is ArtifactType.PDF:
        return await _parse_pdf(
            artifact_id, tenant_id, content, resolved_limits, ocr_provider=ocr_provider
        )
    if resolved_type is ArtifactType.IMAGE:
        return await _parse_image(
            artifact_id, tenant_id, content, resolved_limits, ocr_provider=ocr_provider
        )
    raise ParserFailure("UNSUPPORTED_TYPE", "no deterministic parser is registered")


def _parse_csv(artifact_id: str, content: bytes, limits: ArtifactLimits) -> ParsedArtifact:
    text = _decode_text(content, "CSV")
    _enforce_text_limit(text, limits)
    try:
        dialect = csv.Sniffer().sniff(text[:64_000], delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if len(rows) > limits.max_table_rows:
        raise ParserFailure("TABLE_ROW_LIMIT", "CSV row limit exceeded")
    headers = rows[0] if rows else []
    cells = _cells_for_rows(artifact_id, rows, sheet=None)
    table = ParsedTable(
        table_id=f"{artifact_id}:csv:1",
        headers=headers,
        cells=cells,
        evidence=EvidenceCoordinate(
            artifact_id=artifact_id,
            row_start=1 if rows else None,
            row_end=len(rows) if rows else None,
            col_start=1 if headers else None,
            col_end=len(headers) if headers else None,
        ),
    )
    warnings = []
    if not headers:
        warnings.append(ParserWarning(code="EMPTY_TABLE", message="CSV has no rows"))
    return ParsedArtifact(
        artifact_id=artifact_id,
        parser_name="deterministic-csv",
        parser_version=PARSER_VERSION,
        pages=[ParsedPage(page_number=1, text=text, char_start=0, char_end=len(text))],
        tables=[table],
        warnings=warnings,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def _parse_xlsx(artifact_id: str, content: bytes, limits: ArtifactLimits) -> ParsedArtifact:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names:
                raise ParserFailure("MALFORMED_XLSX", "XLSX content types are missing")
            shared_strings = _xlsx_shared_strings(archive, names)
            sheets = _xlsx_sheets(archive, names)
            if len(sheets) > limits.max_workbook_sheets:
                raise ParserFailure("WORKBOOK_SHEET_LIMIT", "workbook sheet limit exceeded")
            tables = []
            text_parts = []
            warnings: list[ParserWarning] = []
            for sheet_name, sheet_path in sheets:
                rows = _xlsx_rows(archive, sheet_path, shared_strings)
                if len(rows) > limits.max_table_rows:
                    raise ParserFailure("TABLE_ROW_LIMIT", "workbook row limit exceeded")
                headers = rows[0] if rows else []
                cells = _cells_for_rows(artifact_id, rows, sheet=sheet_name)
                max_columns = max((len(row) for row in rows), default=0)
                tables.append(
                    ParsedTable(
                        table_id=f"{artifact_id}:xlsx:{sheet_name}",
                        sheet=sheet_name,
                        headers=headers,
                        cells=cells,
                        evidence=EvidenceCoordinate(
                            artifact_id=artifact_id,
                            sheet=sheet_name,
                            row_start=1 if rows else None,
                            row_end=len(rows) if rows else None,
                            col_start=1 if max_columns else None,
                            col_end=max_columns or None,
                        ),
                    )
                )
                text_parts.append(f"[{sheet_name}]\n" + "\n".join(",".join(row) for row in rows))
                if not rows:
                    warnings.append(
                        ParserWarning(code="EMPTY_SHEET", message=f"sheet {sheet_name} has no rows")
                    )
            text = "\n\n".join(text_parts)
    except ParserFailure:
        raise
    except (KeyError, ValueError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        raise ParserFailure("MALFORMED_XLSX", "XLSX could not be parsed") from exc
    _enforce_text_limit(text, limits)
    return ParsedArtifact(
        artifact_id=artifact_id,
        parser_name="deterministic-xlsx",
        parser_version=PARSER_VERSION,
        tables=tables,
        warnings=warnings,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def _parse_email(artifact_id: str, content: bytes, limits: ArtifactLimits) -> ParsedArtifact:
    try:
        message = BytesParser(policy=policy.default).parsebytes(content)
        headers = [
            f"{name}: {message.get(name)}"
            for name in ("From", "To", "Cc", "Date", "Subject")
            if message.get(name)
        ]
        body = ""
        if message.is_multipart():
            body_part = message.get_body(preferencelist=("plain", "html"))
            if body_part is not None:
                body = body_part.get_content()
        else:
            body = message.get_content()
        if message.get_content_type() == "text/html":
            body = _html_to_text(body)
        text = "\n".join(headers) + ("\n\n" if headers and body else "") + body
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ParserFailure("MALFORMED_EMAIL", "email could not be parsed") from exc
    _enforce_text_limit(text, limits)
    warnings = []
    if not body.strip():
        warnings.append(ParserWarning(code="EMPTY_BODY", message="email has no text body"))
    return ParsedArtifact(
        artifact_id=artifact_id,
        parser_name="deterministic-email",
        parser_version=PARSER_VERSION,
        pages=[ParsedPage(page_number=1, text=text, char_start=0, char_end=len(text))],
        warnings=warnings,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


async def _parse_pdf(
    artifact_id: str,
    tenant_id: str,
    content: bytes,
    limits: ArtifactLimits,
    *,
    ocr_provider: OcrProvider | None,
) -> ParsedArtifact:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ParserFailure("ENCRYPTED_DOCUMENT", "encrypted PDFs are not accepted")
        if len(reader.pages) > limits.max_pdf_pages:
            raise ParserFailure("PDF_PAGE_LIMIT", "PDF page limit exceeded")
        pages: list[ParsedPage] = []
        warnings: list[ParserWarning] = []
        offset = 0
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise ParserFailure(
                    "PDF_TEXT_EXTRACTION_FAILED", "PDF text extraction failed"
                ) from exc
            pages.append(
                ParsedPage(
                    page_number=index,
                    text=text,
                    char_start=offset,
                    char_end=offset + len(text),
                    warnings=["LOW_TEXT"] if not text.strip() else [],
                )
            )
            if not text.strip():
                warnings.append(
                    ParserWarning(
                        code="LOW_TEXT",
                        message=f"page {index} has no extractable text",
                        evidence=EvidenceCoordinate(artifact_id=artifact_id, page=index),
                    )
                )
            offset += len(text)
        if not any(page.text.strip() for page in pages):
            if ocr_provider is None:
                raise ParserFailure(
                    "OCR_PROVIDER_UNAVAILABLE", "scanned PDF requires an OCR provider"
                )
            ocr = await ocr_provider.recognize(
                tenant_id=tenant_id, artifact_id=artifact_id, content=content
            )
            ocr_text = _provider_text(ocr)
            _enforce_text_limit(ocr_text, limits)
            pages = [ParsedPage(page_number=1, text=ocr_text, char_start=0, char_end=len(ocr_text))]
            warnings.append(ParserWarning(code="OCR_USED", message="OCR was used for low-text PDF"))
        text = "".join(page.text for page in pages)
    except ParserFailure:
        raise
    except Exception as exc:
        raise ParserFailure("PDF_PARSE_FAILED", "PDF could not be parsed") from exc
    _enforce_text_limit(text, limits)
    return ParsedArtifact(
        artifact_id=artifact_id,
        parser_name="deterministic-pdf",
        parser_version=PARSER_VERSION,
        pages=pages,
        warnings=warnings,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


async def _parse_image(
    artifact_id: str,
    tenant_id: str,
    content: bytes,
    limits: ArtifactLimits,
    *,
    ocr_provider: OcrProvider | None,
) -> ParsedArtifact:
    if ocr_provider is None:
        raise ParserFailure("OCR_PROVIDER_UNAVAILABLE", "image parsing requires an OCR provider")
    try:
        output = await ocr_provider.recognize(
            tenant_id=tenant_id, artifact_id=artifact_id, content=content
        )
        text = _provider_text(output)
    except Exception as exc:
        raise ParserFailure("OCR_FAILED", "OCR provider failed", retryable=True) from exc
    _enforce_text_limit(text, limits)
    warnings = []
    if not text.strip():
        warnings.append(ParserWarning(code="EMPTY_OCR", message="OCR returned no text"))
    return ParsedArtifact(
        artifact_id=artifact_id,
        parser_name="ocr",
        parser_version=str(output.get("provider_version", PARSER_VERSION)),
        pages=[ParsedPage(page_number=1, text=text, char_start=0, char_end=len(text))],
        warnings=warnings,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def _cells_for_rows(artifact_id: str, rows: list[list[str]], sheet: str | None) -> list[ParsedCell]:
    cells = []
    for row_number, row in enumerate(rows, start=1):
        for column_number, value in enumerate(row, start=1):
            cells.append(
                ParsedCell(
                    row_number=row_number,
                    column_number=column_number,
                    value=value,
                    evidence=EvidenceCoordinate(
                        artifact_id=artifact_id,
                        sheet=sheet,
                        row_start=row_number,
                        row_end=row_number,
                        col_start=column_number,
                        col_end=column_number,
                    ),
                )
            )
    return cells


def _decode_text(content: bytes, kind: str) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParserFailure("INVALID_TEXT", f"{kind} content is not valid UTF-8") from exc


def _enforce_text_limit(text: str, limits: ArtifactLimits) -> None:
    if len(text) > limits.max_extracted_text_chars:
        raise ParserFailure("TEXT_SIZE_LIMIT", "extracted text limit exceeded")


def _provider_text(output: Mapping[str, Any]) -> str:
    text = output.get("text")
    if not isinstance(text, str):
        raise ParserFailure("OCR_INVALID_OUTPUT", "OCR provider returned invalid text")
    return text


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


def _xlsx_shared_strings(archive: zipfile.ZipFile, names: set[str]) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []
    import xml.etree.ElementTree as ET

    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return ["".join(node.itertext()) for node in root.findall("main:si", namespace)]


def _xlsx_sheets(archive: zipfile.ZipFile, names: set[str]) -> list[tuple[str, str]]:
    import xml.etree.ElementTree as ET

    namespace = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall("pkg:Relationship", namespace)
    }
    sheets = []
    for sheet in workbook.findall("main:sheets/main:sheet", namespace):
        relationship_id = sheet.attrib.get(f"{{{namespace['rel']}}}id")
        target = rel_targets.get(relationship_id or "")
        if not target:
            raise ParserFailure("MALFORMED_XLSX", "worksheet relationship is missing")
        path = posixpath.normpath(posixpath.join("xl", target))
        if path not in names:
            raise ParserFailure("MALFORMED_XLSX", "worksheet content is missing")
        sheets.append((sheet.attrib.get("name", "Sheet"), path))
    return sheets


def _xlsx_rows(
    archive: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]
) -> list[list[str]]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(archive.read(sheet_path))
    namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row_node in root.findall(".//main:sheetData/main:row", namespace):
        values: dict[int, str] = {}
        for cell in row_node.findall("main:c", namespace):
            reference = cell.attrib.get("r", "A1")
            column = _column_number(reference)
            value_node = cell.find("main:v", namespace)
            inline_node = cell.find("main:is", namespace)
            value = ""
            if inline_node is not None:
                value = "".join(inline_node.itertext())
            elif value_node is not None and value_node.text is not None:
                value = value_node.text
                if cell.attrib.get("t") == "s":
                    try:
                        value = shared_strings[int(value)]
                    except (IndexError, ValueError) as exc:
                        raise ParserFailure(
                            "MALFORMED_XLSX", "shared string index is invalid"
                        ) from exc
                elif cell.attrib.get("t") == "b":
                    value = "TRUE" if value == "1" else "FALSE"
            values[column] = value
        max_column = max(values, default=0)
        rows.append([values.get(column, "") for column in range(1, max_column + 1)])
    return rows


def _column_number(reference: str) -> int:
    letters = re.match(r"([A-Z]+)", reference.upper())
    if not letters:
        raise ParserFailure("MALFORMED_XLSX", "cell reference is invalid")
    value = 0
    for char in letters.group(1):
        value = value * 26 + ord(char) - ord("A") + 1
    return value
