from __future__ import annotations

import re


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def map_headers(headers: list[str], aliases: dict[str, set[str]]) -> dict[str, int]:
    """Map canonical field names only on exact normalized aliases; never guess."""
    normalized = {normalize_header(header): index for index, header in enumerate(headers)}
    mapping: dict[str, int] = {}
    for canonical, accepted in aliases.items():
        matches = [normalized[header] for header in accepted if header in normalized]
        if len(matches) == 1:
            mapping[canonical] = matches[0]
    return mapping
