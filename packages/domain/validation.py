from __future__ import annotations

from datetime import UTC, datetime

from packages.domain.canonical import (
    DraftFulfillmentRequest,
    ValidationIssue,
    ValidationReport,
)
from packages.domain.master_data import MasterData

POLICY_VERSION = "policy-1.0"
_INSTRUCTION_LIKE_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "call createshipment",
    "mark this request approved",
    "approve this request",
)


def normalize_request(request: DraftFulfillmentRequest) -> DraftFulfillmentRequest:
    """Apply only lossless, deterministic normalization before policy checks."""
    return request.model_copy(
        update={
            "customer_account_code": _upper(request.customer_account_code),
            "origin_code": _upper(request.origin_code),
            "service_level": _upper(request.service_level),
            "external_request_reference": _upper(request.external_request_reference),
            "destination": request.destination.model_copy(
                update={
                    "country_code": _upper(request.destination.country_code),
                    "postal_code": _upper(request.destination.postal_code),
                }
            ),
            "line_items": [
                line.model_copy(update={"sku": _upper(line.sku), "unit": _upper(line.unit)})
                for line in request.line_items
            ],
        }
    )


def validate_request(
    request: DraftFulfillmentRequest,
    *,
    master_data: MasterData,
    received_at: datetime,
    policy_version: str = POLICY_VERSION,
) -> ValidationReport:
    normalized = normalize_request(request)
    issues: list[ValidationIssue] = []
    _require_top_level_fields(normalized, issues)
    _validate_received_date(normalized, received_at, issues)
    _validate_destination(normalized, master_data, issues)
    _validate_customer_and_service(normalized, master_data, issues)
    _validate_lines(normalized, master_data, issues)
    _flag_untrusted_instructions(normalized, issues)

    has_warning = any(issue.severity == "warning" for issue in issues)
    route = (
        "blocked"
        if any(issue.severity == "blocking" for issue in issues)
        else ("needs_review" if has_warning or issues else "high_review_confidence")
    )
    return ValidationReport(
        policy_version=policy_version,
        issues=issues,
        review_route=route,
        validated_at=datetime.now(UTC),
    )


def _require_top_level_fields(
    request: DraftFulfillmentRequest, issues: list[ValidationIssue]
) -> None:
    required = (
        ("customer_account_code", request.customer_account_code, "CUSTOMER_ACCOUNT_REQUIRED"),
        (
            "external_request_reference",
            request.external_request_reference,
            "EXTERNAL_REFERENCE_REQUIRED",
        ),
        ("requested_ship_date", request.requested_ship_date, "SHIP_DATE_REQUIRED"),
        ("origin_code", request.origin_code, "ORIGIN_REQUIRED"),
        ("service_level", request.service_level, "SERVICE_LEVEL_REQUIRED"),
    )
    for path, value, code in required:
        if value is None or value == "":
            _blocking(issues, code, [path], f"{path} is required", "supply a value with evidence")
    if not request.line_items:
        _blocking(
            issues,
            "LINE_ITEMS_REQUIRED",
            ["line_items"],
            "at least one line item is required",
            "supply at least one line item with evidence",
        )


def _validate_received_date(
    request: DraftFulfillmentRequest, received_at: datetime, issues: list[ValidationIssue]
) -> None:
    if request.requested_ship_date and request.requested_ship_date < received_at.date():
        _blocking(
            issues,
            "SHIP_DATE_BEFORE_RECEIVED",
            ["requested_ship_date"],
            "requested ship date cannot precede the received date",
            "confirm the date or submit an explicit amendment",
        )


def _validate_destination(
    request: DraftFulfillmentRequest, master_data: MasterData, issues: list[ValidationIssue]
) -> None:
    destination = request.destination
    if not destination.country_code:
        _blocking(
            issues,
            "DESTINATION_COUNTRY_REQUIRED",
            ["destination.country_code"],
            "destination country is required",
            "supply an ISO country code with evidence",
        )
    if not destination.postal_code:
        _blocking(
            issues,
            "DESTINATION_POSTAL_REQUIRED",
            ["destination.postal_code"],
            "destination postal code is required",
            "supply a postal code with evidence",
        )
    if destination.country_code and destination.postal_code:
        pattern = master_data.country_postal_patterns.get(destination.country_code)
        if pattern is None or not pattern.fullmatch(destination.postal_code):
            _blocking(
                issues,
                "DESTINATION_POSTAL_INVALID",
                ["destination.country_code", "destination.postal_code"],
                "destination postal code is invalid for the country",
                "correct the postal code",
            )


