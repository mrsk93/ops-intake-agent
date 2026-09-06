import io
import zipfile

import pytest

from packages.domain.artifacts import ArtifactLimits
from packages.domain.parsing import ParserFailure
from packages.parsing.header_mapping import map_headers
from packages.parsing.service import parse_artifact


@pytest.mark.asyncio
async def test_csv_parser_preserves_cell_evidence() -> None:
    parsed = await parse_artifact(
        artifact_id="artifact-csv",
        tenant_id="tenant-a",
        artifact_type="csv",
        content=b"SKU,Quantity\nABC-1,2\n",
    )
    assert parsed.tables[0].headers == ["SKU", "Quantity"]
    quantity_cell = next(cell for cell in parsed.tables[0].cells if cell.value == "2")
    assert quantity_cell.evidence.row_start == 2
    assert parsed.text_sha256


def test_header_mapping_never_fuzzy_matches() -> None:
    aliases = {"sku": {"sku", "item_code"}, "quantity": {"quantity", "qty"}}
    assert map_headers(["SKU", "Qty"], aliases) == {"sku": 0, "quantity": 1}
    assert map_headers(["SKU-ish", "Qty maybe"], aliases) == {}


@pytest.mark.asyncio
async def test_xlsx_parser_emits_sheet_and_cell_coordinates() -> None:
    content = _xlsx_bytes()
    parsed = await parse_artifact(
        artifact_id="artifact-xlsx",
        tenant_id="tenant-a",
        artifact_type="xlsx",
        content=content,
    )
    table = parsed.tables[0]
    assert table.sheet == "Orders"
    assert table.headers == ["SKU", "Quantity"]
    assert table.cells[-1].evidence.sheet == "Orders"
    assert table.cells[-1].evidence.row_start == 2


@pytest.mark.asyncio
async def test_email_html_is_reduced_to_text() -> None:
    parsed = await parse_artifact(
        artifact_id="artifact-email",
        tenant_id="tenant-a",
        artifact_type="email",
        content=(
            b"Subject: Synthetic\nContent-Type: text/html; charset=utf-8\n\n"
            b"<b>Ship</b> <script>ignored</script> request"
        ),
    )
    assert "<b>" not in parsed.pages[0].text
    assert "Ship" in parsed.pages[0].text


@pytest.mark.asyncio
async def test_image_requires_ocr_provider_and_records_provider_version() -> None:
    class Ocr:
        async def recognize(self, *, tenant_id, artifact_id, content):
            return {"text": "OCR synthetic", "provider_version": "fake-1"}

    parsed = await parse_artifact(
        artifact_id="artifact-image",
        tenant_id="tenant-a",
        artifact_type="image",
        content=b"\x89PNG\r\n\x1a\nsynthetic",
        ocr_provider=Ocr(),
        limits=ArtifactLimits(max_extracted_text_chars=100),
    )
    assert parsed.parser_version == "fake-1"
    assert parsed.pages[0].text == "OCR synthetic"

    with pytest.raises(ParserFailure, match="OCR provider"):
        await parse_artifact(
            artifact_id="artifact-image",
            tenant_id="tenant-a",
            artifact_type="image",
            content=b"\x89PNG\r\n\x1a\nsynthetic",
        )


def _xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types" />',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Orders" sheetId="1" r:id="rId1" /></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml" />'
            "</Relationships>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>SKU</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>Quantity</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>ABC-1</t></is></c>'
            '<c r="B2"><v>2</v></c></row></sheetData></worksheet>',
        )
    return buffer.getvalue()
