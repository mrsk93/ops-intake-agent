from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ContentFinding:
    code: str
    location: str


_INSTRUCTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "call createshipment",
    "mark this request approved",
    "approve this request",
)


def scan_untrusted_text(text: str, *, location: str = "document") -> list[ContentFinding]:
    lowered = text.casefold()
    findings: list[ContentFinding] = []
    if any(marker in lowered for marker in _INSTRUCTION_MARKERS):
        findings.append(ContentFinding("INSTRUCTION_LIKE_CONTENT", location))
    if "white-on-white" in lowered or "white on white" in lowered:
        findings.append(ContentFinding("HIDDEN_TEXT_CONTENT", location))
    if "sop" in lowered and any(marker in lowered for marker in ("approve", "override", "policy")):
        findings.append(ContentFinding("SOP_LIKE_UNTRUSTED_CONTENT", location))
    if re.search(r"(?:https?://|/embeddedfiles|embedded\s+attachment)", lowered):
        findings.append(ContentFinding("EMBEDDED_LINK_OR_ATTACHMENT", location))
    return findings


def scan_untrusted_payload(payload: dict[str, Any], *, tenant_id: str) -> list[ContentFinding]:
    findings = scan_untrusted_text(
        str(payload.get("handling_instructions") or ""), location="handling_instructions"
    )
    instructions = payload.get("handling_instructions")
    if isinstance(instructions, str) and instructions.startswith(("=", "+", "-", "@")):
        findings.append(ContentFinding("SPREADSHEET_FORMULA", "handling_instructions"))
    customer = str(payload.get("customer_account_code") or "")
    expected_suffix = tenant_id.removeprefix("tenant-").upper()
    if customer and customer != f"ACCT-{expected_suffix}":
        findings.append(ContentFinding("CROSS_TENANT_MASTER_DATA", "customer_account_code"))

    for path, value in (
        ("external_request_reference", payload.get("external_request_reference")),
        ("line_items[0].sku", _first_line_value(payload, "sku")),
    ):
        if isinstance(value, str) and value and value != unicodedata.normalize("NFKC", value):
            findings.append(ContentFinding("UNICODE_LOOKALIKE", path))
        elif isinstance(value, str) and any(ord(character) > 127 for character in value):
            findings.append(ContentFinding("UNICODE_LOOKALIKE", path))

    quantity = _first_line_value(payload, "quantity")
    if isinstance(quantity, float) or (isinstance(quantity, int) and quantity <= 0):
        findings.append(ContentFinding("INVALID_QUANTITY_SHAPE", "line_items[0].quantity"))
    ship_date = payload.get("requested_ship_date")
    if isinstance(ship_date, str) and re.search(r"\d{4}/\d{2}/\d{2}", ship_date):
        findings.append(ContentFinding("CONFLICTING_DATE_FORMAT", "requested_ship_date"))
    return findings


def safe_spreadsheet_value(value: Any) -> Any:
    """Return a display/export-safe value without changing typed numeric data."""

    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _first_line_value(payload: dict[str, Any], key: str) -> Any:
    lines = payload.get("line_items")
    if not isinstance(lines, list) or not lines or not isinstance(lines[0], dict):
        return None
    return lines[0].get(key)