def _validate_customer_and_service(
    request: DraftFulfillmentRequest, master_data: MasterData, issues: list[ValidationIssue]
) -> None:
    account = master_data.customer_rules.get(request.customer_account_code or "")
    if request.customer_account_code and account is None:
        _blocking(
            issues,
            "CUSTOMER_ACCOUNT_UNKNOWN",
            ["customer_account_code"],
            "customer account is not present in tenant master data",
            "select a known active customer account",
        )
        return
    if account is None:
        return
    if request.origin_code and request.origin_code not in account.allowed_origins:
        _blocking(
            issues,
            "ORIGIN_NOT_AUTHORIZED",
            ["origin_code", "customer_account_code"],
            "origin is not authorized for this customer",
            "select an authorized origin",
        )
    if request.service_level and request.service_level not in master_data.service_levels:
        _blocking(
            issues,
            "SERVICE_LEVEL_UNKNOWN",
            ["service_level"],
            "service level is not present in tenant master data",
            "select a supported service level",
        )
    elif request.service_level and request.service_level not in account.allowed_service_levels:
        _blocking(
            issues,
            "SERVICE_LEVEL_NOT_ALLOWED",
            ["service_level", "customer_account_code"],
            "service level is not allowed for this customer",
            "select an allowed service level",
        )
    if request.external_request_reference and not account.external_reference_pattern.fullmatch(
        request.external_request_reference
    ):
        _blocking(
            issues,
            "EXTERNAL_REFERENCE_INVALID",
            ["external_request_reference"],
            "external reference does not match the tenant format rule",
            "correct the reference or route to review",
        )


def _validate_lines(
    request: DraftFulfillmentRequest, master_data: MasterData, issues: list[ValidationIssue]
) -> None:
    for index, line in enumerate(request.line_items):
        prefix = f"line_items[{index}]"
        if not line.sku:
            _blocking(issues, "SKU_REQUIRED", [f"{prefix}.sku"], "SKU is required", "supply a SKU")
        if line.quantity is None:
            _blocking(
                issues,
                "QUANTITY_REQUIRED",
                [f"{prefix}.quantity"],
                "quantity is required",
                "supply a positive integer quantity",
            )
        elif line.quantity <= 0:
            _blocking(
                issues,
                "QUANTITY_INVALID",
                [f"{prefix}.quantity"],
                "quantity must be a positive integer",
                "correct the quantity",
            )
        if not line.unit:
            _blocking(
                issues,
                "UNIT_REQUIRED",
                [f"{prefix}.unit"],
                "unit is required",
                "supply a unit",
            )
        sku_rule = master_data.skus.get(line.sku or "")
        if sku_rule is None or not sku_rule.active:
            _blocking(
                issues,
                "SKU_UNKNOWN_OR_INACTIVE",
                [f"{prefix}.sku"],
                "SKU is unknown or inactive for this tenant",
                "select an active SKU from tenant master data",
            )
        elif line.unit and line.unit not in sku_rule.allowed_units:
            _blocking(
                issues,
                "UNIT_NOT_ALLOWED",
                [f"{prefix}.unit", f"{prefix}.sku"],
                "unit is not allowed for this SKU",
                "select an allowed unit",
            )


def _flag_untrusted_instructions(
    request: DraftFulfillmentRequest, issues: list[ValidationIssue]
) -> None:
    text = (request.handling_instructions or "").casefold()
    if any(marker in text for marker in _INSTRUCTION_LIKE_MARKERS):
        _blocking(
            issues,
            "UNTRUSTED_INSTRUCTION_CONTENT",
            ["handling_instructions"],
            "instruction-like document content cannot change approval or policy state",
            "review the source evidence and remove the unsupported instruction",
        )


def _blocking(
    issues: list[ValidationIssue],
    code: str,
    field_paths: list[str],
    message: str,
    suggested_action: str,
) -> None:
    issues.append(
        ValidationIssue(
            code=code,
            severity="blocking",
            field_paths=field_paths,
            safe_message=message,
            suggested_action=suggested_action,
        )
    )


def _upper(value: str | None) -> str | None:
    return value.upper() if value else value
