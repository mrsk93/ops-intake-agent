from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    raw_artifact_days: int = 30
    derived_text_days: int = 30
    raw_provider_output_days: int = 7
    canonical_metadata_days: int = 90

    def __post_init__(self) -> None:
        if any(
            value < 1
            for value in (
                self.raw_artifact_days,
                self.derived_text_days,
                self.raw_provider_output_days,
                self.canonical_metadata_days,
            )
        ):
            raise ValueError("retention periods must be positive")
