from __future__ import annotations

from dataclasses import dataclass
from re import Pattern, compile


@dataclass(frozen=True, slots=True)
class SkuRule:
    sku: str
    active: bool = True
    allowed_units: frozenset[str] = frozenset({"EA"})


@dataclass(frozen=True, slots=True)
class CustomerRule:
    account_code: str
    allowed_origins: frozenset[str]
    allowed_service_levels: frozenset[str]
    external_reference_pattern: Pattern[str]


@dataclass(frozen=True, slots=True)
class MasterData:
    tenant_id: str
    customer_rules: dict[str, CustomerRule]
    skus: dict[str, SkuRule]
    service_levels: frozenset[str]
    origins: frozenset[str]
    country_postal_patterns: dict[str, Pattern[str]]


def synthetic_master_data(tenant_id: str) -> MasterData:
    """Return isolated, synthetic master data for one demo tenant."""
    normalized_tenant = tenant_id.lower()
    suffix = normalized_tenant.removeprefix("tenant-").upper()
    account = f"ACCT-{suffix}"
    origin = f"ORIGIN-{suffix}"
    return MasterData(
        tenant_id=tenant_id,
        customer_rules={
            account: CustomerRule(
                account_code=account,
                allowed_origins=frozenset({origin}),
                allowed_service_levels=frozenset({"STANDARD", "EXPRESS"}),
                external_reference_pattern=compile(rf"^REQ-{suffix}-[0-9A-Z-]+$"),
            )
        },
        skus={
            "SKU-100": SkuRule("SKU-100", allowed_units=frozenset({"EA", "CASE"})),
            "SKU-200": SkuRule("SKU-200", allowed_units=frozenset({"EA"})),
        },
        service_levels=frozenset({"STANDARD", "EXPRESS"}),
        origins=frozenset({origin}),
        country_postal_patterns={
            "US": compile(r"^[0-9]{5}(?:-[0-9]{4})?$"),
            "CA": compile(r"^[A-Z][0-9][A-Z] ?[0-9][A-Z][0-9]$"),
        },
    )
